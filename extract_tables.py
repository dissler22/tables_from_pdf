#!/usr/bin/env python3
"""
Script principal d'extraction de tableaux depuis des PDF

Usage:
    python extract_tables.py <pdf_path> [options]
    
Exemples:
    python extract_tables.py data/upload/document.pdf
    python extract_tables.py data/upload/document.pdf --mode fast
    python extract_tables.py data/upload/document.pdf --output results/
    python extract_tables.py data/upload/ --all  # Traiter tous les PDFs
"""

import argparse
import sys
import os
from pathlib import Path

# Fix encodage Windows
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Ajouter src au path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from table_extractor import TableExtractionPipeline
from table_extractor.pipeline import PipelineConfig, ExtractionMode


def main():
    parser = argparse.ArgumentParser(
        description="Extraction de tableaux complexes depuis des PDF",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  %(prog)s data/upload/document.pdf
  %(prog)s data/upload/document.pdf --mode fast --output results/
  %(prog)s data/upload/ --all
  %(prog)s tests/data_test/pdf_tables/test1.pdf --pages 0
        """
    )
    
    parser.add_argument(
        "input",
        help="Chemin vers un fichier PDF ou un répertoire"
    )
    
    parser.add_argument(
        "--output", "-o",
        default="data/output",
        help="Répertoire de sortie (défaut: data/output)"
    )
    
    parser.add_argument(
        "--mode", "-m",
        choices=["fast", "accurate", "hybrid"],
        default="accurate",
        help="Mode d'extraction (défaut: accurate)"
    )
    
    parser.add_argument(
        "--ocr",
        choices=["tesseract", "paddleocr", "easyocr", "none"],
        default="tesseract",
        help="Moteur OCR (défaut: tesseract)"
    )
    
    parser.add_argument(
        "--lang",
        default="fra+eng",
        help="Langues OCR (défaut: fra+eng)"
    )
    
    parser.add_argument(
        "--dpi",
        type=int,
        default=200,
        help="Résolution de rendu (défaut: 200)"
    )
    
    parser.add_argument(
        "--pages", "-p",
        type=str,
        default=None,
        help="Pages à traiter (ex: '0,1,2' ou '0-5')"
    )
    
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Traiter tous les PDFs du répertoire"
    )
    
    parser.add_argument(
        "--no-images",
        action="store_true",
        help="Ne pas sauvegarder les images annotées"
    )
    
    parser.add_argument(
        "--confidence",
        type=float,
        default=0.7,
        help="Seuil de confiance pour la détection (défaut: 0.7)"
    )
    
    args = parser.parse_args()
    
    # Parser les pages
    pages = None
    if args.pages:
        pages = parse_pages(args.pages)
    
    # Configuration
    config = PipelineConfig(
        mode=ExtractionMode(args.mode),
        ocr_engine=None if args.ocr == "none" else args.ocr,
        ocr_lang=args.lang,
        dpi=args.dpi,
        pages=pages,
        save_images=not args.no_images,
        detection_confidence=args.confidence,
    )
    
    # Créer le pipeline
    pipeline = TableExtractionPipeline(config)
    
    # Déterminer les fichiers à traiter
    input_path = Path(args.input)
    output_dir = Path(args.output)
    
    if input_path.is_file():
        # Un seul fichier
        pdf_files = [input_path]
    elif input_path.is_dir():
        if args.all:
            # Tous les PDFs du répertoire
            pdf_files = list(input_path.glob("*.pdf"))
            pdf_files = [f for f in pdf_files if not f.name.startswith("~$")]
        else:
            print(f"❌ '{input_path}' est un répertoire. Utilisez --all pour traiter tous les PDFs.")
            sys.exit(1)
    else:
        print(f"❌ Fichier ou répertoire non trouvé: {input_path}")
        sys.exit(1)
    
    if not pdf_files:
        print(f"❌ Aucun fichier PDF trouvé dans: {input_path}")
        sys.exit(1)
    
    print(f"\n{'='*60}")
    print(f"[*] EXTRACTION DE TABLEAUX")
    print(f"{'='*60}")
    print(f"Fichiers: {len(pdf_files)}")
    print(f"Mode: {args.mode}")
    print(f"OCR: {args.ocr} ({args.lang})")
    print(f"DPI: {args.dpi}")
    print(f"Sortie: {output_dir}")
    print(f"{'='*60}\n")
    
    # Traiter chaque fichier
    all_results = []
    for pdf_file in pdf_files:
        result = pipeline.extract(pdf_file, output_dir)
        all_results.append(result)
    
    # Résumé
    print(f"\n{'='*60}")
    print(f"[RESUME]")
    print(f"{'='*60}")
    total_tables = sum(len(r.tables) for r in all_results)
    total_errors = sum(len(r.errors) for r in all_results)
    print(f"Fichiers traités: {len(all_results)}")
    print(f"Tableaux extraits: {total_tables}")
    if total_errors:
        print(f"Erreurs: {total_errors}")
    print(f"{'='*60}\n")


def parse_pages(pages_str: str) -> list:
    """Parse une chaîne de pages en liste d'indices"""
    pages = []
    for part in pages_str.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-")
            pages.extend(range(int(start), int(end) + 1))
        else:
            pages.append(int(part))
    return sorted(set(pages))


if __name__ == "__main__":
    main()

