"""
Module de guidage visuel pour améliorer la détection de tableaux.

Analyse les images de pages PDF pour détecter :
- Les bandes de couleur alternées (lignes de tableau)
- Les lignes horizontales/verticales (bordures)
- Les zones de texte alignées (colonnes)

Ces informations permettent de :
- Fusionner des bboxes fragmentées par DETR
- Corriger les limites des tableaux détectés
- Identifier la structure interne (lignes/colonnes)
"""

from typing import List, Tuple, Optional
from dataclasses import dataclass
import numpy as np
from PIL import Image

try:
    import cv2
except ImportError:
    cv2 = None

from .utils import BoundingBox


@dataclass
class ColorBand:
    """Une bande de couleur horizontale détectée."""
    y_start: int
    y_end: int
    color: str  # "white", "blue", "gray", etc.
    
    @property
    def height(self) -> int:
        return self.y_end - self.y_start
    
    @property
    def center_y(self) -> int:
        return (self.y_start + self.y_end) // 2


@dataclass
class TableRegion:
    """Région de tableau détectée par analyse visuelle."""
    x1: int
    y1: int
    x2: int
    y2: int
    row_positions: List[int]  # Positions Y des lignes
    confidence: float
    
    def to_bbox(self) -> BoundingBox:
        return BoundingBox(
            x1=self.x1, y1=self.y1, x2=self.x2, y2=self.y2,
            confidence=self.confidence, label="table"
        )


