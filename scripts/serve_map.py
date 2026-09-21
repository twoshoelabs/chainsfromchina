"""
Serve map/ on localhost so the page can fetch its JSON (file:// cannot).

    .venv/bin/python scripts/serve_map.py [port]
"""
import functools, http.server, socketserver, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "map"
port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765


class NoCache(http.server.SimpleHTTPRequestHandler):
    """
    Serves map/ with caching switched off.

    Not a detail: the default handler sends Last-Modified, the browser then reuses a cached
    app.js after an edit, and the page silently keeps running the OLD code while the file on
    disk and the file on the wire both look correct. That cost a real debugging detour once —
    a fix that was present in the file, present in the response, and absent from the page.
    """

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()


handler = functools.partial(NoCache, directory=str(ROOT))
socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("127.0.0.1", port), handler) as httpd:
    print(f"serving {ROOT} at http://127.0.0.1:{port}/")
    httpd.serve_forever()
