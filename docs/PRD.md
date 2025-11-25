# PRD – Extracteur de tableaux PDF basé sur GMFT

## Short brief — But & fonctionnement (vue d'ensemble)
- **But** : proposer une solution souveraine permettant de détecter, structurer et exporter automatiquement tous les tableaux présents dans des PDF hétérogènes grâce à GMFT (Graph-based Multi-layout Table Finder) et à une chaîne Python industrialisable.
- **Fonctionnement résumé** :
  1. **Ingestion** : les fichiers sont transférés via l'API `/pdf/upload`, la CLI `gmft-cli ingest` ou l'interface Streamlit. Les lots volumineux utilisent les sessions (`/pdf/upload-sessions/*`) pour découpler l'upload du traitement. Chaque page est normalisée (rotation, contraste, split recto-verso) avant d'être encapsulée pour GMFT.
  2. **Extraction** : GMFT identifie les zones tabulaires (multi-table/multi-colonnes), reconstruit les grilles puis convertit les cellules en DataFrame pandas. Les textes issus d'OCR (Tesseract ou PaddleOCR) sont fusionnés avec les PDF natifs afin d'obtenir des cellules propres et alignées.
  3. **Publication** : les DataFrame enrichis sont stockés dans `tables_store/` (JSON + artefacts Parquet). Le moteur expose des exports CSV/Parquet/Excel et un schéma Arrow pour la connexion aux pipelines de data-engineering.
  4. **Consommation** : une API Python (`gmft_extractor.client`), une CLI robuste et les routes REST `/tables/query`, `/tables/{table_id}` et `/pipelines/hooks` permettent d'orchestrer les extractions, suivre les jobs et brancher des heuristiques métier.

## Synthèse statuts (TDD)
| Feature | Description | Statut |
| --- | --- | --- |
| Feature 1.1 | Ingestion multi-origines (API, CLI, UI) | ✅ |
| Feature 1.2 | Détection de tableaux GMFT + OCR hybride | ✅ |
| Feature 1.3 | Normalisation/standardisation des schémas | ✅ |
| Feature 1.4 | Indexation, exports multiples et requêtes | ✅ |
| Feature 1.5 | API REST & SDK Python | ✅ |
| Feature 1.6 | Observabilité (logs, métriques, traces) | ✅ |
| Feature 1.7 | Outils d'exécution & tests automatisés | ✅ |
| Feature 2.0 | Principes UX généraux (pages Streamlit) | ✅ |
| Feature 2.2 | Page « Recherche » (visualisation tables) | ✅ |
| Feature 2.3 | UX & accessibilité (filtres, dataviz) | ✅ |
| Feature 2.4 | Page « Gestion des heuristiques » | 🚧 |
| Feature 3.1 | Infra minimale (Backend FastAPI + Front) | ✅ |
| Feature 3.2 | Sécurité & gouvernance des données | ✅ |
| Feature 3.3 | Points d'attention (docs, résilience GMFT, extension métier) | ✅ |

---

## Partie 1 — Pipeline, données et algorithmes

### 1) Ingestion des documents
- **Sources prévues** : PDF natifs ou scannés déposés dans `tests/data/pdf_tables/`, uploads utilisateurs (Streamlit, API `multipart/form-data`), archives ZIP traitées côté serveur (`/pdf/upload-zip`), ou `gmft-cli ingest --watch <folder>` pour surveiller un répertoire.
- **Normalisation des chemins** : chaque dépôt génère un `table-run-<hash>` ; les fichiers sources sont recopiés dans `data/uploads/` et horodatés. Le nom original est stocké dans `doc_status` et sur tous les artefacts (`_source_name`).
- **Tracking du traitement** : l'API retourne un `run_id`. La route `/pdf/track_status/{run_id}` expose le statut global, le nombre de pages analysées, le nombre de tableaux extraits et les erreurs GMFT/OCR (`WAITING`, `PREPROCESSING`, `DETECTING`, `POSTPROCESSING`, `DONE`, `FAILED`).
- **Sessions d'upload longues** : `/pdf/upload-sessions` crée un conteneur temporaire (`data/uploads/__sessions__/<session_id>`) dans lequel les utilisateurs poussent des PDF ou ZIP. La commande `/commit` déclenche l'ordonnanceur `gmft_worker`. Les fichiers sont purgés après confirmation pour limiter la surface disque.
- **Répertoires runtime** :
  - `data/metadata/` : métadonnées des runs (pages, orientation, heuristiques appliquées, mapping colonnes).
  - `data/tables_store/` : tables brutes (par page) + agrégations multi-pages (JSON/Parquet/Feather).
  - `data/layouts/` : masques GMFT (`*.gmft.json`) et images annotées (`*_preview.png`) accessibles via `/tables/{table_id}/preview`.

