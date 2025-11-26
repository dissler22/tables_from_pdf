"""
Table Extractor - Extraction de tableaux complexes depuis des PDF

Ce module fournit une solution robuste pour extraire des tableaux 
de documents PDF complexes en utilisant:
- Table Transformer (Microsoft) pour la détection de tableaux
- img2table pour l'extraction de la structure
"""

from .pipeline import TableExtractionPipeline
from .detector import TableDetector
from .extractor import TableStructureExtractor

__all__ = [
    "TableExtractionPipeline",
    "TableDetector", 
    "TableStructureExtractor",
]

__version__ = "1.0.0"

