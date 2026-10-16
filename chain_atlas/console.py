"""
The owner console — a PRIVATE, localhost-only workbench for the PRO pipeline (docs/pro_spec.md §3).

The public site is static, so a secure login-gated area that writes data back is not possible. The
private area is therefore LOCAL: `python -m chain_atlas console` serves a small form in the owner's
browser, bound to 127.0.0.1 ONLY (never 0.0.0.0, never deployed) — the machine itself is the auth
boundary, nothing is exposed to the network. It does two things, on the same schema and stores the CLI
uses:

  * SUBMIT a sourced data point  -> validates via submissions.py, appends to manual/submissions.jsonl
  * WORK the verification queue   -> lists verify.queue(), records verdicts to manual/verifications.jsonl

The HTTP layer is a thin dispatcher over three pure handlers (handle_submit / handle_verdict /
handle_queue) so the logic is testable without sockets. It writes only the append-only intake/verdict
logs — never the typed stores (promotion stays a separate, deliberate step).
"""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

from . import submissions as S
from . import verify


def handle_submit(body: str, subs_path: str = "manual/submissions.jsonl"):
    """POST /api/submit — a raw submission record (JSON) -> validated + appended. (status, payload)."""
    try:
        rec = json.loads(body)
    except Exception:                                           # noqa: BLE001
        return 400, {"ok": False, "error": "body is not valid JSON"}
    try:
        saved = S.append(rec, path=subs_path)
        return 200, {"ok": True, "record": saved}
    except ValueError as e:
        return 400, {"ok": False, "error": str(e)}


def handle_verdict(body: str, verdict_path: str = verify.VERDICT_LOG):
    """POST /api/verdict — {queue_id, verdict, by?, note?, new_confidence?} -> recorded. (status, payload)."""
    try:
        d = json.loads(body)
    except Exception:                                           # noqa: BLE001
        return 400, {"ok": False, "error": "body is not valid JSON"}
    try:
        v = verify.record_verdict(d.get("queue_id"), d.get("verdict"), by=d.get("by", "owner"),
                                  note=d.get("note"), new_confidence=d.get("new_confidence"),
                                  path=verdict_path)
        return 200, {"ok": True, "verdict": v}
    except ValueError as e:
        return 400, {"ok": False, "error": str(e)}


def handle_queue(con, verdict_path: str = verify.VERDICT_LOG):
    """GET /api/queue — the open verification queue + its summary. (status, payload)."""
    items = verify.queue(con, resolved_path=verdict_path)
    return 200, {"summary": verify.summary(items), "items": items}


