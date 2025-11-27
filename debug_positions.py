"""Debug positions X dans le PDF."""
import pdfplumber
from pathlib import Path

pdf_path = Path('data/upload/SDP Série D Ind A.pdf')

with pdfplumber.open(pdf_path) as pdf:
    # Page 1 (référence)
    page1 = pdf.pages[0]
    words1 = page1.extract_words(x_tolerance=3, y_tolerance=3)
    
    # Page 18
    page18 = pdf.pages[17]
    words18 = page18.extract_words(x_tolerance=3, y_tolerance=3)

print("="*80)
print("PAGE 1 - Positions X des premiers éléments de chaque ligne")
print("="*80)

# Grouper par Y
from collections import defaultdict
lines1 = defaultdict(list)
for w in words1:
    y = round(w['top'] / 5) * 5  # Arrondir pour grouper
    lines1[y].append(w)

# Afficher les lignes avec des données
count = 0
for y in sorted(lines1.keys()):
    line_words = sorted(lines1[y], key=lambda w: w['x0'])
    text = " ".join(w['text'][:20] for w in line_words[:8])
    if any(c.isdigit() for c in text) and len(line_words) > 3:
        x_positions = [f"{w['x0']:.0f}" for w in line_words[:8]]
        print(f"Y={y}: X=[{', '.join(x_positions)}]")
        print(f"       {text[:80]}")
        count += 1
        if count > 5:
            break

print("\n" + "="*80)
print("PAGE 18 - Positions X des premiers éléments de chaque ligne")
print("="*80)

lines18 = defaultdict(list)
for w in words18:
    y = round(w['top'] / 5) * 5
    lines18[y].append(w)

count = 0
for y in sorted(lines18.keys()):
    line_words = sorted(lines18[y], key=lambda w: w['x0'])
    text = " ".join(w['text'][:20] for w in line_words[:8])
    if any(c.isdigit() for c in text) and len(line_words) > 3:
        x_positions = [f"{w['x0']:.0f}" for w in line_words[:8]]
        print(f"Y={y}: X=[{', '.join(x_positions)}]")
        print(f"       {text[:80]}")
        count += 1
        if count > 5:
            break

print("\n" + "="*80)
print("COMPARAISON des plages X")
print("="*80)
print("\nColonnes définies actuellement:")
print("  composantes_du_prix:     0-195")
print("  unite:                 195-225")
print("  quantite:              225-275")
print("  duree:                 275-340")
print("  total:                 340-410")
print("  main_oeuvre:           410-475")
print("  materiels:             475-545")
print("  prestations:           545-600")
print("  part_propre:           600-660")
print("  sous_traites_px:       660-720")
print("  sous_traites_mt:       720-780")
print("  total_general:         780-850")