class VisualGuide:
    """
    Analyseur visuel pour guider la détection de tableaux.
    
    Utilise OpenCV pour analyser les images et détecter :
    - Alternance de couleurs (lignes du tableau)
    - Lignes horizontales (séparateurs)
    - Structure du tableau
    """
    
    def __init__(
        self,
        blue_threshold: Tuple[int, int, int] = (180, 200, 255),  # HSV bleu clair
        min_band_height: int = 10,
        min_table_rows: int = 3,
    ):
        """
        Args:
            blue_threshold: Seuil pour détecter le bleu (HSV)
            min_band_height: Hauteur minimale d'une bande de couleur
            min_table_rows: Nombre minimum de lignes pour un tableau
        """
        if cv2 is None:
            raise ImportError("opencv-python est requis. Installez-le avec: pip install opencv-python")
        
        self.blue_threshold = blue_threshold
        self.min_band_height = min_band_height
        self.min_table_rows = min_table_rows
    
    def analyze_page(self, image: Image.Image) -> List[TableRegion]:
        """
        Analyse une page pour détecter les régions de tableaux.
        
        Args:
            image: Image PIL de la page
            
        Returns:
            Liste de TableRegion détectées
        """
        # Convertir PIL -> numpy -> BGR (OpenCV)
        img_array = np.array(image)
        if len(img_array.shape) == 2:  # Grayscale
            img_bgr = cv2.cvtColor(img_array, cv2.COLOR_GRAY2BGR)
        elif img_array.shape[2] == 4:  # RGBA
            img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGBA2BGR)
        else:  # RGB
            img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        
        # Détecter les bandes colorées
        bands = self._detect_color_bands(img_bgr)
        
        # Grouper les bandes en régions de tableau
        regions = self._group_bands_to_tables(bands, img_bgr.shape[1], img_bgr.shape[0])
        
        return regions
    
    def _detect_color_bands(self, img_bgr: np.ndarray) -> List[ColorBand]:
        """
        Détecte les bandes horizontales de couleur.
        
        Cherche l'alternance blanc/bleu typique des tableaux.
        """
        height, width = img_bgr.shape[:2]
        
        # Convertir en HSV pour mieux détecter les couleurs
        img_hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
        
        # Créer un masque pour le bleu clair (typique des lignes de tableau)
        # Bleu clair : H=100-130, S=20-100, V=200-255
        lower_blue = np.array([90, 10, 180])
        upper_blue = np.array([130, 80, 255])
        mask_blue = cv2.inRange(img_hsv, lower_blue, upper_blue)
        
        # Créer un masque pour le gris clair (autre couleur possible)
        lower_gray = np.array([0, 0, 200])
        upper_gray = np.array([180, 30, 240])
        mask_gray = cv2.inRange(img_hsv, lower_gray, upper_gray)
        
        # Analyser ligne par ligne pour détecter les bandes
        bands = []
        current_band = None
        
        for y in range(height):
            # Calculer le pourcentage de pixels bleus/gris sur cette ligne
            row_blue = np.sum(mask_blue[y, :]) / (width * 255)
            row_gray = np.sum(mask_gray[y, :]) / (width * 255)
            
            # Seuil pour considérer la ligne comme colorée
            is_blue = row_blue > 0.3
            is_gray = row_gray > 0.5 and not is_blue
            is_white = not is_blue and not is_gray
            
            if is_blue:
                color = "blue"
            elif is_gray:
                color = "gray"
            else:
                color = "white"
            
            # Grouper en bandes
            if current_band is None:
                current_band = {"y_start": y, "color": color}
            elif current_band["color"] != color:
                # Fin de la bande précédente
                if y - current_band["y_start"] >= self.min_band_height:
                    bands.append(ColorBand(
                        y_start=current_band["y_start"],
                        y_end=y,
                        color=current_band["color"]
                    ))
                current_band = {"y_start": y, "color": color}
        
        # Dernière bande
        if current_band and height - current_band["y_start"] >= self.min_band_height:
            bands.append(ColorBand(
                y_start=current_band["y_start"],
                y_end=height,
                color=current_band["color"]
            ))
        
        return bands
    
    def _group_bands_to_tables(
        self,
        bands: List[ColorBand],
        img_width: int,
        img_height: int,
    ) -> List[TableRegion]:
        """
        Groupe les bandes de couleur en régions de tableau.
        
        Un tableau est détecté quand on a une alternance de couleurs.
        """
        if not bands:
            return []
        
        regions = []
        current_group = []
        last_color = None
        
        for band in bands:
            # Détecter l'alternance
            if last_color is None or band.color != last_color:
                current_group.append(band)
                last_color = band.color
            else:
                # Même couleur deux fois de suite = fin du groupe
                if len(current_group) >= self.min_table_rows:
                    region = self._create_region(current_group, img_width)
                    if region:
                        regions.append(region)
                current_group = [band]
                last_color = band.color
        
        # Dernier groupe
        if len(current_group) >= self.min_table_rows:
            region = self._create_region(current_group, img_width)
            if region:
                regions.append(region)
        
        return regions
    
    def _create_region(
        self,
        bands: List[ColorBand],
        img_width: int,
    ) -> Optional[TableRegion]:
        """Crée une TableRegion à partir d'un groupe de bandes."""
        if not bands:
            return None
        
        y_start = bands[0].y_start
        y_end = bands[-1].y_end
        
        # Positions des lignes = centres des bandes
        row_positions = [band.center_y for band in bands]
        
        # Confidence basée sur le nombre de lignes alternées
        alternating_count = sum(
            1 for i in range(1, len(bands))
            if bands[i].color != bands[i-1].color
        )
        confidence = min(1.0, alternating_count / (len(bands) - 1)) if len(bands) > 1 else 0.5
        
        return TableRegion(
            x1=0,
            y1=y_start,
            x2=img_width,
            y2=y_end,
            row_positions=row_positions,
            confidence=confidence,
        )
    
    def merge_bboxes(
        self,
        detr_boxes: List[BoundingBox],
        visual_regions: List[TableRegion],
        iou_threshold: float = 0.3,
    ) -> List[BoundingBox]:
        """
        Fusionne les bboxes DETR avec les régions visuelles.
        
        Si plusieurs bboxes DETR chevauchent une même région visuelle,
        elles sont fusionnées en une seule bbox.
        
        Args:
            detr_boxes: Bboxes détectées par DETR
            visual_regions: Régions détectées par analyse visuelle
            iou_threshold: Seuil de chevauchement pour la fusion
            
        Returns:
            Liste de bboxes fusionnées
        """
        if not visual_regions:
            return detr_boxes
        
        if not detr_boxes:
            return [r.to_bbox() for r in visual_regions]
        
        merged = []
        used_detr = set()
        
        for region in visual_regions:
            # Trouver les bboxes DETR qui chevauchent cette région
            overlapping = []
            for i, box in enumerate(detr_boxes):
                if i in used_detr:
                    continue
                
                iou = self._compute_iou(box, region)
                if iou > iou_threshold or self._is_inside(box, region):
                    overlapping.append((i, box))
                    used_detr.add(i)
            
            if overlapping:
                # Fusionner toutes les bboxes qui chevauchent cette région
                x1 = min(box.x1 for _, box in overlapping)
                y1 = min(box.y1 for _, box in overlapping)
                x2 = max(box.x2 for _, box in overlapping)
                y2 = max(box.y2 for _, box in overlapping)
                
                # Ajuster avec la région visuelle
                y1 = min(y1, region.y1)
                y2 = max(y2, region.y2)
                
                confidence = max(box.confidence for _, box in overlapping)
                
                merged.append(BoundingBox(
                    x1=x1, y1=y1, x2=x2, y2=y2,
                    confidence=confidence,
                    label="table"
                ))
            else:
                # Aucune bbox DETR, utiliser la région visuelle
                merged.append(region.to_bbox())
        
        # Ajouter les bboxes DETR non utilisées
        for i, box in enumerate(detr_boxes):
            if i not in used_detr:
                merged.append(box)
        
        return merged
    
    def _compute_iou(self, box: BoundingBox, region: TableRegion) -> float:
        """Calcule l'IoU entre une bbox et une région."""
        x1 = max(box.x1, region.x1)
        y1 = max(box.y1, region.y1)
        x2 = min(box.x2, region.x2)
        y2 = min(box.y2, region.y2)
        
        if x2 < x1 or y2 < y1:
            return 0.0
        
        intersection = (x2 - x1) * (y2 - y1)
        
        box_area = (box.x2 - box.x1) * (box.y2 - box.y1)
        region_area = (region.x2 - region.x1) * (region.y2 - region.y1)
        union = box_area + region_area - intersection
        
        return intersection / union if union > 0 else 0.0
    
    def _is_inside(self, box: BoundingBox, region: TableRegion) -> bool:
        """Vérifie si la bbox est majoritairement à l'intérieur de la région."""
        # Vérifier si le centre de la bbox est dans la région
        center_x = (box.x1 + box.x2) / 2
        center_y = (box.y1 + box.y2) / 2
        
        return (region.x1 <= center_x <= region.x2 and
                region.y1 <= center_y <= region.y2)

