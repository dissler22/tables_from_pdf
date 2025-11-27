"""
Extracteur spécialisé pour les documents SDP (Sous-Détail de Prix).

Le format SDP a une structure spécifique :
- En-têtes fixes sur 2 lignes
- Ligne de formules (a, b, 1=axb, etc.)
- Corps avec 3 types de lignes (détail, sous-total, total) selon l'indentation
- Tableau récapitulatif (A + B)
- Prix final
"""

import pdfplumber
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import json


@dataclass
class SDPRow:
    """Représente une ligne du tableau SDP."""
    # Colonne 1: Description
    composantes_du_prix: str
    # Colonne 2: Unité
    unite: str
    # Colonne 3: Quantité (a)
    quantite: str
    # Colonne 4: Durée d'utilisation (b)
    duree_utilisation: str
    # Colonne 5: TOTAL (1=axb)
    total: str
    # Colonne 6: Main d'oeuvre : coût à l'unité (2)
    main_oeuvre_cout_unitaire: str
    # Colonne 7: Matériels et matières consommables : prix unitaire (3)
    materiels_prix_unitaire: str
    # Colonne 8: Prestations : prix unitaire (4)
    prestations_prix_unitaire: str
    # Colonne 9: MONTANT PART PROPRE (5=1x(2+3+4))
    montant_part_propre: str
    # Colonne 10: PART SOUS TRAITES FOURNITURES : prix unitaire (6)
    part_sous_traites_prix_unitaire: str
    # Colonne 11: PART SOUS TRAITES FOURNITURES : MONTANT (7=1x6)
    part_sous_traites_montant: str
    # Colonne 12: TOTAL GENERAL (8=5+7)
    total_general: str
    # Métadonnées
    row_type: str  # "detail", "subtotal", "total", "formula", "total_prix_secs"
    indent_level: int  # 0=none, 1=medium, 2=high


@dataclass
class SDPRecap:
    """Tableau récapitulatif A + B + Prix final."""
    # Partie A : Travaux propres
    total_5: str = ""  # TOTAL 5
    k1_pct: str = ""   # K1 Frais de chantier %
    k1_montant: str = ""  # K1 montant
    k2_pct: str = ""   # K2 Frais proportionnels %
    k2_montant: str = ""  # K2 montant
    k3_pct: str = ""   # K3 Aléas-Bénéfice %
    k3_montant: str = ""  # K3 montant
    total_a_pct: str = ""  # % Total A
    total_a: str = ""  # Total A
    
    # Partie B : Travaux sous traités et fournitures
    total_7: str = ""  # TOTAL 7
    k4_pct: str = ""   # K4 Frais de chantier %
    k4_montant: str = ""  # K4 montant
    k5_pct: str = ""   # K5 Frais proportionnels %
    k5_montant: str = ""  # K5 montant
    k6_pct: str = ""   # K6 Aléas-Bénéfice %
    k6_montant: str = ""  # K6 montant
    total_b_pct: str = ""  # % Total B
    total_b: str = ""  # Total B
    
    # Prix final
    prix_vente_ht: str = ""
    prix_arrondi: str = ""


@dataclass
class SDPPage:
    """Données extraites d'une page SDP."""
    page_number: int
    rows: List[SDPRow]
    recap: Optional[SDPRecap]
    raw_text_lines: List[str]


# Colonnes SDP avec positions X approximatives
# Format: (x_start, x_end, nom_colonne_interne, nom_affichage)
SDP_COLUMNS = [
    (0, 195, "composantes_du_prix", "COMPOSANTES DU PRIX (avec décomposition par sous détails élémentaires)"),
    (195, 225, "unite", "Unité"),
    (225, 275, "quantite", "Quantité (a)"),
    (275, 340, "duree_utilisation", "Durée d'utilisation (b)"),
    (340, 410, "total", "TOTAL (1=axb)"),
    (410, 475, "main_oeuvre_cout_unitaire", "Main d'oeuvre : coût à l'unité (2)"),
    (475, 545, "materiels_prix_unitaire", "Matériels et matières consommables : prix unitaire (3)"),
    (545, 600, "prestations_prix_unitaire", "Prestations : prix unitaire (4)"),
    (600, 660, "montant_part_propre", "MONTANT PART PROPRE (5=1x(2+3+4))"),
    (660, 720, "part_sous_traites_prix_unitaire", "PART SOUS TRAITES FOURNITURES : prix unitaire (6)"),
    (720, 780, "part_sous_traites_montant", "PART SOUS TRAITES FOURNITURES : MONTANT (7=1x6)"),
    (780, 850, "total_general", "TOTAL GENERAL (8=5+7)"),
]