### 2) OCR & extraction de métadonnées
- **Technologie OCR** : GMFT consomme directement le texte natif lorsqu'il existe ; sinon `pytesseract` (par défaut) ou PaddleOCR (`OCR_ENGINE=paddle`) reconstitue les cellules. Le module `backend/gmft_core/ocr/ocr_router.py` gère les retries (`tenacity`) et la fusion multi-langues.
- **Extraction GMFT** : `backend/gmft_core/pipeline/gmft_runner.py` orchestre GMFT (https://github.com/conjuncts/gmft) pour détecter les régions, vectoriser les lignes/colonnes puis produire une grille ordonnée. Chaque cellule est accompagnée d'un `bbox`, d'un `confidence` et d'un `source_layer` (texte natif vs OCR).
- **Enrichissement tabulaire** :
  - Détection des en-têtes récurrents (`headline_detector.py`) pour remplir `schema.columns`.
  - Fusion des cellules fusionnées (row/col span) en préservant l'ordre de lecture.
  - Alignement sur `table_metadata.json` : type de données, unités, indice métier associé.
- **Détection langue & localisation** : `langdetect` + `pycountry` alimentent `table_language` et `number_format` afin d'interpréter correctement les séparateurs décimaux.
- **Propagation** : toutes les métadonnées pertinentes (dossier, provenance, heuristiques utilisées, statut OCR) sont copiées dans les DataFrame exportés (`df.attrs`) et dans les chunks Arrow pour être filtrables côté requêtes.
- **Rechargement partiel** : `backend/gmft_core/scripts/replay_run.py` relance le parsing d'un `run_id` en réutilisant les pages normalisées (`--from-cache`) ou en recalculant uniquement les heuristiques métier (`--features-only`). La page Ingestion du front offre un bouton « Rejouer avec un nouveau profil » qui appelle ce script via `gmft_ops.replay_run`.

### 3) Canonisation & référentiels
- **Organisations (`data/refs/refs_user.json`)** : réutilisées pour mapper les dossiers logiques (service métier, client, marché). Elles servent à pré-remplir `folder` et à taguer les exports, ce qui facilite l'automatisation downstream.
- **Personnes / heuristiques (`data/refs/refs_people.json`)** : dans ce projet, le fichier stocke désormais les **profils d'extraction** : auteur, scope, alias et listes de colonnes attendues. L'API `/people` devient `/profiles` mais conserve les mêmes contrats CRUD afin de ne pas casser les intégrations existantes.
- **Maintenance** : `backend/gmft_core/scripts/update_refs.py` synchronise les profils locaux et ceux définis en API. Les administrateurs peuvent charger un YAML métier (heurs de facturation, identifiants de lignes budgétaires) puis propager les alias via ce script ou via la page « Gestion des heuristiques » (voir Partie 2).

### 4) Indexation & recherche
- **Table store** : chaque tableau est stocké dans `tables_store/kv_store_tables.json` avec son `table_id`, la page d'origine, les colonnes détectées, les statistiques (`row_count`, `column_count`, `measurements`). Les exports Parquet sont générés dans `tables_store/parquet/<table_id>.parquet` pour être directement consommés par Spark ou pandas.
- **Query engine** : `backend/gmft_core/query/table_query.py` propose deux modes :
  - `filtered` (par défaut) qui applique un filtrage dur sur `folder`, `source_file`, `column_set`, `language`, `confidence_min`.
  - `layout` qui exploite les graphes GMFT (`graph_table_relation.graphml`) pour retrouver des tables similaires (structure + densité), utile pour détecter des rapports identiques sur plusieurs mois.
- **Exports** : `/tables/{table_id}/export` accepte `format=csv|parquet|xlsx` et renvoie un flux streamable. Chaque export contient les métadonnées dans un onglet/feuille `__meta__` (Excel) ou dans `pandas.DataFrame.attrs`.
- **Recherche textuelle** : `tables_search_index.sqlite` indexe les cellules pour permettre des recherches full-text rapides côté CLI (`gmft-cli query --text "montant TVA"`).

### 5) API REST principale (FastAPI)
- Démarrage via `python -m gmft_core.api.server` (cf. `docs/other/QUICKSTART.md`).
- **Routes documents** (`backend/gmft_core/api/routers/pdf_routes.py`) :
  - `POST /pdf/upload` : upload unique avec paramètres `folder`, `profile_id`, `extract_strategy` (auto / force_gmft / force_ocr).
  - `POST /pdf/upload-zip` : import massif ; gère jusqu'à 500 Mo avec streaming disque.
  - `POST /pdf/text` : injection d'un export texte externe (pour tests OCR).
  - `GET /pdf/track_status/{run_id}` : statut détaillé par page.
  - `GET /pdf/folders` : liste maintenue via référentiels.
  - `POST /pdf/list` : vue consolidée des runs (filtrable par profil, statut, période).
  - `GET /pdf/{doc_id}/download` : accès au PDF d'origine (contrôle d'accès par namespace).
