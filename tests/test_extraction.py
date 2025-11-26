"""
Tests pour le module d'extraction de tableaux
"""

import pytest
import sys
from pathlib import Path

# Ajouter src au path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from table_extractor import TableExtractionPipeline, TableDetector, TableStructureExtractor
from table_extractor.pipeline import PipelineConfig, ExtractionMode
from table_extractor.utils import BoundingBox, ExtractedTable, pdf_to_images


# Chemins des fichiers de test
TEST_PDF = Path(__file__).parent / "data_test" / "pdf_tables" / "test1.pdf"
UPLOAD_DIR = Path(__file__).parent.parent / "data" / "upload"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "output"


class TestUtils:
    """Tests des utilitaires"""
    
    def test_bounding_box_properties(self):
        """Test des propriétés de BoundingBox"""
        bbox = BoundingBox(x1=10, y1=20, x2=110, y2=120)
        
        assert bbox.width == 100
        assert bbox.height == 100
        assert bbox.area == 10000
        assert bbox.center == (60, 70)
    
    def test_bounding_box_to_dict(self):
        """Test de la sérialisation"""
        bbox = BoundingBox(x1=10, y1=20, x2=110, y2=120, confidence=0.95)
        d = bbox.to_dict()
        
        assert d["x1"] == 10
        assert d["confidence"] == 0.95
    
    def test_pdf_to_images(self):
        """Test de la conversion PDF -> images"""
        if not TEST_PDF.exists():
            pytest.skip(f"Fichier de test non trouvé: {TEST_PDF}")
        
        images = pdf_to_images(TEST_PDF, dpi=100)
        
        assert len(images) > 0
        assert images[0].mode in ("RGB", "RGBA")


class TestTableDetector:
    """Tests du détecteur de tableaux"""
    
    @pytest.fixture
    def detector(self):
        """Crée un détecteur de tableaux"""
        from table_extractor.detector import DetectorConfig
        return TableDetector(config=DetectorConfig(confidence_threshold=0.5))
    
    def test_detector_initialization(self, detector):
        """Test de l'initialisation"""
        assert detector.config is not None
        assert detector.config.confidence_threshold == 0.5
    
    def test_detect_on_test_pdf(self, detector):
        """Test de détection sur le PDF de test"""
        if not TEST_PDF.exists():
            pytest.skip(f"Fichier de test non trouvé: {TEST_PDF}")
        
        images = pdf_to_images(TEST_PDF, dpi=150)
        
        # Tester sur la première page
        detections = detector.detect(images[0])
        
        # Vérifier le format des résultats
        assert isinstance(detections, list)
        for bbox in detections:
            assert isinstance(bbox, BoundingBox)
            assert bbox.x1 < bbox.x2
            assert bbox.y1 < bbox.y2


class TestTableStructureExtractor:
    """Tests de l'extracteur de structure"""
    
    @pytest.fixture
    def extractor(self):
        """Crée un extracteur"""
        return TableStructureExtractor(
            ocr_engine="tesseract",
            ocr_lang="fra+eng"
        )
    
    def test_extractor_initialization(self, extractor):
        """Test de l'initialisation"""
        assert extractor.ocr_engine == "tesseract"
        assert extractor.ocr_lang == "fra+eng"
    
    def test_extract_from_pdf(self, extractor):
        """Test d'extraction directe depuis PDF"""
        if not TEST_PDF.exists():
            pytest.skip(f"Fichier de test non trouvé: {TEST_PDF}")
        
        tables = extractor.extract_from_pdf(TEST_PDF, pages=[0])
        
        assert isinstance(tables, list)
        for table in tables:
            assert isinstance(table, ExtractedTable)
            assert table.page_number >= 0


class TestPipeline:
    """Tests du pipeline complet"""
    
    @pytest.fixture
    def pipeline_fast(self):
        """Pipeline en mode fast"""
        config = PipelineConfig(
            mode=ExtractionMode.FAST,
            ocr_engine="tesseract",
            dpi=150,
            pages=[0],  # Première page seulement
            save_images=False,
        )
        return TableExtractionPipeline(config)
    
    @pytest.fixture
    def pipeline_accurate(self):
        """Pipeline en mode accurate"""
        config = PipelineConfig(
            mode=ExtractionMode.ACCURATE,
            ocr_engine="tesseract",
            dpi=150,
            pages=[0],
            save_images=False,
        )
        return TableExtractionPipeline(config)
    
    def test_pipeline_fast_mode(self, pipeline_fast):
        """Test du pipeline en mode fast"""
        if not TEST_PDF.exists():
            pytest.skip(f"Fichier de test non trouvé: {TEST_PDF}")
        
        result = pipeline_fast.extract(TEST_PDF)
        
        assert result is not None
        assert result.pdf_path == str(TEST_PDF)
        assert isinstance(result.tables, list)
    
    def test_pipeline_accurate_mode(self, pipeline_accurate):
        """Test du pipeline en mode accurate"""
        if not TEST_PDF.exists():
            pytest.skip(f"Fichier de test non trouvé: {TEST_PDF}")
        
        result = pipeline_accurate.extract(TEST_PDF)
        
        assert result is not None
        assert result.pdf_path == str(TEST_PDF)
    
    def test_pipeline_with_output(self, pipeline_fast, tmp_path):
        """Test du pipeline avec sauvegarde"""
        if not TEST_PDF.exists():
            pytest.skip(f"Fichier de test non trouvé: {TEST_PDF}")
        
        result = pipeline_fast.extract(TEST_PDF, output_dir=tmp_path)
        
        # Vérifier que le JSON a été créé
        output_subdir = tmp_path / TEST_PDF.stem
        if result.tables:
            assert (output_subdir / "tables.json").exists()


class TestIntegration:
    """Tests d'intégration sur les PDFs réels"""
    
    def test_extract_journaux_chantier(self):
        """Test sur le PDF des journaux de chantier"""
        pdf_path = UPLOAD_DIR / "ESC_A57_000675_EXE_GEN_0-0000_SS_JDC_5108_A_Journaux_de_chantier_2023_S01.pdf"
        
        if not pdf_path.exists():
            pytest.skip(f"PDF non trouvé: {pdf_path}")
        
        config = PipelineConfig(
            mode=ExtractionMode.ACCURATE,
            ocr_engine="tesseract",
            ocr_lang="fra",
            dpi=200,
            pages=[0, 1],  # Premières pages seulement
            save_images=True,
        )
        
        pipeline = TableExtractionPipeline(config)
        result = pipeline.extract(pdf_path, OUTPUT_DIR)
        
        assert result is not None
        print(f"\n📊 Résultat: {len(result.tables)} tableaux extraits")
        
        for table in result.tables:
            print(f"   Page {table.page_number + 1}: {table.num_rows}x{table.num_cols}")
    
    def test_extract_sdp(self):
        """Test sur le PDF SDP"""
        pdf_path = UPLOAD_DIR / "SDP Série D Ind A.pdf"
        
        if not pdf_path.exists():
            pytest.skip(f"PDF non trouvé: {pdf_path}")
        
        config = PipelineConfig(
            mode=ExtractionMode.ACCURATE,
            ocr_engine="tesseract",
            ocr_lang="fra",
            dpi=200,
            pages=[0, 1, 2],
            save_images=True,
        )
        
        pipeline = TableExtractionPipeline(config)
        result = pipeline.extract(pdf_path, OUTPUT_DIR)
        
        assert result is not None
        print(f"\n📊 Résultat: {len(result.tables)} tableaux extraits")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

