# Feature — Extraction v0 (test1.pdf)

## Objectif
Extraire correctement deux tableaux présents sur la page 1 du PDF de référence `tests/data_test/pdf_tables/test1.pdf` :
- Table principale : en-tête `Indice | Date | Modifications | Rédacteur | Vérificateur | Approbateur` et la ligne `A | 10/01/2023 | Création du document | L. DROUVIN | L. DROUVIN | T. DEVINS`.
- Table de pied : en-tête `SOCIETE | AXE | POINT DE REPERE | PHASE | DOMAINE | NOM D'OUVRAGE | SENS | DOCUMENT | NUMERO D'ORDRE | INDICE` et la ligne `ESC | A57 | 000675 | EXE | GEN | 0-0000 | SS | JDC | 5108 | A`.

## Implémentation
- Détecteur : GMFT avec le détecteur `img2table` (mode natif, pas d'OCR).
- Post-traitement :
  - Nettoyage texte (espaces, ponctuation, initiales, normalisation de `INDICE`).
  - Heuristique de split par en-têtes : détection des lignes d'en-tête et alignement des colonnes par positions trouvées.
  - Artefacts générés : `page1_annotated.png` avec bboxes des tables, et `tables.json` listant les cellules et bboxes.
- Code : `back/extractor.py` (fonction `extract_tables`).

## Tests
- Test automatisé : `PYTHONPATH=. .venv_linux/bin/python3 -m pytest tests/test_extract_test1.py`
  - Compare les tables extraites aux goldens `tests/goldens/test1_main.*` et `tests/goldens/test1_footer.*`.
  - Vérifie la présence des artefacts JSON/PNG.
- Données : `tests/data_test/pdf_tables/test1.pdf` + goldens dans `tests/goldens/`.

## Pré-requis
- Environnement Python 3.12 (virtualenv `.venv_linux`).
- `pip install -r requirements.txt` (roues CPU pour torch et dépendances GMFT/img2table).
- Variable suggérée pour éviter les warnings Matplotlib : `MPLCONFIGDIR=/tmp/mplconfig` lors des runs.

## Limites connues
- Heuristique calibrée sur `test1.pdf` (en-têtes spécifiques, page unique). Pour d'autres PDFs, il faudra généraliser (multi-pages, OCR si scans, détection multi-table sans en-têtes fixes).
- Les bboxes proviennent du détecteur et servent surtout à tracer l'artefact ; aucun calcul de confiance n'est encore exposé.
