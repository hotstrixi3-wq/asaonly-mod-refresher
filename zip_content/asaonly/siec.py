# -*- coding: utf-8 -*-
"""Network boundary: Source RCON and CurseForge HTTP client."""
import json
import socket
import struct
import time
from urllib import error as urlerror
from urllib import request as urlrequest

CF_MODS_BATCH_URL = "https://api.curseforge.com/v1/mods"
USER_AGENT = "ASAonly-(AUTO)Manual-ModRefresher(RCON)/3.86.7"

class RCONError(Exception):
    pass

class RCONUncertainError(RCONError):
    """Polecenie mogło dotrzeć. Nie wolno automatycznie wysyłać go ponownie."""
    retry_safe = False

class RCONClient:
    def __init__(self, host, port, password, timeout=5.0):
        self.host = host
        self.port = int(port)
        self.password = password
        self.timeout = timeout
        self.sock = None
        self._req_id = 0
        self._deadline = None

    def connect(self):
        try:
            self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
            self.sock.settimeout(self.timeout)
            if not self._auth(self.password):
                raise RCONError("Auth failed (wrong password or port).")
        except Exception:
            self.close()
            raise

    def close(self):
        if self.sock is not None:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    def _next_id(self):
        self._req_id = (self._req_id + 1) & 0x7FFFFFFF
        return self._req_id

    def _send(self, ptype, body):
        rid = self._next_id()
        payload = struct.pack("<ii", rid, ptype) + body.encode("utf-8") + b"\x00\x00"
        self.sock.sendall(struct.pack("<i", len(payload)) + payload)
        return rid

    def _recv(self):
        def recvn(n):
            data = b""
            while len(data) < n:
                if self._deadline is not None:
                    remaining = self._deadline - time.monotonic()
                    if remaining <= 0:
                        raise RCONError("Response deadline exceeded.")
                    self.sock.settimeout(remaining)
                chunk = self.sock.recv(n - len(data))
                if not chunk:
                    raise RCONError("Connection closed.")
                data += chunk
            return data
        size = struct.unpack("<i", recvn(4))[0]
        if size < 10 or size > 4 * 1024 * 1024:  # 3.71 (audyt1): min 8B naglowek + 2B NUL
            raise RCONError("Bad frame size from server.")
        data = recvn(size)
        rid, rtype = struct.unpack("<ii", data[:8])
        # Zgodność z 3.86.2: jeden pakiet, bez nowych wymagań wobec ASA.
        body = data[8:].rstrip(b"\x00").decode("utf-8", errors="replace")
        return rid, rtype, body

    def _auth(self, password):
        self._deadline = time.monotonic() + self.timeout
        self._send(3, password)
        for _ in range(8):
            rid, typ, body = self._recv()
            if rid == -1:
                return False
            if typ != 0 or body:
                return True
            # Pusty pakiet typu 0 nie potwierdza hasła; czekamy na właściwy.
        raise RCONError("Authentication response missing.")

    def command(self, cmd):
        if self.sock is None:
            raise RCONError("Not connected.")
        self._deadline = time.monotonic() + self.timeout
        try:
            self._send(2, cmd)
            _, _, body = self._recv()
            return body
        except (OSError, RCONError) as exc:
            raise RCONUncertainError("Command outcome unconfirmed: %s" % exc) from exc

def rcon_send(host, port, password, command, timeout=5.0):
    c = RCONClient(host, port, password, timeout=timeout)
    try:
        c.connect()
        return c.command(command)
    finally:
        c.close()

def cf_request(url, api_key, payload=None):
    """Odpytuje CF API. Jeśli payload istnieje, wykonuje POST."""
    headers = {
        "Accept": "application/json",
        "x-api-key": api_key,
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
    }
    data = None
    if payload:
        data = json.dumps(payload).encode("utf-8")

    req = urlrequest.Request(url, data=data, headers=headers)
    try:
        with urlrequest.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except urlerror.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.reason}")
    except urlerror.URLError as e:
        raise RuntimeError(f"network error: {e.reason}")
    except Exception as e:
        raise RuntimeError(str(e))

