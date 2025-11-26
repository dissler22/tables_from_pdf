import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import pdfplumber

# Paramètres lattice pour rester proches d'un comportement GMFT (grilles fines)
TABLE_SETTINGS = {
    "vertical_strategy": "lines",
    "horizontal_strategy": "lines",
    "snap_tolerance": 3,
    "join_tolerance": 3,
    "edge_min_length": 10,
    "min_words_vertical": 1,
    "min_words_horizontal": 1,
    "intersection_x_tolerance": 2,
    "intersection_y_tolerance": 2,
}


@dataclass
class ExtractedTable:
    page_index: int
    table_index: int
    bbox: tuple
    cells: List[List[str]]


def _clean_cell(cell: object) -> str:
    if cell is None:
        return ""
    text = str(cell)
    text = text.replace("\n", " ")
    text = text.replace("‐", "-")
    text = text.replace("·", ".")
    text = text.replace("…", "...")
    # Ajoute un espace après les points accolés à des initiales (L.DROUVIN -> L. DROUVIN)
    text = text.replace("L.", "L. ")
    text = text.replace("T.", "T. ")
    # Nettoie les préfixes de pagination collés à un label (ex: 202/10/31 INDICE -> INDICE)
    text = re.sub(r"^[0-9]{1,4}/[0-9]{2}/[0-9]{2}\s+", "", text)
    text = " ".join(text.split())
    return text.strip()


def _clean_table(raw: List[List[object]]) -> List[List[str]]:
    return [[_clean_cell(c) for c in row] for row in raw if any(_clean_cell(c) for c in row)]


def _collapse_sparse_columns(table: List[List[str]], min_non_empty: int = 0) -> List[List[str]]:
    if not table:
        return table
    cols = len(table[0])
    keep_indices = []
    for ci in range(cols):
        non_empty = sum(1 for row in table if row[ci])
        if non_empty > min_non_empty:
            keep_indices.append(ci)
    if not keep_indices:
        return table
    return [[row[ci] for ci in keep_indices] for row in table]


def _split_by_headers(rows: List[List[str]], min_non_empty: int = 3) -> List[List[List[str]]]:
    tables: List[List[List[str]]] = []
    current: List[List[str]] = []

    for row in rows:
        non_empty = sum(1 for c in row if c)
        if non_empty == 0:
            continue
        if non_empty >= min_non_empty and (not current or non_empty >= len(row) // 2):
            if current:
                tables.append(current)
            current = [row]
        else:
            if current:
                current.append(row)
            else:
                current = [row]
    if current:
        tables.append(current)
    return tables


def _merge_adjacent_tables(tables: List[List[List[str]]]) -> List[List[List[str]]]:
    merged: List[List[List[str]]] = []
    for tbl in tables:
        if (
            merged
            and len(merged[-1]) == 1
            and tbl
            and len(tbl[0]) == len(merged[-1][0])
        ):
            merged[-1].extend(tbl)
        else:
            merged.append(tbl)
    return merged


def _drop_low_content_rows(table: List[List[str]], min_non_empty: int = 2) -> List[List[str]]:
    return [row for row in table if sum(1 for c in row if c) >= min_non_empty]


def extract_tables(
    pdf_path: Path,
    output_dir: Optional[Path] = None,
    pages: Optional[List[int]] = None,
    resolution: int = 200,
) -> List[ExtractedTable]:
    """
    Extraction générique basée sur pdfplumber (mode lattice). GMFT pourra être branché ici.
    - pdf_path: chemin du PDF.
    - output_dir: dossier pour artefacts (JSON + PNG annotées).
    - pages: liste d'index de pages (0-based). Si None, toutes les pages.
    """
    pdf_path = Path(pdf_path)
    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    all_tables: List[ExtractedTable] = []

    with pdfplumber.open(pdf_path) as pdf:
        page_indices = pages if pages is not None else list(range(len(pdf.pages)))
        for pi in page_indices:
            page = pdf.pages[pi]
            # Détection avec table_settings en mode lignes (lattice)
            table_objs = page.find_tables(table_settings=TABLE_SETTINGS)
            for ti, table_obj in enumerate(table_objs):
                raw = table_obj.extract()
                cleaned = _clean_table(raw)
                split_tables = _merge_adjacent_tables(_split_by_headers(cleaned))
                for _, tbl in enumerate(split_tables):
                    collapsed = _collapse_sparse_columns(tbl)
                    filtered = _drop_low_content_rows(collapsed)
                    if not filtered:
                        continue
                    all_tables.append(
                        ExtractedTable(
                            page_index=pi,
                            table_index=len(all_tables),
                            bbox=table_obj.bbox,
                            cells=filtered,
                        )
                    )

            if output_dir:
                image = page.to_image(resolution=resolution)
                bboxes = [t.bbox for t in table_objs]
                if bboxes:
                    image.draw_rects(bboxes, stroke="red", stroke_width=2)
                image.save(str(output_dir / f"page{pi + 1}_annotated.png"))

    if output_dir:
        json_path = output_dir / "tables.json"
        with json_path.open("w", encoding="utf-8") as fp:
            json.dump(
                [
                    {
                        "page_index": t.page_index,
                        "table_index": t.table_index,
                        "bbox": t.bbox,
                        "cells": t.cells,
                    }
                    for t in all_tables
                ],
                fp,
                ensure_ascii=False,
                indent=2,
            )

    return all_tables
