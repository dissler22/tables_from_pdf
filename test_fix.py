"""Test fix colonnes SDP."""
import sys
sys.path.insert(0, 'src')
from pathlib import Path
import json

from table_extractor.sdp_extractor import SDPExtractor

pdf_path = Path('data/upload/SDP Série D Ind A.pdf')
output_dir = Path('data/output/SDP_full')

extractor = SDPExtractor()

print("="*80)
print("TEST FIX COLONNES - PAGES 18-19")
print("="*80)

for page_idx in [17, 18]:
    page_data = extractor.extract_page(pdf_path, page_number=page_idx)
    
    print(f"\n{'='*80}")
    print(f"PAGE {page_idx + 1} - {len(page_data.rows)} lignes")
    print(f"{'='*80}")
    
    # Afficher quelques lignes avec toutes les colonnes
    for i, r in enumerate(page_data.rows[:5]):
        print(f"\n--- Ligne {i+1}: {r.composantes_du_prix[:40]} ---")
        print(f"  Unité:        [{r.unite}]")
        print(f"  Quantité:     [{r.quantite}]")
        print(f"  Durée:        [{r.duree_utilisation}]")
        print(f"  TOTAL:        [{r.total}]")
        print(f"  Main oeuvre:  [{r.main_oeuvre_cout_unitaire}]")
        print(f"  Matériels:    [{r.materiels_prix_unitaire}]")
        print(f"  Prestations:  [{r.prestations_prix_unitaire}]")
        print(f"  Part propre:  [{r.montant_part_propre}]")
        print(f"  Sous-trait px:[{r.part_sous_traites_prix_unitaire}]")
        print(f"  Sous-trait mt:[{r.part_sous_traites_montant}]")
        print(f"  TOTAL GEN:    [{r.total_general}]")
    
    # Sauvegarder
    result = extractor.to_dict(page_data)
    json_path = output_dir / f'page{page_idx + 1}_fixed.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n-> {json_path}")

