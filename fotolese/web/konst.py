"""fotolese.web.konst – Konstanten, Muster, Monatsnamen und Quellen der Drittmodelle."""
import re

from PIL import Image, ImageFile

from fotolese.gemein import MAX_ORDNER, ORDNER_MUSTER, ORDNER_RE  # Ordnernamen wie in fotosort


VERSION = "2.8.0"
BILD_EXT = {".jpg", ".jpeg", ".png"}
BESTOF_MUSTER = re.compile(rf"({ORDNER_RE})([a-z]?)\.(jpg|png)")  # 0042.jpg, 0042a.jpg, 12345b.png
PAPIERKORB = "Musor"  # Unterordner von SORTIERT; fotosort und bestof lesen nur Ordner 0001–99999
VERBESSERT = "verbessert"  # Unterordner eines Ordners 0001–99999 für die mit ComfyUI verbesserten Fassungen
KOLORIERT = "koloriert"  # Endung der kolorierten Fassung: <Name>_<Workflow>_koloriert.png
BUCHSTABEN = "abcdefghijklmnopqrstuvwxyz"
THUMB = 480
MONATE = ["", "Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September",
          "Oktober", "November", "Dezember"]
MONAT_NR = {m.casefold(): i for i, m in enumerate(MONATE) if m}
MONAT_NR.update({"maerz": 3, "jänner": 1, "jan": 1, "feb": 2, "mär": 3, "apr": 4, "jun": 6, "jul": 7,
                 "aug": 8, "sep": 9, "sept": 9, "okt": 10, "nov": 11, "dez": 12})
GEONAMES_URL = "https://download.geonames.org/export/dump/cities1000.zip"
MODELLE = {
    "yunet": ("face_detection_yunet_2023mar.onnx",
              "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/"
              "face_detection_yunet_2023mar.onnx",
              "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"),
    "sface": ("face_recognition_sface_2021dec.onnx",
              "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_recognition_sface/"
              "face_recognition_sface_2021dec.onnx",
              "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79"),
}
# KI-Suche „Ähnliche Fotos“: Bildteil von OpenAIs CLIP ViT-B/32 (MIT) als ONNX, umgewandelt von Xenova für
# transformers.js; feste Fassung (Commit) und Prüfsumme. (Datei, Adresse, SHA-256, Größe in Bytes)
KI_MODELL = ("clip-vit-base-patch32-vision.onnx",
             "https://huggingface.co/Xenova/clip-vit-base-patch32/resolve/6b7c523703ae26e39be4b03774966f8571c7f523/"
             "onnx/vision_model.onnx",
             "fd6e1402a588279d1723c7534d4bcba5bc0b14b47dfab0e46f8c47b8270d7d40", 351_685_709)
Image.MAX_IMAGE_PIXELS = None
ImageFile.LOAD_TRUNCATED_IMAGES = True  # abgeschnittene Dateien so weit wie möglich zeigen
