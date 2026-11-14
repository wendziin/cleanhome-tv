#!/usr/bin/env python3
"""Painel web do CleanHome.

Servidor HTTP local (sem dependencias) que guarda os wallpapers enviados pelo
navegador e publica um config.json que o launcher na TV busca periodicamente.

    python3 server.py [--port 8099]

Depois abra http://IP_DO_CELULAR:8099/ no navegador.
"""

import argparse
import json
import os
import re
import socket
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse, parse_qs

ROOT = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(ROOT, "public")
DATA_DIR = os.path.join(ROOT, "data")
WALL_DIR = os.path.join(DATA_DIR, "wallpapers")
STATE_PATH = os.path.join(DATA_DIR, "config.json")

LOCK = threading.Lock()
MAX_UPLOAD = 30 * 1024 * 1024
# Quantos wallpapers enviados ficam guardados para a TV. O mais antigo sai
# quando entra um novo, para a galeria não crescer sem fim.
KEEP_MAX = 3
KEEP_MIN = 3

# Precisa bater com a lista embutida no launcher (main.js).
BUILTINS = [
    {"id": "espaco-profundo", "name": "Espaço Profundo"},
    {"id": "montanhas-sunset", "name": "Pôr do Sol nas Montanhas"},
    {"id": "cidade-cyberpunk", "name": "Cidade Neon Cyberpunk"},
    {"id": "floresta-neblina", "name": "Floresta e Neblina"},
    {"id": "ondas-neon", "name": "Ondas Abstratas Azuis"},
    {"id": "deserto-minimalista", "name": "Dunas do Deserto"},
    {"id": "aurora-boreal", "name": "Aurora Boreal"},
    {"id": "ceu-estrelado", "name": "Céu Noturno Estrelado"},
]
BUILTIN_IDS = {entry["id"] for entry in BUILTINS}

SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")
SAFE_HOST = re.compile(r"^[A-Za-z0-9.:\[\]-]{1,120}$")


def default_state():
    # active vazio = a TV mantém o wallpaper que já está usando.
    return {"revision": 0, "active": "", "wallpapers": []}


def load_state():
    state = default_state()
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as handle:
            saved = json.load(handle)
    except (OSError, ValueError):
        return state
    if isinstance(saved.get("revision"), (int, float)):
        state["revision"] = int(saved["revision"])
    if isinstance(saved.get("active"), str):
        state["active"] = saved["active"]
    if isinstance(saved.get("wallpapers"), list):
        for entry in saved["wallpapers"]:
            if not isinstance(entry, dict):
                continue
            wid = entry.get("id")
            name = entry.get("name")
            filename = entry.get("file")
            if not (isinstance(wid, str) and isinstance(filename, str)):
                continue
            path = os.path.join(WALL_DIR, filename)
            if not os.path.isfile(path):
                continue
            state["wallpapers"].append({
                "id": wid,
                "name": name if isinstance(name, str) else wid,
                "file": filename,
            })
    return state


def save_state(state):
    os.makedirs(WALL_DIR, exist_ok=True)
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(state, handle, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_PATH)


def trim_wallpapers(state):
    """Mantém no máximo KEEP_MAX enviados, sem remover o que está ativo."""
    removed = []
    while len(state["wallpapers"]) > KEEP_MAX:
        victim = next((item for item in state["wallpapers"]
                       if item["id"] != state["active"]), None)
        if not victim:
            break
        state["wallpapers"].remove(victim)
        removed.append(victim)
        try:
            os.remove(os.path.join(WALL_DIR, victim["file"]))
        except OSError:
            pass
    return removed


def sniff_extension(data):
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def lan_ip():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


