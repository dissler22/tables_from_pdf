# PRD — Extracteur de tableaux PDF GMFT

Ce document décrit la vision produit, la portée et les exigences de l'extracteur de tableaux PDF (prétraitement PDF → détection → export).

## 1. Contexte et objectifs
- Automatiser l'extraction fiable de tableaux dans des PDF techniques (plans, journaux de chantier, documents de suivi), sans intervention manuelle.
- **Deux types de documents principaux** :
  - **ESC** (Journaux de chantier) : Tableaux standards avec alternance de lignes blanches/bleues, support multi-pages
  - **SDP** (Sous-Détail de Prix) : Format complexe sans bordures claires, positions X variables, récapitulatifs A/B
- S'appuyer sur : `pdfplumber` pour PDFs natifs, `Table Transformer (DETR)` pour scans, exports JSON/CSV + artefacts visuels.
- Priorités actuelles : extraction robuste ESC/SDP (v2), calibration dynamique des colonnes (v2.1), exports structurés.

## 2. Utilisateurs et cas d'usage
- **Chargés d'études / PMO** : extraire rapidement les tableaux de journaux de chantier ou de plans pour reporting.
- **Data engineers / ops** : intégrer l'extracteur dans une pipeline batch, surveiller les artefacts et relancer sur de nouveaux lots PDF.
- **Développeurs internes** : enrichir les heuristiques d'en-tête et brancher de nouveaux tests/goldens à mesure que de nouveaux types de PDF apparaissent.

## 3. Portée fonctionnelle

### 3.1 Entrées
- Fichier PDF ou répertoire de PDFs (CLI `extract_tables.py`)
- Filtrage des pages (`--pages`), modes (`fast`, `accurate`, `hybrid`)
- OCR optionnel (`tesseract/paddleocr/easyocr/none`), résolution (`--dpi`)

### 3.2 Extracteurs spécialisés

| Extracteur | Documents | Méthode |
|------------|-----------|---------|
| `PdfPlumberExtractor` | ESC, PDFs natifs | `pdfplumber.find_tables()` |
| `SDPExtractor` | SDP | Calibration dynamique + groupement par proximité |
| `TableStructureExtractor` | Scans | `img2table` + OCR |

### 3.3 Pipeline
- `TableExtractionPipeline` orchestre rendu PDF → détection → extraction
- Modes : `FAST` (direct), `ACCURATE` (détection + extraction), `HYBRID` (fallback)
- Post-traitement : fusion multi-pages, nettoyage lignes vides/footers

### 3.4 Sorties
- JSON consolidé (`tables.json`) + CSV par tableau
- Images annotées par page (`page{n}_annotated.png`)
- Format condensé (`raw_data`) + format détaillé (`cells`)

### 3.5 Tests
- Goldens dans `tests/goldens/` (ESC page 2, SDP page 1)
- Tests de régression automatisés

## 4. Hors scope (actuel)
- OCR systématique sur scans dégradés (prévu via moteurs configurables, mais non activé par défaut).
- Extraction sémantique avancée (typage de colonnes, validation métier, jointure multi-pages).
- UI web/front : non prévue, usage CLI/API uniquement.

## 5. Parcours utilisateur (CLI)
1) L'utilisateur fournit un PDF ou un répertoire (`--all` pour tout traiter).  
2) Le pipeline rend les pages (dpi configuré), applique la détection (selon mode) puis l'extraction.  
3) Les tables sont sérialisées en JSON + CSV, avec images annotées si activées.  
4) L'utilisateur consulte les artefacts, puis itère (ajout de goldens, réglage seuils OCR/détection si besoin).

## 6. Exigences fonctionnelles détaillées
- **Rendu PDF** : supporte PDF digitaux ; paramètre `dpi` pour ajuster la précision. Gestion multi-pages, filtrage par liste ou plage.
- **Détection** : modèle `microsoft/table-transformer-detection` chargé lazy, device auto (CPU/GPU), seuil configurable ; NMS avec IoU paramétré ; fallback si aucune box.
- **Extraction** : img2table avec options `implicit_rows/columns`, `borderless_tables`; OCR optionnel ; fusion des bboxes détection + extraction (offset appliqué).
- **Exports** : sauvegarde conditionnelle selon `output_format` (json/csv) ; chaque `ExtractionResult` contient erreurs et métadonnées (pages totales, nombre de tables).
- **Artefacts** : images annotées par page (rectangle + label table idx) ; JSON/CSV nommés de façon stable (`page{n}_table{m}.csv`).
- **Tests** : maintien des tests unitaires (utils, détecteur, extracteur, pipeline) et du test de régression `tests/test_extract_test1.py` (vérifie goldens + artefacts).

## 7. Exigences non fonctionnelles
- **Performance** : mode `FAST` privilégié pour volume élevé ; `ACCURATE/HYBRID` pour précision. DPI par défaut 200, ajustable selon latence souhaitée.
- **Compatibilité** : Python 3.12 (tests), dépendances torch/transformers/img2table ; fonctionne CPU par défaut, GPU si dispo.
- **Fiabilité** : logs console synthétiques (mode, OCR, pages, temps d'exécution) ; erreurs collectées dans `ExtractionResult`.
- **Traçabilité** : artefacts (JSON/CSV/PNG) versionnés par run ; goldens indispensables pour éviter régressions.
- **Portabilité** : CLI utilisable Windows/Linux (gestion encodage Windows prévue).

## 8. Données de test et validation
- Dataset principal : `tests/data_test/pdf_tables/test1.pdf` (page unique avec 2 tables). Goldens dans `tests/goldens/` (main/footer).
- Tests automatiques : `pytest tests/test_extract_test1.py` (conforme à `docs/features/extraction_v0.md` et `extraction_v1_general.md`), plus tests unitaires génériques `tests/test_extraction.py`.
- Artefacts attendus : `tables.json`, `page1_annotated.png`, CSV alignés sur goldens.

## 9. Roadmap / incréments

| Version | Statut | Description |
|---------|--------|-------------|
| **v0** | ✅ OK | Heuristique dédiée `test1.pdf`, artefacts PNG/JSON |
| **v1** | ✅ OK | Généralisation multi-tables/pages, pdfplumber |
| **v2** | ✅ OK | Extraction ESC complète avec fusion multi-pages |
| **v2.1** | ✅ OK | SDPExtractor avec calibration dynamique, récaps |
| **v3** | 🔜 | Support OCR pour scans, métriques de confiance |

### Détails v2.1 (SDP)
- Calibration des colonnes X via détection ligne formules (`a b 1=axb 2 3 4...`)
- Groupement des mots par proximité (gap < 12px)
- Séparation automatique unités (`h`, `m3`, `t`)
- Extraction récap : TOTAL 5/7, K1-K6 (pourcentages + montants), prix final

## 10. Risques et hypothèses
- Variabilité des en-têtes : nécessite enrichissement progressif des heuristiques/tokenizers et de jeux de goldens.
- Performance dépendante du modèle DETR (poids à charger) et de torch ; risque de lenteur sur machines sans GPU.
- OCR : dépendances système (tesseract, paddleocr) non packagées ; prévoir dégradations si non installées.
- PDFs scannés ou très bruyants encore peu couverts par les tests actuels.

## 11. Critères de succès / KPIs
- Taux de succès extraction (tables détectées/extraites vs goldens) ≥ 95 % sur le jeu de référence.
- Absence de régressions sur `test1.pdf` (tests verts en CI).
- Temps de traitement moyen < 30 s/page en mode accurate sur CPU standard.
- Artefacts présents et exploitables (JSON/CSV/PNG) pour chaque run sans erreur bloquante.