class ApiZajete(RuntimeError):
    """HTTP 429 — usługa prosi o przerwę (sekundy w .za_ile)."""

    def __init__(self, tekst, za_ile):
        super().__init__(tekst)
        self.za_ile = za_ile


def steam_api_info(url, timeout=15):
    """GET api.steamcmd.net → słownik z JSON-a. Błędy jako RuntimeError z krótkim opisem."""
    req = urlrequest.Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    try:
        with urlrequest.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except urlerror.HTTPError as e:
        if e.code == 429:
            try:
                za_ile = max(1, int(e.headers.get("Retry-After") or 0))
            except (TypeError, ValueError):
                za_ile = 0
            raise ApiZajete("HTTP 429: %s" % e.reason, za_ile)
        raise RuntimeError("HTTP %s: %s" % (e.code, e.reason))
    except urlerror.URLError as e:
        raise RuntimeError("network error: %s" % (e.reason,))
    except ValueError as e:
        raise RuntimeError("JSON: %s" % e)
    except Exception as e:
        raise RuntimeError(str(e))


def select_server_artifact(latest_files):
    """Select ASA's Windows dedicated-server artifact, never by a +N rule."""
    files = [f for f in (latest_files or []) if isinstance(f, dict)]
    server = []
    for f in files:
        text = " ".join(str(f.get(k, "")) for k in
                        ("fileName", "displayName", "fileNameOnDisk")).lower()
        if "windowsserver" in text or "windows server" in text:
            server.append(f)
    pool = server or files
    if not pool:
        return None, False
    return max(pool, key=lambda f: int(f.get("id") or 0)), bool(server)

def cf_get_mods_batch(mod_ids, api_key, chunk_delay=0.0):
    """
    3.39: Pobiera wszystkie dane O(1) zapytaniem POST (Batch).
    Zwraca słownik: { 'mod_id': {'name': '...', 'page': '...', 'fid': '...', 'fname': '...'} }
    3.73: chunk_delay (sek) = przerwa miedzy chunkami po 50 modow - pole
    "Opoznienie CF" z UI wkonca naprawde dziala (wczesniej ignorowane).
    """
    results = {}
    mod_ids_list = list(mod_ids)

    # CF API akceptuje max 50 ID w jednym zapytaniu. Chunkujemy dla pewnosci.
    for i in range(0, len(mod_ids_list), 50):
        # 3.71 FIX (audyt1): API CF oczekuje liczb, nie stringow
        chunk = [int(m) for m in mod_ids_list[i:i+50] if str(m).strip().isdecimal()]
        if not chunk:
            continue
        # Uzywamy endpointu /v1/mods
        resp = cf_request(CF_MODS_BATCH_URL, api_key, payload={"modIds": chunk})
        if i + 50 < len(mod_ids_list) and chunk_delay:
            # 3.73: przerwa miedzy chunkami (max 60 s, zeby literowka w polu
            # nie uspila workera na godzine)
            time.sleep(max(0.0, min(float(chunk_delay), 60.0)))

        for mod in resp.get("data", []):
            mid = str(mod.get("id"))
            name = mod.get("name") or f"Mod {mid}"

            page = (mod.get("links") or {}).get("websiteUrl") or ""
            if not page and mod.get("slug"):
                page = f"https://www.curseforge.com/ark-survival-ascended/mods/{mod.get('slug')}"

            latest_fid = "0"
            latest_fname = ""

            # W ASA najnowsze pliki sa zazwyczaj pod 'latestFiles' (Tablica)
            latest_files = mod.get("latestFiles", [])
            latest, server_artifact = select_server_artifact(latest_files)
            if latest:
                latest_fid = str(latest.get("id"))
                latest_fname = latest.get("displayName") or latest.get("fileName") or ""

            results[mid] = {
                "name": name,
                "page": page,
                "fid": latest_fid,
                "fname": latest_fname,
                "server_artifact": server_artifact
            }

    return results
