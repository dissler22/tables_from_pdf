"""
Pipeline principal d'extraction de tableaux

Ce module fournit un pipeline complet pour extraire les tableaux
de documents PDF complexes.
"""

from typing import List, Optional, Union, Callable
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
import time

from .utils import (
    ExtractionResult, 
    ExtractedTable, 
    pdf_to_images,
    ensure_output_dir
)
from .detector import TableDetector, DetectorConfig
from .extractor import TableStructureExtractor, HybridExtractor


class ExtractionMode(Enum):
    """Mode d'extraction"""
    FAST = "fast"           # img2table seul (rapide, bon pour tableaux simples)
    ACCURATE = "accurate"   # Table Transformer + img2table (précis, plus lent)
    HYBRID = "hybrid"       # Combinaison intelligente


@dataclass
class PipelineConfig:
    """Configuration du pipeline d'extraction"""
    # Mode d'extraction
    mode: ExtractionMode = ExtractionMode.ACCURATE
    
    # OCR
    ocr_engine: str = "tesseract"  # "tesseract", "paddleocr", "easyocr", None
    ocr_lang: str = "fra+eng"
    
    # Détection
    detection_confidence: float = 0.7
    detect_borderless: bool = True
    
    # Rendu PDF
    dpi: int = 200
    
    # Sortie
    output_format: List[str] = field(default_factory=lambda: ["json", "csv"])
    save_images: bool = True
    
    # Pages
    pages: Optional[List[int]] = None  # None = toutes les pages


