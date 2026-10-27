"""fotolese.web.konst – Konstanten, Muster, Monatsnamen und Quellen der Drittmodelle."""
import re

from PIL import Image, ImageFile


VERSION = "2.7.1"
BILD_EXT = {".jpg", ".jpeg", ".png"}
ORDNER_MUSTER = re.compile(r"\d{4}")
BESTOF_MUSTER = re.compile(r"(\d{4})([a-z]?)\.(jpg|png)")
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
Image.MAX_IMAGE_PIXELS = None
ImageFile.LOAD_TRUNCATED_IMAGES = True  # abgeschnittene Dateien so weit wie möglich zeigen
