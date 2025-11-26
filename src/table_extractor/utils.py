"""
Utilitaires pour l'extraction de tableaux
"""

import os
from pathlib import Path
from typing import List, Tuple, Optional, Union
from dataclasses import dataclass, field
from PIL import Image
import json


@dataclass
class BoundingBox:
    """Représente une boîte englobante"""
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float = 1.0
    label: str = "table"
    
    @property
    def width(self) -> float:
        return self.x2 - self.x1
    
    @property
    def height(self) -> float:
        return self.y2 - self.y1
    
    @property
    def area(self) -> float:
        return self.width * self.height
    
    @property
    def center(self) -> Tuple[float, float]:
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)
    
    def to_dict(self) -> dict:
        return {
            "x1": self.x1,
            "y1": self.y1,
            "x2": self.x2,
            "y2": self.y2,
            "confidence": self.confidence,
            "label": self.label
        }
    
    def to_tuple(self) -> Tuple[float, float, float, float]:
        return (self.x1, self.y1, self.x2, self.y2)


@dataclass
class TableCell:
    """Représente une cellule de tableau"""
    row: int
    col: int
    row_span: int = 1
    col_span: int = 1
    content: str = ""
    bbox: Optional[BoundingBox] = None
    
    def to_dict(self) -> dict:
        result = {
            "row": self.row,
            "col": self.col,
            "row_span": self.row_span,
            "col_span": self.col_span,
            "content": self.content,
        }
        if self.bbox:
            result["bbox"] = self.bbox.to_dict()
        return result


@dataclass
class ExtractedTable:
    """Représente un tableau extrait"""
    page_number: int
    table_index: int
    bbox: BoundingBox
    cells: List[TableCell] = field(default_factory=list)
    num_rows: int = 0
    num_cols: int = 0
    raw_data: List[List[str]] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "page_number": self.page_number,
            "table_index": self.table_index,
            "bbox": self.bbox.to_dict(),
            "num_rows": self.num_rows,
            "num_cols": self.num_cols,
            "cells": [cell.to_dict() for cell in self.cells],
            "raw_data": self.raw_data
        }
    
    def to_dataframe(self):
        """Convertit en DataFrame pandas"""
        import pandas as pd
        if self.raw_data:
            if len(self.raw_data) > 1:
                return pd.DataFrame(self.raw_data[1:], columns=self.raw_data[0])
            return pd.DataFrame(self.raw_data)
        return pd.DataFrame()
    
    def to_csv(self, path: Union[str, Path]) -> None:
        """Exporte en CSV"""
        df = self.to_dataframe()
        df.to_csv(path, index=False, encoding='utf-8-sig')
    
    def to_json(self) -> str:
        """Exporte en JSON"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


@dataclass 
class ExtractionResult:
    """Résultat complet d'une extraction"""
    pdf_path: str
    total_pages: int
    tables: List[ExtractedTable] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "pdf_path": self.pdf_path,
            "total_pages": self.total_pages,
            "total_tables": len(self.tables),
            "tables": [t.to_dict() for t in self.tables],
            "errors": self.errors
        }
    
    def save_json(self, path: Union[str, Path]) -> None:
        """Sauvegarde le résultat en JSON"""
        import numpy as np
        
        def convert_types(obj):
            """Convertit les types numpy en types Python natifs"""
            if isinstance(obj, dict):
                return {k: convert_types(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_types(item) for item in obj]
            elif isinstance(obj, (np.integer, np.int64, np.int32)):
                return int(obj)
            elif isinstance(obj, (np.floating, np.float64, np.float32)):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            return obj
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(convert_types(self.to_dict()), f, ensure_ascii=False, indent=2)
    
    def save_all_csv(self, output_dir: Union[str, Path]) -> List[Path]:
        """Sauvegarde tous les tableaux en CSV"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        saved_files = []
        for table in self.tables:
            filename = f"page{table.page_number}_table{table.table_index}.csv"
            filepath = output_dir / filename
            table.to_csv(filepath)
            saved_files.append(filepath)
        
        return saved_files


def pdf_to_images(pdf_path: Union[str, Path], dpi: int = 200) -> List[Image.Image]:
    """
    Convertit un PDF en liste d'images PIL
    
    Args:
        pdf_path: Chemin vers le fichier PDF
        dpi: Résolution en DPI (défaut: 200)
        
    Returns:
        Liste d'images PIL, une par page
    """
    import pypdfium2 as pdfium
    
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF non trouvé: {pdf_path}")
    
    pdf = pdfium.PdfDocument(str(pdf_path))
    images = []
    
    scale = dpi / 72  # 72 DPI est la résolution de base PDF
    
    for page_index in range(len(pdf)):
        page = pdf[page_index]
        bitmap = page.render(scale=scale)
        pil_image = bitmap.to_pil()
        images.append(pil_image)
    
    pdf.close()
    return images


def crop_image(image: Image.Image, bbox: BoundingBox, padding: int = 5) -> Image.Image:
    """
    Découpe une région d'une image
    
    Args:
        image: Image PIL source
        bbox: Boîte englobante
        padding: Marge en pixels
        
    Returns:
        Image découpée
    """
    x1 = max(0, int(bbox.x1) - padding)
    y1 = max(0, int(bbox.y1) - padding)
    x2 = min(image.width, int(bbox.x2) + padding)
    y2 = min(image.height, int(bbox.y2) + padding)
    
    return image.crop((x1, y1, x2, y2))


def ensure_output_dir(base_dir: Union[str, Path], pdf_name: str) -> Path:
    """Crée et retourne le répertoire de sortie pour un PDF"""
    output_dir = Path(base_dir) / Path(pdf_name).stem
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir

