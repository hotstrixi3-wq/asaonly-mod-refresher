"""Only suspends the child created here. No process enumeration or live ARK."""
import os, pathlib, subprocess, sys, tempfile, time
from asaonly.zamrazanie import ApiWindows
api = ApiWindows()
with tempfile.TemporaryDirectory(prefix='asa-native-resume-') as folder:
    beat = pathlib.Path(folder) / 'heartbeat'
    code = 'import pathlib,sys,time\np=pathlib.Path(sys.argv[1])\nwhile True:\n p.write_text(str(time.monotonic()))\n time.sleep(.02)\n'
    p = subprocess.Popen([sys.executable, '-c', code, str(beat)], creationflags=subprocess.CREATE_NO_WINDOW)
    record = {'pid': p.pid, 'start': api.czas_startu(p.pid)}
    def value():
        for _ in range(100):
            try:
                return float(beat.read_text())
            except (OSError, ValueError):
                time.sleep(.02)
        raise AssertionError('heartbeat unavailable')
    def progressing(expected):
        a = value(); time.sleep(.15); b = value()
        assert (b > a) == expected, (a, b, expected)
    try:
        progressing(True)
        api.zamroz_wpis(record); progressing(False)
        api.odmroz_wpis(record); progressing(True)
        api.odmroz_wpis(record); progressing(True)
        print('one suspend + two resumes: PASS, child is progressing')
        api.zamroz_wpis(record); api.zamroz_wpis(record); progressing(False)
        api.odmroz_wpis(record); progressing(False)
        api.odmroz_wpis(record); progressing(True)
        print('two suspends + one resume: still suspended; second resume consumes remaining count')
    finally:
        p.terminate(); p.wait(timeout=5)
