"""Test robustesse sur pages 1, 18, 19."""
import sys
sys.path.insert(0, 'src')
from pathlib import Path
import json

from table_extractor.sdp_extractor import SDPExtractor

pdf_path = Path('data/upload/SDP Série D Ind A.pdf')
output_dir = Path('data/output/SDP_full')

extractor = SDPExtractor()

for page_idx in [0, 17, 18]:  # Pages 1, 18, 19
    page_data = extractor.extract_page(pdf_path, page_number=page_idx)
    
    print(f"\n{'='*80}")
    print(f"PAGE {page_idx + 1} - {len(page_data.rows)} lignes")
    print(f"{'='*80}")
    
    # Afficher 2 lignes
    for i, r in enumerate(page_data.rows[:2]):
        print(f"\n--- {r.composantes_du_prix[:50]} ---")
        print(f"  Unite={r.unite}  Qte={r.quantite}  Total={r.total}")
        print(f"  Main={r.main_oeuvre_cout_unitaire}  Mat={r.materiels_prix_unitaire}")
        print(f"  PartPropre={r.montant_part_propre}  SousTraitMt={r.part_sous_traites_montant}  TotalGen={r.total_general}")
    
    # Sauvegarder
    result = extractor.to_dict(page_data)
    json_path = output_dir / f'page{page_idx + 1}_fixed.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

print("\n\n-> Fichiers sauvegardés dans data/output/SDP_full/")

