"""
Tests de régression sur la page 2 du PDF ESC journaux de chantier.

On vérifie que les tableaux extraits correspondent aux goldens avec une
tolérance aux différences mineures (lignes vides en plus = OK).
"""

from pathlib import Path
import json
import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# Chemins possibles pour le PDF de test
PDF_PATHS = [
    Path(__file__).parent / "data_test" / "pdf_tables" / "ESC_A57_000675_EXE_GEN_0-0000_SS_JDC_5108_A_Journaux_de_chantier_2023_S01.pdf",
    Path(__file__).parent.parent / "data" / "upload" / "ESC_A57_000675_EXE_GEN_0-0000_SS_JDC_5108_A_Journaux_de_chantier_2023_S01.pdf",
]
GOLDENS_DIR = Path(__file__).parent / "goldens"


def _get_pdf_path() -> Path:
    """Retourne le premier chemin PDF existant."""
    for path in PDF_PATHS:
        if path.exists():
            return path
    return PDF_PATHS[0]


def _load_golden_rows(table_idx: int):
    """Charge le golden JSON."""
    path = GOLDENS_DIR / f"esc_page2_table{table_idx}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _is_row_empty(row: list) -> bool:
    """Vérifie si une ligne est vide (toutes cellules vides ou juste des 0)."""
    for cell in row:
        if cell and cell.strip() and cell.strip() != "0":
            return False
    return True


def _compare_tables_tolerant(extracted: list, golden: list) -> dict:
    """
    Compare deux tableaux avec tolérance aux différences mineures.
    
    Returns:
        dict avec:
        - ok: bool - True si les données importantes sont présentes
        - missing_rows: list - lignes du golden non trouvées
        - extra_rows: list - lignes extraites non dans le golden (hors vides)
        - mismatches: list - lignes différentes
    """
    result = {
        "ok": True,
        "missing_rows": [],
        "extra_empty_rows": 0,
        "mismatches": [],
    }
    
    # Filtrer les lignes vides de l'extraction
    extracted_content = [row for row in extracted if not _is_row_empty(row)]
    golden_content = [row for row in golden if not _is_row_empty(row)]
    
    # Compter les lignes vides en plus (toléré)
    result["extra_empty_rows"] = len(extracted) - len(extracted_content)
    
    # Vérifier que toutes les lignes du golden sont présentes
    for i, golden_row in enumerate(golden_content):
        found = False
        for ext_row in extracted_content:
            # Comparer la première cellule (identifiant de ligne)
            if ext_row[0] == golden_row[0]:
                found = True
                # Vérifier le contenu des autres cellules
                for j in range(1, min(len(ext_row), len(golden_row))):
                    if ext_row[j] != golden_row[j]:
                        result["mismatches"].append({
                            "row": golden_row[0],
                            "col": j,
                            "expected": golden_row[j][:50] if golden_row[j] else "",
                            "got": ext_row[j][:50] if ext_row[j] else "",
                        })
                break
        
        if not found:
            result["missing_rows"].append(golden_row[0])
            result["ok"] = False
    
    # Si trop de mismatches, c'est un problème
    if len(result["mismatches"]) > len(golden_content) * 0.2:  # Plus de 20% de différences
        result["ok"] = False
    
    return result


def test_esc_page2_tables_extraction():
    """
    La page 2 (index 1) doit produire la table d'encadrement.
    
    Vérifie que :
    - Au moins un tableau est extrait
    - Les données importantes du golden sont présentes
    - Tolère les lignes vides en plus
    """
    from table_extractor.pipeline import TableExtractionPipeline, PipelineConfig, ExtractionMode
    
    pdf_path = _get_pdf_path()
    if not pdf_path.exists():
        pytest.skip(f"PDF de test manquant: {pdf_path}")

    config = PipelineConfig(
        mode=ExtractionMode.ACCURATE,
        ocr_engine=None,
        pages=[1],
    )
    pipeline = TableExtractionPipeline(config)
    result = pipeline.extract(pdf_path)

    # Au moins un tableau extrait
    tables_page2 = [t for t in result.tables if t.page_number == 1]
    assert len(tables_page2) >= 1, "Aucun tableau extrait sur la page 2"

    # Prendre le plus grand tableau (celui avec le plus de lignes non-vides)
    table = max(tables_page2, key=lambda t: len([r for r in t.raw_data if not _is_row_empty(r)]))
    golden = _load_golden_rows(0)
    
    # Comparaison tolérante
    comparison = _compare_tables_tolerant(table.raw_data, golden)
    
    # Afficher les résultats
    print(f"\n=== Résultat extraction ===")
    print(f"Lignes extraites: {len(table.raw_data)} (dont {comparison['extra_empty_rows']} vides)")
    print(f"Lignes golden: {len(golden)}")
    
    if comparison["missing_rows"]:
        print(f"⚠ Lignes manquantes: {comparison['missing_rows']}")
    
    if comparison["mismatches"]:
        print(f"⚠ Différences ({len(comparison['mismatches'])}):")
        for m in comparison["mismatches"][:5]:  # Max 5 affichées
            print(f"   - {m['row']}, col {m['col']}")
    
    # Le test passe si les données importantes sont là
    assert comparison["ok"], f"Données manquantes: {comparison['missing_rows']}"
    assert not comparison["missing_rows"], f"Lignes du golden non trouvées: {comparison['missing_rows']}"
