# Pipeline d'extraction v2

## Vue d'ensemble

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           TableExtractionPipeline                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────┐    ┌──────────────┐    ┌─────────────┐    ┌──────────────┐   │
│   │   PDF   │───▶│  Rendu Image │───▶│  Détection  │───▶│  Extraction  │   │
│   │ (natif) │    │  (pdf2image) │    │   (DETR)    │    │ (pdfplumber) │   │
│   └─────────┘    └──────────────┘    └─────────────┘    └──────────────┘   │
│                                              │                   │          │
│                                              ▼                   ▼          │
│                                      ┌─────────────┐    ┌──────────────┐   │
│                                      │   Guidage   │    │    Fusion    │   │
│                                      │   Visuel    │    │ Multi-pages  │   │
│                                      └─────────────┘    └──────────────┘   │
│                                                                  │          │
│                                                                  ▼          │
│                                                         ┌──────────────┐   │
│                                                         │    Export    │   │
│                                                         │  JSON / CSV  │   │
│                                                         └──────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Étapes du pipeline

### 1. Chargement PDF
- Le PDF est chargé et converti en images (une par page)
- Résolution configurable via `dpi` (défaut: 200)
- Filtre optionnel sur les pages (`pages=[0, 1, 2]`)

### 2. Détection des tableaux

**Mode ACCURATE (recommandé pour ESC/SDP):**
- **Stratégie 1** : `pdfplumber` directement sur le PDF natif
  - Plus fiable pour les PDFs avec texte extractible
  - Pas besoin d'OCR ni de détection visuelle
  - Utilisé par défaut quand le PDF est natif

- **Stratégie 2** (fallback) : DETR + Guidage visuel
  - Modèle `microsoft/table-transformer-detection`
  - Guidage visuel via détection des bandes colorées (alternance blanc/bleu)
  - Utilisé si pdfplumber échoue ou pour les scans

**Mode FAST:**
- `img2table` directement sur les images
- Plus rapide mais moins précis

### 3. Extraction du contenu

**Pour PDFs natifs (pdfplumber):**
```python
import pdfplumber

with pdfplumber.open(pdf_path) as pdf:
    page = pdf.pages[page_number]
    tables = page.find_tables()
    for table in tables:
        data = table.extract()  # Liste de listes
```

**Pour scans (img2table + OCR):**
- Découpe de l'image selon les bboxes détectées
- Extraction via `img2table` avec OCR (tesseract/paddleocr)

### 4. Fusion multi-pages

Détection automatique des tableaux qui continuent sur plusieurs pages :

```python
def _is_continuation_table(table):
    """Un tableau est une continuation si:
    1. La 1ère ligne contient un header de page (pas des colonnes)
    2. Ou la 1ère cellule est vide
    """
    first_row = table.raw_data[0]
    
    # Header de page = "Guintoli - EHTP...", "Journaux de chantier..."
    if _is_page_header_row(first_row):
        return True
    
    return False
```

**Critères de fusion:**
- Page N+1 est une continuation de page N
- Même nombre de colonnes
- Pas d'en-têtes de colonnes (juste header de page)

**Résultat:**
- Les données sont concaténées
- L'en-tête du premier tableau est conservé
- Le header de page des continuations est ignoré

### 5. Post-traitement

Module `postprocess.py` avec fonctions génériques :

| Fonction | Description |
|----------|-------------|
| `clean_empty_rows()` | Supprime lignes >95% vides |
| `clean_footer_rows()` | Supprime pieds de page (visa, événements) |
| `clean_repeated_headers()` | Nettoie les jours fériés avec en-têtes répétés |
| `merge_multipage_tables()` | Fusionne tableaux multi-pages |

### 6. Export

- **JSON** : `tables.json` avec toutes les tables
- **CSV** : Un fichier par tableau (`page{n}_table{m}.csv`)
- **Images** : Pages annotées avec bboxes (`page{n}_annotated.png`)

## Configuration

