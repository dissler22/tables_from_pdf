"""
Module de post-traitement des tableaux extraits.

Applique des règles de nettoyage et de normalisation après l'extraction brute.
Inclut la fusion automatique des tableaux multi-pages.
"""

from typing import List, Optional, Callable
import re

from .utils import ExtractedTable, TableCell, BoundingBox


# Marqueurs génériques d'un header de page (pas d'en-têtes de colonnes)
# Ces mots indiquent un header de document, pas des colonnes de tableau
PAGE_HEADER_MARKERS = [
    "maître d'œuvre",
    "maître d'ouvrage",
    "client",
    "projet",
    "document",
    "référence",
    "indice",
    "page",
]


def clean_empty_rows(table: ExtractedTable, threshold: float = 0.95) -> ExtractedTable:
    """
    Supprime les lignes quasi-vides (plus de threshold% de cellules vides).
    
    Note: threshold=0.95 pour garder les lignes avec au moins 1 cellule non vide
    (comme les jours fériés avec juste la date).
    """
    if not table.raw_data:
        return table
    
    cleaned_rows = []
    for row in table.raw_data:
        empty_count = sum(1 for cell in row if not cell or not cell.strip())
        # Garder la ligne si elle a au moins une cellule non vide
        if empty_count / len(row) < threshold:
            cleaned_rows.append(row)
    
    return _rebuild_table(table, cleaned_rows)


def clean_footer_rows(table: ExtractedTable, footer_markers: List[str] = None) -> ExtractedTable:
    """
    Supprime les lignes de pied de page (événements marquants, visa, etc.)
    """
    if not table.raw_data:
        return table
    
    footer_markers = footer_markers or [
        "événements marquants",
        "evénements marquants", 
        "visa",
        "date :",
    ]
    
    cleaned_rows = []
    for row in table.raw_data:
        # Vérifier si c'est une ligne de footer
        is_footer = False
        for cell in row:
            if cell:
                cell_lower = cell.lower()
                for marker in footer_markers:
                    if marker in cell_lower:
                        is_footer = True
                        break
            if is_footer:
                break
        
        if not is_footer:
            cleaned_rows.append(row)
    
    return _rebuild_table(table, cleaned_rows)


def clean_repeated_headers(table: ExtractedTable) -> ExtractedTable:
    """
    Détecte et nettoie les lignes qui répètent les en-têtes.
    
    Typiquement pour les jours fériés/vides où le PDF contient les en-têtes
    répétés au lieu de cellules vides.
    """
    if not table.raw_data or len(table.raw_data) < 2:
        return table
    
    headers = table.raw_data[0]
    cleaned_rows = [headers]
    
    for row in table.raw_data[1:]:
        if len(row) != len(headers):
            cleaned_rows.append(row)
            continue
        
        # Vérifier si cette ligne contient des en-têtes répétés
        # Indicateur 1: la dernière colonne est "Colonne2" ou non-numérique
        last_cell = row[-1] if row else ""
        last_is_invalid = last_cell in ("Colonne2", None, "") or (
            last_cell and not last_cell.strip().replace(".", "").isdigit()
        )
        
        # Indicateur 2: les cellules intermédiaires ne contiennent pas "N x "
        has_personnel = False
        for cell in row[1:-1]:
            if cell and re.search(r'\d+\s*x\s+', cell):
                has_personnel = True
                break
        
        if last_is_invalid and not has_personnel:
            # C'est une ligne vide/férié - la nettoyer
            first_cell = row[0] if row else ""
            new_row = [first_cell] + [""] * (len(headers) - 2) + ["0"]
            cleaned_rows.append(new_row)
        else:
            cleaned_rows.append(row)
    
    return _rebuild_table(table, cleaned_rows)


def limit_rows(table: ExtractedTable, max_rows: int) -> ExtractedTable:
    """
    Limite le nombre de lignes du tableau.
    """
    if not table.raw_data or len(table.raw_data) <= max_rows:
        return table
    
    return _rebuild_table(table, table.raw_data[:max_rows])


