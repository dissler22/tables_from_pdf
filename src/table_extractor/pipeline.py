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
                    tables = self._extract_page_accurate(image, page_num)
                else:  # HYBRID
                    tables = self.hybrid.extract_from_image(image, page_num)
                
                result.tables.extend(tables)
                print(f"[OK] {len(tables)} tableau(x)")
                
            except Exception as e:
                error_msg = f"Erreur page {page_num + 1}: {str(e)}"
                result.errors.append(error_msg)
                print(f"[X] {error_msg}")
        
        return result
    
    def _extract_page_accurate(
        self,
        image,
        page_number: int,
    ) -> List[ExtractedTable]:
        """Extraction précise d'une page"""
        from .utils import crop_image
        
        # Étape 1: Détecter les tableaux
        detections = self.detector.detect(image)
        
        if not detections:
            # Essayer img2table sur la page entière
            return self.extractor.extract_from_image(image, page_number)
        
        # Étape 2: Extraire chaque tableau
        tables = []
        for idx, bbox in enumerate(detections):
            # Découper la région
            cropped = crop_image(image, bbox, padding=10)
            
            # Extraire avec img2table
            extracted = self.extractor.extract_from_image(
                cropped,
                page_number=page_number,
                bbox=bbox
            )
            
            for table in extracted:
                table.table_index = len(tables)
                tables.append(table)
        
        return tables
    
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