_PAGE = """<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width, initial-scale=1"><title>CFC owner console</title>
<style>
:root{--ink:#1a1a1a;--muted:#6b6b6b;--rule:#e2e2e2;--surface:#fafafa;--accent:#b23b2e}
*{box-sizing:border-box}body{font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
 color:var(--ink);max-width:860px;margin:0 auto;padding:18px 16px 60px;background:#fff}
h1{font-size:19px;margin:0 0 2px}.priv{color:var(--accent);font-size:12px;font-weight:600}
.sub{color:var(--muted);margin:2px 0 18px}
section{border:1px solid var(--rule);border-radius:3px;padding:16px;margin:0 0 18px;background:var(--surface)}
h2{font-size:15px;margin:0 0 10px}label{display:block;font-size:13px;color:var(--muted);margin:9px 0 0}
input,select,textarea{width:100%;margin-top:3px;padding:7px 8px;border:1px solid #cfcfcf;border-radius:3px;
 font:inherit;background:#fff}.row{display:flex;gap:10px;flex-wrap:wrap}.row>label{flex:1;min-width:150px}
button{font:inherit;padding:7px 14px;border:1px solid var(--ink);background:var(--ink);color:#fff;
 border-radius:3px;cursor:pointer;margin-top:12px}button.sec{background:#fff;color:var(--ink)}
button.v{background:#1f7a3d;border-color:#1f7a3d;padding:3px 10px;margin:0}
button.x{background:#fff;color:var(--accent);border-color:var(--accent);padding:3px 10px;margin:0 0 0 6px}
.msg{margin-top:10px;font-size:13px}.ok{color:#1f7a3d}.err{color:var(--accent)}
.qi{border-top:1px solid var(--rule);padding:9px 0;display:flex;gap:8px;align-items:flex-start;flex-wrap:wrap}
.qi .tag{font-size:11px;background:#eee;border-radius:3px;padding:1px 6px;color:#444}
.qi .b{font-weight:600}.qi .s{color:var(--muted);font-size:12px;flex-basis:100%}
.qi input.note{flex-basis:100%;margin:4px 0 0}.counts{color:var(--muted);font-size:12px;margin:0 0 8px}
</style></head><body>
<h1>Chains From China — owner console <span class=priv>· PRIVATE · localhost only</span></h1>
<p class=sub>Submit sourced data points and work the verification queue. Writes to the append-only intake
and verdict logs; nothing here is published.</p>

<section><h2>Submit a data point</h2>
<div class=row>
 <label>Chain (chain_id)<input id=brand placeholder="mixue"></label>
 <label>Dimension<select id=dimension>
   <option value=presence>presence</option><option value=scale selected>scale</option>
   <option value=economics>economics</option><option value=structure>structure</option>
   <option value=narrative>narrative</option></select></label>
 <label>Metric<input id=metric placeholder="store_count_total"></label>
</div>
<label>Value / fact<input id=value placeholder="59823 — or a sentence"></label>
<div class=row>
 <label>Unit<input id=unit placeholder="stores / USD (optional)"></label>
 <label>As of (YYYY-MM-DD)<input id=as_of placeholder="2025-12-31"></label>
 <label>Confidence<select id=confidence>
   <option>high</option><option selected>medium</option><option>low</option></select></label>
</div>
<label>Source<input id=source placeholder="FY2025 annual report (HKEX:2555)"></label>
<div class=row>
 <label>Source URL<input id=source_url placeholder="https://… (optional)"></label>
 <label>Provenance tier<select id=provenance_tier>
   <option value="">(infer)</option><option>measured</option><option>filed</option>
   <option>modeled</option><option>reported</option></select></label>
 <label>Submitter<input id=submitter value=owner></label>
</div>
<label>Note<textarea id=note rows=2 placeholder="optional"></textarea></label>
<label>Geo address (presence only)<input id=geo_address placeholder="123 Main St, City, ST"></label>
<button onclick=submit()>Save data point</button>
<div id=smsg class=msg></div>
</section>

<section><h2>Verification queue</h2>
<div id=counts class=counts>loading…</div>
<div id=queue></div>
</section>

<script>
const $ = id => document.getElementById(id);
async function submit(){
 const dim = $('dimension').value;
 const r = {brand:$('brand').value.trim(), dimension:dim, metric:$('metric').value.trim()||dim,
   value:$('value').value.trim(), unit:$('unit').value.trim()||null, as_of:$('as_of').value.trim(),
   confidence:$('confidence').value, source:$('source').value.trim(),
   source_url:$('source_url').value.trim()||null,
   provenance_tier:$('provenance_tier').value||undefined,
   submitter:$('submitter').value.trim()||'owner', note:$('note').value.trim()||null, status:'submitted'};
 if(dim==='presence' && $('geo_address').value.trim())
   r.geo={address:$('geo_address').value.trim()};
 const res = await fetch('/api/submit',{method:'POST',body:JSON.stringify(r)});
 const j = await res.json(); const m = $('smsg');
 if(j.ok){ m.className='msg ok'; m.textContent='Saved · id '+j.record.id+' · tier '+j.record.provenance_tier;
   ['brand','metric','value','unit','as_of','source','source_url','note','geo_address'].forEach(i=>$(i).value='');
   loadQueue(); }
 else { m.className='msg err'; m.textContent='Rejected: '+j.error; }
}
async function loadQueue(){
 const j = await (await fetch('/api/queue')).json();
 $('counts').textContent = j.summary.total+' open — '+
   Object.entries(j.summary.by_reason).map(([k,v])=>k+':'+v).join('  ');
 const q = $('queue'); q.innerHTML='';
 for(const i of j.items.slice(0,60)){
   const d = document.createElement('div'); d.className='qi';
   d.innerHTML = '<span class=tag>'+i.reason+'</span>'+
     '<span class=b>'+(i.brand||'')+'</span>/'+i.layer+':'+i.metric+' = '+
     String(i.value).slice(0,60)+' <span style="color:#999">('+(i.confidence||'')+')</span>';
   const note = document.createElement('input'); note.className='note'; note.placeholder='verdict note (optional)';
   const bv = document.createElement('button'); bv.className='v'; bv.textContent='Verify';
   const bx = document.createElement('button'); bx.className='x'; bx.textContent='Reject';
   bv.onclick = ()=>verdict(i.id,'verified',note.value);
   bx.onclick = ()=>verdict(i.id,'rejected',note.value);
   const src = document.createElement('span'); src.className='s'; src.textContent = i.source||'';
   d.append(document.createElement('br'), bv, bx, note, src);
   q.append(d);
 }
 if(j.items.length>60){ const more=document.createElement('p'); more.className='counts';
   more.textContent='…and '+(j.items.length-60)+' more'; q.append(more);}
}
async function verdict(id,v,note){
 await fetch('/api/verdict',{method:'POST',body:JSON.stringify({queue_id:id,verdict:v,by:'owner',note:note||null})});
 loadQueue();
}
loadQueue();
</script></body></html>"""


class _Handler(BaseHTTPRequestHandler):
    def _send(self, status, body, ctype="application/json"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):                                           # noqa: N802
        if self.path in ("/", "/index.html") or self.path.startswith("/?"):
            return self._send(200, _PAGE, "text/html; charset=utf-8")
        if self.path.startswith("/api/queue"):
            from . import db
            status, payload = handle_queue(db.connect())
            return self._send(status, json.dumps(payload, ensure_ascii=False))
        return self._send(404, '{"error":"not found"}')

    def do_POST(self):                                          # noqa: N802
        n = int(self.headers.get("Content-Length", "0") or 0)
        body = self.rfile.read(n).decode("utf-8") if n else ""
        if self.path == "/api/submit":
            status, payload = handle_submit(body)
        elif self.path == "/api/verdict":
            status, payload = handle_verdict(body)
        else:
            status, payload = 404, {"error": "not found"}
        return self._send(status, json.dumps(payload, ensure_ascii=False))

    def log_message(self, *a):                                  # quiet — no request logging
        pass


def serve(port: int = 8787, open_browser: bool = True):
    """Start the private console on 127.0.0.1:<port>. Blocks until Ctrl-C."""
    httpd = HTTPServer(("127.0.0.1", port), _Handler)           # localhost ONLY — never 0.0.0.0
    url = f"http://127.0.0.1:{port}/"
    print(f"owner console — PRIVATE, localhost only → {url}   (Ctrl-C to stop)")
    if open_browser:
        try:
            import webbrowser
            webbrowser.open(url)
        except Exception:                                      # noqa: BLE001
            pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()
