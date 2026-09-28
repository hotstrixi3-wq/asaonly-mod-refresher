@echo off
REM ============================================================
REM  ASAonly - ManualModRefresher - launcher (PL)
REM  Sprawdza Pythona, w razie potrzeby instaluje, odpala program.
REM  Dziala z folderu, w ktorym lezy (nie zalezy od PATH).
REM  Wymagany plik obok:
REM    "ASAonly - (AUTO)Manual - ModRefresher (RCON).py"
REM  (dokumentacja lezy w WIEDZA_O_PROGRAMIE\)
REM  V3.84: konce linii CRLF - cmd.exe przy samych LF potrafi nie
REM  znalezc etykiety (call :probe / goto :found).
REM
REM  Poprawki wzgledem poprzedniej wersji:
REM   - curl z -f: 404 NIE jest juz "sukcesem" pobierania,
REM   - wykrywanie Pythona po instalacji: sondy plikow w
REM     standardowych lokalizacjach per-user (bez zaleznosci od PATH),
REM   - usuniety refresh_path (nadpisywal PATH niewyexpandowana
REM     trescia z rejestru i mogl zepsuc biezaca sesje),
REM   - kontrola rozmiaru pobranego pliku przed instalacja,
REM   - test Tkintera takze dla galezi py na starcie,
REM   - dluzsza lista URL - kazdy adres sprawdzany przed pobraniem,
REM     martwe pozycje (404) pomijane automatycznie.
REM ============================================================
setlocal
cd /d "%~dp0"
set "PY="

REM --- 1) py launcher w PATH ---
where py >nul 2>&1
if not errorlevel 1 (
    py -3 -c "import tkinter" >nul 2>&1
    if not errorlevel 1 set "PY=py -3"
)

REM --- 2) python w PATH (odrzucamy atrape ze sklepu MS) ---
if not defined PY (
    where python >nul 2>&1
    if not errorlevel 1 (
        python -c "import sys, tkinter" >nul 2>&1
        if not errorlevel 1 set "PY=python"
    )
)

REM --- 3) sondy: standardowe lokalizacje per-user (bez PATH) ---
if not defined PY call :probe "%LocalAppData%\Programs\Python\Launcher\py.exe"
if not defined PY call :probe "%LocalAppData%\Programs\Python\Python314\python.exe"
if not defined PY call :probe "%LocalAppData%\Programs\Python\Python313\python.exe"
if not defined PY call :probe "%LocalAppData%\Programs\Python\Python312\python.exe"
if not defined PY call :probe "%LocalAppData%\Programs\Python\Python311\python.exe"
if defined PY goto :found

echo.
echo ============================================================
echo  Nie znaleziono Pythona (lub brak Tkintera).
echo  Instaluje najnowszy stabilny Python...
echo ============================================================
echo.

REM --- 4a) winget (Windows 10/11 w standardzie) ---
winget --version >nul 2>&1
if not errorlevel 1 (
    echo [winget] Instaluje Python.Python.3.14...
    winget install -e --id Python.Python.3.14 --silent --accept-source-agreements --accept-package-agreements --override "/quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_tcltk=1 Include_launcher=1 AssociateFiles=1 Shortcuts=1"
    if not errorlevel 1 goto :installed_ok
    echo [winget] Nie udalo sie. Probuje 3.13...
    winget install -e --id Python.Python.3.13 --silent --accept-source-agreements --accept-package-agreements --override "/quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_tcltk=1 Include_launcher=1 AssociateFiles=1 Shortcuts=1"
    if not errorlevel 1 goto :installed_ok
    echo [winget] Nie udalo sie. Przechodze do pobierania z python.org...
    echo.
)

REM --- 4b) instalator wprost z python.org ---
REM  Lista "na czuja": kazdy URL sprawdzamy przed pobraniem, martwe
REM  pozycje (404) pomijane. Nowe wersje dopisuj na GORE listy.
:download
set "PYURL="
call :try_url "https://www.python.org/ftp/python/3.14.7/python-3.14.7-amd64.exe"
call :try_url "https://www.python.org/ftp/python/3.14.5/python-3.14.5-amd64.exe"
call :try_url "https://www.python.org/ftp/python/3.14.0/python-3.14.0-amd64.exe"
call :try_url "https://www.python.org/ftp/python/3.13.12/python-3.13.12-amd64.exe"
call :try_url "https://www.python.org/ftp/python/3.13.5/python-3.13.5-amd64.exe"
call :try_url "https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe"

