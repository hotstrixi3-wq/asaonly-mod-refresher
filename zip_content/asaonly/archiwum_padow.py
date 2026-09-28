"""Read-only snapshots of crash evidence; all writes stay under Refresher."""
import hashlib
import json
import os
import re
import time
import uuid
from pathlib import Path
from .jezyk import t
from .logtail import open_log_shared
from .retencja_padow import DEFAULT_LIMIT_MIB, MIB, FORMAT, LOCK, maintain, _linked

MAX_FILE = 128 * 1024 * 1024
MAX_TOTAL = 256 * 1024 * 1024
MAX_FILES = 64


def zapisz_dowody(knowledge_dir, mapa, logs, powod, identity=None, now=None,
                  limit_bytes=DEFAULT_LIMIT_MIB * MIB):
    now = time.time() if now is None else now
    safe = re.sub(r'[^\w.-]+', '_', str(mapa)).strip('. ')[:60] or 'map'
    safe = 'map_' + safe  # Windows reserved names cannot be used as a component
    target = Path(knowledge_dir) / 'PADY' / safe / (time.strftime('%Y%m%d-%H%M%S', time.localtime(now)) + '-' + uuid.uuid4().hex[:10])
    report = {'format': FORMAT, 'map': str(mapa), 'captured_at': now, 'reason': powod, 'process': identity,
              'files': [], 'errors': [], 'limits': {'file': MAX_FILE, 'total': MAX_TOTAL, 'count': MAX_FILES}}
    usage = None
    warning = False
    try:
        for parent in (Path(knowledge_dir), target.parent.parent, target.parent):
            if parent.exists() and _linked(parent):
                raise OSError('archive destination is a link/reparse point: '+str(parent))
        target.mkdir(parents=True, exist_ok=False)
        logdir = Path(logs)
        candidates = [(logdir / 'ShooterGame.log', 'Logs/ShooterGame.log')]
        # Only crash artifacts, never configs or game saves; bounded traversal.
        for folder, prefix in ((logdir, 'Logs'), (logdir.parent / 'Crashes', 'Crashes')):
            if not folder.is_dir():
                continue
            for base, dirs, names in os.walk(folder, followlinks=False):
                rel = Path(base).relative_to(folder)
                dirs[:] = [d for d in dirs if len(rel.parts) < 2 and not (Path(base)/d).is_symlink()]
                for name in sorted(names):
                    p = Path(base) / name
                    low = name.lower()
                    if p.is_symlink() or not (low.endswith(('.crashstack', '.dmp', '.runtime-xml')) or low == 'crashcallstack.txt'):
                        continue
                    try:
                        if now - p.stat().st_mtime > 300:
                            continue
                    except OSError as exc:
                        report['errors'].append('%s: %s' % (p, exc)); continue
                    candidates.append((p, str(Path(prefix) / rel / name)))
        used = 0
        if len(candidates) > MAX_FILES:
            report['errors'].append('file count limit; %d omitted' % (len(candidates) - MAX_FILES))
        for src, rel in candidates[:MAX_FILES]:
            entry = {'source': str(src), 'copy': rel}
            try:
                fh = open_log_shared(str(src), binary=True)
                if fh is None:
                    raise OSError('source unavailable (missing, rotated or access denied)')
                with fh:
                    before = os.fstat(fh.fileno())
                    limit = min(before.st_size, MAX_FILE, max(0, MAX_TOTAL-used))
                    dst = target / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    digest = hashlib.sha256()
                    copied = 0
                    with dst.open('xb') as out:
                        while copied < limit:
                            chunk = fh.read(min(1024*1024, limit-copied))
                            if not chunk: break
                            out.write(chunk); digest.update(chunk); copied += len(chunk)
                    after = os.fstat(fh.fileno())
                    entry.update(original_size=before.st_size, copied=copied, sha256=digest.hexdigest(),
                                 truncated=copied < before.st_size, source_mtime_ns=before.st_mtime_ns,
                                 changed_during_copy=(before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns))
                    used += copied
            except OSError as exc:
                entry['error'] = str(exc)
                report['errors'].append('%s: %s' % (src, exc))
            report['files'].append(entry)
        # Copy first: the manager may remove the source log in seconds. Cleanup
        # cannot delay this urgent capture. Only sealed snapshots are candidates.
        with LOCK:
            (target/'metadata.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            usage = maintain(Path(knowledge_dir)/'PADY', target, max(0, limit_bytes))
        incomplete = bool(report['errors']) or any(x.get('truncated') or x.get('changed_during_copy') for x in report['files'])
        status = t('NIEPEŁNA / zmieniana podczas zapisu', 'INCOMPLETE / changed during capture') if incomplete else 'OK'
        message = t('[DOWODY PADU] %s: %s — %s', '[CRASH EVIDENCE] %s: %s — %s') % (mapa, status, target)
        warning = bool(usage['errors']) or bool(limit_bytes and usage['bytes'] > limit_bytes)
        message += t(' | PADY: %.1f MiB; limit %s MiB; usunięto %d starych kopii.',
                     ' | PADY: %.1f MiB; limit %s MiB; removed %d old snapshots.') % (
                         usage['bytes']/MIB, str(limit_bytes//MIB) if limit_bytes else 'OFF', len(usage['removed']))
        if warning:
            message += t(' UWAGA: limit przekroczony lub pomiar/rotacja niepełne; zachowano chronione i nierozpoznane dane. Sprawdź PADY.',
                         ' WARNING: over budget or incomplete accounting/rotation; protected and unrecognized data retained. Check PADY.')
            if usage['errors']:
                message += ' ' + '; '.join(usage['errors'][:3])
    except OSError as exc:
        report['errors'].append(str(exc))
        message = t('[DOWODY PADU] %s: zapis nieudany: %s', '[CRASH EVIDENCE] %s: capture failed: %s') % (mapa, exc)
        warning = True
    return {'path': str(target), 'report': report, 'message': message, 'usage': usage, 'warning': warning}