- **Routes tables** (`backend/gmft_core/api/routers/table_routes.py`) :
  - `POST /tables/query` : filtrage/agrégation (mode `filtered` ou `layout`).
  - `GET /tables/{table_id}` : métadonnées, aperçu PNG, statue heuristiques appliquées.
  - `GET /tables/{table_id}/export` : export multi-format.
- **Routes référentiels & hooks** :
  - `/references` pour gérer les alias dossiers.
  - `/profiles` (héritage `/people`) pour stocker les profils heuristiques.
  - `/hooks` pour déclarer des modules d'extension (voir §3 Points d'attention).
- **Auth** : dépendances `gmft_core.auth.get_auth` ; support clé API (`X-API-Key`), namespaces (`X-Workspace`) et OAuth interne (optionnel) pour la CLI.
- **Ergonomie** : `frontend/streamlit/services/api_client.py` mutualise les appels, gère l'attente des jobs longs via polling exponentiel et renvoie des DataFrame pandas directement exploitables par la page Recherche.

### 6) Observabilité & logs
- **Logs structurés** : `gmft_core.utils.logger` produit des événements JSON (étape, durée, nb de tables). Les diagnostics (`scripts/diagnostics/check_upload.py`, `scripts/diagnostics/check_table_quality.py`) lisent ces fichiers pour repérer les anomalies GMFT.
- **Métriques** : `prometheus_fastapi_instrumentator` expose `gmft_tables_detected_total`, `gmft_run_duration_seconds`, `gmft_export_errors_total`. Un dashboard Grafana modèle est fourni dans `observability/grafana/gmft_tables.json`.
- **Suivi pipeline** : `run_status.json` garde l'historique complet (même après purge) afin que la page Ingestion puisse afficher les tendances (durées moyennes, taux d'erreur OCR).

### 7) Exécution & tests
- **Scripts CLI** :
  - `backend/gmft_core/scripts/ingest_sample.py` : pipeline complet sur `tests/data/pdf_tables/`.
  - `gmft-cli query` et `gmft-cli export` : scénarios de bout en bout utilisés dans `docs/other/QUICKSTART.md`.
  - `scripts/diagnostics/check_profile.py` : valide les profils heuristiques.
- **Tests automatisés** :
  - `tests/backend/test_table_api.py` : CRUD sur `/tables/*` et `/profiles`.
  - `tests/integration/test_cli_ingest.py` : vérifie ingestion + export CSV.
- **Environnements requis** :
  - `backend/gmft_core/pyproject.toml` + `backend/gmft_core/requirements-ocr.txt` (pour Paddle/Tesseract) + `frontend/streamlit/requirements.txt`.
  - Variables documentées dans `CONFIG.md` (backend) et `FRONTEND_CONFIG_GUIDE.md` (front) ; `GMFT_MODEL_PATH` et `GMFT_CACHE_DIR` sont obligatoires.

---

## Partie 2 — Front Streamlit (comportement & UX)

