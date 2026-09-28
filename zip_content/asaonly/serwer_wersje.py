# -*- coding: utf-8 -*-
"""Pure parsers for ASA CFCore logs and its local installation registry."""
import json
import os
import re

def parse_cfcore_event(line):
    """Parse the real CFCore messages observed in ASA startup logs."""
    line = line or ""
    # V3.81: pierwsza linia nowego procesu. Dowody wersji należą do procesu,
    # więc zerujemy je TU — w kolejności linii — a nie przy zmianie statusu,
    # która przychodzi po zdarzeniach całego odczytanego fragmentu.
    if "Log file open" in line:
        return {"type": "log_open"}
    m = re.search(r"Mod:\s+(.+?)\s+\((\d+)\)\s+requires upgrade/downgrade\s+\((\d+)\s*->\s*(\d+)\)", line, re.I)
    if m:
        return {"type": "upgrade_required", "name": m.group(1).strip(),
                "mod_id": m.group(2), "old_file_id": m.group(3),
                "file_id": m.group(4)}
    m = re.search(r"Request to Install mod\s+'([^']+)'\s+\(modId=(\d+),\s*fileId=(\d+)\)", line, re.I)
    if m:
        return {"type": "install_requested", "name": m.group(1),
                "mod_id": m.group(2), "file_id": m.group(3)}
    m = re.search(r"Successfully installed mod\s+'([^']+)'\s+\(modId=(\d+),\s*fileId=(\d+)\)", line, re.I)
    if m:
        return {"type": "install_succeeded", "name": m.group(1),
                "mod_id": m.group(2), "file_id": m.group(3)}
    if re.search(r"Starting download\s+-", line, re.I):
        return {"type": "download_started"}
    if "UShooterEngine::LoadGameMods" in line:
        # V3.81: prawdziwy format ASA (log serwera, wersja gry 93.28) to jedna
        # linia na mod ze ścieżką katalogu <ModID>_<FileID>:
        #   ...LoadGameMods Loading Mod ShooterGame/Mods/83374/928548_7005633/Shiny...
        # Stary format par "mod (plik)" zostaje obsłużony dla starszych logów.
        pairs = re.findall(r"Mods[\\/]\d+[\\/](\d{5,12})_(\d{5,12})[\\/]", line)
        pairs += re.findall(r"(\d{6,12})\s*\((\d{6,12})\)", line)
        return {"type": "mods_loaded", "mods": dict(pairs)}
    return None

def library_json_path(mods_dir):
    """Map .../ShooterGame/Mods/83374 to .../ModsUserData/83374/library.json."""
    if not mods_dir:
        return None
    p = os.path.normpath(mods_dir)
    parent = os.path.dirname(p)              # .../Mods
    if os.path.basename(parent).lower() != "mods":
        return None
    return os.path.join(os.path.dirname(parent), "ModsUserData",
                        os.path.basename(p), "library.json")

def _field(mapping, *names):
    """CFCore's JSON serializer uses unusual casing such as iD and uRL."""
    if not isinstance(mapping, dict):
        return None
    for name in names:
        if name in mapping:
            return mapping[name]
    wanted = {str(name).lower() for name in names}
    for key, value in mapping.items():
        if str(key).lower() in wanted:
            return value
    return None


def _numeric_file_id(value):
    if isinstance(value, dict):
        value = _field(value, "id", "fileId")
    value = str(value or "")
    return value if value.isdigit() else None


def _mod_id_from_path(path):
    match = re.search(r"(?:^|[\\/])(\d{6,12})_(\d{6,12})(?:$|[\\/])",
                      str(path or ""))
    return match.group(1) if match else None


def read_cfcore_records(path):
    """Read real CFCore `installedMods` records into a compact stable schema."""
    if not path or not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            root = json.load(fh)
    except Exception:
        return {}
    records = {}
    installed_mods = _field(root, "installedMods") or []
    if not isinstance(installed_mods, list):
        return {}
    for entry in installed_mods:
        if not isinstance(entry, dict):
            continue
        details = _field(entry, "details") or {}
        installed_file = _field(entry, "installedFile") or {}
        path_on_disk = str(_field(entry, "pathOnDisk", "path") or "")
        mod_id = _numeric_file_id(_field(details, "id", "modId"))
        if not mod_id:
            mod_id = _mod_id_from_path(path_on_disk)
        file_id = _numeric_file_id(installed_file)
        if not file_id:
            match = re.search(r"_(\d{6,12})(?:$|[\\/])", path_on_disk)
            file_id = match.group(1) if match else None
        if not (mod_id and file_id):
            continue
        records[mod_id] = {
            "mod_id": mod_id,
            "installed_file_id": file_id,
            "name": str(_field(details, "name") or ("Mod " + mod_id)),
            "filename": str(_field(installed_file, "filename", "fileName") or ""),
            "path_on_disk": path_on_disk,
            "status": str(_field(entry, "status") or ""),
            "enabled": bool(_field(entry, "enabled")),
            "date_installed": str(_field(entry, "dateInstalled") or ""),
            "date_updated": str(_field(entry, "dateUpdated") or ""),
        }
    return records


def read_cfcore_library(path):
    """Return {mod_id: installed windows-server file_id}."""
    return {mid: row["installed_file_id"]
            for mid, row in read_cfcore_records(path).items()}
