"""Buduje lokalną stronę do ręcznego przeglądu danych: ml/data/review/review.html.

Tylko realne dane (bez syntetyków), sporne przypadki na górze. Decyzje zapisują się w przeglądarce (localStorage),
przycisk „Eksportuj” pobiera review_decisions.json – wrzuć go do ml/data/review/.

  uv run python scripts/build_review.py --limit 250
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from investwatch_ml.labels import FLAGS_BY_KEY
from investwatch_ml.schema import read_jsonl

ML_DIR = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8")
TEACHERS = {"Bielik": "teacher", "Gemini": "teacher_gemini", "Groq": "teacher_groq"}
SOURCES = {"youtube": "youtube.jsonl", "cert_wayback": "cert_wayback.jsonl", "reddit": "reddit.jsonl", "scraper": "scraper.jsonl"}

HTML = r"""<!doctype html><html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'">
<title>Przegląd danych</title><style>
:root{--bg:#f6f7f9;--card:#fff;--tx:#1b1f24;--mut:#667;--line:#d9dde3;--acc:#1f5fbf;--warn:#a33}
@media(prefers-color-scheme:dark){:root{--bg:#14171b;--card:#1e2329;--tx:#e7e9ec;--mut:#9aa3ad;--line:#343b44;--acc:#7fb0ff;--warn:#ff9a8f}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);font:15px/1.5 system-ui,sans-serif}
header{position:sticky;top:0;background:var(--card);border-bottom:1px solid var(--line);padding:10px 16px;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
main{display:grid;grid-template-columns:minmax(0,1fr) 380px;gap:14px;padding:14px 16px;max-width:1400px;margin:auto}@media(max-width:900px){main{grid-template-columns:1fr}}
section{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:15px/1.6 system-ui,sans-serif;margin:0;max-height:68vh;overflow:auto}
button,select,textarea{font:inherit;color:inherit;background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:6px 10px}button{cursor:pointer}
.v{display:block;width:100%;text-align:left;margin:4px 0}.v.on{background:var(--acc);color:#fff;border-color:var(--acc)}.m{color:var(--mut);font-size:13px;overflow-wrap:anywhere}.w{color:var(--warn)}
textarea{width:100%;min-height:54px}h3{font-size:14px;margin:12px 0 4px}ul{margin:4px 0;padding-left:18px}label{display:block;margin:5px 0}</style></head><body>
<header><button id="prev">← Poprzedni</button><button id="next">Następny →</button><b id="pos"></b><span class="m" id="done"></span>
<select id="filter"><option value="all">Wszystkie</option><option value="todo">Nieocenione</option><option value="spor">Sporne</option></select><button id="exp">Eksportuj decyzje</button></header>
<main><section><h2 id="title" style="font-size:17px;margin:0 0 4px"></h2><div class="m" id="meta"></div><div class="m" id="link" style="margin:6px 0 10px"></div><pre id="text"></pre></section>
<aside><section><b>Twój werdykt</b> <span class="m">(klawisze 1–8)</span><div id="verdicts"></div>
<h3>Dodatkowo</h3><div id="extra"></div><h3>Notatka</h3><textarea id="note"></textarea></section>
<section style="margin-top:14px"><b>Co powiedziały modele</b><div id="teachers"></div></section></aside></main>
<script id="data" type="application/json">__DATA__</script><script>
const D=JSON.parse(document.getElementById('data').textContent),K='investwatch_review_v1';let S={};try{S=JSON.parse(localStorage.getItem(K)||'{}')}catch(e){}
const V=[['M1','M1: reklama firmy inwestycyjnej przez osobę trzecią / finfluencera'],['M2_BAD','M2: materiał firmy z brakami (ryzyko, oznaczenie)'],['M2_OK','M2: materiał firmy, wygląda poprawnie'],['M3','M3: faktyczne doradztwo / zarządzanie, możliwe bez zezwolenia'],['SCAM','Oszustwo inwestycyjne'],['PUSH','Nieuprawnione namawianie / rekomendacja kup-sprzedaj (poza M1–M3)'],['OK','Neutralne: edukacja, news, opinia, ostrzeżenie'],['NF','Niefinansowe / śmieci / strona nieczytelna']];
const X=[['no_risk','Zysk bez informacji o ryzyku'],['no_ad','Brak oznaczenia reklamy / współpracy'],['guarantee','Gwarancja zysku lub brak ryzyka'],['knf','Nadzór KNF jako argument bezpieczeństwa'],['unsure','Nie jestem pewien']];
const $=i=>document.getElementById(i);let list=D.map((_,i)=>i),p=0;function save(){try{localStorage.setItem(K,JSON.stringify(S))}catch(e){}}
function st(id){return S[id]||(S[id]={verdict:null,extra:[],note:''})}function el(t,c,x){const e=document.createElement(t);if(c)e.className=c;if(x!=null)e.textContent=x;return e}
function render(){if(!list.length){$('pos').textContent='Brak pozycji';return}p=Math.max(0,Math.min(p,list.length-1));const d=D[list[p]],s=S[d.id]||{verdict:null,extra:[],note:''};
$('pos').textContent=(p+1)+' / '+list.length;$('done').textContent='ocenione: '+Object.values(S).filter(x=>x.verdict).length+' z '+D.length;$('title').textContent=d.title||'(bez tytułu)';
$('meta').textContent=[d.source,d.kind,d.author,d.date,d.disputed?'SPORNE':''].filter(Boolean).join(' · ');const L=$('link');L.replaceChildren();
if(d.safe_url){const a=el('a',null,d.link_label);a.href=d.safe_url;a.target='_blank';a.rel='noopener noreferrer';L.append(a)}if(d.raw_url&&d.raw_url!==d.safe_url){L.append(el('div','w','Oryginalny adres (nie otwieraj): '+d.raw_url))}$('text').textContent=d.text;$('text').scrollTop=0;
const vb=$('verdicts');vb.replaceChildren();V.forEach(([k,n],i)=>{const b=el('button','v'+(s.verdict===k?' on':''),(i+1)+'. '+n);b.onclick=()=>setV(k);vb.append(b)});
const xb=$('extra');xb.replaceChildren();X.forEach(([k,n])=>{const l=el('label'),c=el('input');c.type='checkbox';c.checked=(s.extra||[]).includes(k);c.onchange=()=>{const a=st(d.id);a.extra=c.checked?[...a.extra,k]:a.extra.filter(v=>v!==k);save()};l.append(c,document.createTextNode(' '+n));xb.append(l)});
$('note').value=s.note||'';const T=$('teachers');T.replaceChildren();d.teachers.forEach(t=>{T.append(el('h3',null,t.name+': '+t.summary));if(t.rationale)T.append(el('div','m',t.rationale));const u=el('ul');t.flags.forEach(f=>u.append(el('li',null,f)));T.append(u)})}
function setV(k){const d=D[list[p]],a=st(d.id);a.verdict=a.verdict===k?null:k;save();render()}$('prev').onclick=()=>{p--;render()};$('next').onclick=()=>{p++;render()};$('note').oninput=e=>{st(D[list[p]].id).note=e.target.value;save()};
$('filter').onchange=e=>{const f=e.target.value;list=D.map((_,i)=>i).filter(i=>f==='all'||(f==='todo'&&!(S[D[i].id]||{}).verdict)||(f==='spor'&&D[i].disputed));p=0;render()};
document.addEventListener('keydown',e=>{if(/TEXTAREA|SELECT/.test(e.target.tagName))return;if(e.key>='1'&&e.key<='8')setV(V[+e.key-1][0]);if(e.key==='ArrowRight'){p++;render()}if(e.key==='ArrowLeft'){p--;render()}});
$('exp').onclick=()=>{const o=Object.entries(S).filter(([,v])=>v.verdict||v.note||(v.extra||[]).length).map(([id,v])=>({id,...v}));const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(o,null,1)],{type:'application/json'}));a.download='review_decisions.json';a.click();URL.revokeObjectURL(a.href)};render();
</script></body></html>"""


def summary(lb: dict) -> str:
    return f"{lb['topic']} / {lb['content_type']} / scam: {'TAK' if lb['is_scam'] else 'nie'} ({lb['scam_confidence']})"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=250)
    ap.add_argument("--max-chars", type=int, default=7000)
    args = ap.parse_args()
    labels: dict[str, dict[str, dict]] = defaultdict(dict)
    for name, f in TEACHERS.items():
        for r in read_jsonl(ML_DIR / f"data/silver/{f}.jsonl"):
            if r.get("label"):
                labels[str(r["id"])][name] = r["label"]
    rows = []
    for src, f in SOURCES.items():
        for r in read_jsonl(ML_DIR / "data/pool" / f):
            ls = labels.get(str(r["id"]))
            if not ls or (r.get("meta") or {}).get("synthetic"):
                continue
            vals = list(ls.values())
            disputed = len(vals) > 1 and len({(v["topic"], v["content_type"], v["is_scam"]) for v in vals}) > 1
            relevant = any(v["topic"] == "INVESTMENT" and v["content_type"] not in ("NEWS_EDU", "OPINION_DISCUSSION", "NONE")
                           or v["is_scam"] for v in vals)
            prio = (0 if disputed and relevant else 1 if src in ("cert_wayback", "scraper") else 2 if src == "youtube" else
                    3 if relevant else 4 if disputed else 5)
            rows.append((prio, r, ls, disputed))
    rows.sort(key=lambda x: (x[0], x[1]["id"]))
    out = []
    for _, r, ls, disputed in rows[: args.limit]:
        meta, raw = r.get("meta") or {}, r.get("url") or ""
        safe, label = (raw, "Otwórz źródło") if r["source"] != "cert_wayback" else (
            f"https://web.archive.org/web/{meta.get('wayback_ts')}/{raw}", "Otwórz kopię w archiwum (bezpieczniej)")
        if not safe.startswith("https://"):
            safe, label = "", ""
        out.append({
            "id": r["id"], "source": r["source"], "kind": r["kind"], "author": r.get("author"), "date": r.get("published_at"),
            "title": r.get("title"), "text": (r.get("text") or "")[: args.max_chars], "safe_url": safe, "link_label": label,
            "raw_url": raw if r["source"] == "cert_wayback" else "", "disputed": disputed,
            "teachers": [{"name": n, "summary": summary(v), "rationale": (v.get("rationale") or "")[:350],
                          "flags": [f"{FLAGS_BY_KEY[h['flag']].name_pl}: „{(h.get('quote') or '')[:130]}”" for h in v["flags"][:10]]}
                         for n, v in ls.items()],
        })
    data = json.dumps(out, ensure_ascii=True).replace("<", "\\u003c")
    path = ML_DIR / "data/review/review.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(HTML.replace("__DATA__", data), encoding="utf-8")
    print(f"{len(out)} pozycji z {len(rows)} oznaczonych realnych; sporne: {sum(x['disputed'] for x in out)}")
    print({s: sum(x["source"] == s for x in out) for s in SOURCES})
    print(path)


if __name__ == "__main__":
    main()