### 0) Principes généraux
- Application Streamlit unique (`frontend/streamlit/app.py`) avec trois pages : `1_Ingestion.py`, `2_Recherche.py`, `3_Gestion_heuristiques.py`. Navigation via menu latéral ; état commun (`st.session_state`) pour partager les derniers runs et profils chargés.
- **Configuration dynamique** : `frontend/streamlit/utils/config.py` lit `.env` et expose `API_BASE_URL`, `API_KEY`, `DEFAULT_PROFILE`. Les valeurs sont affichées dans un encart diagnostic pour aider les équipes data.
- **API Client** : `frontend/streamlit/services/api_client.py` encapsule toutes les routes (upload, status, tables, exports, profils) et traduit les réponses JSON en DataFrame.
- **Stockage d'état** : `session_state` garde les dossiers, profils sélectionnés, derniers exports et préférences d'affichage (format large / condensé).

### 1) Page « Ingestion »
- **Objectifs** : permettre aux équipes métiers de lancer des extractions et de comparer la qualité GMFT vs OCR.
- **Fonctionnalités clés** :
  - Upload drag & drop multi-fichiers avec sélection du profil heuristique et du dossier logique.
  - Onglet ZIP (import mensuel) + champ pour sélectionner une session existante.
  - Résumé temps réel : nb de pages traitées, nb de tables par document, alertes (taux de confiance < seuil, colonnes manquantes).
  - Tableau des runs récents avec boutons « Rejouer », « Exporter toutes les tables », « Télécharger les préviews ».
  - Panneau « ♻️ Recalcul » : choix du mode (rejouer complet, recharger depuis cache, heuristiques uniquement) qui déclenche `gmft_ops.replay_run` et affiche stdout/stderr dans un `st.expander`.
  - Gestion des erreurs : messages explicites si GMFT indisponible ou si un OCR tiers manque ; suggestions automatiques (installer `tesseract`, vérifier `GMFT_MODEL_PATH`).

### 2) Page « Recherche »
- **Objectifs** : filtrer et visualiser les tableaux extraits, puis exporter ceux qui intéressent l'utilisateur.
- **Filtres disponibles** : dossier, profil, statut de run, date (période), langue, mot-clé dans les colonnes, plage du nombre de colonnes. Les filtres sont stockés côté session pour faciliter le va-et-vient avec la page Ingestion.
- **Résultats** :
  - Tableau interactif (`st.dataframe`) listant `table_id`, run, page, nb lignes, colonnes détectées (chips), niveau de confiance.
  - Boutons d'action : prévisualiser (ouvre l'image annotée), télécharger CSV/Parquet/Excel, ouvrir dans pandas (affichage inline via `st.data_editor`).
  - Statistiques : totaux par profil, moyenne de lignes, ratio OCR vs texte natif.
- **Recherche RAG-like** : champ libre alimentant `/tables/query` mode `layout` pour retrouver des tables structurellement similaires (ex : "tableaux de dépenses mensuelles"). Résultats présentés avec un score, l'origine et une recommandation d'export.

### 3) Page « Gestion des acteurs »
- **Objectifs** : piloter les profils heuristiques (alias colonnes, règles de nettoyage) et les dossiers logiques depuis Streamlit.
- **Vue profils** :
  - Filtres : dossier + type de profil (global, local, expérimental).
  - Tableau `st.dataframe` listant nom, alias, colonnes attendues, modules d'extension activés.
  - Formulaire d'ajout/mise à jour (`APIClient.upsert_profile`) avec options `merge_columns` et `append_hooks`.
  - Actions rapides : dupliquer un profil, exporter/importer en JSON, forcer une synchronisation avec le backend.
- **Bloc dossiers** :
  - Liste des dossiers disponibles (`/references/folders`).
  - Boutons « Copier », « Nettoyer », « Recharger depuis backend » pour maintenir les alias.
  - Historique des modifications stocké dans `st.session_state['folders_audit']`.