```python
from table_extractor import TableExtractionPipeline, PipelineConfig, ExtractionMode

config = PipelineConfig(
    mode=ExtractionMode.ACCURATE,  # FAST, ACCURATE, HYBRID
    ocr_engine=None,               # None pour PDF natif, "tesseract" pour scans
    dpi=200,                       # Résolution de rendu
    pages=[0, 1, 2],               # Pages à extraire (None = toutes)
    output_format=["json", "csv"], # Formats de sortie
    save_images=True,              # Sauvegarder images annotées
)

pipeline = TableExtractionPipeline(config)
result = pipeline.extract("document.pdf", output_dir="output/")
```

## Modules

```
src/table_extractor/
├── __init__.py          # Exports + lazy loading
├── pipeline.py          # TableExtractionPipeline (orchestration)
├── detector.py          # TableDetector (DETR)
├── extractor.py         # TableStructureExtractor, PdfPlumberExtractor
├── sdp_extractor.py     # SDPExtractor (calibration dynamique)
├── visual_guide.py      # VisualGuide (détection bandes colorées)
├── postprocess.py       # Nettoyage + fusion multi-pages
└── utils.py             # BoundingBox, ExtractedTable, helpers
```

### SDPExtractor - Architecture

```
SDPExtractor
├── extract_page(pdf, page_num)
│   ├── _group_by_lines(words)           # Grouper mots par Y
│   ├── _calibrate_columns_from_formula_line()  # Calibrer X
│   └── _parse_lines(lines)              # Parser lignes
│       ├── _parse_row(words)            # → SDPRow
│       └── _parse_recap_line(text)      # → SDPRecap
│
├── SDPRow                               # Dataclass: 12 colonnes + métadonnées
├── SDPRecap                             # Dataclass: A/B totaux, K1-K6, prix
└── SDPPage                              # Dataclass: rows + recap + raw_text
```

## Dépendances

**Essentielles:**
- `pdfplumber` : Extraction directe PDF natif
- `pdf2image` : Conversion PDF → images
- `Pillow` : Manipulation images

**Optionnelles (pour scans/détection avancée):**
- `torch` + `transformers` : Modèle DETR
- `opencv-python` : Guidage visuel
- `img2table` : Extraction depuis images

## Tests

```bash
# Activer l'environnement
.\.venv_win\Scripts\Activate.ps1

# Test de régression page 2 ESC
python -m pytest tests/test_extract_esc_page2.py -v

# Test manuel
python -c "
from table_extractor import TableExtractionPipeline, PipelineConfig, ExtractionMode
pipe = TableExtractionPipeline(PipelineConfig(mode=ExtractionMode.ACCURATE, pages=[1]))
result = pipe.extract('data/upload/ESC_...pdf', output_dir='data/output/test')
print(f'{len(result.tables)} tables extraites')
"
```

## Extracteur SDP spécialisé

Pour les documents SDP (Sous-Détail de Prix), un extracteur dédié `SDPExtractor` :

```python
from table_extractor.sdp_extractor import SDPExtractor

extractor = SDPExtractor()
page = extractor.extract_page(pdf_path, page_number=0)

# Données structurées
for row in page.rows:
    print(f"{row.composantes_du_prix}: {row.montant_part_propre}")

# Récapitulatif
if page.recap:
    print(f"TOTAL 5: {page.recap.total_5}")
    print(f"K1 ({page.recap.k1_pct}): {page.recap.k1_montant}")
```

### Fonctionnalités SDP

| Fonctionnalité | Description |
|----------------|-------------|
| Calibration dynamique | Positions X calibrées via ligne formules `a b 1=axb...` |
| Groupement par proximité | Mots proches (<12px) groupés ensemble |
| Séparation unités | `h`, `m3`, `t` extraits automatiquement |
| Récap A/B | TOTAL 5/7, K1-K6, prix final |
| Nettoyage montants | Espaces supprimés, € normalisés |

## Limites actuelles

- **Fusion multi-pages** : Basée sur la détection d'absence d'en-têtes de colonnes
- **Guidage visuel** : Implémenté mais non utilisé par défaut (pdfplumber suffit)
- **SDP** : Légères variations de position X entre pages (calibration par page)
- **OCR** : Non testé sur scans (prévu pour v3)

## Prochaines étapes

1. [x] ~~Tester sur SDP~~ → SDPExtractor implémenté
2. [x] ~~Calibration dynamique colonnes~~ → Détection ligne formules
3. [ ] Ajouter goldens pour autres pages ESC
4. [ ] Support scans avec OCR

