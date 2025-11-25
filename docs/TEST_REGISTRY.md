# TEST_REGISTRY — Extracteur de tableaux GMFT

Ce registre recense les tests à exécuter pour garantir la qualité du pipeline GMFT (ingestion, détection, exports, front Streamlit, CLI).

## Matrice des tests
| ID | Feature | Description | Commande | Type | Statut |
| --- | --- | --- | --- | --- | --- |
| T1 | Ingestion | Vérifier l'upload multi-fichiers et le suivi des runs | `pytest tests/backend/test_pdf_api.py -k upload` | API | ✅ |
| T2 | GMFT Core | Détection tables + OCR hybride sur les fixtures | `pytest tests/backend/test_table_api.py -k detect` | Backend | ✅ |
| T3 | Exports | Export CSV/Parquet/Excel d'un `table_id` | `pytest tests/backend/test_table_api.py -k export` | Backend | ✅ |
| T4 | CLI | Parcours `gmft-cli ingest` + `gmft-cli query` sur `tests/data/pdf_tables/` | `python scripts/tests/run_cli.py` | CLI | ✅ |
| T5 | Front Recherche | Chargement des tables dans Streamlit + filtres | `streamlit run frontend/streamlit/pages/2_Recherche.py` (test manuel) | Front | ✅ |
| T6 | Profils/Heuristiques | CRUD `/profiles` + application des hooks | `pytest tests/backend/test_profiles_api.py` | API | 🚧 |
| T7 | Observabilité | Vérifications Prometheus + logs structurés | `python scripts/diagnostics/check_upload.py` | Scripts | ✅ |

## Jeux de données
- `tests/data/pdf_tables/` : PDF synthétiques couvrant les cas multi-colonnes, colonnes fusionnées, scans bruités.
- `tests/data/pdf_tables/scans/` : jeux dédiés à la validation OCR (Tesseract/Paddle).
- `tests/data/profiles/*.json` : profils heuristiques utilisés par les tests T4 et T6.

## Commandes rapides
- `gmft-cli ingest --data tests/data/pdf_tables --profile default` : ingestion locale de référence.
- `gmft-cli query --folder "Direction Financière" --format parquet` : validation export CLI.
- `python scripts/replay_run.py --run-id <id> --from-cache` : rejoue un run pour investiguer un test rouge.
- `python scripts/tests/compare_exports.py --table-id <id>` : compare CSV vs Parquet (détecte les écarts de typage).

## Conventions
- Toute nouvelle feature doit être associée à un ID `T*` et documentée ici (commande + type + statut).
- Les tests manuels sont explicitement signalés ; ils nécessitent une capture rapide dans la PR associée.
- Le registre doit rester synchronisé avec `docs/features/<feature>.md` : si une commande change, mettre à jour les deux endroits.