class SDPExtractor:
    """Extracteur pour documents SDP."""
    
    def __init__(self):
        self.default_columns = SDP_COLUMNS
        self.page_columns = {}  # Colonnes calibrées par page
    
    def _calibrate_columns_from_formula_line(self, lines: List[Tuple[float, List[dict]]]) -> List[Tuple[int, int, str, str]]:
        """
        Calibre les colonnes en détectant la ligne de formules "a b 1=axb 2 3 4 5=..."
        """
        # Chercher la ligne contenant "1=axb" ou "a b"
        formula_words = None
        for _, line_words in lines:
            text = " ".join(w['text'] for w in line_words)
            if "1=axb" in text or ("a" in text and "b" in text and "2" in text and "3" in text):
                formula_words = sorted(line_words, key=lambda w: w['x0'])
                break
        
        if not formula_words:
            return self.default_columns
        
        # Extraire les positions des marqueurs de colonnes
        markers = {}
        for w in formula_words:
            text = w['text']
            x = w['x0']
            if text == 'a':
                markers['quantite'] = x
            elif text == 'b':
                markers['duree'] = x
            elif text == '1=axb':
                markers['total'] = x
            elif text == '2':
                markers['main_oeuvre'] = x
            elif text == '3':
                markers['materiels'] = x
            elif text == '4':
                markers['prestations'] = x
            elif text.startswith('5=') or text == '5':
                markers['part_propre'] = x
            elif text == '6':
                markers['sous_traites_px'] = x
            elif text == '7' or text.startswith('7='):
                markers['sous_traites_mt'] = x
            elif text == '8' or text.startswith('8='):
                markers['total_general'] = x
        
        if len(markers) < 4:
            return self.default_columns
        
        # Construire les colonnes calibrées
        # Description: de 0 jusqu'à un peu avant 'a'
        desc_end = markers.get('quantite', 250) - 30
        
        columns = [
            (0, desc_end, "composantes_du_prix", "COMPOSANTES DU PRIX"),
            (desc_end, desc_end + 30, "unite", "Unité"),
        ]
        
        # Colonnes numériques basées sur les marqueurs détectés
        # Les noms internes doivent correspondre à ceux de SDPRow
        col_order = ['quantite', 'duree_utilisation', 'total', 'main_oeuvre_cout_unitaire', 
                     'materiels_prix_unitaire', 'prestations_prix_unitaire', 'montant_part_propre', 
                     'part_sous_traites_prix_unitaire', 'part_sous_traites_montant', 'total_general']
        col_names = {
            'quantite': "Quantité (a)",
            'duree_utilisation': "Durée d'utilisation (b)", 
            'total': "TOTAL (1=axb)",
            'main_oeuvre_cout_unitaire': "Main d'oeuvre : coût à l'unité (2)",
            'materiels_prix_unitaire': "Matériels et matières consommables : prix unitaire (3)",
            'prestations_prix_unitaire': "Prestations : prix unitaire (4)",
            'montant_part_propre': "MONTANT PART PROPRE (5=1x(2+3+4))",
            'part_sous_traites_prix_unitaire': "PART SOUS TRAITES FOURNITURES : prix unitaire (6)",
            'part_sous_traites_montant': "PART SOUS TRAITES FOURNITURES : MONTANT (7=1x6)",
            'total_general': "TOTAL GENERAL (8=5+7)",
        }
        
        # Mapping des marqueurs vers les noms internes
        marker_to_col = {
            'quantite': 'quantite',
            'duree': 'duree_utilisation',
            'total': 'total',
            'main_oeuvre': 'main_oeuvre_cout_unitaire',
            'materiels': 'materiels_prix_unitaire',
            'prestations': 'prestations_prix_unitaire',
            'part_propre': 'montant_part_propre',
            'sous_traites_px': 'part_sous_traites_prix_unitaire',
            'sous_traites_mt': 'part_sous_traites_montant',
            'total_general': 'total_general',
        }
        
        # Convertir les marqueurs vers les noms internes
        converted_markers = {}
        for marker, x in markers.items():
            if marker in marker_to_col:
                converted_markers[marker_to_col[marker]] = x
        markers = converted_markers
        
        prev_x = desc_end + 30
        for i, col in enumerate(col_order):
            if col in markers:
                x_start = markers[col] - 25
                # Trouver la fin: soit le prochain marqueur, soit +60
                next_x = 850
                for next_col in col_order[i+1:]:
                    if next_col in markers:
                        next_x = markers[next_col] - 25
                        break
                x_end = min(next_x, markers[col] + 60)
                columns.append((x_start, x_end, col, col_names.get(col, col)))
                prev_x = x_end
        
        return columns
    
    def extract_page(self, pdf_path: Path, page_number: int) -> SDPPage:
        """
        Extrait les données d'une page SDP.
        
        Args:
            pdf_path: Chemin vers le PDF
            page_number: Numéro de page (0-based)
            
        Returns:
            SDPPage avec les données extraites
        """
        with pdfplumber.open(pdf_path) as pdf:
            if page_number >= len(pdf.pages):
                raise ValueError(f"Page {page_number} n'existe pas")
            
            page = pdf.pages[page_number]
            
            # Extraire les mots avec positions
            words = page.extract_words(x_tolerance=3, y_tolerance=3)
            
            # Grouper par ligne
            lines = self._group_by_lines(words)
            
            # Calibrer les colonnes sur cette page
            self.columns = self._calibrate_columns_from_formula_line(lines)
            
            # Parser les lignes
            rows, recap, raw_lines = self._parse_lines(lines)
            
            return SDPPage(
                page_number=page_number,
                rows=rows,
                recap=recap,
                raw_text_lines=raw_lines,
            )
    
    def _group_by_lines(self, words: List[dict]) -> List[Tuple[float, List[dict]]]:
        """Groupe les mots par ligne (position Y)."""
        lines = defaultdict(list)
        for w in words:
            y = round(w['top'] / 8) * 8  # Arrondir à 8px
            lines[y].append(w)
        
        # Trier par Y puis par X dans chaque ligne
        sorted_lines = []
        for y in sorted(lines.keys()):
            line_words = sorted(lines[y], key=lambda w: w['x0'])
            sorted_lines.append((y, line_words))
        
        return sorted_lines
    
    def _parse_lines(self, lines: List[Tuple[float, List[dict]]]) -> Tuple[List[SDPRow], Optional[SDPRecap], List[str]]:
        """Parse les lignes et extrait les données structurées."""
        rows = []
        recap = SDPRecap()
        raw_lines = []
        
        # Trouver le début du tableau (après la ligne "1=axb")
        table_start_idx = 0
        for i, (y, line_words) in enumerate(lines):
            text = " ".join(w['text'] for w in line_words)
            raw_lines.append(text)
            if "1=axb" in text or "1=ax" in text:
                table_start_idx = i + 1
                break
        
        # État du parsing
        in_main_table = True
        in_recap = False
        
        # Parser les lignes
        for y, line_words in lines[table_start_idx:]:
            text = " ".join(w['text'] for w in line_words)
            
            # Détecter TOTAL PRIX SECS (fin du tableau principal)
            if "TOTAL PRIX SECS" in text:
                # Extraire les totaux
                self._parse_total_prix_secs(line_words, recap)
                in_main_table = False
                in_recap = True
                continue
            
            # Détecter le début du récap
            if "A : Travaux" in text:
                in_main_table = False
                in_recap = True
                continue
            
            # Parser le récap
            if in_recap:
                self._parse_recap_line(text, recap)
                continue
            
            # Ligne de données normale (tableau principal)
            if in_main_table:
                row = self._parse_row(line_words)
                if row and row.composantes_du_prix:
                    rows.append(row)
        
        return rows, recap, raw_lines
    
    def _parse_recap_line(self, text: str, recap: SDPRecap) -> None:
        """Parse une ligne du tableau récapitulatif."""
        import re
        
        # TOTAL 5 et TOTAL 7
        if "TOTAL 5" in text:
            recap.total_5 = self._extract_amount(text, "TOTAL 5")
            recap.total_7 = self._extract_amount(text, "TOTAL 7")
        
        # K1 et K4 (Frais de chantier)
        elif "K1" in text and "Frais de chantier" in text:
            # Format: "K1 Frais de chantier, en % du total 5: 0,10 soit: 4 011,71€ K4..."
            recap.k1_pct = self._extract_pct_before_soit(text, first=True)
            recap.k1_montant = self._extract_amount_after(text, "soit:")
            recap.k4_pct = self._extract_pct_before_soit(text, first=False)
            recap.k4_montant = self._extract_amount_after_last(text, "soit:")
        
        # K2 et K5 (Frais proportionnels)
        elif "K2" in text and "Frais proportionnels" in text:
            recap.k2_pct = self._extract_pct_before_soit(text, first=True)
            recap.k2_montant = self._extract_amount_after(text, "soit:")
            recap.k5_pct = self._extract_pct_before_soit(text, first=False)
            recap.k5_montant = self._extract_amount_after_last(text, "soit:")
        
        # K3 et K6 (Aléas-Bénéfice)
        elif "K3" in text and ("Aléas" in text or "Aleas" in text):
            recap.k3_pct = self._extract_pct_before_soit(text, first=True)
            recap.k3_montant = self._extract_amount_after(text, "soit:")
            recap.k6_pct = self._extract_pct_before_soit(text, first=False)
            recap.k6_montant = self._extract_amount_after_last(text, "soit:")
        
        # Total A et Total B (format: "25% Total A 10 029,28€ 15% Total B 14 398,19")
        elif "Total A" in text or "Total B" in text:
            # Chercher pattern avec % avant Total
            match_a = re.search(r'(\d+)\s*%\s*Total\s*A\s*([\d\s]+,\d+)', text, re.IGNORECASE)
            if match_a:
                recap.total_a_pct = match_a.group(1) + "%"
                recap.total_a = self._clean_amount(match_a.group(2)) + " €"
            # Aussi chercher format "Total A XXX,XX €"
            elif "Total A" in text:
                match = re.search(r'Total\s*A\s*([\d\s]+,\d+)', text, re.IGNORECASE)
                if match:
                    recap.total_a = self._clean_amount(match.group(1)) + " €"
            
            match_b = re.search(r'(\d+)\s*%\s*Total\s*B\s*([\d\s]+,\d+)', text, re.IGNORECASE)
            if match_b:
                recap.total_b_pct = match_b.group(1) + "%"
                recap.total_b = self._clean_amount(match_b.group(2)) + " €"
            elif "Total B" in text:
                match = re.search(r'Total\s*B\s*([\d\s]+,\d+)', text, re.IGNORECASE)
                if match:
                    recap.total_b = self._clean_amount(match.group(1)) + " €"
        
        # Prix de vente HT (format: "PRIX DE VENTE HORS TAXES ( (A) + (B) ): XXX,XX Arrondi à: XXX,XX €")
        elif "PRIX DE VENTE" in text or "Arrondi" in text:
            amounts = re.findall(r'[\d\s]+,\d+\s*€?', text)
            if amounts:
                recap.prix_vente_ht = self._clean_amount(amounts[0]) + " €"
                if len(amounts) > 1:
                    recap.prix_arrondi = self._clean_amount(amounts[-1])
                    if not recap.prix_arrondi.endswith("€"):
                        recap.prix_arrondi += " €"
    
    def _extract_pct_before_soit(self, text: str, first: bool = True) -> str:
        """Extrait le pourcentage avant 'soit:' (premier ou dernier)."""
        import re
        # Chercher tous les patterns "X,XX soit:" ou "XX% soit:"
        parts = text.split("soit:")
        if first and len(parts) >= 1:
            before = parts[0]
        elif not first and len(parts) >= 2:
            before = parts[-2] if len(parts) > 2 else parts[0]
        else:
            return ""
        
        # Chercher le pourcentage ou la valeur décimale
        match = re.search(r'(\d+(?:,\d+)?)\s*%?\s*$', before.strip())
        if match:
            val = match.group(1)
            # Convertir 0,10 en 10%
            try:
                num = float(val.replace(',', '.'))
                if num < 1:
                    return f"{int(num * 100)}%"
                return f"{int(num)}%"
            except:
                return val + "%"
        return ""
    
    def _clean_amount(self, amount: str) -> str:
        """Nettoie un montant en supprimant les espaces internes."""
        import re
        if not amount:
            return ""
        # Supprimer tous les espaces autour de la virgule
        cleaned = re.sub(r'\s*,\s*', ',', amount)
        # Supprimer les espaces entre les chiffres (ex: "40 117" -> "40117")
        cleaned = re.sub(r'(\d)\s+(\d)', r'\1\2', cleaned)
        # S'assurer qu'il y a un espace avant € si présent
        cleaned = re.sub(r'(\d)€', r'\1 €', cleaned)
        return cleaned.strip()
    
    def _parse_total_prix_secs(self, line_words: List[dict], recap: SDPRecap) -> None:
        """Extrait les totaux de la ligne TOTAL PRIX SECS."""
        text = " ".join(w['text'] for w in line_words)
        import re
        # Chercher les montants dans le texte
        amounts = re.findall(r'[\d\s]+,\d+\s*€?', text)
        if len(amounts) >= 2:
            recap.total_5 = self._clean_amount(amounts[0])
            recap.total_7 = self._clean_amount(amounts[1])
    
    def _extract_amount(self, text: str, marker: str) -> str:
        """Extrait un montant après un marqueur."""
        import re
        idx = text.find(marker)
        if idx >= 0:
            after = text[idx + len(marker):]
            match = re.search(r'[\d\s]+,\d+\s*€?', after)
            if match:
                return self._clean_amount(match.group())
        return ""
    
    def _extract_amount_after(self, text: str, marker: str) -> str:
        """Extrait le premier montant après un marqueur."""
        import re
        idx = text.find(marker)
        if idx >= 0:
            after = text[idx + len(marker):]
            match = re.search(r'[\d\s]+,\d+\s*€?', after)
            if match:
                return self._clean_amount(match.group())
        return ""
    
    def _extract_amount_after_last(self, text: str, marker: str) -> str:
        """Extrait le dernier montant après la dernière occurrence du marqueur."""
        import re
        idx = text.rfind(marker)
        if idx >= 0:
            after = text[idx + len(marker):]
            match = re.search(r'[\d\s]+,\d+\s*€?', after)
            if match:
                return self._clean_amount(match.group())
        return ""
    
    def _extract_pct(self, text: str, after_marker: str) -> str:
        """Extrait un pourcentage juste avant un marqueur (ex: '10% soit:')."""
        import re
        idx = text.find(after_marker)
        if idx >= 0:
            before = text[:idx]
            # Chercher un pourcentage ou un nombre décimal (0,10 = 10%)
            match = re.search(r'(\d+(?:,\d+)?)\s*%?\s*$', before.strip())
            if match:
                val = match.group(1)
                # Convertir 0,10 en 10%
                if ',' in val and float(val.replace(',', '.')) < 1:
                    pct = int(float(val.replace(',', '.')) * 100)
                    return f"{pct}%"
                return val + "%"
        return ""
    
    def _extract_first_amount(self, text: str) -> str:
        """Extrait le premier montant du texte."""
        import re
        match = re.search(r'[\d\s]+,\d+\s*€?', text)
        return self._clean_amount(match.group()) if match else ""
    
    def _extract_last_amount(self, text: str) -> str:
        """Extrait le dernier montant du texte."""
        import re
        matches = re.findall(r'[\d\s]+,\d+\s*€?', text)
        return self._clean_amount(matches[-1]) if matches else ""
    
    def _group_words_by_proximity(self, line_words: List[dict], gap_threshold: float = 12.0) -> List[str]:
        """
        Groupe les mots par proximité X.
        Les mots proches (gap < threshold) forment un seul groupe/valeur.
        
        Returns:
            Liste de valeurs (groupes de mots) ordonnées de gauche à droite
        """
        if not line_words:
            return []
        
        # Trier par position X
        sorted_words = sorted(line_words, key=lambda w: w['x0'])
        
        groups = []
        current_group = [sorted_words[0]['text']]
        current_x1 = sorted_words[0]['x1']  # Position de fin du mot
        
        for word in sorted_words[1:]:
            gap = word['x0'] - current_x1  # Espace entre les mots
            
            # Le symbole € doit toujours être collé au nombre précédent
            if word['text'] == '€' and gap < 25:
                current_group.append(word['text'])
            elif gap < gap_threshold:
                # Mot proche -> même groupe
                current_group.append(word['text'])
            else:
                # Nouveau groupe
                groups.append(" ".join(current_group))
                current_group = [word['text']]
            
            current_x1 = word['x1']
        
        # Ajouter le dernier groupe
        groups.append(" ".join(current_group))
        
        # Post-traitement: fusionner "- €" isolés
        cleaned_groups = []
        i = 0
        while i < len(groups):
            g = groups[i]
            # Fusionner "-" suivi de "€"
            if g == '-' and i + 1 < len(groups) and groups[i + 1] == '€':
                cleaned_groups.append('- €')
                i += 2
            # Supprimer les "€" isolés (déjà attachés aux nombres)
            elif g == '€':
                i += 1
            else:
                cleaned_groups.append(g)
                i += 1
        
        return cleaned_groups
    
    def _parse_row(self, line_words: List[dict], row_type: str = "detail") -> Optional[SDPRow]:
        """Parse une ligne en SDPRow avec approche hybride position X + proximité."""
        if not line_words:
            return None
        
        # Détecter l'indentation basée sur la position X du premier mot
        first_x = min(w['x0'] for w in line_words)
        if first_x > 50:
            indent = 2  # high (detail)
        elif first_x > 30:
            indent = 1  # medium (subtotal)
        else:
            indent = 0  # none (total)
        
        # Grouper les mots par proximité et garder leur position X centrale
        groups_with_pos = self._group_words_with_positions(line_words)
        
        # Initialiser avec des valeurs vides
        col_values = {col[2]: "" for col in self.columns}
        
        if not groups_with_pos:
            return None
        
        # Pour chaque groupe, trouver la colonne la plus proche
        for x_center, text in groups_with_pos:
            # Trouver la colonne dont le centre est le plus proche
            best_col = None
            best_dist = float('inf')
            
            for x_start, x_end, col_name, _ in self.columns:
                col_center = (x_start + x_end) / 2
                dist = abs(x_center - col_center)
                
                # Vérifier aussi si le groupe est dans la plage de la colonne
                in_range = x_start - 30 <= x_center <= x_end + 30
                
                if in_range and dist < best_dist:
                    best_dist = dist
                    best_col = col_name
            
            if best_col:
                if col_values[best_col]:
                    col_values[best_col] += " " + text
                else:
                    col_values[best_col] = text
        
        return SDPRow(
            composantes_du_prix=col_values["composantes_du_prix"].strip(),
            unite=col_values["unite"].strip(),
            quantite=col_values["quantite"].strip(),
            duree_utilisation=col_values["duree_utilisation"].strip(),
            total=col_values["total"].strip(),
            main_oeuvre_cout_unitaire=col_values["main_oeuvre_cout_unitaire"].strip(),
            materiels_prix_unitaire=col_values["materiels_prix_unitaire"].strip(),
            prestations_prix_unitaire=col_values["prestations_prix_unitaire"].strip(),
            montant_part_propre=col_values["montant_part_propre"].strip(),
            part_sous_traites_prix_unitaire=col_values["part_sous_traites_prix_unitaire"].strip(),
            part_sous_traites_montant=col_values["part_sous_traites_montant"].strip(),
            total_general=col_values["total_general"].strip(),
            row_type=row_type,
            indent_level=indent,
        )
    
    def _group_words_with_positions(self, line_words: List[dict], gap_threshold: float = 12.0) -> List[Tuple[float, str]]:
        """
        Groupe les mots par proximité et retourne (position_x_centre, texte).
        """
        if not line_words:
            return []
        
        # Trier par position X
        sorted_words = sorted(line_words, key=lambda w: w['x0'])
        
        groups = []
        current_texts = [sorted_words[0]['text']]
        current_x0 = sorted_words[0]['x0']
        current_x1 = sorted_words[0]['x1']
        
        for word in sorted_words[1:]:
            gap = word['x0'] - current_x1
            
            # Le symbole € doit toujours être collé au nombre précédent
            if word['text'] == '€' and gap < 25:
                current_texts.append(word['text'])
                current_x1 = word['x1']
            elif gap < gap_threshold:
                current_texts.append(word['text'])
                current_x1 = word['x1']
            else:
                # Nouveau groupe - sauvegarder l'ancien
                x_center = (current_x0 + current_x1) / 2
                groups.append((x_center, " ".join(current_texts)))
                current_texts = [word['text']]
                current_x0 = word['x0']
                current_x1 = word['x1']
        
        # Ajouter le dernier groupe
        x_center = (current_x0 + current_x1) / 2
        groups.append((x_center, " ".join(current_texts)))
        
        # Post-traitement: fusionner "- €" isolés et supprimer € isolés
        cleaned = []
        i = 0
        while i < len(groups):
            x, text = groups[i]
            if text == '-' and i + 1 < len(groups) and groups[i + 1][1] == '€':
                cleaned.append((x, '- €'))
                i += 2
            elif text == '€':
                i += 1
            else:
                cleaned.append((x, text))
                i += 1
        
        # Post-traitement: séparer les unités fusionnées avec la description
        # Si le dernier mot d'un groupe est une unité, le séparer
        final_groups = []
        units = {'m', 'm2', 'm3', 'ml', 'h', 't', 'j', 'u', 'kg', 'l', 'ens', 'forf', 'km'}
        
        for x, text in cleaned:
            words = text.split()
            if len(words) > 1 and words[-1].lower() in units:
                # Séparer l'unité
                desc = " ".join(words[:-1])
                unit = words[-1]
                # La description garde la position d'origine
                final_groups.append((x - 20, desc))
                # L'unité a une position légèrement après
                final_groups.append((x + 20, unit))
            else:
                final_groups.append((x, text))
        
        return final_groups
    
    def _is_unit_or_number(self, text: str) -> bool:
        """Vérifie si le texte est une unité ou un nombre."""
        import re
        text = text.strip()
        
        # Unités courantes
        units = {'m', 'm2', 'm3', 'ml', 'h', 't', 'j', 'u', 'kg', 'l', 'ens', 'forf', 'km'}
        if text.lower() in units:
            return True
        
        # Nombre (avec ou sans décimales, espaces comme séparateurs de milliers)
        if re.match(r'^[\d\s]+([,\.]\d+)?(\s*€)?$', text):
            return True
        
        # Tiret seul (valeur vide/nulle)
        if text == '-' or text == '- €':
            return True
        
        return False
    
    def extract_all_pages(self, pdf_path: Path, pages: Optional[List[int]] = None) -> List[SDPPage]:
        """Extrait toutes les pages SDP d'un PDF."""
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
        
        if pages is None:
            pages = list(range(total_pages))
        
        results = []
        for page_num in pages:
            try:
                page_data = self.extract_page(pdf_path, page_num)
                results.append(page_data)
            except Exception as e:
                print(f"Erreur page {page_num + 1}: {e}")
        
        return results
    
    def to_dict(self, page: SDPPage) -> dict:
        """Convertit une SDPPage en dictionnaire."""
        recap_dict = None
        if page.recap:
            recap_dict = {
                "A_Travaux_propres": {
                    "TOTAL 5": page.recap.total_5,
                    "K1_Frais_chantier": {"pct": page.recap.k1_pct, "montant": page.recap.k1_montant},
                    "K2_Frais_proportionnels": {"pct": page.recap.k2_pct, "montant": page.recap.k2_montant},
                    "K3_Aleas_Benefice": {"pct": page.recap.k3_pct, "montant": page.recap.k3_montant},
                    "Total_A": {"pct": page.recap.total_a_pct, "montant": page.recap.total_a},
                },
                "B_Travaux_sous_traites": {
                    "TOTAL 7": page.recap.total_7,
                    "K4_Frais_chantier": {"pct": page.recap.k4_pct, "montant": page.recap.k4_montant},
                    "K5_Frais_proportionnels": {"pct": page.recap.k5_pct, "montant": page.recap.k5_montant},
                    "K6_Aleas_Benefice": {"pct": page.recap.k6_pct, "montant": page.recap.k6_montant},
                    "Total_B": {"pct": page.recap.total_b_pct, "montant": page.recap.total_b},
                },
                "PRIX_DE_VENTE_HT": page.recap.prix_vente_ht,
                "PRIX_ARRONDI": page.recap.prix_arrondi,
            }
        
        return {
            "page_number": page.page_number,
            "num_rows": len(page.rows),
            "rows": [
                {
                    "COMPOSANTES DU PRIX": r.composantes_du_prix,
                    "Unité": r.unite,
                    "Quantité (a)": r.quantite,
                    "Durée d'utilisation (b)": r.duree_utilisation,
                    "TOTAL (1=axb)": r.total,
                    "Main d'oeuvre : coût à l'unité (2)": r.main_oeuvre_cout_unitaire,
                    "Matériels et matières consommables : prix unitaire (3)": r.materiels_prix_unitaire,
                    "Prestations : prix unitaire (4)": r.prestations_prix_unitaire,
                    "MONTANT PART PROPRE (5=1x(2+3+4))": r.montant_part_propre,
                    "PART SOUS TRAITES FOURNITURES : prix unitaire (6)": r.part_sous_traites_prix_unitaire,
                    "PART SOUS TRAITES FOURNITURES : MONTANT (7=1x6)": r.part_sous_traites_montant,
                    "TOTAL GENERAL (8=5+7)": r.total_general,
                    "row_type": r.row_type,
                    "indent_level": r.indent_level,
                }
                for r in page.rows
            ],
            "recap": recap_dict,
        }
    
    def to_flat_rows(self, page: SDPPage) -> List[List[str]]:
        """Convertit en format liste de listes (comme raw_data)."""
        # En-têtes avec les vrais noms du document SDP
        headers = [
            "COMPOSANTES DU PRIX (avec décomposition par sous détails élémentaires)",
            "Unité",
            "Quantité (a)",
            "Durée d'utilisation (b)",
            "TOTAL (1=axb)",
            "Main d'oeuvre : coût à l'unité (2)",
            "Matériels et matières consommables : prix unitaire (3)",
            "Prestations : prix unitaire (4)",
            "MONTANT PART PROPRE (5=1x(2+3+4))",
            "PART SOUS TRAITES FOURNITURES : prix unitaire (6)",
            "PART SOUS TRAITES FOURNITURES : MONTANT (7=1x6)",
            "TOTAL GENERAL (8=5+7)",
            "Type ligne",
            "Niveau indentation"
        ]
        
        rows = [headers]
        for r in page.rows:
            rows.append([
                r.composantes_du_prix,
                r.unite,
                r.quantite,
                r.duree_utilisation,
                r.total,
                r.main_oeuvre_cout_unitaire,
                r.materiels_prix_unitaire,
                r.prestations_prix_unitaire,
                r.montant_part_propre,
                r.part_sous_traites_prix_unitaire,
                r.part_sous_traites_montant,
                r.total_general,
                r.row_type,
                str(r.indent_level),
            ])
        
        return rows