### 4) UX & accessibilité
- Interface full FR, icônes 🎯📄📊 pour rythmer les cards.
- Rappels contextuels : infobulles pour expliquer `confidence`, `profil`, `layout score`.
- Mode compact pour afficher >50 tables ; switch accessible via la barre latérale.
- Guide de configuration (`FRONTEND_CONFIG_GUIDE.md`) mis à jour avec les variables spécifiques GMFT (profils par défaut, dossier d'exports partagés).

---

## Partie 3 — Exigences techniques & contraintes

### 1) Infrastructure minimale
- **Backend** : Python 3.10+, GMFT (sous-module Git) + PyMuPDF, pdfplumber, pytesseract, PaddleOCR (optionnel). Variables obligatoires : `GMFT_MODEL_PATH`, `GMFT_CACHE_DIR`, `TESSDATA_PREFIX`.
- **Frontend** : Streamlit ≥1.51, Plotly pour les préviews et `streamlit-aggrid` pour la data grid.
- **Stockage** : 200 Mo/run pour les préviews + Parquet ; prévoir 5 Go libres pour des projets moyens. Les exports sont compressés via `pyarrow`.
- **Performances** : objectif <45 s pour un PDF de 50 pages en mode mixte (texte + OCR). Les exports sont streamés pour éviter les timeouts.

### 2) Sécurité & conformité
- **Secrets** : clés OCR (si usage cloud) stockées serveur-side (Vault ou `.env`).
- **Gouvernance** : les PDF sont isolés par dossier logique (`namespace`). Les exports peuvent être chiffrés (`--encrypt`).
- **Traçabilité** : chaque table garde un hash du PDF d'origine (`source_hash`). Les journaux listent qui a téléchargé quoi (page Recherche > Audit).

### 3) Points d'attention
- **Documentation** : nombreuses références (`INDEX.md`, `README_adaptations.md`, `PROJECT_STRUCTURE.md`). Les pages GMFT doivent rester synchronisées : tout changement de script → mise à jour doc associée.
- **Résilience GMFT** : prévoir des fallback (détection heuristique `legacy_detector`) quand GMFT échoue sur des scans très bruités. Les alertes critiques déclenchent une notification via `/hooks`.
- **Extensions métier** : l'écosystème repose sur les hooks d'extension (module `backend/gmft_core/hooks`). Les évolutions doivent documenter les invariants : format d'entrée DataFrame, variables d'environnement requises.
- **Compatibilité CLI** : `gmft-cli` doit rester compatible Windows/Linux ; les chemins gérés par `pathlib` et les exports compressés sous forme relative.

---

## Glossaire
- **GMFT** : librairie open source (Graph-based Multi-layout Table Finder) permettant de détecter et de structurer les tableaux dans des PDF complexes.
- **Profil** : configuration regroupant les heuristiques métier (liste de colonnes attendues, règles de nettoyage, hooks).
- **Run** : traitement complet d'une ou plusieurs sources PDF ; contient les pages normalisées et les tables produites.
- **Table ID** : identifiant stable d'un tableau, utilisé pour tout export/filtrage.
- **Hooks** : modules Python injectés dans la pipeline pour enrichir ou transformer les DataFrame générées.

---

## Ouvertures (post-v1)
- Support d'autres moteurs (Detectron2, TabStructNet) et d'exports SQL directs.
- Normalisation automatique des unités (monnaies, pourcentages, quantités) via un moteur de règles.
- Visualisations interactives temps réel (graphiques derivés des tables) directement dans Streamlit.
- Autoscaling du worker GMFT (Ray ou Celery) pour traiter des milliers de PDF en parallèle.

---

## Organisation du développement (référence TDD incrémentale)
- **Découpage** : chaque incrément couvre un maillon du pipeline (prétraitement, détection, normalisation, export). Les dépendances sont rappelées dans la fiche feature concernée.
- **Cadre TDD** : écrire d'abord les tests CLI/API (ex. `pytest tests/backend/test_table_api.py -k export`), ensuite implémenter, puis factoriser. Conserver des fixtures PDF synthétiques dans `tests/data/pdf_tables/`.
- **Suivi documentaire** : mettre à jour cette PRD et les fiches `docs/features/<feature>.md` lorsqu'une feature bascule de 🚧 à ✅. Mentionner les commandes exactes permettant de retester.
- **Tests** : un test représentatif par feature (ingestion, détection, export, hooks) consigné dans `docs/TEST_REGISTRY.md`.
- **Référence** : le prompt TDD complet (`specs/tdd/DEV_PROMPT_REFERENCE.md`) reste la source pour alimenter Codex.
- **Commandes** : privilégier `pytest`, `gmft-cli` et les scripts listés dans `docs/runbooks/COMMANDS.md`. Toute nouvelle commande doit être ajoutée à ce runbook et liée à la feature.
- **Commits** : cycle `test/feat/refactor` par incrément, validation obligatoire des tests critiques avant merge.
