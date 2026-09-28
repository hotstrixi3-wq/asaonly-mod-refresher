# -*- coding: utf-8 -*-
# V3.81: testy nie piszą do prawdziwej czarnej skrzynki programu
# (WIEDZA_O_PROGRAMIE/asa_debug.log). Fałszywe błędy z testów trafiają
# do pliku tymczasowego.
import os as _os
import tempfile as _tempfile

_os.environ.setdefault("ASAONLY_DEBUG_LOG", _os.path.join(
    _tempfile.gettempdir(), "asaonly-testy-asa_debug.log"))
# V3.86.2: dziennik zdarzeń w pliku — w testach do katalogu tymczasowego.
_os.environ.setdefault("ASAONLY_EVENT_LOG_DIR", _os.path.join(
    _tempfile.gettempdir(), "asaonly-testy-dziennik"))
