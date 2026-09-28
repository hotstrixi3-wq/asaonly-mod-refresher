# -*- coding: utf-8 -*-
"""Pure monitor parsers, classifiers and rotating journal."""
import os
import re
import unicodedata

DZIENNIK_KEEP=15
DZIENNIK_MAX_B=10*1024

def rytm_fazowy_s(od_poczatku_s):
    """3.71: wspolny zegar fazowy 1/3/15 (sondy CF, nadzor serwera).
    0-15 min -> 60 s; 15-60 min -> 180 s; powyzej godziny -> 900 s."""
    m = od_poczatku_s / 60.0
    if m < 15:
        return 60
    if m < 60:
        return 180
    return 900

def _netstat_map(tekst):
    """3.73: port(TCP, sluchajacy) -> PID z tekstu netstat -ano (czysta funkcja,
    testowalna). Przyjmuje "LISTENING" i "NASLUCHUJACE" (polski Windows; kozak,
    raport inzyniera 3.73) oraz warianty z utraconymi ogonkami (NFKD->ascii;
    fallback NAS+UCHUJ lapie "NAS?UCHUJ?CE" po zlym dekodowaniu)."""
    mapa = {}
    for linia in tekst.splitlines():
        m = re.search(r"\s(?:\S+):(\d+)\s+\S+", linia)  # 3.73: port z ADRESU LOKALNEGO (stan za obcym)
        mp = re.search(r"\s(\d+)\s*$", linia)
        if not (m and mp):
            continue
        try:
            up = unicodedata.normalize("NFKD", linia).encode(
                "ascii", "ignore").decode("ascii").upper()
        except Exception:
            up = linia.upper()
        if ("LISTENING" in up or "NASLUCHUJACE" in up
                or ("NAS" in up and "UCHUJ" in up)):
            mapa.setdefault(m.group(1), int(mp.group(1)))
    return mapa

def pad_klasyfikuj(alive, crash_slad):
    """3.71: czysta klasyfikacja "pewnych" padow (proces zniknal).
    Zwraca None (zyje) / "PAD_CRASH" / "PAD_BEZ_SLADU"."""
    if alive:
        return None
    return "PAD_CRASH" if crash_slad else "PAD_BEZ_SLADU"

def dziennik_dopisz(katalog, linie, keep=DZIENNIK_KEEP, max_b=DZIENNIK_MAX_B):
    """3.71: dopisuje wpis do dziennik-modow.txt z rotacja keep plikow po
    max_b (rotacja PRZED dopisaniem -> zaden plik nie przekroczy limitu)."""
    try:
        os.makedirs(katalog, exist_ok=True)
        path = os.path.join(katalog, "dziennik-modow.txt")
        try:
            if os.path.exists(path) and os.path.getsize(path) >= max_b:
                najst = os.path.join(katalog, "dziennik-modow.%02d.txt" % keep)
                if os.path.exists(najst):
                    os.remove(najst)
                for i in range(keep - 1, 0, -1):
                    z = os.path.join(katalog, "dziennik-modow.%02d.txt" % i)
                    do = os.path.join(katalog, "dziennik-modow.%02d.txt" % (i + 1))
                    if os.path.exists(z):
                        os.replace(z, do)
                os.replace(path, os.path.join(katalog, "dziennik-modow.01.txt"))
        except Exception:
            return None
        with open(path, "a", encoding="utf-8") as f:
            f.write("\n".join(linie) + "\n")
        return path
    except Exception:
        return None
