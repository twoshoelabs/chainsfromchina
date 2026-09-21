"""
Serve map/ on localhost so the page can fetch its JSON (file:// cannot).

    .venv/bin/python scripts/serve_map.py [port]
"""
import functools, http.server, socketserver, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "map"
port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("127.0.0.1", port), handler) as httpd:
    print(f"serving {ROOT} at http://127.0.0.1:{port}/")
    httpd.serve_forever()
