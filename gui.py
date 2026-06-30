#!/usr/bin/env python3
"""
Excito GUI — a zero-dependency browser front end for RSPMatch.

Uses only the Python standard library (no numpy/matplotlib/streamlit/tkinter),
so it runs anywhere Python 3 does. It is a thin shell over the existing run.sh:
pick a run configuration, click Run, and see the target-vs-matched spectrum
plotted in the browser along with the convergence log.

    python3 gui.py            # then open http://localhost:8000

The chart is drawn with a small hand-rolled SVG log-log plotter (below), so
there are no external CDN or package dependencies.
"""

import http.server
import socketserver
import json
import os
import subprocess
import urllib.parse

REPO = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR = os.path.join(REPO, "input")
OUTPUT_DIR = os.path.join(REPO, "output")
PORT = int(os.environ.get("EXCITO_PORT", "8000"))


# ---------------------------------------------------------------------------
# Parsing helpers (stdlib only — plain lists, no numpy)
# ---------------------------------------------------------------------------

def parse_rsp(path):
    """Return list of {freq, target, computed, initial} rows from a .rsp file."""
    rows = []
    in_table = False
    with open(path) as f:
        for line in f:
            if "Freq" in line and "Damping" in line and "Target" in line:
                in_table = True
                continue
            if in_table:
                parts = line.split()
                if len(parts) >= 5:
                    try:
                        fr = float(parts[0])
                        if fr > 0:
                            rows.append({
                                "freq": fr,
                                "target": float(parts[2]),
                                "computed": float(parts[3]),
                                "initial": float(parts[4]),
                            })
                    except ValueError:
                        continue
    return rows


def parse_acc(path):
    """Return (dt, [acc...]) from an RSPMatch .acc file."""
    with open(path) as f:
        lines = f.readlines()
    hdr = lines[1].split()
    npts, dt = int(hdr[0]), float(hdr[1])
    acc = []
    for line in lines[2:]:
        for v in line.split():
            try:
                acc.append(float(v))
            except ValueError:
                pass
    return dt, acc[:npts]


def decimate(acc, dt, max_buckets=800):
    """Peak-preserving downsample for plotting: keep min & max per time bucket."""
    n = len(acc)
    if n <= max_buckets * 2:
        return ([round(i * dt, 4) for i in range(n)],
                [round(v, 5) for v in acc])
    step = n / max_buckets
    t, a = [], []
    for b in range(max_buckets):
        lo, hi = int(b * step), int((b + 1) * step)
        if hi <= lo:
            hi = lo + 1
        seg = range(lo, min(hi, n))
        imin = min(seg, key=lambda i: acc[i])
        imax = max(seg, key=lambda i: acc[i])
        for idx in sorted((imin, imax)):
            t.append(round(idx * dt, 4))
            a.append(round(acc[idx], 5))
    return t, a


def acc_data(run_dir):
    """Return downsampled matched + seed time histories (with true PGA) for a run."""
    out = {}
    mp = os.path.join(run_dir, "matched.acc")
    if os.path.exists(mp):
        dt, acc = parse_acc(mp)
        if acc:
            t, a = decimate(acc, dt)
            out["matched"] = {"name": "matched.acc", "dt": dt,
                              "pga": max(abs(v) for v in acc), "t": t, "a": a}
    seed = None
    for name in ("elcentro.acc", "ferndale.acc", "holtville.acc",
                 "treasure_island.acc", "seed.acc", "input.acc"):
        p = os.path.join(run_dir, name)
        if os.path.exists(p):
            seed = p
            break
    if seed is None:
        for f in os.listdir(run_dir):
            if f.endswith(".acc") and f != "matched.acc":
                seed = os.path.join(run_dir, f)
                break
    if seed:
        dt, acc = parse_acc(seed)
        if acc:
            t, a = decimate(acc, dt)
            out["seed"] = {"name": os.path.basename(seed), "dt": dt,
                           "pga": max(abs(v) for v in acc), "t": t, "a": a}
    return out


def read_inp_summary(name):
    """Read target (line 17) and accelerogram (line 18) from a run .inp file."""
    path = os.path.join(INPUT_DIR, name)
    target = accel = "?"
    try:
        with open(path) as f:
            lines = f.read().splitlines()
        if len(lines) >= 18:
            target = lines[16].strip()
            accel = lines[17].strip()
    except OSError:
        pass
    return {"target": target, "accel": accel}


def list_inputs():
    files = sorted(f for f in os.listdir(INPUT_DIR) if f.endswith(".inp")
                   and f != "master.inp")
    return [{"name": n, **read_inp_summary(n)} for n in files]


