# 🚀 Quick Start - Extracteur de tableaux PDF

## ⚡ Installation (Windows)

```powershell
# Créer l'environnement
python -m venv .venv_win
.\.venv_win\Scripts\Activate.ps1

# Dépendances essentielles
pip install pdfplumber pdf2image Pillow

# Optionnel (pour DETR / scans)
pip install torch transformers opencv-python
```

## 📋 Structure du projet

```
tables_from_pdf/
├── src/table_extractor/      # Code source
│   ├── pipeline.py           # Pipeline principal
│   ├── extractor.py          # PdfPlumberExtractor
│   ├── sdp_extractor.py      # Extracteur SDP
│   └── postprocess.py        # Nettoyage
├── data/
│   ├── upload/               # PDFs à traiter
│   └── output/               # Résultats
└── tests/goldens/            # Fichiers de référence
```

## 🎯 Extraction ESC (Journaux de chantier)

```python
from pathlib import Path
import sys
sys.path.insert(0, 'src')

from table_extractor import TableExtractionPipeline, PipelineConfig, ExtractionMode

# Configuration
config = PipelineConfig(
    mode=ExtractionMode.ACCURATE,
    pages=[1, 2, 3],  # Pages 2, 3, 4 (0-indexed)
    output_format=["json", "csv"],
)

# Extraction
pipeline = TableExtractionPipeline(config)
result = pipeline.extract(
    "data/upload/ESC_A57_000675_EXE_GEN_0-0000_SS_JDC_5108_A_Journaux_de_chantier_2023_S01.pdf",
    output_dir="data/output/ESC_test"
)

print(f"✅ {len(result.tables)} tables extraites")
```

## 🎯 Extraction SDP (Sous-Détail de Prix)

```python
from pathlib import Path
import sys
sys.path.insert(0, 'src')

from table_extractor.sdp_extractor import SDPExtractor
import json

# Extraction
extractor = SDPExtractor()
page = extractor.extract_page(
    Path("data/upload/SDP Série D Ind A.pdf"),
    page_number=0  # Page 1
)

# Afficher les données
print(f"📊 {len(page.rows)} lignes extraites")

for row in page.rows[:3]:
    print(f"  - {row.composantes_du_prix}: {row.montant_part_propre}")

# Récapitulatif
if page.recap:
    print(f"\n💰 Récap:")
    print(f"  TOTAL 5: {page.recap.total_5}")
    print(f"  K1 ({page.recap.k1_pct}): {page.recap.k1_montant}")
    print(f"  PRIX HT: {page.recap.prix_vente_ht}")

# Sauvegarder en JSON
output = extractor.to_dict(page)
with open("data/output/sdp_page1.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
```

## 📊 Formats de sortie

### JSON (tables.json)
```json
{
  "tables": [
    {
      "page": 2,
      "table_index": 0,
      "raw_data": [
        ["Col1", "Col2", "Col3"],
        ["Val1", "Val2", "Val3"]
      ]
    }
  ]
}
```

### CSV (page2_table0.csv)
```csv
Col1,Col2,Col3
Val1,Val2,Val3
```

## 🔧 Options utiles

| Option | Description | Défaut |
|--------|-------------|--------|
| `mode` | FAST, ACCURATE, HYBRID | ACCURATE |
| `pages` | Liste de pages (0-indexed) | Toutes |
| `dpi` | Résolution rendu | 200 |
| `ocr_engine` | tesseract, paddleocr, None | None |
| `save_images` | Sauvegarder images annotées | True |

## 🐛 Dépannage

| Problème | Solution |
|----------|----------|
| `ModuleNotFoundError: pdfplumber` | `pip install pdfplumber` |
| `No tables found` | Vérifier que le PDF contient du texte extractible |
| `Colonnes décalées (SDP)` | Normal, calibration par page |
| `torch not found` | Installer uniquement si scans: `pip install torch` |

## 📚 Voir aussi

- `docs/PRD.md` - Vision produit
- `docs/features/extraction_v2_pipeline.md` - Architecture détaillée
- `tests/goldens/` - Fichiers de référence