def apply_postprocessing(
    table: ExtractedTable,
    processors: List[Callable[[ExtractedTable], ExtractedTable]] = None,
) -> ExtractedTable:
    """
    Applique une chaîne de post-processeurs au tableau.
    
    Args:
        table: Tableau à traiter
        processors: Liste de fonctions de traitement (ordre d'application)
        
    Returns:
        Tableau traité
    """
    if processors is None:
        # Chaîne par défaut
        processors = [
            clean_repeated_headers,
            clean_footer_rows,
            clean_empty_rows,
        ]
    
    result = table
    for processor in processors:
        result = processor(result)
    
    return result


def _rebuild_table(original: ExtractedTable, new_raw_data: List[List[str]]) -> ExtractedTable:
    """Reconstruit un ExtractedTable avec de nouvelles données."""
    cells = []
    for row_idx, row in enumerate(new_raw_data):
        for col_idx, content in enumerate(row):
            cells.append(TableCell(
                row=row_idx,
                col=col_idx,
                content=content or "",
            ))
    
    return ExtractedTable(
        page_number=original.page_number,
        table_index=original.table_index,
        bbox=original.bbox,
        cells=cells,
        num_rows=len(new_raw_data),
        num_cols=len(new_raw_data[0]) if new_raw_data else 0,
        raw_data=new_raw_data,
    )


def _is_page_header_row(row: List[str]) -> bool:
    """
    Détecte si une ligne est un header de page (pas des en-têtes de colonnes).
    
    Critère STRICT : la première cellule doit contenir un texte très long
    avec plusieurs retours à la ligne (typique d'un cartouche de document).
    """
    if not row or not row[0]:
        return False
    
    first_cell = row[0]
    
    # SEUL critère fiable : texte très long (>100 chars) avec plusieurs \n
    # C'est typiquement un cartouche "Entreprise - Projet - Maître d'oeuvre..."
    newline_count = first_cell.count("\n")
    if len(first_cell) > 100 and newline_count >= 3:
        return True
    
    return False


def _is_continuation_table(table: ExtractedTable) -> bool:
    """
    Détecte si un tableau est une continuation du précédent (pas d'en-têtes propres).
    
    Logique : on cherche si la première ligne contient des en-têtes de colonnes.
    Si NON → c'est une continuation.
    
    En-têtes typiques ESC : jours de la semaine, "Personnel", "Effectif", etc.
    """
    if not table.raw_data:
        return False
    
    first_row = table.raw_data[0]
    
    # Critère 1: Header de page (cartouche long) → continuation
    if _is_page_header_row(first_row):
        return True
    
    # Critère 2: Première cellule vide → continuation
    if not first_row[0] or first_row[0].strip() == "":
        return True
    
    # Critère 3: Chercher des marqueurs d'en-têtes de colonnes
    # Si on en trouve → ce n'est PAS une continuation
    header_markers = [
        "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche",
        "personnel", "effectif", "observations", "date", "total",
        "janvier", "février", "mars", "avril", "mai", "juin",
        "juillet", "août", "septembre", "octobre", "novembre", "décembre",
    ]
    
    row_text = " ".join(str(cell).lower() for cell in first_row if cell)
    
    # Si on trouve au moins 2 marqueurs d'en-têtes → c'est un vrai tableau avec en-têtes
    markers_found = sum(1 for m in header_markers if m in row_text)
    if markers_found >= 2:
        return False  # Pas une continuation, a ses propres en-têtes
    
    # Critère 4: Si la première ligne contient des données numériques → continuation
    # (les en-têtes sont rarement des nombres)
    numeric_cells = sum(1 for cell in first_row if cell and _looks_like_data(cell))
    if numeric_cells >= len(first_row) * 0.5:
        return True  # Plus de la moitié des cellules sont des données → continuation
    
    return False