def list_runs():
    if not os.path.isdir(OUTPUT_DIR):
        return []
    runs = sorted((d for d in os.listdir(OUTPUT_DIR)
                   if d.startswith(("run-", "multipass-"))), reverse=True)
    return runs


def newest_run():
    runs = list_runs()
    return runs[0] if runs else None


def run_match(inp_name):
    """Invoke run.sh with the chosen .inp, return (ok, log, rsp_rows, run_dir, stats)."""
    proc = subprocess.run(
        ["./run.sh", inp_name],
        cwd=REPO, capture_output=True, text=True,
    )
    log = proc.stdout + ("\n" + proc.stderr if proc.stderr else "")
    run_dir = newest_run()
    rows, stats, acc = [], {}, {}
    if run_dir:
        rdir = os.path.join(OUTPUT_DIR, run_dir)
        rsp = os.path.join(rdir, "matched.rsp")
        if os.path.exists(rsp):
            rows = parse_rsp(rsp)
            acc = acc_data(rdir)
            if rows:
                misfits = [abs(r["computed"] - r["target"]) / r["target"] * 100
                           for r in rows if r["target"] > 0]
                stats = {
                    "avg_misfit": sum(misfits) / len(misfits) if misfits else 0,
                    "max_misfit": max(misfits) if misfits else 0,
                    "n_freq": len(rows),
                }
    return (proc.returncode == 0 and bool(rows), log, rows, run_dir, stats, acc)


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # quiet

    def _send(self, code, body, ctype="application/json"):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/":
            self._send(200, PAGE, "text/html; charset=utf-8")
        elif path == "/api/inputs":
            self._send(200, json.dumps({"inputs": list_inputs(),
                                        "runs": list_runs()}))
        elif path == "/api/results":
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            run = (qs.get("run") or [None])[0]
            if not run:
                run = newest_run()
            rows, acc = [], {}
            if run:
                rdir = os.path.join(OUTPUT_DIR, run)
                rsp = os.path.join(rdir, "matched.rsp")
                if os.path.exists(rsp):
                    rows = parse_rsp(rsp)
                    acc = acc_data(rdir)
            self._send(200, json.dumps({"run": run, "rows": rows, "acc": acc}))
        else:
            self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        if urllib.parse.urlparse(self.path).path == "/api/run":
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or "{}")
            inp = payload.get("inp", "run.inp")
            # guard against path traversal: only allow bare filenames in input/
            if "/" in inp or ".." in inp or not inp.endswith(".inp"):
                self._send(400, json.dumps({"error": "invalid run file"}))
                return
            if not os.path.exists(os.path.join(INPUT_DIR, inp)):
                self._send(404, json.dumps({"error": f"{inp} not found"}))
                return
            ok, log, rows, run_dir, stats, acc = run_match(inp)
            self._send(200, json.dumps({
                "ok": ok, "log": log, "rows": rows,
                "run": run_dir, "stats": stats, "acc": acc,
            }))
        else:
            self._send(404, json.dumps({"error": "not found"}))


# ---------------------------------------------------------------------------
# Front end (single self-contained HTML page, vanilla JS + SVG plot)
# ---------------------------------------------------------------------------

PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Excito — Spectral Matching</title>
<style>
  :root {
    --bg:#0d1117; --panel:#161b22; --line:#30363d; --ink:#e6edf3;
    --muted:#8b949e; --accent:#f0883e; --target:#e6edf3; --matched:#f0533e;
    --initial:#4493f8; --good:#3fb950;
  }
  * { box-sizing:border-box; }
  body { margin:0; font:14px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;
         background:var(--bg); color:var(--ink); }
  header { padding:18px 26px; border-bottom:1px solid var(--line);
           display:flex; align-items:baseline; gap:14px; }
  header h1 { margin:0; font-size:20px; letter-spacing:.5px; }
  header .tag { color:var(--accent); font-size:12px; }
  header .sub { color:var(--muted); font-size:12px; margin-left:auto; }
  main { display:grid; grid-template-columns:320px 1fr; gap:0; height:calc(100vh - 61px); }
  .side { border-right:1px solid var(--line); padding:22px; overflow-y:auto; }
  .content { padding:22px 26px; overflow-y:auto; }
  label { display:block; color:var(--muted); font-size:11px; text-transform:uppercase;
          letter-spacing:.8px; margin:0 0 8px; }
  select { width:100%; background:var(--panel); color:var(--ink);
           border:1px solid var(--line); border-radius:7px; padding:10px; font:inherit; }
  .meta { margin:14px 0 0; padding:12px 14px; background:var(--panel);
          border:1px solid var(--line); border-radius:7px; font-size:12px; color:var(--muted); }
  .meta b { color:var(--ink); font-weight:600; }
  button { width:100%; margin-top:18px; padding:13px; font:inherit; font-weight:600;
           background:var(--accent); color:#1a1206; border:0; border-radius:7px;
           cursor:pointer; letter-spacing:.4px; }
  button:disabled { opacity:.5; cursor:wait; }
  .stats { display:flex; gap:12px; margin-bottom:18px; flex-wrap:wrap; }
  .stat { flex:1; min-width:120px; background:var(--panel); border:1px solid var(--line);
          border-radius:8px; padding:14px 16px; }
  .stat .k { color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.6px; }
  .stat .v { font-size:22px; font-weight:600; margin-top:4px; }
  .v.good { color:var(--good); } .v.warn { color:var(--matched); }
  svg { width:100%; height:auto; background:var(--panel);
        border:1px solid var(--line); border-radius:8px; }
  .legend { display:flex; gap:20px; margin:12px 2px; font-size:12px; }
  .legend span::before { content:""; display:inline-block; width:14px; height:3px;
        margin-right:6px; vertical-align:middle; }
  .legend .t::before { background:var(--target); }
  .legend .c::before { background:var(--matched); }
  .legend .i::before { background:var(--initial); border-top:2px dashed var(--initial); height:0; }
  .legend .i2::before { background:var(--initial); }
  pre { background:#010409; border:1px solid var(--line); border-radius:8px;
        padding:14px; font-size:12px; color:#9da7b3; max-height:320px; overflow:auto;
        white-space:pre-wrap; margin-top:22px; }
  h2 { font-size:13px; text-transform:uppercase; letter-spacing:.8px; color:var(--muted);
       margin:0 0 12px; font-weight:600; }
  .empty { color:var(--muted); padding:60px 0; text-align:center; }
</style>
</head>
<body>
<header>
  <h1>EXCITO</h1><span class="tag">excito match · RSPMatch</span>
  <span class="sub" id="sub">time-domain spectral matching</span>
</header>
<main>
  <div class="side">
    <label for="inp">Run configuration</label>
    <select id="inp"></select>
    <div class="meta" id="meta">—</div>
    <button id="run">▶ Run Match</button>
    <label style="margin-top:24px">Previous runs</label>
    <select id="runs"></select>
  </div>
  <div class="content">
    <div class="stats" id="stats" style="display:none">
      <div class="stat"><div class="k">Avg misfit</div><div class="v" id="avg">—</div></div>
      <div class="stat"><div class="k">Max misfit</div><div class="v" id="max">—</div></div>
      <div class="stat"><div class="k">Frequencies</div><div class="v" id="nf">—</div></div>
    </div>
    <div class="legend" id="legend" style="display:none">
      <span class="t">Target</span><span class="c">Matched</span><span class="i">Initial (seed)</span>
    </div>
    <div id="plot"><div class="empty">Pick a configuration and click Run, or load a previous run.</div></div>
    <div id="thwrap" style="display:none">
      <h2 style="margin-top:26px">Time History</h2>
      <div class="legend" id="thlegend"></div>
      <div id="th"></div>
    </div>
    <pre id="log" style="display:none"></pre>
  </div>
</main>
<script>
const $ = s => document.querySelector(s);

async function loadInputs() {
  const r = await fetch('/api/inputs'); const d = await r.json();
  const sel = $('#inp'); sel.innerHTML = '';
  d.inputs.forEach(i => {
    const o = document.createElement('option');
    o.value = i.name; o.textContent = i.name;
    o.dataset.target = i.target; o.dataset.accel = i.accel;
    sel.appendChild(o);
  });
  const runs = $('#runs'); runs.innerHTML = '<option value="">— select —</option>';
  d.runs.forEach(rn => { const o=document.createElement('option'); o.value=rn; o.textContent=rn; runs.appendChild(o); });
  updateMeta();
}
function updateMeta() {
  const o = $('#inp').selectedOptions[0];
  $('#meta').innerHTML = o ? `target → <b>${o.dataset.target}</b><br>seed&nbsp;&nbsp;&nbsp;→ <b>${o.dataset.accel}</b>` : '—';
}
$('#inp').addEventListener('change', updateMeta);

