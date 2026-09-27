from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stock_model.human_need_network import build_snapshot, graph_records, load_network

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "human_need_network"
OUTPUT = ROOT / "reports" / "human_need_resource_network.html"


def build_html(nodes: list[dict[str, str]], edges: list[dict[str, str]], as_of: str, carrier_count: int) -> str:
    data = json.dumps({"nodes": nodes, "edges": edges}, ensure_ascii=False)
    title = html.escape("人的生物需求—资源—生产网络")
    template = '''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>
:root{color-scheme:light dark;--bg:#f7f4ec;--fg:#22251f;--muted:#687066;--line:#b7beb3;--surface:#fffdf7;--material:#597a9c;--repro:#a26739;--neural:#477f73;--social:#7d5b91;--spiritual:#9a6b30;--candidate:#a87c2a} @media(prefers-color-scheme:dark){:root{--bg:#151915;--fg:#ece9df;--muted:#b7beb1;--line:#4a554b;--surface:#20251f;--material:#9dbfe1;--repro:#e0a36d;--neural:#86d0c3;--social:#c7a9d5;--spiritual:#dfba68;--candidate:#dfba68}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font-family:"Microsoft YaHei","Segoe UI",system-ui,sans-serif}main{max-width:1220px;margin:auto;padding:22px 18px 38px}h1{font-size:25px;font-weight:500;margin:0}h2{font-size:18px;font-weight:500;margin:24px 0 10px}h3{font-size:16px;font-weight:500;margin:0 0 8px}p{color:var(--muted);line-height:1.55;margin:7px 0 12px}.meta{font-size:13px}.stats{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0}.stat{border:1px solid var(--line);border-radius:6px;padding:7px 10px;color:var(--muted);font-size:13px}.stat strong{color:var(--fg);font-weight:500}.root{border:2px solid var(--social);border-radius:9px;background:var(--surface);padding:13px 16px;text-align:center;margin:18px auto;max-width:480px}.systems{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;align-items:start}.system{background:var(--surface);border:1px solid var(--line);border-top:4px solid var(--system-color);border-radius:8px;padding:12px 10px}.system h3{color:var(--system-color)}.branch{margin:8px 0 0;padding-left:8px;border-left:1px solid var(--line)}.branch-title{color:var(--muted);font-size:12px;margin:6px 0 4px}.need{display:block;width:100%;text-align:left;border:0;border-bottom:1px solid color-mix(in srgb,var(--line) 65%,transparent);background:transparent;color:var(--fg);padding:6px 3px;font:inherit;font-size:13px;cursor:pointer}.need:hover,.need:focus{color:var(--system-color);outline:2px solid color-mix(in srgb,var(--system-color) 40%,transparent)}.need.subsystem{font-weight:500}.detail,.pilot{background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:12px 14px;color:var(--muted);font-size:13px;line-height:1.55;margin-top:14px}.detail strong{color:var(--fg);font-weight:500}.flow{display:flex;flex-wrap:wrap;align-items:center;gap:7px}.chip{border:1px solid var(--line);border-radius:999px;padding:5px 9px;font-size:13px}.arrow{color:var(--muted)}.candidate-list{margin:12px 0 0;padding:0;list-style:none;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px}.candidate-list li{border-left:3px dashed var(--candidate);padding:6px 8px;color:var(--muted);font-size:13px}.note{color:var(--candidate);font-size:13px}@media(max-width:980px){.systems{grid-template-columns:repeat(3,minmax(0,1fr))}}@media(max-width:650px){main{padding:16px 11px 28px}.systems{grid-template-columns:1fr}.candidate-list{grid-template-columns:1fr}h1{font-size:22px}}
</style></head><body><main>
<h1>__TITLE__</h1><p>从物种/群体的生物连续性出发，先看需求树，再看目前已经落地的生产—资源试点。个人、企业和股票都不是需求根节点。</p>
<p class="meta">知识时点：__ASOF__　|　过程承载者映射：__CARRIER__ 条　|　精神需求按生物—认知—社会涌现建模，不预设超自然事实</p>
<div id="stats" class="stats"></div><section><h2>需求全景</h2><div class="root"><strong>人类生物种群持续存在与发展</strong><br><span class="meta">唯一根节点：代谢、繁衍、神经、社会、符号五个系统共同作用</span></div><div id="systems" class="systems"></div></section>
<div id="detail" class="detail">点击需求节点，查看其生物基础、可能的剥夺反应和文化可变性。</div>
<section><h2>当前生产—资源试点</h2><div class="pilot"><div id="flow" class="flow"></div><ul id="candidates" class="candidate-list"></ul><p class="note">虚线候选关系只表示“需要证据”，不表示已测得数量、成本或价格影响。</p></div></section>
<script>
const payload=__DATA__;const needs=payload.nodes.filter(n=>n.type==='need');const byId=Object.fromEntries(needs.map(n=>[n.id,n]));const edges=payload.edges;const detail=document.getElementById('detail');
const colors={material_homeostasis:'var(--material)',reproduction_care:'var(--repro)',neural_regulation:'var(--neural)',social_coordination:'var(--social)',symbolic_spiritual:'var(--spiritual)'};
const names={material_homeostasis:'物质代谢与身体稳态',reproduction_care:'繁衍与代际照护',neural_regulation:'神经与心理调节',social_coordination:'依恋与群体协作',symbolic_spiritual:'符号与精神调节'};
function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}function children(id){return needs.filter(n=>n.parent_id===id)}
function renderNeed(n){const kids=children(n.id);let out='<button type="button" class="need '+(n.level==='subsystem'?'subsystem':'')+'" data-id="'+esc(n.id)+'">'+esc(n.label)+'</button>';if(kids.length){out+='<div class="branch">';kids.forEach(k=>out+=renderNeed(k));out+='</div>'}return out}
function drawTaxonomy(){const systems=children('NEED_HUMAN_BIOLOGICAL_CONTINUITY');document.getElementById('systems').innerHTML=systems.map(s=>'<article class="system" style="--system-color:'+colors[s.domain]+'"><h3>'+esc(names[s.domain]||s.label)+'</h3>'+children(s.id).map(renderNeed).join('')+'</article>').join('');document.querySelectorAll('.need').forEach(b=>b.addEventListener('click',()=>{const n=byId[b.dataset.id];detail.innerHTML='<strong>'+esc(n.label)+'</strong>　层级：'+esc(n.level)+'　尺度：'+esc(n.population_scope)+'<br>生物基础（待逐项核验）：'+esc(n.biological_basis)+'<br>可能的剥夺反应（模型假设）：'+esc(n.deprivation_response)+'<br>文化可变性：'+esc(n.cultural_variability)+'<br>'+esc(n.description)}))}
function drawStats(){const leaves=needs.filter(n=>n.level==='leaf').length;const domains=new Set(needs.map(n=>n.domain));document.getElementById('stats').innerHTML='<span class="stat"><strong>'+needs.length+'</strong> 个需求节点</span><span class="stat"><strong>'+domains.size+'</strong> 个需求系统</span><span class="stat"><strong>'+leaves+'</strong> 个末端需求</span><span class="stat"><strong>'+edges.filter(e=>e.status==='candidate_needs_evidence').length+'</strong> 条资源候选</span>'}
function label(id){return byId[id]?.label||payload.nodes.find(n=>n.id===id)?.label||id}function drawPilot(){const chosen=['NEED_BASIC_NUTRITION','FUNC_NUTRIENT_SUPPLY','FUNC_PROTEIN_SUPPLY','FUNC_ANIMAL_PROTEIN','PROCESS_PIG_PRODUCTION'];document.getElementById('flow').innerHTML=chosen.map((id,i)=>(i?'<span class="arrow">→</span>':'')+'<span class="chip">'+esc(label(id))+'</span>').join('');document.getElementById('candidates').innerHTML=edges.filter(e=>e.status==='candidate_needs_evidence').map(e=>'<li>'+esc(label(e.target))+'：'+esc(e.label)+'</li>').join('')}
drawStats();drawTaxonomy();drawPilot();
</script></main></body></html>'''
    return template.replace("__TITLE__", title).replace("__ASOF__", html.escape(as_of)).replace("__CARRIER__", str(carrier_count)).replace("__DATA__", data)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default=str(DATA_DIR))
    parser.add_argument("--as-of", default="2026-08-18T12:00:00+08:00")
    parser.add_argument("--output", default=str(OUTPUT))
    args = parser.parse_args()
    tables = load_network(args.data_dir)
    snapshot = build_snapshot(tables, as_of=args.as_of, include_candidates=True)
    nodes, edges = graph_records(snapshot)
    for _, row in snapshot.satisfaction_functions.iterrows():
        parent = str(row.get("parent_function_id", ""))
        if parent:
            edges.append({"source": parent, "target": str(row["function_id"]), "label": "subfunction", "status": "accepted_model_structure"})
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_html(nodes, edges, args.as_of, len(snapshot.process_carrier_mappings)), encoding="utf-8")
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
