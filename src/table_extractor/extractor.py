"""
Module d'extraction de structure de tableaux utilisant img2table

Ce module utilise img2table pour extraire la structure et le contenu
des tableaux à partir d'images.
"""

from typing import List, Optional, Union, Tuple
from pathlib import Path
from PIL import Image
import tempfile
import os

from .utils import BoundingBox, TableCell, ExtractedTable


class TableStructureExtractor:
    """
    Extracteur de structure de tableaux basé sur img2table
    
    Utilise img2table pour détecter et extraire la structure 
    complète des tableaux (lignes, colonnes, cellules fusionnées).
    """
    
    def __init__(
        self,
        ocr_engine: str = "tesseract",  # "tesseract", "paddleocr", "easyocr", None
        ocr_lang: str = "fra+eng",
        detect_borderless: bool = True,
        min_confidence: float = 50.0,
    ):
        """
        Initialise l'extracteur
        
        Args:
            ocr_engine: Moteur OCR à utiliser ("tesseract", "paddleocr", "easyocr", None)
            ocr_lang: Langues pour l'OCR (format Tesseract)
            detect_borderless: Détecter les tableaux sans bordures
            min_confidence: Confiance minimale pour les cellules OCR
        """
        self.ocr_engine = ocr_engine
        self.ocr_lang = ocr_lang
        self.detect_borderless = detect_borderless
        self.min_confidence = min_confidence
        self._ocr = None
    
    def _get_ocr(self):
        """Initialise le moteur OCR"""
        if self._ocr is None and self.ocr_engine:
            if self.ocr_engine == "tesseract":
                from img2table.ocr import TesseractOCR
                self._ocr = TesseractOCR(lang=self.ocr_lang)
            elif self.ocr_engine == "paddleocr":
                from img2table.ocr import PaddleOCR
                lang = "fr" if "fra" in self.ocr_lang else "en"
                self._ocr = PaddleOCR(lang=lang)
            elif self.ocr_engine == "easyocr":
                from img2table.ocr import EasyOCR
                langs = []
                if "fra" in self.ocr_lang:
                    langs.append("fr")
                if "eng" in self.ocr_lang:
                    langs.append("en")
                self._ocr = EasyOCR(lang=langs or ["en"])
        return self._ocr
    
    def extract_from_image(
        self, 
        image: Image.Image,
        page_number: int = 0,
        bbox: Optional[BoundingBox] = None,
    ) -> List[ExtractedTable]:
        """
        Extrait les tableaux d'une image
        
        Args:
            image: Image PIL
            page_number: Numéro de page (pour le rapport)
            bbox: BoundingBox optionnel si on travaille sur une région
            
        Returns:
            Liste de ExtractedTable
        """
        from img2table.document import Image as Img2TableImage
        
        # Sauvegarder temporairement l'image
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            image.save(tmp.name)
            tmp_path = tmp.name
        
        try:
            # Créer le document img2table
            doc = Img2TableImage(src=tmp_path)
            
            # Extraire les tableaux
            ocr = self._get_ocr()
            tables = doc.extract_tables(
                ocr=ocr,
                implicit_rows=True,
                implicit_columns=True,
                borderless_tables=self.detect_borderless,
                min_confidence=self.min_confidence,
            )
            
            # Convertir en ExtractedTable
            extracted = []
            for idx, table in enumerate(tables):
                ext_table = self._convert_table(table, page_number, idx, bbox)
                if ext_table:
                    extracted.append(ext_table)
            
            return extracted
            
        finally:
            # Nettoyer le fichier temporaire
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    def extract_from_pdf(
        self,
        pdf_path: Union[str, Path],
        pages: Optional[List[int]] = None,
    ) -> List[ExtractedTable]:
        """
        Extrait les tableaux directement d'un PDF
        
        Args:
            pdf_path: Chemin vers le PDF
            pages: Liste des pages à traiter (None = toutes)
            
        Returns:
            Liste de ExtractedTable
        """
        from img2table.document import PDF
        
        pdf_path = Path(pdf_path)
        
        # Créer le document img2table
        doc = PDF(src=str(pdf_path), pages=pages)
        
        # Extraire les tableaux
        ocr = self._get_ocr()
        tables_by_page = doc.extract_tables(
            ocr=ocr,
            implicit_rows=True,
            implicit_columns=True,
            borderless_tables=self.detect_borderless,
            min_confidence=self.min_confidence,
        )
        
        # Convertir en ExtractedTable
        all_tables = []
        for page_num, tables in tables_by_page.items():
            for idx, table in enumerate(tables):
                ext_table = self._convert_table(table, page_num, idx)
                if ext_table:
                    all_tables.append(ext_table)
        
        return all_tables
    
    def _convert_table(
        self, 
        img2table_table,
        page_number: int,
        table_index: int,
        offset_bbox: Optional[BoundingBox] = None,
    ) -> Optional[ExtractedTable]:
        """
        Convertit un tableau img2table en ExtractedTable
        """
        try:
            # Obtenir les données du tableau
            df = img2table_table.df
            if df is None or df.empty:
                return None
            
            # BoundingBox du tableau
            tb = img2table_table.bbox
            bbox = BoundingBox(
                x1=tb.x1 + (offset_bbox.x1 if offset_bbox else 0),
                y1=tb.y1 + (offset_bbox.y1 if offset_bbox else 0),
                x2=tb.x2 + (offset_bbox.x1 if offset_bbox else 0),
                y2=tb.y2 + (offset_bbox.y1 if offset_bbox else 0),
                confidence=1.0,
                label="table"
            )
            
            # Construire les cellules
            cells = []
            raw_data = []
            
            for row_idx, row in df.iterrows():
                row_data = []
                for col_idx, value in enumerate(row):
                    cell = TableCell(
                        row=row_idx,
                        col=col_idx,
                        content=str(value) if value is not None else ""
                    )
                    cells.append(cell)
                    row_data.append(str(value) if value is not None else "")
                raw_data.append(row_data)
            
            return ExtractedTable(
                page_number=page_number,
                table_index=table_index,
                bbox=bbox,
                cells=cells,
                num_rows=len(df),
                num_cols=len(df.columns),
                raw_data=raw_data
            )
            
        except Exception as e:
            print(f"Erreur conversion tableau: {e}")
            return None


