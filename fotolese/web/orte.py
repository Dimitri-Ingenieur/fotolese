"""fotolese.web.orte – GeoNames offline: GPS -> nächster größerer Ort, Ortsname -> Koordinaten."""
import io
import math
import zipfile

import numpy as np


class Orte:
    AUSGESCHLOSSEN = {"PPLX", "PPLH", "PPLQ", "PPLW", "PPLCH"}  # Ortsteile, historische Orte

    def __init__(self, zip_pfad, min_ew):
        self.zip_pfad, self.min_ew = zip_pfad, min_ew
        self.bereit = False
        self._namen, self._lat, self._lon, self._such = [], None, None, {}

    def laden(self):
        namen, lat, lon, such = [], [], [], {}
        with zipfile.ZipFile(self.zip_pfad) as z:
            txt = next(n for n in z.namelist() if n.endswith(".txt"))
            with z.open(txt) as roh:
                for zeile in io.TextIOWrapper(roh, encoding="utf-8"):
                    t = zeile.rstrip("\n").split("\t")
                    if len(t) < 15:
                        continue
                    try:
                        breite, laenge, ew = float(t[4]), float(t[5]), int(t[14] or 0)
                    except ValueError:
                        continue
                    eintrag = (ew, t[1], breite, laenge, t[8])
                    schluessel = {t[1].casefold(), t[2].casefold()}
                    if ew >= 500000:
                        schluessel.update(a.casefold() for a in t[3].split(",") if a)
                    for k in schluessel:
                        if k and (k not in such or such[k][0] < ew):
                            such[k] = eintrag
                    if ew >= self.min_ew and t[7] not in self.AUSGESCHLOSSEN:
                        namen.append(t[1])
                        lat.append(breite)
                        lon.append(laenge)
        self._namen = namen
        self._lat, self._lon = np.radians(np.array(lat)), np.radians(np.array(lon))
        self._such = such
        self.bereit = True
        return len(namen), len(such)

    def naechster(self, lat, lon):
        if not self.bereit or not self._namen:
            return None, None
        p, la = math.radians(lat), math.radians(lon)
        a = (np.sin((self._lat - p) / 2) ** 2
             + math.cos(p) * np.cos(self._lat) * np.sin((self._lon - la) / 2) ** 2)
        i = int(np.argmin(a))
        return self._namen[i], round(12742.0 * math.asin(min(1.0, math.sqrt(float(a[i])))), 1)

    def suchen(self, text):
        treffer = self._such.get(text.casefold()) if self.bereit else None
        return None if treffer is None else {"name": treffer[1], "lat": treffer[2], "lon": treffer[3]}