// --- log-log SVG plotter ---------------------------------------------------
function plot(rows) {
  if (!rows || !rows.length) { $('#plot').innerHTML = '<div class="empty">No spectrum data in this run.</div>'; return; }
  const W=820, H=440, m={l:64,r:20,t:18,b:52};
  const fx = rows.map(r=>r.freq);
  const ys = rows.flatMap(r=>[r.target,r.computed,r.initial]).filter(v=>v>0);
  const xmin=Math.min(...fx), xmax=Math.max(...fx);
  const ymin=Math.min(...ys), ymax=Math.max(...ys);
  const lx=Math.log10, X=v=>m.l+(lx(v)-lx(xmin))/(lx(xmax)-lx(xmin))*(W-m.l-m.r);
  const Y=v=>H-m.b-(lx(Math.max(v,ymin))-lx(ymin))/(lx(ymax)-lx(ymin))*(H-m.t-m.b);
  const path=(key,extra)=>{
    const pts=rows.filter(r=>r[key]>0).map(r=>`${X(r.freq).toFixed(1)},${Y(r[key]).toFixed(1)}`);
    return `<polyline fill="none" points="${pts.join(' ')}" ${extra}/>`;
  };
  const ticks=(min,max)=>{ const t=[]; let p=Math.floor(lx(min));
    for(;p<=Math.ceil(lx(max));p++){[1,2,5].forEach(d=>{const v=d*10**p; if(v>=min&&v<=max)t.push(v);});} return t; };
  let g='';
  // green "good match" band: contiguous frequencies within 5% of target
  const good=rows.filter(r=>r.target>0 && Math.abs(r.computed-r.target)/r.target<0.05).map(r=>r.freq);
  if(good.length){ const gx1=X(Math.min(...good)), gx2=X(Math.max(...good));
    g+=`<rect x="${gx1.toFixed(1)}" y="${m.t}" width="${(gx2-gx1).toFixed(1)}" height="${H-m.b-m.t}" fill="#3fb950" opacity=".08"/>`;
    g+=`<text x="${((gx1+gx2)/2).toFixed(1)}" y="${m.t+14}" fill="#3fb950" font-size="10" text-anchor="middle" opacity=".75">good match ${Math.min(...good)}–${Math.max(...good)} Hz</text>`; }
  ticks(xmin,xmax).forEach(v=>{ const x=X(v);
    g+=`<line x1="${x}" y1="${m.t}" x2="${x}" y2="${H-m.b}" stroke="#30363d" stroke-width=".5"/>`;
    g+=`<text x="${x}" y="${H-m.b+18}" fill="#8b949e" font-size="11" text-anchor="middle">${v>=1?v:v}</text>`; });
  ticks(ymin,ymax).forEach(v=>{ const y=Y(v);
    g+=`<line x1="${m.l}" y1="${y}" x2="${W-m.r}" y2="${y}" stroke="#30363d" stroke-width=".5"/>`;
    g+=`<text x="${m.l-8}" y="${y+4}" fill="#8b949e" font-size="11" text-anchor="end">${v>=0.1?v:v.toExponential(0)}</text>`; });
  const svg=`<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg">
    ${g}
    <text x="${(W)/2}" y="${H-10}" fill="#8b949e" font-size="12" text-anchor="middle">Frequency (Hz)</text>
    <text x="16" y="${H/2}" fill="#8b949e" font-size="12" text-anchor="middle" transform="rotate(-90 16 ${H/2})">Spectral Acceleration (g)</text>
    ${path('initial','stroke="#4493f8" stroke-width="1.4" stroke-dasharray="5 4" opacity=".8"')}
    ${path('target','stroke="#e6edf3" stroke-width="2.5"')}
    ${path('computed','stroke="#f0533e" stroke-width="1.8"')}
    ${rows.filter(r=>r.computed>0).map(r=>`<circle cx="${X(r.freq).toFixed(1)}" cy="${Y(r.computed).toFixed(1)}" r="3" fill="#f0533e"/>`).join('')}
  </svg>`;
  $('#plot').innerHTML=svg; $('#legend').style.display='flex';
}

