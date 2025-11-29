"""
Table Extractor - Extraction de tableaux complexes depuis des PDF

Ce module fournit une solution robuste pour extraire des tableaux 
de documents PDF complexes en utilisant:
- Table Transformer (Microsoft) pour la détection de tableaux
- Guidage visuel (détection couleurs/lignes) pour améliorer les bboxes
- img2table pour l'extraction de la structure
"""

__version__ = "1.0.0"

# Imports lazy pour éviter de charger torch au démarrage
__all__ = [
    "TableExtractionPipeline",
    "PipelineConfig",
    "ExtractionMode",
    "TableDetector", 
    "TableStructureExtractor",
]


def __getattr__(name):
    """Import lazy des modules qui nécessitent des dépendances lourdes."""
    if name == "TableExtractionPipeline":
        from .pipeline import TableExtractionPipeline
        return TableExtractionPipeline
    if name == "PipelineConfig":
        from .pipeline import PipelineConfig
        return PipelineConfig
    if name == "ExtractionMode":
        from .pipeline import ExtractionMode
        return ExtractionMode
    if name == "TableDetector":
        from .detector import TableDetector
        return TableDetector
    if name == "TableStructureExtractor":
        from .extractor import TableStructureExtractor
        return TableStructureExtractor
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

