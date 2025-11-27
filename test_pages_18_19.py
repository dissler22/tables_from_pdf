"""Test robustesse SDP sur 2 pages (18-19)."""
import sys
sys.path.insert(0, 'src')
from pathlib import Path
import json

from table_extractor.sdp_extractor import SDPExtractor

pdf_path = Path('data/upload/SDP Série D Ind A.pdf')
output_dir = Path('data/output/SDP_full')

extractor = SDPExtractor()

print("="*70)
print("TEST ROBUSTESSE SDP - PAGES 18-19")
print("="*70)

# Extraire pages 18 et 19 (index 17 et 18)
for page_idx in [17, 18]:
    page_data = extractor.extract_page(pdf_path, page_number=page_idx)
    
    print(f"\n{'='*70}")
    print(f"PAGE {page_idx + 1}")
    print(f"{'='*70}")
    print(f"Lignes de données: {len(page_data.rows)}")
    
    # Afficher les premières et dernières lignes
    if page_data.rows:
        print("\nPremières lignes:")
        for i, r in enumerate(page_data.rows[:3]):
            print(f"  {i+1}. [{r.row_type}] {r.composantes_du_prix[:50]}")
        
        if len(page_data.rows) > 3:
            print("  ...")
            print("\nDernières lignes:")
            for i, r in enumerate(page_data.rows[-3:]):
                idx = len(page_data.rows) - 3 + i + 1
                print(f"  {idx}. [{r.row_type}] {r.composantes_du_prix[:50]}")
    
    # Afficher le récap si présent
    if page_data.recap:
        r = page_data.recap
        has_recap = any([r.total_5, r.k1_montant, r.total_a, r.prix_vente_ht])
        if has_recap:
            print("\nRÉCAP DÉTECTÉ:")
            if r.total_5:
                print(f"  TOTAL 5: {r.total_5}")
            if r.total_7:
                print(f"  TOTAL 7: {r.total_7}")
            if r.prix_vente_ht:
                print(f"  PRIX DE VENTE HT: {r.prix_vente_ht}")
        else:
            print("\n[Pas de récap sur cette page]")
    else:
        print("\n[Pas de récap sur cette page]")

# Sauvegarder les détails
for page_idx in [17, 18]:
    page_data = extractor.extract_page(pdf_path, page_number=page_idx)
    result = extractor.to_dict(page_data)
    json_path = output_dir / f'page{page_idx + 1}_test.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n-> {json_path}")

