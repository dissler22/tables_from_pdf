"""
Module de détection de tableaux utilisant Table Transformer (Microsoft)

Ce module utilise le modèle DETR pré-entraîné de Microsoft pour détecter
les tableaux dans les images de pages PDF.
"""

from typing import List, Optional, Tuple
from PIL import Image
import torch
from dataclasses import dataclass

from .utils import BoundingBox


@dataclass
class DetectorConfig:
    """Configuration du détecteur de tableaux"""
    model_name: str = "microsoft/table-transformer-detection"
    device: str = "auto"  # "auto", "cpu", "cuda"
    confidence_threshold: float = 0.7
    nms_threshold: float = 0.5  # Non-Maximum Suppression


class TableDetector:
    """
    Détecteur de tableaux basé sur Table Transformer (DETR)
    
    Utilise le modèle microsoft/table-transformer-detection pour
    détecter les tableaux dans les images de pages PDF.
    """
    
    def __init__(self, config: Optional[DetectorConfig] = None):
        """
        Initialise le détecteur
        
        Args:
            config: Configuration du détecteur (optionnel)
        """
        self.config = config or DetectorConfig()
        self._model = None
        self._processor = None
        self._device = None
        
    @property
    def device(self) -> torch.device:
        """Retourne le device utilisé"""
        if self._device is None:
            if self.config.device == "auto":
                self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            else:
                self._device = torch.device(self.config.device)
        return self._device
    
    def _load_model(self):
        """Charge le modèle si nécessaire"""
        if self._model is None:
            from transformers import AutoModelForObjectDetection, AutoImageProcessor
            
            print(f"Chargement du modèle {self.config.model_name}...")
            self._processor = AutoImageProcessor.from_pretrained(self.config.model_name)
            self._model = AutoModelForObjectDetection.from_pretrained(self.config.model_name)
            self._model.to(self.device)
            self._model.eval()
            print(f"Modèle chargé sur {self.device}")
    
    def detect(self, image: Image.Image) -> List[BoundingBox]:
        """
        Détecte les tableaux dans une image
        
        Args:
            image: Image PIL de la page
            
        Returns:
            Liste de BoundingBox des tableaux détectés
        """
        self._load_model()
        
        # Convertir en RGB si nécessaire
        if image.mode != "RGB":
            image = image.convert("RGB")
        
        # Préparer l'image pour le modèle
        inputs = self._processor(images=image, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        # Inférence
        with torch.no_grad():
            outputs = self._model(**inputs)
        
        # Post-traitement
        target_sizes = torch.tensor([image.size[::-1]]).to(self.device)  # (height, width)
        results = self._processor.post_process_object_detection(
            outputs, 
            threshold=self.config.confidence_threshold,
            target_sizes=target_sizes
        )[0]
        
        # Convertir en BoundingBox
        boxes = []
        for score, label, box in zip(results["scores"], results["labels"], results["boxes"]):
            bbox = BoundingBox(
                x1=box[0].item(),
                y1=box[1].item(),
                x2=box[2].item(),
                y2=box[3].item(),
                confidence=score.item(),
                label=self._model.config.id2label[label.item()]
            )
            boxes.append(bbox)
        
        # Appliquer NMS si plusieurs détections
        if len(boxes) > 1:
            boxes = self._apply_nms(boxes)
        
        return boxes
    
    def detect_batch(self, images: List[Image.Image]) -> List[List[BoundingBox]]:
        """
        Détecte les tableaux dans plusieurs images
        
        Args:
            images: Liste d'images PIL
            
        Returns:
            Liste de listes de BoundingBox (une liste par image)
        """
        results = []
        for image in images:
            boxes = self.detect(image)
            results.append(boxes)
        return results
    
    def _apply_nms(self, boxes: List[BoundingBox]) -> List[BoundingBox]:
        """
        Applique Non-Maximum Suppression pour éliminer les détections redondantes
        """
        if not boxes:
            return boxes
        
        # Trier par confidence décroissante
        boxes = sorted(boxes, key=lambda b: b.confidence, reverse=True)
        
        keep = []
        while boxes:
            best = boxes.pop(0)
            keep.append(best)
            
            # Filtrer les boxes qui ont un IoU élevé avec la meilleure
            boxes = [
                b for b in boxes 
                if self._compute_iou(best, b) < self.config.nms_threshold
            ]
        
        return keep
    
    @staticmethod
    def _compute_iou(box1: BoundingBox, box2: BoundingBox) -> float:
        """Calcule l'Intersection over Union entre deux boxes"""
        x1 = max(box1.x1, box2.x1)
        y1 = max(box1.y1, box2.y1)
        x2 = min(box1.x2, box2.x2)
        y2 = min(box1.y2, box2.y2)
        
        if x2 < x1 or y2 < y1:
            return 0.0
        
        intersection = (x2 - x1) * (y2 - y1)
        union = box1.area + box2.area - intersection
        
        return intersection / union if union > 0 else 0.0


class TableStructureRecognizer:
    """
    Reconnaissance de structure de tableaux avec Table Transformer
    
    Utilise microsoft/table-transformer-structure-recognition pour
    identifier les lignes, colonnes et cellules d'un tableau.
    """
    
    def __init__(self, device: str = "auto", confidence_threshold: float = 0.6):
        self.model_name = "microsoft/table-transformer-structure-recognition"
        self.confidence_threshold = confidence_threshold
        self._model = None
        self._processor = None
        
        if device == "auto":
            self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self._device = torch.device(device)
    
    def _load_model(self):
        """Charge le modèle si nécessaire"""
        if self._model is None:
            from transformers import AutoModelForObjectDetection, AutoImageProcessor
            
            print(f"Chargement du modèle {self.model_name}...")
            self._processor = AutoImageProcessor.from_pretrained(self.model_name)
            self._model = AutoModelForObjectDetection.from_pretrained(self.model_name)
            self._model.to(self._device)
            self._model.eval()
            print(f"Modèle de structure chargé sur {self._device}")
    
    def recognize(self, table_image: Image.Image) -> dict:
        """
        Reconnaît la structure d'un tableau
        
        Args:
            table_image: Image du tableau découpé
            
        Returns:
            Dictionnaire avec les éléments structurels détectés
        """
        self._load_model()
        
        if table_image.mode != "RGB":
            table_image = table_image.convert("RGB")
        
        inputs = self._processor(images=table_image, return_tensors="pt")
        inputs = {k: v.to(self._device) for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = self._model(**inputs)
        
        target_sizes = torch.tensor([table_image.size[::-1]]).to(self._device)
        results = self._processor.post_process_object_detection(
            outputs,
            threshold=self.confidence_threshold,
            target_sizes=target_sizes
        )[0]
        
        # Organiser par type d'élément
        structure = {
            "rows": [],
            "columns": [],
            "cells": [],
            "headers": []
        }
        
        label_map = self._model.config.id2label
        
        for score, label, box in zip(results["scores"], results["labels"], results["boxes"]):
            label_name = label_map[label.item()]
            bbox = BoundingBox(
                x1=box[0].item(),
                y1=box[1].item(),
                x2=box[2].item(),
                y2=box[3].item(),
                confidence=score.item(),
                label=label_name
            )
            
            if "row" in label_name.lower():
                structure["rows"].append(bbox)
            elif "column" in label_name.lower():
                structure["columns"].append(bbox)
            elif "cell" in label_name.lower():
                structure["cells"].append(bbox)
            elif "header" in label_name.lower():
                structure["headers"].append(bbox)
        
        # Trier les lignes et colonnes
        structure["rows"] = sorted(structure["rows"], key=lambda b: b.y1)
        structure["columns"] = sorted(structure["columns"], key=lambda b: b.x1)
        
        return structure

