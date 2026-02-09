import http.server
import json
import os
import socketserver
from pathlib import Path

PORT = 8080
BASE = Path(__file__).parent
GAME = BASE / "game_data"

ASSET_ROUTES = {
    "hlod":      (GAME / "hlod",     ".obj", "model/obj"),
    "terrain":   (GAME / "terrain",  ".obj", "model/obj"),
    "hlod_all":  (GAME / "hlod_all", ".obj", "model/obj"),
    "textures":  (GAME / "textures", ".png", "image/png"),
}

SINGLE_FILE_ROUTES = {
    "/manifest":          (BASE / "manifests" / "android_manifest.json", "application/json"),
    "/all_hlod_manifest": (BASE / "manifests" / "all_hlod_manifest.json", "application/json"),
    "/ocean.obj":         (BASE / "ocean.obj",  "model/obj"),
    "/ocean.glb":         (BASE / "ocean.glb",  "model/gltf-binary"),
    "/skybox.png":        (BASE / "skybox.png", "image/png"),
    "/overrides.json":    (BASE / "overrides.json", "application/json"),
}


def safe_resolve(directory: Path, filename: str) -> Path | None:
    try:
        resolved = (directory / filename).resolve()
        if resolved.is_relative_to(directory.resolve()):
            return resolved
    except (ValueError, OSError):
        pass
    return None


def list_files(directory: Path, ext: str) -> list[str]:
    if not directory.exists():
        return []
    return sorted(f for f in os.listdir(directory) if f.endswith(ext))


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(BASE), **kw)

    def do_GET(self):
        path = self.path.split("?")[0]

        # Single-file routes
        if path in SINGLE_FILE_ROUTES:
            fpath, ctype = SINGLE_FILE_ROUTES[path]
            return self._serve_file(fpath, ctype)

        # Asset list endpoints: /list_<name>
        if path.startswith("/list_"):
            name = path[6:]  # strip "/list_"
            if name in ASSET_ROUTES:
                directory, ext, _ = ASSET_ROUTES[name]
                return self._serve_json(list_files(directory, ext))

        # Asset file endpoints: /<name>/filename
        for name, (directory, _, ctype) in ASSET_ROUTES.items():
            prefix = f"/{name}/"
            if path.startswith(prefix):
                filename = path[len(prefix):]
                resolved = safe_resolve(directory, filename)
                if resolved:
                    return self._serve_file(resolved, ctype)
                return self.send_error(404)

        # Default: serve static files (index.html, etc.)
        if path == "/":
            self.path = "/index.html"
        super().do_GET()

    def _serve_json(self, data):
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_file(self, path: Path, ctype: str):
        if not path.exists():
            return self.send_error(404)
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=3600")
        self.end_headers()
        self.wfile.write(data)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def log_message(self, format, *args):
        if any(str(arg) == "404" for arg in args):
            return
        super().log_message(format, *args)


class ThreadedServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True


if __name__ == "__main__":
    counts = {name: len(list_files(d, ext))
              for name, (d, ext, _) in ASSET_ROUTES.items()}
    summary = " | ".join(f"{n}: {c}" for n, c in counts.items())
    print(f"http://localhost:{PORT}/ | {summary}")
    with ThreadedServer(("", PORT), Handler) as httpd:
        httpd.serve_forever()
