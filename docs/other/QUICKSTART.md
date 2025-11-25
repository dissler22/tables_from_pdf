# 🚀 Guide de démarrage rapide

Ce guide explique comment lancer l'extracteur GMFT et produire vos premiers exports tabulaires en 5 minutes.

> ℹ️ **Organisation des fichiers**  
> - Le cœur backend vit dans `backend/gmft_core/`.  
> - Les artefacts générés sont stockés dans `data/` (`data/uploads`, `data/layouts`, `data/tables_store`).  
> - Les PDF d'exemple se trouvent dans `tests/data/pdf_tables/`. Pensez à adapter les chemins aux vôtres.

## 📋 Prérequis

- Python 3.10+
- GMFT (téléchargé automatiquement via submodule) + poids du modèle (`GMFT_MODEL_PATH`)
- PDF de test contenant au moins un tableau (idéalement 2 pour valider multi-pages)
- Tesseract installé si vous traitez des scans

## ⚡ Installation rapide

### 1. Installer les dépendances

```bash
cd backend/gmft_core
pip install -e .
pip install -r requirements-ocr.txt  # si OCR nécessaire
cd ../..
```

### 2. Configurer l'environnement

Créez (ou complétez) `.env` à la racine :

```bash
# GMFT
GMFT_MODEL_PATH=./models/gmft_large.pt
GMFT_CACHE_DIR=./.gmft_cache
GMFT_PROFILE=default

# OCR
OCR_ENGINE=tesseract
TESSDATA_PREFIX=/usr/share/tesseract-ocr/4.00/tessdata

# Référentiels
REFS_FILE=./data/refs/refs_user.json
REFS_PROFILES_FILE=./data/refs/refs_people.json

# Stockage
TABLES_STORE=./data/tables_store
UPLOAD_DIR=./data/uploads
LAYOUT_DIR=./data/layouts

# FastAPI
API_HOST=0.0.0.0
API_PORT=9726
API_KEY=demo-key
```

### 3. Initialiser les référentiels

Créez `data/refs/refs_user.json` :

```json
{
  "Direction Financière": ["DirFin", "Finance centrale"],
  "BU Infrastructures": ["Infra", "Business Unit Infra"]
}
```

Créez `data/refs/refs_people.json` pour vos profils heuristiques :

```json
{
  "__meta__": {
    "version": 1,
    "updated_at": null
  },
  "profiles": []
}
```

## 🎯 Utilisation

### Étape 1 : Ingestion d'un PDF

```bash
cd backend/gmft_core
python scripts/ingest_sample.py --data ../tests/data/pdf_tables --profile default
```

**Sortie attendue** :
```
================================================================================
GMFT INGEST - Configuration
================================================================================
Data directory: ./tests/data/pdf_tables
OCR engine: tesseract
GMFT model: ./models/gmft_large.pt
================================================================================

[INFO] Found 2 PDF file(s)
   - bilan_financier.pdf (312 KB)
   - rapport_travaux.pdf (1.2 MB)

[1/2] Processing: bilan_financier.pdf
   -> Preprocessing pages (deskew, contrast, binarize)
   -> GMFT running... 3 tables detected
   -> Normalizing schema and casting columns
   [OK] Exported table_id: tbl-0c89fe...

[SUCCESS] All runs completed!
```

Chaque run crée :
- un dossier `data/layouts/<run_id>/` avec les prévisualisations.
- des DataFrame dans `data/tables_store/parquet/`.

### Étape 2 : Tester les requêtes

**API REST** :
```bash
python -m gmft_core.api.server  # dans un terminal
```

Puis :
```bash
curl -H "X-API-Key: demo-key" \
     -X POST http://localhost:9726/tables/query \
     -H "Content-Type: application/json" \
     -d '{"filters": {"folder": "Direction Financière"}}'
```

**CLI** :
```bash
cd ..
gmft-cli query --folder "Direction Financière" --format csv --output ./exports
```

## 📝 Exemples de requêtes

### 1. Recherche par dossier

```python
from gmft_extractor.client import GMFTClient

client = GMFTClient(api_key="demo-key")
result = client.query_tables(filters={"folder": "BU Infrastructures"})
```

### 2. Recherche par colonnes

```python
client.query_tables(filters={"column_set": ["Lot", "Montant HT", "TVA"]})
```

### 3. Export spécifique

```python
client.export_table(table_id="tbl-0c89fe...", fmt="parquet", output_path="./exports")
```

### 4. Rejouer un run avec un nouveau profil

```bash
python scripts/replay_run.py --run-id run-20240112-1145 --profile audit
```

## 🔧 Commandes utiles

### Purger les artefacts

```bash
cd backend/gmft_core
rm -rf ./data/tables_store ./data/layouts
python scripts/ingest_sample.py
```

### Inspecter les métadonnées

```bash
ls data/metadata/
cat data/metadata/run-20240112-1145.json | jq '.'
```

### Liste des tables

```bash
python -c "import json; data=json.load(open('data/tables_store/kv_store_tables.json')); print(len(data))"
```

### Prévisualiser un tableau annoté

```bash
python scripts/preview_table.py --table-id tbl-0c89fe...
```

## 🐛 Dépannage rapide

### Erreur : `GMFT_MODEL_PATH not found`
→ Vérifier que le modèle est téléchargé et que la variable pointe au bon chemin.

### Erreur : `OCR engine not available`
→ Installer Tesseract (`sudo apt install tesseract-ocr`) ou changer `OCR_ENGINE`.

### Tables vides
→ Utiliser `scripts/debug_cells.py --run-id <id>` pour inspecter les cellules brutes et ajuster le profil heuristique.

### Exports incomplets
→ Vérifier `data/tables_store/export.log` pour les colonnes ignorées ; relancer avec `--strict-mode` pour bloquer si une colonne clé manque.

## 📚 Prochaines étapes

1. **Ajouter de nouveaux profils** : via `/profiles` ou `frontend/streamlit/pages/3_Gestion_heuristiques.py`.
2. **Brancher vos pipelines** : consommer les Parquet via Spark/DBT.
3. **Automatiser** : lancer `gmft-cli ingest --watch <dossier>` pour surveiller un répertoire partagé.
4. **Déployer** : dockeriser `gmft_core.api.server` + worker et connecter Prometheus/Grafana.

## 🆘 Besoin d'aide ?

- **Documentation complète** : `README.md`
- **Architecture détaillée** : `README_adaptations.md`
- **Règles Cursor** : `.cursorrules`

---

**Setup estimé** : 5-10 minutes  
**Temps d'extraction** : ~45 s pour 50 pages  
**Temps de requête** : ~1 s en mode `filtered`
