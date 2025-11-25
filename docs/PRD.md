# PRD – Extracteur de tableaux PDF basé sur GMFT

## Short brief — But & fonctionnement (vue d'ensemble)
- **But** : livrer un outil minimaliste et auto-hébergeable capable d'isoler tous les tableaux présents dans un PDF et de les exporter proprement, sans interface graphique, avec un focus sur la robustesse et la souveraineté des traitements.
- **Fonctionnement résumé** :
  1. **Ingestion** : les PDF sont fournis via une CLI (`gmft-cli ingest`) ou une simple API Python (`gmft_extractor.process_pdf`). Les fichiers sont copiés dans `data/uploads/`, signés (hash) et découpés page par page.
  2. **Extraction** : GMFT (https://github.com/conjuncts/gmft) détecte les zones tabulaires, fusionne les cellules et reconstruit les grilles. Les pages scannées sont OCRisées avec Tesseract ou PaddleOCR selon configuration.
  3. **Publication** : chaque tableau devient une DataFrame pandas enrichie d'attributs (source, page, confiance). Les exports CSV/Parquet/Excel sont générés dans `data/tables_store/`.
  4. **Consommation** : en attendant un front, tout passe par la CLI (listing des runs, filtres, exports) ou par l'API Python (importable dans un notebook ou un pipeline airflow/dbt).

## Synthèse statuts (TDD)
| Feature | Description | Statut |
| --- | --- | --- |
| Feature 1.1 | Ingestion multi-origines (CLI + API Python) | 🚧 |
| Feature 1.2 | Détection de tableaux GMFT + OCR hybride | 🚧 |
| Feature 1.3 | Normalisation/standardisation des schémas | 🚧 |
| Feature 1.4 | Indexation légère & exports multiples | 🚧 |
| Feature 1.5 | API Python (pas d'API REST) | 🚧 |
| Feature 1.6 | Observabilité minimale (logs + métriques locales) | 🚧 |
| Feature 1.7 | Scripts d'exécution & base de tests | 🚧 |
| Feature 2.0 | Expérience utilisateur (CLI) | 🚧 |
| Feature 2.2 | Recherche/filtrage via CLI | 🚧 |
| Feature 2.3 | Ergonomie & accessibilité (messages CLI) | 🚧 |
| Feature 2.4 | Gestion des heuristiques/profils via fichiers | 🚧 |
| Feature 3.1 | Infrastructure minimale (Python + dépendances OCR) | 🚧 |
| Feature 3.2 | Sécurité & gouvernance des données | 🚧 |
| Feature 3.3 | Points d'attention (docs, résilience, extension) | 🚧 |

> **Statut global** : tout est encore en construction ; les sections ci-dessous décrivent la cible à atteindre.

---

## Partie 1 — Pipeline, données et algorithmes

### 1) Ingestion des documents
- **Sources prévues** : commandes CLI, scripts Python ou watchers simples (`gmft-cli ingest --watch <folder>`). Pas de dépôt Streamlit ni de REST.
- **Normalisation** : chaque run crée un identifiant `run-<horodatage>-<hash>` ; les PDF sont copiés dans `data/uploads/<run_id>/` et leur nom original est stocké dans `run_status.json`.
- **Tracking** : la CLI écrit un journal `data/runs/<run_id>.json` (statut `PENDING`, `PROCESSING`, `DONE`, `FAILED`). Les scripts Python renvoient cette structure en mémoire pour intégration dans un pipeline aval.
- **Sessions longues** : non supportées pour l'instant ; les lots se gèrent via un dossier surveillé. Un plan d'évolution mentionne des « batch manifests » mais hors périmètre v1.
- **Répertoires runtime** :
  - `data/metadata/` : configuration du run, paramètres heuristiques, stats par page.
  - `data/tables_store/` : tables JSON/Parquet/Excel + résumé `kv_store_tables.json`.
  - `data/layouts/` : prévisualisations (images annotées) pour debug local.

### 2) OCR & extraction de métadonnées
- **Pipeline** : `backend/gmft_core/pipeline/basic_runner.py` prépare les pages (deskew, binarize), appelle GMFT, puis associe les cellules aux textes OCR si nécessaire.
- **OCR** : Tesseract (par défaut) ou PaddleOCR (`OCR_ENGINE=paddle`). Le sélecteur `ocr_router.py` reste volontairement simple (pas de retries sophistiqués, juste un fallback natif → OCR).
- **Métadonnées** : chaque tableau embarque `table_id`, `source_file`, `page_index`, `confidence`, `schema.columns`, `column_types`. Pas d'extraction LLM ni de canonisation automatique ; seules les règles déclarées dans un profil YAML sont appliquées.
- **Langue & formats** : `langdetect` optionnel pour indiquer `table_language`, utile pour les séparateurs décimaux. Si non configuré, la CLI affiche un avertissement.
- **Rechargement partiel** : `scripts/replay_run.py` peut rejouer un run en réutilisant les pages prétraitées (`--from-cache`). Pas de modes avancés (pas de multi-profil simultané).

### 3) Canonisation & référentiels
- **Profils** : simples fichiers YAML/JSON dans `data/profiles/`. Chaque profil liste les colonnes attendues, des regex de nettoyage et des conversions unitaires.
- **Organisations** : si besoin, `data/refs/refs_user.json` mappe des dossiers logiques, mais l'application ne dépend pas de cet input ; c'est un bonus pour classer les exports.
- **Maintenance** : la CLI propose `gmft-cli profiles validate` pour vérifier qu'un profil est lisible. Aucun workflow CRUD distant n'est prévu pour la v1.

### 4) Indexation & recherche
- **Store** : `kv_store_tables.json` sert d'annuaire minimal (pas de base vectorielle). Chaque entrée contient `table_id`, `run_id`, `folder`, `columns`, `row_count`.
- **Requêtes** : `gmft-cli query` filtre ce fichier JSON selon `folder`, `source_file`, `column_contains`, `confidence_min`. Pas de scoring avancé ni de similarité structurelle.
- **Exports** : `gmft-cli export --table-id` génère CSV/Parquet/Excel en réinjectant les attributs dans un onglet `__meta__` (pour Excel) ou dans `DataFrame.attrs` (pour pandas).

### 5) API Python (pas d'API REST)
- **Usage** : `from gmft_extractor import process_pdf` renvoie la liste des tables + métadonnées. Une classe `GMFTExtractor` encapsule la config (profil, OCR, chemins).
- **Intégration** : pensés pour être appelés dans des notebooks, des jobs Airflow ou des scripts d'automatisation. Aucun serveur FastAPI n'est planifié à ce stade.

### 6) Observabilité & logs
- **Logs** : `gmft_core.utils.logger` écrit dans la console + `logs/gmft.log` avec niveau `INFO`. Pas de stack ELK, seulement un format JSON léger.
- **Métriques** : un simple fichier `data/runs/metrics.csv` cumule durée par run, nb de tables détectées, taux moyen de confiance. Pas d'export Prometheus.
- **Diagnostics** : `scripts/diagnostics/check_run.py` lit un run et signale les pages sans table ou les colonnes manquantes.

### 7) Exécution & tests
- **Scripts** : `scripts/ingest_sample.py` (ingestion), `scripts/query_tables.py` (filtre), `scripts/export_tables.py` (export). Tous fonctionnent en CLI pure.
- **Tests** : à écrire (voir `docs/TEST_REGISTRY.md`). Objectif : un test CLI (ingestion), un test pipeline GMFT, un test export.
- **Environnement** : Python 3.10+, dépendances listées dans `backend/gmft_core/pyproject.toml` + OCR optionnel (`requirements-ocr.txt`).

---

## Partie 2 — Interface utilisateur (CLI) & ergonomie

### 0) Principes généraux
- Pas de front. Les interactions se font via la CLI (`gmft-cli`) ou via l'API Python exposeé par le module `gmft_extractor`.
- Les commandes affichent toujours un récapitulatif clair : fichiers pris en compte, `run_id`, nombre de tables, chemin des exports.
- Les paramètres (profils, chemins, OCR) se configurent via `.env` + options CLI.

### 1) Page « Ingestion » (équivalent CLI)
- Correspond au flux `gmft-cli ingest`.
- Entrées : dossier contenant des PDF, profil facultatif, mode OCR (`auto|force_ocr|force_native`).
- Sorties : `run_id`, chemins des artefacts, stats (pages, tables). Un résumé JSON est stocké dans `data/runs/<run_id>.json`.
- Gestion d'erreur : si un PDF échoue, le run passe en `FAILED` et aucune table n'est produite. La CLI affiche la trace et suggère de relancer avec `--debug`.

### 2) Page « Recherche » (équivalent CLI)
- Commande `gmft-cli query` ou `python scripts/query_tables.py`.
- Filtres : `--folder`, `--source`, `--column`, `--confidence-min`, `--limit`.
- Résultats : tableau texte (tabulate) listant `table_id`, `run_id`, `page`, `colonnes`, `confiance`. Option `--json` pour intégration.

### 3) Page « Gestion des acteurs » (profils)
- Commande `gmft-cli profiles list|show|validate`.
- Gère uniquement les fichiers YAML locaux. Pas de base distante.
- Permet d'ajouter/éditer un profil en clonant un modèle (`gmft-cli profiles create --from default`).

### 4) UX & accessibilité
- Messages en français, emojis légers 🔍📄 pour repérer les sections.
- Mode `--quiet` pour les scripts d'automatisation ; mode `--debug` pour afficher les étapes GMFT.
- Documentation regroupée dans `docs/other/QUICKSTART.md` + PRD.

---

## Partie 3 — Exigences techniques & contraintes

### 1) Infrastructure minimale
- **Runtime** : Python 3.10+, PyMuPDF, pdfplumber, pytesseract (si OCR) ; GMFT récupéré via submodule Git.
- **OS ciblés** : Linux/WSL principalement, Windows supporté si Tesseract installé.
- **Données** : prévoir 2-3 Go pour stocker PDF + exports.

### 2) Sécurité & conformité
- Pas de transfert réseau : tout se passe en local.
- Les PDF peuvent contenir des données sensibles ; prévoir chiffrement manuel si export vers dossiers partagés.
- Les fichiers temporaires (`data/uploads/`) sont à purger régulièrement.

### 3) Points d'attention
- **Qualité OCR** : dépend fortement des fonts et du bruit. Documenter les limites et fournir un guide d'amélioration (à écrire).
- **Profils** : la cohérence des colonnes dépend des profils YAML ; prévoir des validations strictes.
- **Évolution future** : si un front ou une API REST est demandé, ce PRD devra être élargi (champs réseau, auth, UX).

---

## Glossaire
- **GMFT** : moteur open source pour repérer les tableaux dans des PDF multi-mises en page.
- **Run** : exécution complète de l'ingestion + extraction.
- **Profil** : configuration décrivant les colonnes attendues et les heuristiques liées.
- **Table ID** : identifiant unique pour chaque tableau détecté.

---

## Ouvertures (post-v1)
- Ajouter une API REST légère puis, plus tard, un front.
- Supporter d'autres moteur OCR (Azure, AWS Textract) si besoin.
- Automatiser la surveillance d'un dossier partagé avec notifications.

---

## Organisation du développement (référence TDD)
- Chaque incrément couvre un maillon (ingestion, extraction, export).
- Règle : écrire/adapter les tests avant le code (voir `docs/TEST_REGISTRY.md`).
- Pas de nouvelle doc hors PRD/TODO/QUICKSTART sans validation.
- Les commandes de référence sont consignées dans `docs/other/QUICKSTART.md`.
- Les commits suivent le cycle `test → feat → refactor`, même si la base de tests est encore à construire.
