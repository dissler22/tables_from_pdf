# 🚀 Guide de démarrage rapide

Ce guide explique comment exécuter l'extracteur GMFT en mode local (CLI + API Python). Aucun front n'est requis.

> ℹ️ **Organisation**  
> - Code backend : `backend/gmft_core/`  
> - Artefacts : `data/` (`uploads`, `metadata`, `tables_store`, `layouts`)  
> - PDFs d'exemple : `tests/data/pdf_tables/`

## 📋 Prérequis
- Python 3.10+
- GMFT (submodule git) et poids modèle (`GMFT_MODEL_PATH`)
- Tesseract installé si vous traitez des scans (PaddleOCR optionnel)
- Quelques PDF contenant des tableaux

## ⚡ Installation
```bash
cd backend/gmft_core
pip install -e .
pip install -r requirements-ocr.txt  # si OCR nécessaire
cd ../..
```

Créer `.env` à la racine :
```bash
GMFT_MODEL_PATH=./models/gmft_small.pt
GMFT_CACHE_DIR=./.gmft_cache
OCR_ENGINE=tesseract
TESSDATA_PREFIX=/usr/share/tesseract-ocr/4.00/tessdata
TABLES_STORE=./data/tables_store
UPLOAD_DIR=./data/uploads
PROFILE=default
```

Optionnel : `data/profiles/default.yaml` pour définir vos colonnes (voir exemples dans `data/profiles/`).

## 🎯 Utilisation

### 1. Ingestion via CLI
```bash
gmft-cli ingest --data tests/data/pdf_tables --profile default
```
Sortie typique :
```
RUN ID: run-20250217-1015-7b8c
PDFs: 2 | Pages: 35 | Tables détectées: 9
Exports: data/tables_store/run-20250217-1015-7b8c
```

### 2. Interroger les tables
```bash
gmft-cli query --folder "Direction Financière" --column "Montant" --confidence-min 0.7
```

### 3. Exporter un tableau
```bash
gmft-cli export --table-id tbl-0c89fe --format parquet --output ./exports
```

### 4. Utiliser l'API Python
```python
from gmft_extractor import GMFTExtractor

extractor = GMFTExtractor(profile="default")
result = extractor.process_pdf("tests/data/pdf_tables/bilan.pdf")
for table in result.tables:
    table.dataframe.to_parquet("./exports/%s.parquet" % table.table_id)
```

## 🔧 Commandes utiles
- `gmft-cli runs list` : voir les runs précédents
- `gmft-cli runs show --run-id <id>` : voir les stats / chemins
- `python backend/gmft_core/scripts/replay_run.py --run-id <id> --from-cache` : rejouer sans relancer l'OCR
- `gmft-cli profiles validate --file data/profiles/default.yaml` : vérifier un profil

## 🐛 Dépannage
- `GMFT_MODEL_PATH not found` → vérifier le chemin / télécharger le modèle
- `TesseractNotFoundError` → installer Tesseract ou passer `OCR_ENGINE=none`
- `No tables detected` → activer `--debug` pour voir les prétraitements, ajuster le profil
- `Export empty` → vérifier `kv_store_tables.json` puis relancer `gmft-cli export` avec un `table_id` valide

## 📚 Prochaines étapes
1. Ajouter des tests (voir `docs/TEST_REGISTRY.md`)
2. Documenter vos profils dans `data/profiles/`
3. Planifier une API REST ou un front si besoin
