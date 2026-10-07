"""mind-viz: render a swarm's message board as an interactive constellation.

`swarm viz swarms/<name>` writes a single self-contained HTML file:
no dependencies, no network — a starfield where the swarm's goal is the
center, agents orbit it, and findings/questions/answers hang as stars
you can hover, drag and zoom.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

from .board import Board

SOURCE_RE = re.compile(r"\[source:\s*([^\];]+)")


def _src(text: str) -> str | None:
    m = SOURCE_RE.search(text)
    return m.group(1).strip() if m else None


def build_graph(board: Board) -> dict:
    """Nodes + edges laid out radially (deterministic, no physics needed)."""
    nodes: list[dict] = []
    edges: list[dict] = []

    def nid(prefix: str, i: int) -> str:
        return f"{prefix}{i}"

    nodes.append({
        "id": "hub", "kind": "goal", "label": board.goal or board.name,
        "x": 0.0, "y": 0.0, "r": 26, "detail": f"swarm: {board.name}",
    })

    n_agents = max(len(board.agents), 1)
    for i, role in enumerate(board.agents):
        ang = 2 * math.pi * i / n_agents - math.pi / 2
        nodes.append({
            "id": f"agent{i}", "kind": "agent", "label": role,
            "x": 210 * math.cos(ang), "y": 210 * math.sin(ang), "r": 13,
            "detail": f"agents/{role}.md",
        })
        edges.append({"a": "hub", "b": f"agent{i}", "kind": "member"})

    items = len(board.findings) + len(board.questions)
    ring = 0
    for i, f in enumerate(board.findings):
        ang = 2 * math.pi * i / max(items, 1) + 0.35 * ring
        nodes.append({
            "id": nid("f", i), "kind": "finding", "label": f[:90],
            "x": 400 * math.cos(ang), "y": 400 * math.sin(ang), "r": 7,
            "detail": _src(f) or "findings.md",
        })
        edges.append({"a": "hub", "b": nid("f", i), "kind": "finding"})

    for j, q in enumerate(board.questions):
        ang = 2 * math.pi * (len(board.findings) + j) / max(items, 1) + 0.35 * ring
        qx, qy = 400 * math.cos(ang), 400 * math.sin(ang)
        asker_idx = board.agents.index(q.asker) if q.asker in board.agents else None
        nodes.append({
            "id": nid("q", j), "kind": "question",
            "label": f"{q.asker} asks: {q.text[:80]}",
            "x": qx, "y": qy, "r": 9 if q.answered else 11,
            "detail": f"questions.md:{q.line}" + (" — OPEN" if not q.answered else ""),
        })
        edges.append({
            "a": f"agent{asker_idx}" if asker_idx is not None else "hub",
            "b": nid("q", j), "kind": "asks",
        })
        for k, a in enumerate(q.answers):
            off = 2 * math.pi * k / max(len(q.answers), 1)
            nodes.append({
                "id": nid(f"a{j}_", k), "kind": "answer", "label": a[:80],
                "x": qx + 64 * math.cos(off), "y": qy + 64 * math.sin(off), "r": 5,
                "detail": _src(a) or "questions.md",
            })
            edges.append({"a": nid("q", j), "b": nid(f"a{j}_", k), "kind": "answer"})

    return {
        "title": f"{board.name} — {board.goal}",
        "stats": {
            "agents": len(board.agents), "findings": len(board.findings),
            "questions": len(board.questions), "open": len(board.open_questions),
            "converged": board.converged,
        },
        "nodes": nodes, "edges": edges,
    }


_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>
html,body{margin:0;height:100%;background:#05070f;overflow:hidden;font-family:ui-monospace,Menlo,Consolas,monospace}
canvas{display:block;cursor:grab}
canvas:active{cursor:grabbing}
#hud{position:fixed;top:16px;left:16px;color:#cdd6f4;font-size:13px;line-height:1.7;
  background:rgba(10,14,28,.72);border:1px solid #1e2748;border-radius:10px;padding:12px 16px;
  backdrop-filter:blur(6px);max-width:340px;pointer-events:none}
#hud b{color:#fff;font-size:14px}
.badge{display:inline-block;padding:1px 8px;border-radius:20px;font-size:11px;margin-left:6px}
.open{background:#33261a;color:#f5a623}.done{background:#14332a;color:#5be49b}
.legend{position:fixed;bottom:16px;left:16px;color:#8892b0;font-size:12px;line-height:1.9;
  background:rgba(10,14,28,.6);border:1px solid #1e2748;border-radius:10px;padding:10px 14px}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:8px}
#tip{position:fixed;pointer-events:none;color:#e6ebff;font-size:12px;line-height:1.6;
  background:rgba(13,18,36,.94);border:1px solid #2a3560;border-radius:8px;padding:10px 12px;
  max-width:380px;display:none;box-shadow:0 8px 30px rgba(0,0,0,.6)}
#tip .k{color:#8892b0;font-size:11px;text-transform:uppercase;letter-spacing:.08em}
</style></head><body>
<canvas id="c"></canvas>
<div id="hud"></div>
<div class="legend">
  <span class="dot" style="background:#fff"></span>goal&nbsp;&nbsp;
  <span class="dot" style="background:#b48cff"></span>agent&nbsp;&nbsp;
  <span class="dot" style="background:#4dd7ff"></span>finding<br>
  <span class="dot" style="background:#f5a623"></span>question&nbsp;&nbsp;
  <span class="dot" style="background:#5be49b"></span>answer<br>
  <span style="opacity:.7">drag to pan &middot; wheel to zoom &middot; hover a star</span>
</div>
<div id="tip"></div>
<script>
const G = __GRAPH__;
const cv = document.getElementById('c'), ctx = cv.getContext('2d');
const tip = document.getElementById('tip'), hud = document.getElementById('hud');
const KIND = {goal:'#ffffff',agent:'#b48cff',finding:'#4dd7ff',question:'#f5a623',answer:'#5be49b'};
const OPEN = '__OPEN__' === '1';
hud.innerHTML = '<b>' + G.title + '</b><span class="badge ' + (G.stats.converged?'done':'open') + '">'
  + (G.stats.converged ? 'converged' : G.stats.open + ' open') + '</span><br>'
  + G.stats.agents + ' agents &middot; ' + G.stats.findings + ' findings &middot; '
  + G.stats.questions + ' questions &middot; ' + G.nodes.length + ' stars';
const stars = Array.from({length:260},()=>({x:Math.random(),y:Math.random(),r:Math.random()*1.3+.3,p:Math.random()*6.28}));
let ox=0,oy=0,z=1,drag=null,hover=null,t=0;
const DPR = Math.min(devicePixelRatio||1,2);
function fit(){cv.width=innerWidth*DPR;cv.height=innerHeight*DPR;cv.style.width=innerWidth+'px';cv.style.height=innerHeight+'px'}
addEventListener('resize',fit);fit();
function map(n){const cx=cv.width/2/DPR,cy=cv.height/2/DPR;return[cx+(n.x+ox)*z,cy+(n.y+oy)*z]}
function pick(mx,my){let best=null,bd=1e9;for(const n of G.nodes){const[x,y]=map(n);const d=Math.hypot(mx-x,my-y);if(d<Math.max(n.r*z+6,10)&&d<bd){best=n;bd=d}}return best}
cv.addEventListener('pointerdown',e=>{drag={x:e.clientX,y:e.clientY,ox,oy};cv.setPointerCapture(e.pointerId)});
cv.addEventListener('pointermove',e=>{
  if(drag){ox=drag.ox+(e.clientX-drag.x)/z;oy=drag.oy+(e.clientY-drag.y)/z;return}
  const n=pick(e.clientX,e.clientY);hover=n;
  if(n){tip.style.display='block';tip.style.left=(e.clientX+14)+'px';tip.style.top=(e.clientY+14)+'px';
    tip.innerHTML='<div class="k">'+n.kind+'</div>'+esc(n.label)+(n.detail?'<br><span style="color:#8892b0">'+esc(n.detail)+'</span>':'')}
  else tip.style.display='none';
});
cv.addEventListener('pointerup',()=>drag=null);
cv.addEventListener('wheel',e=>{e.preventDefault();z*=e.deltaY<0?1.13:0.885;z=Math.min(4,Math.max(.25,z))},{passive:false});
function esc(s){return String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}
function draw(){
  t+=0.016;ctx.setTransform(DPR,0,0,DPR,0,0);
  ctx.fillStyle='#05070f';ctx.fillRect(0,0,innerWidth,innerHeight);
  for(const s of stars){ctx.globalAlpha=.25+.25*Math.sin(t+s.p);ctx.fillStyle='#8ea2d8';
    ctx.fillRect(s.x*innerWidth,s.y*innerHeight,s.r,s.r)}
  ctx.globalAlpha=1;
  for(const e of G.edges){const a=G.nodes.find(n=>n.id===e.a),b=G.nodes.find(n=>n.id===e.b);
    if(!a||!b)continue;const[x1,y1]=map(a),[x2,y2]=map(b);
    const glow=(Math.sin(t*2+x1*.01)+1)/2;
    ctx.strokeStyle=e.kind==='answer'?'rgba(91,228,155,.5)':e.kind==='asks'?'rgba(245,166,35,.45)':'rgba(120,140,220,.28)';
    ctx.lineWidth=e.kind==='member'?1.6:1;
    ctx.setLineDash(e.kind==='finding'?[2,6]:[]);ctx.lineDashOffset=-t*8;
    ctx.beginPath();ctx.moveTo(x1,y1);ctx.lineTo(x2,y2);ctx.stroke();ctx.setLineDash([])}
  for(const n of G.nodes){const[x,y]=map(n);const r=n.r*z;const col=KIND[n.kind];
    const pulse=n.kind==='question'&&!n.detail.includes('OPEN')?1:.12*Math.sin(t*3+n.x)+1;
    const g=ctx.createRadialGradient(x,y,0,x,y,r*3.4);
    g.addColorStop(0,col+'cc');g.addColorStop(.35,col+'33');g.addColorStop(1,col+'00');
    ctx.fillStyle=g;ctx.beginPath();ctx.arc(x,y,r*3.4*pulse,0,6.29);ctx.fill();
    ctx.fillStyle=col;ctx.beginPath();ctx.arc(x,y,r,0,6.29);ctx.fill();
    if(n.kind==='question'&&n.detail.includes('OPEN')){ctx.strokeStyle='#f5a623';ctx.lineWidth=1.5;
      ctx.beginPath();ctx.arc(x,y,r+4+2*Math.sin(t*3),0,6.29);ctx.stroke()}
    if(n===hover||n.kind==='agent'||n.kind==='goal'){ctx.fillStyle='#e6ebff';
      ctx.font=(n.kind==='goal'?'600 14px':'12px')+' ui-monospace,monospace';ctx.textAlign='center';
      const short=n.label.length>34?n.label.slice(0,34)+'…':n.label;
      ctx.fillText(short,x,y-r-8)}}
  requestAnimationFrame(draw)}
draw();
</script></body></html>
"""


def render_viz(board: Board) -> str:
    graph = build_graph(board)
    html = _HTML.replace("__GRAPH__", json.dumps(graph, ensure_ascii=False))
    html = html.replace("__TITLE__", f"mind-viz — {board.name}")
    html = html.replace("__OPEN__", "1" if board.open_questions else "0")
    return html


def render_repo_viz(repo_root: Path) -> str:
    """Placeholder for whole-repo viz (future: every swarm in one sky)."""
    raise NotImplementedError("point `swarm viz` at a swarms/<name> folder")
