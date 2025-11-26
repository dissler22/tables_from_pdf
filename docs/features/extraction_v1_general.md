# Feature — Extraction v1 (généralisation)

## Objectif
Passer d'une heuristique spécifique à `test1.pdf` à une extraction plus générique :
- Supporter plusieurs tables détectées par GMFT/img2table sur une page, avec segmentation par en-têtes.
- Conserver la compatibilité avec les goldens v0 (test1.pdf) et préparer le terrain pour d'autres PDFs (y compris multi-pages et structures différentes).
- Rester en mode natif (pas d'OCR) tant que les PDFs sont digitaux ; activer OCR ultérieurement si des scans sont ajoutés.

## Implémentation
- Détecteur : GMFT `Img2TableDetector`.
- Post-traitement générique :
  - Nettoyage texte (espaces, ponctuation, initiales, normalisation de `INDICE`).
  - Détection d'en-têtes par présence de tokens (ex. `Indice/Date/Modifications` ou `SOCIETE/AXE/INDICE`), alignement des colonnes par positions trouvées, extraction des lignes qui suivent.
  - Fallback : si aucune en-tête reconnue, la table GMFT brute est retournée telle quelle.
  - Artefacts : PNG annotées et `tables.json` par run.
- Code : `back/extractor.py` (fonction `extract_tables`).

## Tests
- Réutilise le test T1 (v0) : `PYTHONPATH=. .venv_linux/bin/python3 -m pytest tests/test_extract_test1.py` — doit rester ✅.
- À ajouter (prochain incrément) : goldens pour au moins une page de `data/upload/ESC_A57_000675_EXE_GEN_0-0000_SS_JDC_5108_A_Journaux_de_chantier_2023_S01.pdf` et `data/upload/SDP Série D Ind A.pdf`.

## Pré-requis
- Python 3.12, venv `.venv_linux`.
- `pip install -r requirements.txt` (roues CPU torch + deps GMFT/img2table).
- Optionnel : `MPLCONFIGDIR=/tmp/mplconfig` pour éviter les warnings Matplotlib.

## Limites
- Heuristique d'en-têtes encore basée sur tokens connus ; nécessite des goldens supplémentaires pour affiner sur d'autres structures ou scans.
- Pas d'OCR activé pour l'instant (mode natif seulement).
