"""Size accounting and conservative retention of Refresher crash snapshots."""
import json
import math
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import threading

MIB = 1024 * 1024
DEFAULT_LIMIT_MIB = 2048
FORMAT = 'asaonly-crash-v1'
LOCK = threading.RLock()


def limit_mib(value):
    try:
        number = int(str(value).strip())
        if number == 0 or 256 <= number <= 65536:
            return number
    except (ValueError, TypeError):
        pass
    return DEFAULT_LIMIT_MIB


def _linked(path):
    s = path.lstat()
    return stat.S_ISLNK(s.st_mode) or bool(getattr(s, 'st_file_attributes', 0) & 0x400)


def _inventory(root):
    """Never follow links/junctions; an incomplete count is explicitly reported."""
    files, errors = {}, []
    if _linked(root):
        raise OSError('PADY is a link or reparse point')
    def error(exc):
        errors.append(str(exc))
    for base, dirs, names in os.walk(root, followlinks=False, onerror=error):
        for name in list(dirs):
            try:
                if _linked(Path(base)/name):
                    dirs.remove(name)
                    errors.append('link/reparse point skipped: '+str(Path(base)/name))
            except OSError as exc:
                dirs.remove(name); error(exc)
        for name in names:
            p = Path(base)/name
            try:
                if _linked(p):
                    errors.append('link/reparse point skipped: '+str(p))
                elif p.is_file():
                    files[p] = p.stat().st_size
            except OSError as exc:
                error(exc)
    return files, errors


def _owned(snapshot, files):
    """Delete only sealed snapshots in our format with an exact file manifest.

    Legacy snapshots and files manually added by the operator are counted but
    retained. A path in metadata never supplies a deletion target.
    """
    try:
        meta = snapshot/'metadata.json'
        if files.get(meta, 1_000_001) > 1_000_000:
            return None
        data = json.loads(meta.read_text(encoding='utf-8'))
        if data.get('format') != FORMAT:
            return None
        captured = float(data['captured_at'])
        if not math.isfinite(captured):
            return None
        expected = {meta}
        for entry in data['files']:
            rel = PurePosixPath(entry['copy'].replace('\\', '/'))
            if rel.is_absolute() or '..' in rel.parts or not rel.parts or rel.parts[0] not in ('Logs', 'Crashes'):
                return None
            path = snapshot.joinpath(*rel.parts)
            # A failed copy may have left a partial file; it still belongs to
            # this snapshot. Missing files do not authorize deleting others.
            if path in files:
                expected.add(path)
        actual = {p for p in files if p.is_relative_to(snapshot)}
        if actual != expected:
            return None
        return captured, not bool(data.get('errors')) and not any(
            e.get('truncated') or e.get('changed_during_copy') for e in data['files'])
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return None


def maintain(root, current, limit_bytes):
    """Called under LOCK, after sealing the urgent copy. The limit is soft:
    keep the latest snapshot and latest complete snapshot of each map, plus the
    current capture. Never remove incomplete/in-progress or foreign trees.
    """
    root, current = Path(root).absolute(), Path(current).absolute()
    result = {'bytes': 0, 'limit_bytes': limit_bytes, 'removed': [], 'errors': []}
    try:
        files, errors = _inventory(root)
        result['errors'].extend(errors)
        result['bytes'] = sum(files.values())
        # Uncertain inventory: retain everything, including trees containing links.
        if errors or not limit_bytes or result['bytes'] <= limit_bytes:
            return result
        candidates, protected = [], {current}
        for group in root.iterdir():
            if not group.is_dir() or not group.name.startswith('map_') or _linked(group):
                continue
            records = []
            for snapshot in group.iterdir():
                if not snapshot.is_dir() or _linked(snapshot):
                    continue
                owned = _owned(snapshot, files)
                if owned:
                    captured, complete = owned
                    records.append((captured, str(snapshot), snapshot, complete))
            records.sort()
            if records:
                protected.add(records[-1][2])
                complete = [r for r in records if r[3]]
                if complete:
                    protected.add(complete[-1][2])
            candidates.extend(records)
        for _, _, snapshot, _ in sorted(candidates):
            if result['bytes'] <= limit_bytes:
                break
            if snapshot in protected:
                continue
            # Re-check the resolved absolute target and every descendant immediately
            # before recursive deletion. All operations stay within this PADY root.
            resolved = snapshot.resolve(strict=True)
            resolved_root = root.resolve(strict=True)
            if resolved == resolved_root or not resolved.is_relative_to(resolved_root) or resolved != snapshot:
                raise OSError('retention target outside PADY: '+str(snapshot))
            fresh, fresh_errors = _inventory(snapshot)
            if fresh_errors or _owned(snapshot, fresh) is None:
                result['errors'].extend(fresh_errors or ['snapshot changed: '+str(snapshot)])
                continue
            shutil.rmtree(snapshot)
            result['bytes'] -= sum(files[p] for p in files if p.is_relative_to(snapshot))
            result['removed'].append(str(snapshot))
        # Actual space after cleanup, including concurrent in-progress captures.
        files, errors = _inventory(root)
        result['bytes'] = sum(files.values())
        result['errors'].extend(errors)
    except OSError as exc:
        result['errors'].append(str(exc))
    return result
