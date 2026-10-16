"""
The owner console — a PRIVATE, localhost-only workbench for the PRO pipeline (docs/pro_spec.md §3).

The public site is static, so a secure login-gated area that writes data back is not possible. The
private area is therefore LOCAL: `python -m chain_atlas console` serves a small form in the owner's
browser, bound to 127.0.0.1 ONLY (never 0.0.0.0, never deployed) — the machine itself is the auth
boundary, nothing is exposed to the network. It does two things, on the same stores the CLI uses:

  * DROP a source   -> press/financial/analyst/filings per chain into the git-ignored evidence library
                       (sources.py): the raw material PRO facts get extracted from.
  * WORK the queue  -> lists verify.queue(), records verdicts (verified/watch/rejected) with an optional
                       screenshot, to manual/verifications.jsonl.

The HTTP layer is a thin dispatcher over the pure handlers (handle_source / handle_library /
handle_verdict / handle_queue) so the logic is testable without sockets. It writes only the local
evidence library and the append-only verdict log — never the typed stores (promotion stays separate).
"""
import base64
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

from . import sources
from . import verify


def handle_source(body: str, lib=sources.LIB):
    """POST /api/source — drop a source (metadata + pasted text and/or a base64 file). (status, payload)."""
    try:
        d = json.loads(body)
    except Exception:                                          # noqa: BLE001
        return 400, {"ok": False, "error": "body is not valid JSON"}
    fb = fn = None
    f = d.get("file")
    if f and f.get("b64"):
        try:
            fb = base64.b64decode(f["b64"])
            fn = f.get("name")
        except Exception:                                      # noqa: BLE001
            return 400, {"ok": False, "error": "attached file is not valid base64"}
    meta = {k: d.get(k) for k in ("chain", "kind", "title", "publisher", "date", "url",
                                  "tags", "note", "submitter")}
    try:
        rec = sources.add_source(meta, text=d.get("text"), file_bytes=fb, file_name=fn, lib=lib)
        return 200, {"ok": True, "source": rec}
    except ValueError as e:
        return 400, {"ok": False, "error": str(e)}


def handle_library(lib=sources.LIB):
    """GET /api/library — the corpus shape (counts per chain) + the most recent drops. (status, payload)."""
    return 200, {"by_chain": sources.by_chain(lib=lib), "recent": sources.list_sources(lib=lib)[:30]}


def handle_verdict(body: str, verdict_path: str = verify.VERDICT_LOG, lib=sources.LIB):
    """POST /api/verdict — {queue_id, verdict, by?, note?, new_confidence?, brand?,
    screenshots?[{name,b64}], screenshot?{name,b64}}. verdict is one of verify.VERDICTS
    (verified/rejected/watch); any attached screenshots are saved into the chain's evidence library and
    referenced from the verdict (`evidence` is a list of paths). The legacy singular `screenshot` is still
    accepted. (status, payload)."""
    try:
        d = json.loads(body)
    except Exception:                                           # noqa: BLE001
        return 400, {"ok": False, "error": "body is not valid JSON"}
    shots = list(d.get("screenshots") or [])
    if d.get("screenshot"):                                     # legacy singular
        shots.append(d["screenshot"])
    evidence = []
    for n, shot in enumerate(shots, 1):
        if not (shot and shot.get("b64")):
            continue
        try:
            fb = base64.b64decode(shot["b64"])
            srec = sources.add_source(
                {"chain": d.get("brand") or "_unassigned", "kind": "other",
                 "title": f"Verdict evidence — {d.get('queue_id')}" + (f" ({n})" if len(shots) > 1 else ""),
                 "note": d.get("note"), "tags": ["verdict-evidence"]},
                file_bytes=fb, file_name=shot.get("name"), lib=lib)
            evidence.append(srec["file"])
        except Exception as e:                                 # noqa: BLE001
            return 400, {"ok": False, "error": f"screenshot not saved: {e}"}
    try:
        v = verify.record_verdict(d.get("queue_id"), d.get("verdict"), by=d.get("by", "owner"),
                                  note=d.get("note"), new_confidence=d.get("new_confidence"),
                                  evidence=(evidence or None), path=verdict_path)
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
 color:var(--ink);max-width:880px;margin:0 auto;padding:18px 16px 60px;background:#fff}
h1{font-size:19px;margin:0 0 2px}.priv{color:var(--accent);font-size:12px;font-weight:600}
.sub{color:var(--muted);margin:2px 0 18px}
section{border:1px solid var(--rule);border-radius:3px;padding:16px;margin:0 0 18px;background:var(--surface)}
h2{font-size:15px;margin:0 0 4px}.h2note{color:var(--muted);font-size:12px;margin:0 0 10px}
label{display:block;font-size:13px;color:var(--muted);margin:9px 0 0}
input,select,textarea{width:100%;margin-top:3px;padding:7px 8px;border:1px solid #cfcfcf;border-radius:3px;
 font:inherit;background:#fff}textarea{font-family:ui-monospace,Menlo,monospace;font-size:12.5px}
.row{display:flex;gap:10px;flex-wrap:wrap}.row>label{flex:1;min-width:140px}
button{font:inherit;padding:7px 14px;border:1px solid var(--ink);background:var(--ink);color:#fff;
 border-radius:3px;cursor:pointer;margin-top:12px}
button.v{background:#1f7a3d;border-color:#1f7a3d;padding:3px 10px;margin:0}
button.w{background:#b07d12;border-color:#b07d12;padding:3px 10px;margin:0 0 0 6px}
button.x{background:#fff;color:var(--accent);border-color:var(--accent);padding:3px 10px;margin:0 0 0 6px}
.qi input.shot{margin:4px 0 0;font-size:12px}
.msg{margin-top:10px;font-size:13px}.ok{color:#1f7a3d}.err{color:var(--accent)}
.chips{display:flex;gap:6px;flex-wrap:wrap;margin:2px 0 10px}
.chip{font-size:12px;background:#eee;border-radius:12px;padding:2px 9px;color:#333}
.chip b{color:var(--accent)}
.src{border-top:1px solid var(--rule);padding:8px 0}.src .t{font-weight:600}
.src .m{color:var(--muted);font-size:12px}.src .e{color:#444;font-size:12.5px;margin-top:2px}
.qi{border-top:1px solid var(--rule);padding:9px 0}.qi .tag{font-size:11px;background:#eee;border-radius:3px;padding:1px 6px;color:#444}
.qi .b{font-weight:600}.qi .s{color:var(--muted);font-size:12px;display:block;margin-top:4px}
.qi a.s.link{color:var(--accent);text-decoration:none}.qi a.s.link:hover{text-decoration:underline}
.qi input.note{margin:4px 0 0}.counts{color:var(--muted);font-size:12px;margin:0 0 8px}
.screen{border:1px dashed #bbb;border-radius:4px;padding:8px 10px;margin:6px 0 0;background:#fff;
 cursor:pointer;font-size:12px;color:var(--muted);outline:none}
.screen:focus{border-color:#999}.screen.drag{border-color:var(--accent);background:#fff6f5;color:var(--accent)}
.screen.has{border-style:solid;border-color:#cfcfcf;color:#444}
.thumbs{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}
.thumb{position:relative;width:56px;height:56px;border:1px solid var(--rule);border-radius:3px;
 overflow:hidden;background:#f3f3f3}.thumb img{width:100%;height:100%;object-fit:cover;display:block}
.thumb b{position:absolute;top:0;right:0;color:#fff;background:rgba(0,0,0,.6);border-radius:0 0 0 4px;
 font-size:12px;line-height:1;padding:2px 5px;cursor:pointer}
</style></head><body>
<h1>Chains From China — owner console <span class=priv>· PRIVATE · localhost only</span></h1>
<p class=sub>Build depth on each chain: drop the raw material (press, financial, analyst, filings), then
work the verification queue. Sources stay on this machine; nothing here is published.</p>

<section><h2>Drop a source</h2>
<p class=h2note>A press report, financial filing, analyst note or company statement — paste the text,
 attach a file, or both. This is the evidence PRO facts get extracted from.</p>
<div class=row>
 <label>Chain (chain_id) <input id=chain placeholder="chabaidao"></label>
 <label>Kind <select id=kind>
   <option>press</option><option>financial</option><option>analyst</option>
   <option>filing</option><option>company</option><option>other</option></select></label>
 <label>Date (YYYY-MM-DD) <input id=date placeholder="2026-04-24"></label>
</div>
<label>Title <input id=title placeholder="ChaPanda FY2025 Annual Report"></label>
<div class=row>
 <label>Publisher / outlet <input id=publisher placeholder="HKEX · Caixin · Nomura"></label>
 <label>URL <input id=url placeholder="https://… (optional)"></label>
 <label>Tags (comma-sep) <input id=tags placeholder="revenue, store-count"></label>
</div>
<label>Content — paste the article / report text <textarea id=text rows=8
   placeholder="Paste the full text or the relevant passages here…"></textarea></label>
<label>…or attach a file (PDF, etc.) <input type=file id=file></label>
<label>Note <input id=note placeholder="what's useful in it (optional)"></label>
<button onclick=dropSource()>Save to library</button>
<div id=dmsg class=msg></div>
</section>

<section><h2>Library</h2>
<p class=h2note>The corpus so far — how much depth each chain has.</p>
<div id=bychain class=chips>loading…</div>
<div id=recent></div>
</section>

<section><h2>Verification queue</h2>
<p class=h2note><b>Verify</b> = confirmed open/true · <b>Watch</b> = real but not open yet
 (coming-soon / temporarily closed) · <b>Reject</b> = not real. Each item has a screenshot space —
 attach as many as you like (click, drag-drop, or ⌘V paste); they're saved as evidence with the verdict.</p>
<div id=counts class=counts>loading…</div>
<div id=queue></div>
</section>

<script>
const $ = id => document.getElementById(id);
function readFile(input){
 return new Promise(res => {
   const f = input.files && input.files[0];
   if(!f){ res(null); return; }
   const r = new FileReader();
   r.onload = () => res({name:f.name, b64:r.result.split(',')[1]});
   r.readAsDataURL(f);
 });
}
async function dropSource(){
 const file = await readFile($('file'));
 const meta = {chain:$('chain').value.trim(), kind:$('kind').value,
   title:$('title').value.trim(), publisher:$('publisher').value.trim()||null,
   date:$('date').value.trim()||null, url:$('url').value.trim()||null,
   tags:$('tags').value.split(',').map(s=>s.trim()).filter(Boolean),
   note:$('note').value.trim()||null, submitter:'owner',
   text:$('text').value, file:file};
 const j = await (await fetch('/api/source',{method:'POST',body:JSON.stringify(meta)})).json();
 const m = $('dmsg');
 if(j.ok){ m.className='msg ok'; m.textContent='Saved · '+j.source.id
     +(j.source.file?' · file '+j.source.orig_name:'')+(j.source.text?' · text':'');
   ['title','publisher','url','tags','text','note'].forEach(i=>$(i).value=''); $('file').value='';
   loadLibrary(); }
 else { m.className='msg err'; m.textContent='Rejected: '+j.error; }
}
async function loadLibrary(){
 const j = await (await fetch('/api/library')).json();
 const bc = $('bychain'); bc.innerHTML='';
 const ents = Object.entries(j.by_chain);
 if(!ents.length){ bc.innerHTML='<span class=counts>No sources yet — drop the first one above.</span>'; }
 for(const [c,n] of ents){ const s=document.createElement('span'); s.className='chip';
   s.innerHTML=c+' <b>'+n+'</b>'; bc.append(s); }
 const r = $('recent'); r.innerHTML='';
 for(const s of j.recent){ const d=document.createElement('div'); d.className='src';
   d.innerHTML='<div class=t>['+s.kind+'] '+s.title+'</div>'+
     '<div class=m>'+s.chain+(s.publisher?' · '+s.publisher:'')+(s.date?' · '+s.date:'')
     +(s.file?' · 📎 '+(s.orig_name||'file'):'')+'</div>'+
     (s.excerpt?'<div class=e>'+s.excerpt+'…</div>':''); r.append(d); }
}
let activeSpace = null;                       // the screenshot space a ⌘V paste lands in
function fileToB64(f){ return new Promise(res=>{ const r=new FileReader();
  r.onload=()=>res(r.result.split(',')[1]); r.readAsDataURL(f); }); }
function makeScreenSpace(){
 const stash = [];                            // {name, b64, url}
 const wrap = document.createElement('div');
 const zone = document.createElement('div'); zone.className='screen'; zone.tabIndex=0;
 const thumbs = document.createElement('div'); thumbs.className='thumbs';
 const inp = document.createElement('input'); inp.type='file'; inp.accept='image/*';
 inp.multiple=true; inp.style.display='none';
 wrap.append(zone, thumbs, inp);
 const space = {el:wrap, stash, addFiles};
 function label(){ zone.classList.toggle('has', stash.length>0);
   zone.textContent = stash.length ? ('📷 '+stash.length+' screenshot'+(stash.length>1?'s':'')
     +' — click / drop / ⌘V to add more') : '📷 Screenshots — click, drop, or paste (⌘V)'; }
 function render(){ thumbs.innerHTML='';
   stash.forEach((s,idx)=>{ const t=document.createElement('div'); t.className='thumb';
     const im=document.createElement('img'); im.src=s.url;
     const x=document.createElement('b'); x.textContent='×'; x.title='remove';
     x.onclick=(e)=>{ e.stopPropagation(); stash.splice(idx,1); render(); };
     t.append(im,x); thumbs.append(t); }); label(); }
 async function addFiles(files){
   for(const f of files){ if(!f || !(f.type||'').startsWith('image/')) continue;
     const b64 = await fileToB64(f);
     stash.push({name:f.name||'screenshot.png', b64, url:'data:'+f.type+';base64,'+b64}); }
   render(); }
 zone.onclick = ()=>{ activeSpace=space; inp.click(); };
 zone.onfocus = ()=>{ activeSpace=space; };
 // snapshot the FileList to an array BEFORE clearing the input — clearing empties the live FileList
 // that addFiles() iterates asynchronously, which would drop all but the first pick.
 inp.onchange = ()=>{ const fs=[...inp.files]; inp.value=''; addFiles(fs); };
 zone.ondragover = (e)=>{ e.preventDefault(); zone.classList.add('drag'); };
 zone.ondragleave = ()=>zone.classList.remove('drag');
 zone.ondrop = (e)=>{ e.preventDefault(); zone.classList.remove('drag');
   activeSpace=space; addFiles([...e.dataTransfer.files]); };
 label();
 return space;
}
document.addEventListener('paste', e=>{
 if(!activeSpace || !e.clipboardData) return;
 const files=[]; for(const it of e.clipboardData.items){
   if((it.type||'').startsWith('image/')){ const f=it.getAsFile(); if(f) files.push(f); } }
 if(files.length){ e.preventDefault(); activeSpace.addFiles(files); }
});
async function loadQueue(){
 const j = await (await fetch('/api/queue')).json();
 $('counts').textContent = j.summary.total+' open — '+
   Object.entries(j.summary.by_reason).map(([k,v])=>k+':'+v).join('  ');
 const q = $('queue'); q.innerHTML='';
 for(const i of j.items.slice(0,60)){
   const d = document.createElement('div'); d.className='qi';
   d.innerHTML = '<span class=tag>'+i.reason+'</span> <span class=b>'+(i.brand||'')+'</span>/'
     +i.layer+':'+i.metric+' = '+String(i.value).slice(0,60)
     +' <span style="color:#999">('+(i.confidence||'')+')</span>';
   const note = document.createElement('input'); note.className='note'; note.placeholder='verdict note (optional)';
   const space = makeScreenSpace();
   const bv = document.createElement('button'); bv.className='v'; bv.textContent='Verify';
   const bw = document.createElement('button'); bw.className='w'; bw.textContent='Watch';
   const bx = document.createElement('button'); bx.className='x'; bx.textContent='Reject';
   bv.onclick = ()=>verdict(i.id,'verified',note.value,i.brand,space);
   bw.onclick = ()=>verdict(i.id,'watch',note.value,i.brand,space);
   bx.onclick = ()=>verdict(i.id,'rejected',note.value,i.brand,space);
   let src;
   if(i.source_url){ src = document.createElement('a'); src.className='s link';
     src.href=i.source_url; src.target='_blank'; src.rel='noopener noreferrer';
     src.textContent=(i.source||i.source_url)+' ↗'; }
   else { src = document.createElement('span'); src.className='s'; src.textContent = i.source||''; }
   d.append(document.createElement('div'), bv, bw, bx, note, space.el, src);
   q.append(d);
 }
 if(j.items.length>60){ const more=document.createElement('p'); more.className='counts';
   more.textContent='…and '+(j.items.length-60)+' more'; q.append(more);}
}
async function verdict(id,v,note,brand,space){
 const shots = (space ? space.stash : []).map(s=>({name:s.name, b64:s.b64}));
 await fetch('/api/verdict',{method:'POST',body:JSON.stringify(
   {queue_id:id,verdict:v,by:'owner',note:note||null,brand:brand||null,screenshots:shots})});
 loadQueue();
}
loadLibrary(); loadQueue();
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
        if self.path.startswith("/api/library"):
            status, payload = handle_library()
            return self._send(status, json.dumps(payload, ensure_ascii=False))
        return self._send(404, '{"error":"not found"}')

    def do_POST(self):                                          # noqa: N802
        n = int(self.headers.get("Content-Length", "0") or 0)
        body = self.rfile.read(n).decode("utf-8") if n else ""
        if self.path == "/api/source":
            status, payload = handle_source(body)
        elif self.path == "/api/verdict":
            status, payload = handle_verdict(body)
        else:
            status, payload = 404, {"error": "not found"}
        return self._send(status, json.dumps(payload, ensure_ascii=False))

    def log_message(self, *a):                                  # quiet — no request logging
        pass


def serve(port: int = 8787, open_browser: bool = True):
    """Start the private console on 127.0.0.1:<port>. Blocks until Ctrl-C."""
    import errno
    try:
        httpd = HTTPServer(("127.0.0.1", port), _Handler)       # localhost ONLY — never 0.0.0.0
    except OSError as e:
        if e.errno == errno.EADDRINUSE:                         # an earlier console is still running
            print(f"Port {port} is already in use — an earlier console is probably still running.")
            print(f"  stop it:  lsof -ti :{port} | xargs kill")
            print(f"  or:       python -m chain_atlas console --port {port + 1}")
            return 1
        raise
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
