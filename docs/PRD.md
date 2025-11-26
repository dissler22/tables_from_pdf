# PRD – Extracteur de tableaux PDF (v0 simple)

## Vision courte
- **But final** : outil local/CLI pour extraire proprement les tableaux de PDF et les exporter en CSV/Parquet/Excel, sans dépendance réseau.
- **Cœur du projet** : utiliser GMFT en mode lattice (détection de lignes) pour reconstruire les grilles, éviter l’OCR tant que les PDF sont natifs, produire des artefacts de debug (images annotées, JSON de cellules) et des exports structurés.
- **Périmètre v0 (unique feature)** : extraire correctement les tableaux du fichier de référence `tests/data_test/pdf_tables/test1.pdf`, qui contient un tableau principal (6 colonnes) et un tableau de pied (10 colonnes) sur la page 1.

## Feature v0 — Extraction ciblée `test1.pdf`
- **Entrée** : `tests/data_test/pdf_tables/test1.pdf`, page 1.
- **Sorties attendues** :
  - Table principale (en-tête Indice/Date/Modifications/Rédacteur/Vérificateur/Approbateur) avec la ligne `A | 10/01/2023 | Création du document | L. DROUVIN | L. DROUVIN | T. DEVINS`.
  - Table de pied (bandeau bleu) avec les 10 champs `SOCIETE | AXE | POINT DE REPERE | PHASE | DOMAINE | NOM D'OUVRAGE | SENS | DOCUMENT | NUMERO D'ORDRE | INDICE` et la ligne `ESC | A57 | 000675 | EXE | GEN | 0-0000 | SS | JDC | 5108 | A`.
  - Artefacts de debug : image annotée et JSON des cellules détectées.
- **Pipeline minimal** :
  1) Chargement PDF natif, pas d’OCR.
  2) Détection GMFT en mode lattice avec tolérance sur segments fins ; recadrage vertical pour ignorer le header graphique et viser la zone des tableaux.
  3) Séparation explicite des deux tableaux (principal vs pied) avant export.
  4) Export CSV/JSON des deux tables + sauvegarde des artefacts (image annotée).
- **Critères d’acceptation** :
  - Les deux tables sont extraites sans lignes vides ni colonnes parasites.
  - Les valeurs exactes ci-dessus apparaissent à la bonne colonne.
  - Les artefacts de debug sont produits et lisibles.

## Exécution et tests
- **Run local** : script/CLI à venir (`gmft-cli extract tests/data_test/pdf_tables/test1.pdf --page 1`).
- **Tests** : tests golden sur la page 1 comparant la sortie CSV/JSON aux goldens (table principale 6 colonnes, table pied 10 colonnes), plus vérification que les artefacts sont générés.
- **Env** : Python 3.12, dépendances GMFT + pdfplumber/pypdfium2 pour debug ; OCR désactivé par défaut.

## Prochaines extensions (post-v0)
- Généraliser à d’autres PDF multi-pages, ajouter profils de nettoyage (YAML), activer OCR uniquement pour scans.
- Ajouter ingestion CLI multi-fichiers et exports multiples (Parquet/Excel).
- Enrichir la recherche locale (`kv_store`) et métriques minimales.
