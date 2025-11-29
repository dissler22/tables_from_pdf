"""Extraction test pages 55-56"""
import sys
sys.path.insert(0, 'src')
from pathlib import Path

from table_extractor import TableExtractionPipeline, PipelineConfig, ExtractionMode

pdf_path = Path('data/upload/ESC_A57_000675_EXE_GEN_0-0000_SS_JDC_5108_A_Journaux_de_chantier_2023_S01.pdf')

config = PipelineConfig(
    mode=ExtractionMode.ACCURATE,
    pages=[54, 55],  # pages 55-56
    output_format=["json"],
    save_images=False,
)

pipeline = TableExtractionPipeline(config)
result = pipeline.extract(str(pdf_path), output_dir='data/output/test_p55_56')

print(f"Tables extraites: {len(result.tables)}")
for t in result.tables:
    print(f"\nPage {t.page_number + 1}, table {t.table_index}, lignes={len(t.raw_data)}")
    if t.raw_data:
        print("  Premiere ligne:", t.raw_data[0])
        print("  Derniere ligne:", t.raw_data[-1])