def _looks_like_data(text: str) -> bool:
    """Vérifie si un texte ressemble à une donnée (nombre, date, etc.)."""
    if not text:
        return False
    text = text.strip()
    
    # Nombre (entier ou décimal)
    if re.match(r'^[\d\s.,]+$', text):
        return True
    
    # Date format JJ/MM ou JJ/MM/YYYY
    if re.match(r'^\d{1,2}/\d{1,2}(/\d{2,4})?$', text):
        return True
    
    # "N x Personnel" format
    if re.match(r'^\d+\s*x\s+', text):
        return True
    
    return False


def merge_multipage_tables(tables: List[ExtractedTable]) -> List[ExtractedTable]:
    """
    Fusionne les tableaux qui s'étendent sur 2 pages (max).
    
    Logique : on part de la FIN de la liste.
    Si un tableau n'a pas d'en-têtes reconnaissables, c'est une continuation
    de la page précédente.
    
    Note: Un tableau ne fait JAMAIS plus de 2 pages.
    
    Args:
        tables: Liste des tableaux extraits (triés par page)
        
    Returns:
        Liste des tableaux après fusion
    """
    if not tables or len(tables) <= 1:
        return tables
    
    # Trier par page puis par index de tableau
    sorted_tables = sorted(tables, key=lambda t: (t.page_number, t.table_index))
    
    # Parcourir de la fin vers le début
    merged = []
    skip_next = False
    
    for i in range(len(sorted_tables) - 1, -1, -1):
        if skip_next:
            skip_next = False
            continue
        
        table = sorted_tables[i]
        
        # Vérifier si ce tableau n'a PAS d'en-têtes (= continuation)
        if i > 0 and _is_continuation_table(table):
            prev_table = sorted_tables[i - 1]
            
            # Vérifier que c'est bien la page suivante et même nombre de colonnes
            is_valid_continuation = (
                table.page_number == prev_table.page_number + 1 and
                table.num_cols == prev_table.num_cols
            )
            
            if is_valid_continuation:
                # Fusionner: prev_table + table
                fused = _merge_two_tables(prev_table, table)
                merged.insert(0, fused)
                skip_next = True  # Sauter prev_table car déjà fusionné
                continue
        
        # Pas de fusion, garder le tableau tel quel
        merged.insert(0, table)
    
    return merged


def _merge_two_tables(table1: ExtractedTable, table2: ExtractedTable) -> ExtractedTable:
    """
    Fusionne deux tableaux consécutifs.
    
    Garde les en-têtes de table1 et ajoute les données de table2
    (en ignorant le header de page de table2).
    """
    if not table1.raw_data:
        return table2
    if not table2.raw_data:
        return table1
    
    # Garder les données de table1
    merged_data = list(table1.raw_data)
    
    # Ajouter les données de table2 (sans le header de page)
    for row in table2.raw_data:
        # Ignorer les headers de page et les lignes vides de début
        if _is_page_header_row(row):
            continue
        # Ignorer les lignes quasi-vides (juste "0" à la fin)
        if all(not c or c.strip() == "" or c.strip() == "0" for c in row):
            continue
        merged_data.append(row)
    
    # Créer le tableau fusionné
    cells = []
    for row_idx, row in enumerate(merged_data):
        for col_idx, content in enumerate(row):
            cells.append(TableCell(
                row=row_idx,
                col=col_idx,
                content=content or "",
            ))
    
    # Étendre la bbox pour couvrir les deux pages
    merged_bbox = BoundingBox(
        x1=min(table1.bbox.x1, table2.bbox.x1),
        y1=table1.bbox.y1,  # Garder le haut de la première page
        x2=max(table1.bbox.x2, table2.bbox.x2),
        y2=table2.bbox.y2,  # Garder le bas de la dernière page
    )
    
    return ExtractedTable(
        page_number=table1.page_number,  # Garder la page de début
        table_index=table1.table_index,
        bbox=merged_bbox,
        cells=cells,
        num_rows=len(merged_data),
        num_cols=len(merged_data[0]) if merged_data else 0,
        raw_data=merged_data,
    )

