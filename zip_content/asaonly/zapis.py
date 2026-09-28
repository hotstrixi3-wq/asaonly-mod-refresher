# -*- coding: utf-8 -*-
"""Atomic, versioned JSON persistence and legacy-file migrations."""
import json
import os
import re
import time

BACKUP_KEEP = 10
TS_RE = re.compile(r"(\d{2})\.(\d{2})\.(\d{4}) (\d{2})-(\d{2})-(\d{2})")
REV_RE = re.compile(r" \((\d+)\)\.json$", re.IGNORECASE)
_debug_logger = lambda message: None

def set_debug_logger(logger):
    global _debug_logger
    _debug_logger = logger or (lambda message: None)

def write_json_atomic(path, data):
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        # os.replace(tmp, path) atomically replaces an existing destination on
        # Windows and POSIX. Moving the old file away first created a crash
        # window in which the authoritative checkpoint did not exist.
        os.replace(tmp, path)
        if os.name != "nt":
            try:
                fd = os.open(os.path.dirname(path) or ".", os.O_RDONLY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
            except OSError:
                pass
        return True
    except Exception as e:
        _debug_logger(f"JSON save error {path}: {e}")
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        return False

def file_stamp(t=None):
    """3.45: znacznik czasu do nazwy pliku: DD.MM.YYYY HH-MM-SS."""
    return time.strftime("%d.%m.%Y %H-%M-%S", time.localtime(t))

def _ts_key(fname):
    """Order revisions exactly as save_versioned creates them.

    Several writes in one second share the timestamp; `(2)`, `(3)`, ... are
    later durable revisions and must not tie with the unsuffixed file.
    """
    m = TS_RE.search(fname)
    if not m:
        return (0, 0, 0, 0, 0, 0, 0)
    d, mo, y, h, mi, s = (int(x) for x in m.groups())
    revision_match = REV_RE.search(fname)
    revision = int(revision_match.group(1)) if revision_match else 1
    return (y, mo, d, h, mi, s, revision)

def newest_matching(directory, base):
    """3.45: najnowszy plik 'base *.json' w katalogu (wg daty z NAZWY)."""
    try:
        cands = [f for f in os.listdir(directory)
                 if f.startswith(base) and f.endswith(".json")]
        if not cands:
            return None
        return os.path.join(directory, max(cands, key=_ts_key))
    except Exception:
        return None

def save_versioned(directory, base, data, keep=BACKUP_KEEP):
    """3.45: zapis do NOWEGO pliku z data/godzina; bez zmian tresci = nic
    nie tworzymy; rotacja trzyma 'keep' najnowszych. Zwraca sciezke."""
    try:
        os.makedirs(directory, exist_ok=True)
        newest = newest_matching(directory, base)
        if newest:
            try:
                with open(newest, "r", encoding="utf-8") as f:
                    if json.load(f) == data:
                        return newest
            except Exception:
                pass
        stem = "%s %s" % (base, file_stamp())
        path = os.path.join(directory, stem + ".json")
        revision = 2
        while os.path.exists(path):
            path = os.path.join(directory, "%s (%d).json" % (stem, revision))
            revision += 1
        if not write_json_atomic(path, data):
            return None
        cands = [f for f in os.listdir(directory)
                 if f.startswith(base) and f.endswith(".json")]
        for old in sorted(cands, key=_ts_key)[:-keep]:
            try:
                os.remove(os.path.join(directory, old))
            except Exception:
                pass
        return path
    except Exception as e:
        _debug_logger("save_versioned error (%s): %s" % (base, e))
        return None

def migrate_old_file(old_path, directory, base):
    """3.45: jednorazowa zmiana nazwy starego pliku na nowa konwencje
    (znacznik czasu = data modyfikacji starego pliku, nie 'teraz')."""
    try:
        if not os.path.exists(old_path):
            return None
        if newest_matching(directory, base):
            # Konflikt nie oznacza, że legacy jest gorsze. Zachowujemy go w
            # kwarantannie zamiast bezpowrotnie kasować potencjalnie jedyną
            # poprawną konfigurację lub sekret.
            quarantine = os.path.join(directory, "LEGACY_KWARANTANNA")
            os.makedirs(quarantine, exist_ok=True)
            target = os.path.join(quarantine, os.path.basename(old_path))
            suffix = 2
            while os.path.exists(target):
                root, ext = os.path.splitext(os.path.basename(old_path))
                target = os.path.join(quarantine, "%s (%d)%s" % (root, suffix, ext))
                suffix += 1
            os.replace(old_path, target)
            _debug_logger("legacy conflict quarantined: %s -> %s" % (old_path, target))
            return target
        os.makedirs(directory, exist_ok=True)
        stamp = file_stamp(os.path.getmtime(old_path))
        new_path = os.path.join(directory, "%s %s.json" % (base, stamp))
        os.rename(old_path, new_path)
        return new_path
    except Exception:
        return None

def migrate_old_base(directory, old_base, new_dir, new_base):
    """3.63/3.64: jednorazowa zmiana konwencji - cala rodzina plikow
    'old_base <data>.json' trafia do new_dir jako 'new_base <data>.json'
    (daty w nazwach zostaja, wiec historia backupow i rotacja sa bez
    zmian)."""
    try:
        for f in os.listdir(directory):
            if f.startswith(old_base) and f.endswith(".json"):
                try:
                    os.makedirs(new_dir, exist_ok=True)
                    os.rename(os.path.join(directory, f),
                              os.path.join(new_dir,
                                           new_base + f[len(old_base):]))
                except Exception:
                    pass
    except Exception:
        pass
