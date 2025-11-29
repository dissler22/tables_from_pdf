"""Test fusion bi-page avec nouvelle logique."""
import sys
sys.path.insert(0, 'src')
from pathlib import Path

from table_extractor import TableExtractionPipeline, PipelineConfig, ExtractionMode

pdf_path = Path('data/upload/ESC_A57_000675_EXE_GEN_0-0000_SS_JDC_5108_A_Journaux_de_chantier_2023_S01.pdf')

# Pages 11 et 12 (index 10 et 11)
config = PipelineConfig(
    mode=ExtractionMode.ACCURATE,
    pages=[10, 11],
    output_format=["json"],
    save_images=False,
)

pipeline = TableExtractionPipeline(config)
result = pipeline.extract(str(pdf_path), output_dir='data/output/test_bipage')

print(f"Tables extraites: {len(result.tables)}")
for t in result.tables:
    print(f"\n  Page {t.page_number + 1}, table {t.table_index}")
    print(f"  Lignes: {len(t.raw_data)}")
    if t.raw_data:
        print(f"  Première ligne: {t.raw_data[0][:3]}...")
        print(f"  Dernière ligne: {t.raw_data[-1][:3]}...")