class PanelHandler(BaseHTTPRequestHandler):
    server_version = "CleanHomePanel/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        print("[%s] %s" % (time.strftime("%H:%M:%S"), fmt % args), flush=True)

    # ---- helpers -------------------------------------------------------
    def cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def respond(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.cors()
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.respond(status, body, "application/json; charset=utf-8")

    def fail(self, status, message):
        self.send_json({"error": message}, status)

    def send_file(self, path, content_type):
        try:
            with open(path, "rb") as handle:
                body = handle.read()
        except OSError:
            self.fail(404, "arquivo não encontrado")
            return
        self.respond(200, body, content_type)

    def read_body(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0:
            return b""
        if length > MAX_UPLOAD:
            return None
        return self.rfile.read(length)

    def read_json(self):
        data = self.read_body()
        if data is None:
            self.fail(413, "requisição grande demais")
            return None
        try:
            return json.loads(data.decode("utf-8") or "{}")
        except ValueError:
            self.fail(400, "JSON inválido")
            return None

    def base_url(self):
        host = self.headers.get("Host") or ""
        if not SAFE_HOST.match(host):
            host = "%s:%d" % (lan_ip(), self.server.server_port)
        return "http://" + host

    # ---- rotas ---------------------------------------------------------
    def do_OPTIONS(self):
        self.send_response(204)
        self.cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path in ("/", "/index.html"):
            self.send_file(os.path.join(PUBLIC_DIR, "index.html"),
                           "text/html; charset=utf-8")
            return

        if path == "/config.json":
            with LOCK:
                state = load_state()
            base = self.base_url()
            self.send_json({
                "version": 1,
                "revision": state["revision"],
                "active": state["active"],
                "wallpapers": [
                    {
                        "id": entry["id"],
                        "name": entry["name"],
                        "file": base + "/wallpapers/" + entry["file"],
                        "thumb": base + "/wallpapers/" + entry["file"],
                        "category": "custom",
                        "still": True,
                    }
                    for entry in state["wallpapers"]
                ],
            })
            return

        if path == "/api/state":
            with LOCK:
                state = load_state()
            base = self.base_url()
            self.send_json({
                "revision": state["revision"],
                "active": state["active"],
                "base": base,
                "keep": KEEP_MAX,
                "builtins": [
                    {"id": entry["id"], "name": entry["name"],
                     "thumb": "/builtin/" + entry["id"] + ".jpg"}
                    for entry in BUILTINS
                ],
                "wallpapers": [
                    {"id": entry["id"], "name": entry["name"],
                     "url": "/wallpapers/" + entry["file"]}
                    for entry in state["wallpapers"]
                ],
            })
            return

        if path == "/health":
            self.send_json({"ok": True})
            return

        if path.startswith("/builtin/"):
            name = SAFE_NAME.sub("", path[len("/builtin/"):])
            if name.endswith(".jpg"):
                self.send_file(os.path.join(PUBLIC_DIR, "builtin", name),
                               "image/jpeg")
                return
            self.fail(404, "não encontrado")
            return

        if path.startswith("/wallpapers/"):
            name = SAFE_NAME.sub("", path[len("/wallpapers/"):])
            if name:
                content_type = "image/jpeg"
                if name.endswith(".png"):
                    content_type = "image/png"
                elif name.endswith(".webp"):
                    content_type = "image/webp"
                self.send_file(os.path.join(WALL_DIR, name), content_type)
                return
            self.fail(404, "não encontrado")
            return

        self.fail(404, "não encontrado")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path == "/api/select":
            payload = self.read_json()
            if payload is None:
                return
            target = payload.get("id")
            if not isinstance(target, str):
                self.fail(400, "id ausente")
                return
            with LOCK:
                state = load_state()
                known = target in ("off", "") or target in BUILTIN_IDS or any(
                    entry["id"] == target for entry in state["wallpapers"])
                if not known:
                    self.fail(404, "wallpaper desconhecido")
                    return
                state["active"] = target
                state["revision"] += 1
                save_state(state)
            self.send_json({"ok": True, "active": target,
                            "revision": state["revision"]})
            return

        if path == "/api/upload":
            query = parse_qs(parsed.query)
            raw_name = (query.get("filename") or ["wallpaper"])[0]
            data = self.read_body()
            if data is None:
                self.fail(413, "imagem maior que 30 MB")
                return
            if not data:
                self.fail(400, "corpo vazio")
                return
            extension = sniff_extension(data)
            if not extension:
                self.fail(415, "formato não suportado (use JPG, PNG ou WebP)")
                return
            label = os.path.splitext(os.path.basename(raw_name))[0].strip()
            label = re.sub(r"\s+", " ", label)[:60] or "Wallpaper"
            wid = "w%d%s" % (int(time.time() * 1000), uuid.uuid4().hex[:4])
            filename = wid + "." + extension
            os.makedirs(WALL_DIR, exist_ok=True)
            with open(os.path.join(WALL_DIR, filename), "wb") as handle:
                handle.write(data)
            with LOCK:
                state = load_state()
                state["wallpapers"].append(
                    {"id": wid, "name": label, "file": filename})
                evicted = trim_wallpapers(state)
                # Se o wallpaper ativo saiu da janela (não deveria acontecer),
                # o novo entra no lugar para a TV não ficar sem imagem.
                active = state["active"]
                if active and active not in BUILTIN_IDS and active != "off" and \
                        not any(item["id"] == active for item in state["wallpapers"]):
                    state["active"] = wid
                    state["revision"] += 1
                save_state(state)
            self.send_json({"ok": True, "id": wid, "name": label,
                            "evicted": [item["id"] for item in evicted],
                            "keep": KEEP_MAX})
            return

        if path == "/api/delete":
            payload = self.read_json()
            if payload is None:
                return
            target = payload.get("id")
            with LOCK:
                state = load_state()
                entry = next((item for item in state["wallpapers"]
                              if item["id"] == target), None)
                if not entry:
                    self.fail(404, "wallpaper desconhecido")
                    return
                state["wallpapers"] = [
                    item for item in state["wallpapers"] if item["id"] != target]
                try:
                    os.remove(os.path.join(WALL_DIR, entry["file"]))
                except OSError:
                    pass
                if state["active"] == target:
                    state["active"] = "off"
                    state["revision"] += 1
                save_state(state)
            self.send_json({"ok": True})
            return

        self.fail(404, "não encontrado")


def main():
    global KEEP_MAX
    parser = argparse.ArgumentParser(description="Painel web do CleanHome")
    parser.add_argument("--port", type=int, default=8099)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--keep", type=int, default=KEEP_MAX,
                        help="wallpapers enviados mantidos (mínimo %d)" % KEEP_MIN)
    args = parser.parse_args()
    KEEP_MAX = max(KEEP_MIN, args.keep)

    os.makedirs(WALL_DIR, exist_ok=True)
    if not os.path.isfile(STATE_PATH):
        save_state(default_state())

    server = ThreadingHTTPServer((args.host, args.port), PanelHandler)
    server.daemon_threads = True
    print("CleanHome: painel em http://%s:%d/" % (lan_ip(), args.port), flush=True)
    print("Na TV, o launcher busca %s/config.json" % (
        "http://%s:%d" % (lan_ip(), args.port)), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrado.")


if __name__ == "__main__":
    main()