if not defined PYURL (
    echo.
    echo BLAD: Nie moge pobrac Pythona. Zrob to recznie:
    echo   https://www.python.org/downloads/
    echo i ZAZNACZ "Add Python to PATH" - dolne pole wyboru.
    echo.
    pause
    exit /b 1
)

echo [python.org] Pobieram: %PYURL%
curl -sfL --retry 2 -o "%TEMP%\asa_python_install.exe" "%PYURL%"
if errorlevel 1 (
    echo BLAD: Pobieranie sie nie powiodlo. Sprawdz internet.
    pause
    exit /b 1
)

REM Kontrola rozmiaru: strona 404 zamiast instalatora nie przejdzie
set "FSize="
for %%A in ("%TEMP%\asa_python_install.exe") do set "FSize=%%~zA"
if not defined FSize (
    echo BLAD: Pobrany plik nie istnieje.
    pause
    exit /b 1
)
if %FSize% LSS 1000000 (
    echo BLAD: Pobrany plik jest zbyt maly - to nie instalator.
    del "%TEMP%\asa_python_install.exe" >nul 2>&1
    pause
    exit /b 1
)

echo [python.org] Instaluje...
"%TEMP%\asa_python_install.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_tcltk=1 Include_launcher=1 AssociateFiles=1 Shortcuts=1
del "%TEMP%\asa_python_install.exe" >nul 2>&1

:installed_ok
echo.
echo Instalacja zakonczona. Szukam Pythona w standardowych lokalizacjach...
call :probe "%LocalAppData%\Programs\Python\Launcher\py.exe"
if not defined PY call :probe "%LocalAppData%\Programs\Python\Python314\python.exe"
if not defined PY call :probe "%LocalAppData%\Programs\Python\Python313\python.exe"
if not defined PY call :probe "%LocalAppData%\Programs\Python\Python312\python.exe"

REM Ostateczna proba po PATH (swieza instalacja zwykle i tak nie jest
REM widoczna w tej sesji - sondy powyzej zalatwiaja sprawe)
if not defined PY (
    where py >nul 2>&1
    if not errorlevel 1 set "PY=py -3"
)

if not defined PY (
    echo.
    echo Python zostal zainstalowany, ale nie moge go znalezc w tej sesji.
    echo Zamknij to okno i odpal %~nx0 ponownie.
    echo.
    pause
    exit /b 1
)

:found
REM Finalny test Tkintera (na wszelki wypadek)
call %PY% -c "import tkinter" >nul 2>&1
if errorlevel 1 (
    echo BLAD: Ten Python nie ma Tkintera.
    echo Zainstaluj Pythona z opcja "tcl/tk and IDLE".
    pause
    exit /b 1
)

REM --- 5) Odpalamy program ---
if not exist "ASAonly - (AUTO)Manual - ModRefresher (RCON).py" goto :fallback_py
call %PY% "ASAonly - (AUTO)Manual - ModRefresher (RCON).py"
exit /b %errorlevel%

:fallback_py
REM Plik ma zmieniona nazwe? Szukamy pierwszego .py obok bata.
set "PYFILE="
for %%F in (*.py) do if not defined PYFILE set "PYFILE=%%F"
if not defined PYFILE (
    echo BLAD: Nie znaleziono zadnego pliku .py w tym folderze.
    echo Skopiuj program obok %~nx0 i sprobuj ponownie.
    pause
    exit /b 1
)
echo Uwaga: nie znaleziono "ASAonly - (AUTO)Manual - ModRefresher (RCON).py",
echo uzywam: %PYFILE%
call %PY% "%PYFILE%"
exit /b %errorlevel%


REM ============================================================
REM  Sonda: %1 = pelna sciezka do python.exe / py.exe.
REM  Ustawia PY (w cudzyslowach) gdy exe istnieje i ma Tkintera.
REM ============================================================
:probe
if defined PY goto :eof
if not exist "%~1" goto :eof
"%~1" -c "import tkinter" >nul 2>&1
if errorlevel 1 goto :eof
set PY="%~1"
goto :eof


REM ============================================================
REM  Sprawdza czy URL zwraca plik (HTTP 200); jesli tak, zapisuje
REM  go w PYURL. -f jest KLUCZOWE: bez niego 404 tez daje kod 0.
REM ============================================================
:try_url
if defined PYURL goto :eof
curl -sfI -o nul --max-time 15 "%~1" >nul 2>&1
if not errorlevel 1 set "PYURL=%~1"
goto :eof
