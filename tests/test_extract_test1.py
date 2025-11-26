import csv
import json
from pathlib import Path

from back.extractor import ExtractedTable, extract_tables


def _read_csv(path: Path):
    with path.open(newline="", encoding="utf-8") as fp:
        return [row for row in csv.reader(fp)]


def _find_by_header(tables: list[ExtractedTable], header: list[str]) -> list[list[str]]:
    for t in tables:
        if t.cells and t.cells[0] == header:
            return t.cells
    return []


def test_extract_test1(tmp_path):
    pdf_path = Path("tests/data_test/pdf_tables/test1.pdf")
    output_dir = tmp_path / "artifacts"

    tables = extract_tables(pdf_path, output_dir=output_dir, pages=[0])

    expected_main = _read_csv(Path("tests/goldens/test1_main.csv"))
    expected_footer = _read_csv(Path("tests/goldens/test1_footer.csv"))

    main_cells = _find_by_header(tables, expected_main[0])
    footer_cells = _find_by_header(tables, expected_footer[0])

    assert main_cells == expected_main
    assert footer_cells == expected_footer

    # Artefacts générés
    annotated = output_dir / "page1_annotated.png"
    json_out = output_dir / "tables.json"
    assert annotated.exists(), "L'image annotée doit être générée."
    assert json_out.exists(), "Le JSON des tables doit être généré."

    with json_out.open(encoding="utf-8") as fp:
        data = json.load(fp)
    # Vérification que les tables attendues sont bien présentes dans le JSON
    assert any(tbl["cells"][0] == expected_main[0] for tbl in data)
    assert any(tbl["cells"][0] == expected_footer[0] for tbl in data)
