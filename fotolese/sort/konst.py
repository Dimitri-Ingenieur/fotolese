"""fotolese.sort.konst – Konstanten, Erweiterungslisten und das optionale rawpy."""
import errno

from PIL import Image
from datetime import datetime

try:
    import rawpy
except ImportError:
    rawpy = None

VERSION = "1.3"
HASH_VERSION = "1"
BILD_EXT = {".jpg", ".jpeg", ".png", ".nef"}
BEGLEIT_EXT = {".xmp", ".pp3", ".aae"}
SKIP_ORDNER = {"@eaDir", "$RECYCLE.BIN", "System Volume Information", "lost+found"}
WINDOWS_FS = {"vfat", "msdos", "exfat", "ntfs", "ntfs3", "fuseblk", "cifs", "smb3"}
KRITISCH = {errno.ENOSPC, errno.EIO, errno.EROFS, errno.ENODEV, errno.ENXIO, errno.EDQUOT}
MAX_ORDNER = 9999
FLACH_STD = 1.0          # praktisch einfarbige Bilder nicht per Hash verknüpfen
DRAFT = (256, 256)       # JPEG nur in 1/2, 1/4 oder 1/8 Auflösung dekodieren
SYNC_BYTES = 1 << 30     # nach spätestens 1 GiB Kopie: sync, dann Quellen löschen
SYNC_DATEIEN = 500

_DREHUNG = {2: Image.Transpose.FLIP_LEFT_RIGHT, 3: Image.Transpose.ROTATE_180,
            4: Image.Transpose.FLIP_TOP_BOTTOM, 5: Image.Transpose.TRANSPOSE,
            6: Image.Transpose.ROTATE_270, 7: Image.Transpose.TRANSVERSE,
            8: Image.Transpose.ROTATE_90}
_EPOCHE = datetime(1970, 1, 1)