class TableExtractionPipeline:
    """
    Pipeline complet d'extraction de tableaux
    
    Gère l'ensemble du processus :
    1. Chargement et rendu du PDF
    2. Détection des tableaux
    3. Extraction de la structure et du contenu
    4. Export des résultats
    """
    
    def __init__(self, config: Optional[PipelineConfig] = None):
        """
        Initialise le pipeline
        
        Args:
            config: Configuration du pipeline (optionnel)
        """
        self.config = config or PipelineConfig()
        self._detector = None
        self._extractor = None
        self._hybrid = None
    
    @property
    def detector(self) -> TableDetector:
        """Détecteur de tableaux (lazy loading)"""
        if self._detector is None:
            self._detector = TableDetector(
                config=DetectorConfig(
                    confidence_threshold=self.config.detection_confidence
                )
            )
        return self._detector
    
    @property
    def extractor(self) -> TableStructureExtractor:
        """Extracteur de structure (lazy loading)"""
        if self._extractor is None:
            self._extractor = TableStructureExtractor(
                ocr_engine=self.config.ocr_engine,
                ocr_lang=self.config.ocr_lang,
                detect_borderless=self.config.detect_borderless,
            )
        return self._extractor
    
    @property
    def hybrid(self) -> HybridExtractor:
        """Extracteur hybride (lazy loading)"""
        if self._hybrid is None:
            self._hybrid = HybridExtractor(
                ocr_engine=self.config.ocr_engine,
                ocr_lang=self.config.ocr_lang,
                detection_confidence=self.config.detection_confidence,
                detect_borderless=self.config.detect_borderless,
            )
        return self._hybrid
    
    def extract(
        self,
        pdf_path: Union[str, Path],
        output_dir: Optional[Union[str, Path]] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> ExtractionResult:
        """
        Extrait les tableaux d'un PDF
        
        Args:
            pdf_path: Chemin vers le fichier PDF
            output_dir: Répertoire de sortie (optionnel)
            progress_callback: Callback de progression (page, total, message)
            
        Returns:
            ExtractionResult avec tous les tableaux extraits
        """
        pdf_path = Path(pdf_path)
        start_time = time.time()
        
        print(f"[PDF] Traitement de: {pdf_path.name}")
        print(f"   Mode: {self.config.mode.value}")
        print(f"   OCR: {self.config.ocr_engine or 'desactive'}")
        
        # Initialiser le résultat
        result = ExtractionResult(
            pdf_path=str(pdf_path),
            total_pages=0,
            tables=[],
            errors=[]
        )
        
        try:
            # Mode FAST: utiliser img2table directement sur le PDF
            if self.config.mode == ExtractionMode.FAST:
                result = self._extract_fast(pdf_path, result, progress_callback)
            else:
                # Modes ACCURATE et HYBRID: convertir en images
                result = self._extract_with_images(pdf_path, result, progress_callback)
            
        except Exception as e:
            error_msg = f"Erreur lors de l'extraction: {str(e)}"
            result.errors.append(error_msg)
            print(f"[ERREUR] {error_msg}")
        
        # Sauvegarder les résultats
        if output_dir:
            self._save_results(result, pdf_path, output_dir)
        
        elapsed = time.time() - start_time
        print(f"\n[OK] Extraction terminee en {elapsed:.1f}s")
        print(f"   {len(result.tables)} tableau(x) extrait(s)")
        
        return result
    
    def _extract_fast(
        self,
        pdf_path: Path,
        result: ExtractionResult,
        progress_callback: Optional[Callable] = None,
    ) -> ExtractionResult:
        """Extraction rapide avec img2table directement"""
        print("   Extraction directe avec img2table...")
        
        tables = self.extractor.extract_from_pdf(
            pdf_path,
            pages=self.config.pages
        )
        
        result.tables = tables
        result.total_pages = max(t.page_number for t in tables) + 1 if tables else 0
        
        return result
    
    def _extract_with_images(
        self,
        pdf_path: Path,
        result: ExtractionResult,
        progress_callback: Optional[Callable] = None,
    ) -> ExtractionResult:
        """Extraction avec conversion en images"""
        
        # Convertir le PDF en images
        print(f"   Conversion PDF -> Images (DPI: {self.config.dpi})...")
        images = pdf_to_images(pdf_path, dpi=self.config.dpi)
        result.total_pages = len(images)
        print(f"   {len(images)} page(s) chargée(s)")
        
        # Filtrer les pages si spécifié
        pages_to_process = self.config.pages or list(range(len(images)))
        
        # Traiter chaque page
        for i, page_num in enumerate(pages_to_process):
            if page_num >= len(images):
                continue
                
            image = images[page_num]
            
            if progress_callback:
                progress_callback(i + 1, len(pages_to_process), f"Page {page_num + 1}")
            
            print(f"   [Page {page_num + 1}/{len(images)}]", end=" ")
            
            try:
                if self.config.mode == ExtractionMode.ACCURATE:
                    tables = self._extract_page_accurate(image, page_num, pdf_path)
                else:  # HYBRID
                    tables = self.hybrid.extract_from_image(image, page_num)
                
                result.tables.extend(tables)
                print(f"[OK] {len(tables)} tableau(x)")
                
            except Exception as e:
                error_msg = f"Erreur page {page_num + 1}: {str(e)}"
                result.errors.append(error_msg)
                print(f"[X] {error_msg}")
        
        # Fusionner les tableaux multi-pages
        if len(result.tables) > 1:
            from .postprocess import merge_multipage_tables
            original_count = len(result.tables)
            result.tables = merge_multipage_tables(result.tables)
            if len(result.tables) < original_count:
                merged = original_count - len(result.tables)
                print(f"   [FUSION] {merged} tableau(x) fusionné(s) (multi-pages)")
        
        return result
    
    def _extract_page_accurate(
        self,
        image,
        page_number: int,
        pdf_path: Optional[Path] = None,
    ) -> List[ExtractedTable]:
        """
        Extraction précise d'une page.
        
        Stratégie:
        1. Si PDF natif disponible → utiliser pdfplumber directement (plus fiable)
        2. Sinon → DETR + guidage visuel + img2table
        """
        from .utils import crop_image
        
        # Stratégie 1: PDF natif avec pdfplumber (plus fiable pour texte extractible)
        try:
            import pdfplumber
            if pdf_path and pdf_path.exists():
                tables = self._extract_with_pdfplumber_direct(pdf_path, page_number)
                if tables:
                    print(f"[PDFPLUMBER] {len(tables)} tableau(x)")
                    return tables
        except ImportError:
            pass
        except Exception as e:
            print(f"      [PDFPLUMBER] Échec: {e}")
        
        # Stratégie 2: DETR + guidage visuel
        detections = self.detector.detect(image)
        
        try:
            from .visual_guide import VisualGuide
            guide = VisualGuide()
            visual_regions = guide.analyze_page(image)
            
            if visual_regions:
                detections = guide.merge_bboxes(detections, visual_regions)
                print(f"      [VISUAL] {len(visual_regions)} région(s)")
        except Exception as e:
            print(f"      [VISUAL] Échec: {e}")
        
        if not detections:
            return self.extractor.extract_from_image(image, page_number)
        
        # Fallback: img2table sur les images croppées
        tables = []
        for idx, bbox in enumerate(detections):
            cropped = crop_image(image, bbox, padding=10)
            extracted = self.extractor.extract_from_image(
                cropped,
                page_number=page_number,
                bbox=bbox
            )
            for table in extracted:
                table.table_index = len(tables)
                tables.append(table)
        
        return tables
    
    def _extract_with_pdfplumber_direct(
        self,
        pdf_path: Path,
        page_number: int,
    ) -> List[ExtractedTable]:
        """
        Extraction directe avec pdfplumber (sans passer par DETR).
        
        Plus fiable pour les PDFs natifs avec texte extractible.
        """
        import pdfplumber
        from .utils import BoundingBox, TableCell
        from .postprocess import apply_postprocessing
        
        tables = []
        
        with pdfplumber.open(pdf_path) as pdf:
            if page_number >= len(pdf.pages):
                return []
            
            page = pdf.pages[page_number]
            pdf_tables = page.find_tables()
            
            for idx, pdf_table in enumerate(pdf_tables):
                raw_data = pdf_table.extract()
                if not raw_data:
                    continue
                
                # Nettoyer les None
                raw_data = [[cell if cell else "" for cell in row] for row in raw_data]
                
                # Filtrer les petites tables (moins de 3 lignes ou 3 colonnes)
                if len(raw_data) < 3 or len(raw_data[0]) < 3:
                    continue
                
                bbox = BoundingBox(
                    x1=pdf_table.bbox[0],
                    y1=pdf_table.bbox[1],
                    x2=pdf_table.bbox[2],
                    y2=pdf_table.bbox[3],
                    confidence=1.0,
                    label="table"
                )
                
                cells = []
                for row_idx, row in enumerate(raw_data):
                    for col_idx, content in enumerate(row):
                        cells.append(TableCell(
                            row=row_idx,
                            col=col_idx,
                            content=content,
                        ))
                
                extracted = ExtractedTable(
                    page_number=page_number,
                    table_index=len(tables),
                    bbox=bbox,
                    cells=cells,
                    num_rows=len(raw_data),
                    num_cols=len(raw_data[0]) if raw_data else 0,
                    raw_data=raw_data,
                )
                
                # Appliquer le post-traitement
                extracted = apply_postprocessing(extracted)
                tables.append(extracted)
        
        return tables
    
    def _extract_with_pdfplumber(
        self,
        pdf_path: Path,
        page_number: int,
        bboxes: List,
    ) -> List[ExtractedTable]:
        """Extrait le contenu des tableaux avec pdfplumber + post-traitement."""
        import pdfplumber
        from .utils import BoundingBox, TableCell
        from .postprocess import apply_postprocessing
        
        tables = []
        
        with pdfplumber.open(pdf_path) as pdf:
            if page_number >= len(pdf.pages):
                return []
            
            page = pdf.pages[page_number]
            pdf_tables = page.find_tables()
            
            # Pour chaque bbox détectée, trouver la table pdfplumber correspondante
            for bbox_idx, bbox in enumerate(bboxes):
                # Convertir les coordonnées (image DPI -> PDF points)
                # Ratio approximatif : image_coord / dpi * 72
                scale = 72.0 / self.config.dpi
                pdf_bbox = (
                    bbox.x1 * scale,
                    bbox.y1 * scale,
                    bbox.x2 * scale,
                    bbox.y2 * scale,
                )
                
                # Trouver la meilleure table pdfplumber qui correspond
                best_table = None
                best_overlap = 0
                
                for pdf_table in pdf_tables:
                    overlap = self._compute_overlap(pdf_bbox, pdf_table.bbox)
                    if overlap > best_overlap:
                        best_overlap = overlap
                        best_table = pdf_table
                
                if best_table and best_overlap > 0.3:
                    raw_data = best_table.extract()
                    # Nettoyer les None
                    raw_data = [[cell if cell else "" for cell in row] for row in raw_data]
                    
                    cells = []
                    for row_idx, row in enumerate(raw_data):
                        for col_idx, content in enumerate(row):
                            cells.append(TableCell(
                                row=row_idx,
                                col=col_idx,
                                content=content,
                            ))
                    
                    extracted = ExtractedTable(
                        page_number=page_number,
                        table_index=len(tables),
                        bbox=bbox,
                        cells=cells,
                        num_rows=len(raw_data),
                        num_cols=len(raw_data[0]) if raw_data else 0,
                        raw_data=raw_data,
                    )
                    
                    # Appliquer le post-traitement
                    extracted = apply_postprocessing(extracted)
                    tables.append(extracted)
        
        return tables
    
    @staticmethod
    def _compute_overlap(bbox1: tuple, bbox2: tuple) -> float:
        """Calcule le ratio de chevauchement entre deux bboxes."""
        x1 = max(bbox1[0], bbox2[0])
        y1 = max(bbox1[1], bbox2[1])
        x2 = min(bbox1[2], bbox2[2])
        y2 = min(bbox1[3], bbox2[3])
        
        if x2 < x1 or y2 < y1:
            return 0.0
        
        intersection = (x2 - x1) * (y2 - y1)
        area1 = (bbox1[2] - bbox1[0]) * (bbox1[3] - bbox1[1])
        area2 = (bbox2[2] - bbox2[0]) * (bbox2[3] - bbox2[1])
        
        # Ratio par rapport à la plus petite bbox
        min_area = min(area1, area2)
        return intersection / min_area if min_area > 0 else 0.0
    
    def _save_results(
        self,
        result: ExtractionResult,
        pdf_path: Path,
        output_dir: Union[str, Path],
    ) -> None:
        """Sauvegarde les résultats"""
        output_dir = ensure_output_dir(output_dir, pdf_path.name)
        
        print(f"\n   [SAVE] Sauvegarde dans: {output_dir}")
        
        # JSON
        if "json" in self.config.output_format:
            json_path = output_dir / "tables.json"
            result.save_json(json_path)
            print(f"      - {json_path.name}")
        
        # CSV
        if "csv" in self.config.output_format:
            csv_files = result.save_all_csv(output_dir)
            print(f"      - {len(csv_files)} fichier(s) CSV")
        
        # Images annotées
        if self.config.save_images and result.tables:
            self._save_annotated_images(pdf_path, result, output_dir)
    
    def _save_annotated_images(
        self,
        pdf_path: Path,
        result: ExtractionResult,
        output_dir: Path,
    ) -> None:
        """Sauvegarde les images avec les tableaux annotés"""
        from PIL import ImageDraw
        
        images = pdf_to_images(pdf_path, dpi=self.config.dpi)
        
        # Grouper les tableaux par page
        tables_by_page = {}
        for table in result.tables:
            page = table.page_number
            if page not in tables_by_page:
                tables_by_page[page] = []
            tables_by_page[page].append(table)
        
        # Annoter et sauvegarder
        for page_num, tables in tables_by_page.items():
            if page_num >= len(images):
                continue
            
            image = images[page_num].copy()
            draw = ImageDraw.Draw(image)
            
            for table in tables:
                bbox = table.bbox
                # Rectangle rouge
                draw.rectangle(
                    [bbox.x1, bbox.y1, bbox.x2, bbox.y2],
                    outline="red",
                    width=3
                )
                # Label
                draw.text(
                    (bbox.x1 + 5, bbox.y1 + 5),
                    f"Table {table.table_index + 1}",
                    fill="red"
                )
            
            img_path = output_dir / f"page{page_num + 1}_annotated.png"
            image.save(img_path)


def quick_extract(
    pdf_path: Union[str, Path],
    output_dir: Optional[Union[str, Path]] = None,
    mode: str = "accurate",
    ocr_lang: str = "fra+eng",
) -> ExtractionResult:
    """
    Fonction utilitaire pour une extraction rapide
    
    Args:
        pdf_path: Chemin vers le PDF
        output_dir: Répertoire de sortie (optionnel)
        mode: "fast", "accurate", ou "hybrid"
        ocr_lang: Langues OCR
        
    Returns:
        ExtractionResult
    """
    config = PipelineConfig(
        mode=ExtractionMode(mode),
        ocr_lang=ocr_lang,
    )
    
    pipeline = TableExtractionPipeline(config)
    return pipeline.extract(pdf_path, output_dir)