// --- linear time-history plotter (seed vs matched) -------------------------
function plotTH(acc) {
  const box=$('#th'), wrap=$('#thwrap');
  if(!acc || (!acc.seed && !acc.matched)){ wrap.style.display='none'; return; }
  wrap.style.display='block';
  const series=[acc.seed,acc.matched].filter(Boolean);
  const W=820,H=300,m={l:64,r:20,t:18,b:46};
  const tmax=Math.max(...series.map(s=>s.t[s.t.length-1]||0));
  const amax=Math.max(...series.map(s=>Math.max(...s.a.map(Math.abs))))||0.1;
  const X=v=>m.l+v/tmax*(W-m.l-m.r);
  const Y=v=>m.t+(H-m.t-m.b)/2 - v/amax*((H-m.t-m.b)/2);
  const line=(s,color,w)=>`<polyline fill="none" stroke="${color}" stroke-width="${w}" opacity=".75" points="${
    s.t.map((t,i)=>`${X(t).toFixed(1)},${Y(s.a[i]).toFixed(1)}`).join(' ')}"/>`;
  let g='';
  for(let k=0;k<=4;k++){ const tv=tmax*k/4, x=X(tv);
    g+=`<line x1="${x}" y1="${m.t}" x2="${x}" y2="${H-m.b}" stroke="#30363d" stroke-width=".5"/>`;
    g+=`<text x="${x}" y="${H-m.b+18}" fill="#8b949e" font-size="11" text-anchor="middle">${tv.toFixed(0)}</text>`; }
  [-amax,0,amax].forEach(v=>{ const y=Y(v);
    g+=`<line x1="${m.l}" y1="${y.toFixed(1)}" x2="${W-m.r}" y2="${y.toFixed(1)}" stroke="#30363d" stroke-width=".5"/>`;
    g+=`<text x="${m.l-8}" y="${(y+4).toFixed(1)}" fill="#8b949e" font-size="11" text-anchor="end">${v.toFixed(2)}</text>`; });
  const pgaTxt=`PGA seed ${acc.seed?acc.seed.pga.toFixed(3):'—'}g  |  PGA matched ${acc.matched?acc.matched.pga.toFixed(3):'—'}g`;
  box.innerHTML=`<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg">${g}
    <text x="${W/2}" y="${H-8}" fill="#8b949e" font-size="12" text-anchor="middle">Time (seconds)</text>
    <text x="16" y="${H/2}" fill="#8b949e" font-size="12" text-anchor="middle" transform="rotate(-90 16 ${H/2})">Acceleration (g)</text>
    ${acc.seed?line(acc.seed,'#4493f8',0.7):''}
    ${acc.matched?line(acc.matched,'#f0533e',0.8):''}
    <text x="${m.l+6}" y="${H-m.b-6}" fill="#8b949e" font-size="11">${pgaTxt}</text>
  </svg>`;
  $('#thlegend').innerHTML = (acc.seed?`<span class="i2">Original (${acc.seed.name})</span>`:'')+
                             (acc.matched?'<span class="c">Matched</span>':'');
}
function showStats(s) {
  if (!s || s.n_freq===undefined) { $('#stats').style.display='none'; return; }
  $('#stats').style.display='flex';
  const a=$('#avg'), x=$('#max');
  a.textContent=s.avg_misfit.toFixed(1)+'%'; x.textContent=s.max_misfit.toFixed(0)+'%';
  $('#nf').textContent=s.n_freq;
  a.className='v '+(s.avg_misfit<5?'good':'warn');
  x.className='v '+(s.max_misfit<10?'good':'warn');
}

$('#run').addEventListener('click', async () => {
  const btn=$('#run'); btn.disabled=true; btn.textContent='⏳ Running…';
  $('#sub').textContent='running '+$('#inp').value+' …';
  try {
    const r=await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({inp:$('#inp').value})});
    const d=await r.json();
    $('#log').style.display='block'; $('#log').textContent=d.log||'(no output)';
    plot(d.rows); plotTH(d.acc); showStats(d.stats||{});
    $('#sub').textContent=d.run?('output → '+d.run):'done';
    loadInputs();
  } catch(e){ $('#log').style.display='block'; $('#log').textContent='Error: '+e; }
  btn.disabled=false; btn.textContent='▶ Run Match';
});

$('#runs').addEventListener('change', async e => {
  if (!e.target.value) return;
  const r=await fetch('/api/results?run='+encodeURIComponent(e.target.value));
  const d=await r.json(); plot(d.rows); plotTH(d.acc);
  $('#sub').textContent='viewing → '+d.run;
  const ms=d.rows.filter(x=>x.target>0).map(x=>Math.abs(x.computed-x.target)/x.target*100);
  showStats({avg_misfit:ms.reduce((a,b)=>a+b,0)/ms.length, max_misfit:Math.max(...ms), n_freq:d.rows.length});
  $('#log').style.display='none';
});

loadInputs();
</script>
</body>
</html>
"""


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("", PORT), Handler) as httpd:
        print(f"Excito GUI → http://localhost:{PORT}  (Ctrl-C to stop)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped.")


if __name__ == "__main__":
    main()