class HybridExtractor:
    """
    Extracteur hybride combinant Table Transformer et img2table
    
    Utilise Table Transformer pour la détection initiale des tableaux,
    puis img2table pour l'extraction de la structure et du contenu.
    """
    
    def __init__(
        self,
        ocr_engine: str = "tesseract",
        ocr_lang: str = "fra+eng",
        detection_confidence: float = 0.7,
        detect_borderless: bool = True,
    ):
        from .detector import TableDetector, DetectorConfig
        
        self.detector = TableDetector(
            config=DetectorConfig(confidence_threshold=detection_confidence)
        )
        self.extractor = TableStructureExtractor(
            ocr_engine=ocr_engine,
            ocr_lang=ocr_lang,
            detect_borderless=detect_borderless,
        )
    
    def extract_from_image(
        self,
        image: Image.Image,
        page_number: int = 0,
    ) -> List[ExtractedTable]:
        """
        Extrait les tableaux d'une image en utilisant la détection DETR
        puis l'extraction img2table sur les régions détectées
        """
        from .utils import crop_image
        
        # Étape 1: Détection avec Table Transformer
        detections = self.detector.detect(image)
        
        if not detections:
            # Fallback: utiliser img2table sur l'image entière
            return self.extractor.extract_from_image(image, page_number)
        
        # Étape 2: Extraction sur chaque région détectée
        all_tables = []
        for idx, bbox in enumerate(detections):
            # Découper la région du tableau
            cropped = crop_image(image, bbox, padding=10)
            
            # Extraire avec img2table
            tables = self.extractor.extract_from_image(
                cropped, 
                page_number=page_number,
                bbox=bbox
            )
            
            # Si img2table n'a rien trouvé, créer un tableau vide avec le bbox
            if not tables:
                empty_table = ExtractedTable(
                    page_number=page_number,
                    table_index=idx,
                    bbox=bbox,
                    cells=[],
                    num_rows=0,
                    num_cols=0,
                    raw_data=[]
                )
                all_tables.append(empty_table)
            else:
                # Mettre à jour les index
                for table in tables:
                    table.table_index = len(all_tables)
                    all_tables.append(table)
        
        return all_tables

