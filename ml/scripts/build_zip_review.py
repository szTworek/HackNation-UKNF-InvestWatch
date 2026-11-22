"""Strona do ręcznej oceny czystych rekordów z zipa: ml/data/skill/zip_review.html (bez etykiet modelu).

  python ml/scripts/build_zip_review.py
Decyzje zapisują się w przeglądarce. „Eksportuj” pobiera zip_review_decisions.json – wrzuć go do ml/data/skill/.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "ml/data/skill"
sys.stdout.reconfigure(encoding="utf-8")

HTML = r"""<!doctype html><html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'">
<title>Ocena rekordów</title><style>
:root{--bg:#f6f7f9;--card:#fff;--tx:#1b1f24;--mut:#667;--line:#d9dde3;--acc:#1f5fbf;--ok:#1e7a3c}
@media(prefers-color-scheme:dark){:root{--bg:#14171b;--card:#1e2329;--tx:#e7e9ec;--mut:#9aa3ad;--line:#343b44;--acc:#7fb0ff;--ok:#5fd18a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);font:15px/1.55 system-ui,sans-serif}
header{position:sticky;top:0;z-index:1;background:var(--card);border-bottom:1px solid var(--line);padding:10px 16px;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
main{display:grid;grid-template-columns:minmax(0,1fr) 360px;gap:14px;padding:14px 16px;max-width:1400px;margin:auto}@media(max-width:900px){main{grid-template-columns:1fr}}
section{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px}
.sec{margin:0 0 12px}.sec b{display:block;font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--mut)}.sec p{margin:2px 0 0;white-space:pre-wrap;overflow-wrap:anywhere}
button,select,textarea{font:inherit;color:inherit;background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:6px 10px}button{cursor:pointer}
.v{display:block;width:100%;text-align:left;margin:4px 0}.v.on{background:var(--acc);color:#fff;border-color:var(--acc)}
.m{color:var(--mut);font-size:13px;overflow-wrap:anywhere}textarea{width:100%;min-height:60px}h3{font-size:14px;margin:14px 0 4px}label{display:block;margin:5px 0}
.v.ai{outline:2px dashed var(--acc);outline-offset:-2px}.ai-box{border-left:4px solid var(--acc);padding:8px 10px;margin:0 0 10px;background:var(--bg);border-radius:4px}.bar{flex:1;min-width:120px;height:6px;background:var(--line);border-radius:3px;overflow:hidden}.bar i{display:block;height:100%;background:var(--ok)}</style></head><body>
<header><button id="prev">←</button><button id="next">→</button><b id="pos"></b><div class="bar"><i id="prog"></i></div><span class="m" id="done"></span>
<select id="filter"><option value="all">Wszystkie</option><option value="todo">Nieocenione</option><option value="doneOnly">Ocenione</option></select>
<select id="src"><option value="">Każde źródło</option></select><button id="exp">Eksportuj decyzje</button></header>
<main><section><div class="m" id="meta"></div><h2 id="who" style="font-size:17px;margin:4px 0 10px"></h2><div id="body"></div></section>
<aside><section><div class="ai-box" id="ai"></div><b>Twój werdykt</b> <span class="m">(klawisze 1–__N__; Enter akceptuje propozycję, jeśli jest)</span><div id="verdicts"></div>
<h3>Dodatkowo</h3><div id="extra"></div><h3>Notatka</h3><textarea id="note" placeholder="np. dlaczego, co jest granicą"></textarea>
<p class="m">← → przełączają rekordy. Postęp zapisuje się w tej przeglądarce.</p></section></aside></main>
<script id="data" type="application/json">__DATA__</script><script>
const D=JSON.parse(document.getElementById('data').textContent),K='__KEY__';let S={};try{S=JSON.parse(localStorage.getItem(K)||'{}')}catch(e){}
const V=__VERDICTS__;
const X=[['no_risk','Zysk bez informacji o ryzyku'],['no_ad','Brak oznaczenia reklamy / współpracy'],['guarantee','Gwarancja zysku / brak ryzyka'],['knf','KNF / licencja jako argument bezpieczeństwa'],['pressure','Presja czasu / niska kwota startowa'],['contact','Kontakt poza platformą (WhatsApp, Telegram, telefon)'],['unsure','Nie jestem pewien']];
const NAMES={title:'Tytuł',post:'Post',ad_body:'Treść reklamy',description:'Opis',link_description:'Opis linku',cta:'Przycisk',transcript:'Transkrypcja',ocr:'Tekst z obrazu (OCR)',page:'Strona',risk_disclaimer:'Ostrzeżenie o ryzyku'};
const $=i=>document.getElementById(i);let list=D.map((_,i)=>i),p=0;
function save(){try{localStorage.setItem(K,JSON.stringify(S))}catch(e){}}function st(id){return S[id]||(S[id]={verdict:null,extra:[],note:''})}
function el(t,c,x){const e=document.createElement(t);if(c)e.className=c;if(x!=null)e.textContent=x;return e}
[...new Set(D.map(d=>d.folder))].forEach(f=>$('src').append(new Option(f,f)));
function applyFilter(){const f=$('filter').value,s=$('src').value;list=D.map((_,i)=>i).filter(i=>{const v=(S[D[i].id]||{}).verdict;return(!s||D[i].folder===s)&&(f==='all'||(f==='todo'&&!v)||(f==='doneOnly'&&v))});p=0;render()}
function render(){const n=Object.values(S).filter(x=>x.verdict).length;$('done').textContent='ocenione '+n+' z '+D.length;$('prog').style.width=(100*n/D.length)+'%';
if(!list.length){$('pos').textContent='Brak pozycji';$('body').replaceChildren();$('who').textContent='';$('meta').textContent='';return}
p=Math.max(0,Math.min(p,list.length-1));const d=D[list[p]],s=S[d.id]||{verdict:null,extra:[],note:''};
$('pos').textContent=(p+1)+' / '+list.length;$('meta').textContent=[d.id,d.folder,d.content_type,d.published_at&&d.published_at.slice(0,10),'zapytanie: '+(d.query||[]).join(', ')].filter(Boolean).join(' · ');
$('who').textContent=d.author||d.sponsor||'(autor nieznany)';const B=$('body');B.replaceChildren();
Object.entries(d.sections).forEach(([k,v])=>{const w=el('div','sec');w.append(el('b',null,NAMES[k]||k),el('p',null,v));B.append(w)});
const w=el('div','sec');w.append(el('b',null,'Linki'));const lk=(u,t)=>{const a=el('a',null,t||u);a.href=u;a.target='_blank';a.rel='noopener noreferrer nofollow';a.style.overflowWrap='anywhere';return a};
if(/^https:\/\//.test(d.url||'')){const r=el('p');r.append('Źródło: ',lk(d.url));w.append(r)}
d.links.filter(u=>/^https?:\/\//.test(u)).forEach(u=>{const r=el('p','m');r.append('Strona docelowa: ',lk(u),' · ',lk('https://web.archive.org/web/2026/'+u,'kopia w archiwum'));w.append(r)});
if(d.links.length)w.append(el('p','m','Strony docelowe mogą należeć do oszustów: nie podawaj tam danych, bezpieczniej otwierać kopię w archiwum.'));B.append(w);
const c=d.claude||{},AI=$('ai');AI.replaceChildren();AI.style.display=(c.verdict||d.hint)?'':'none';if(d.hint)AI.append(el('b',null,'Dlaczego wybrany (filtr regułowy, nie werdykt)'),el('div',null,d.hint));if(c.verdict){AI.append(el('b',null,'Propozycja Claude: '+((V.find(v=>v[0]===c.verdict)||[0,c.verdict])[1])),el('div',null,c.reason||''));if(['M1','M2_BAD','M2_OK'].includes(c.verdict))AI.append(el('div','m',(c.rules&&c.rules.length?'możliwe naruszenia reguł: '+c.rules.join(', '):'brak wykrytych naruszeń w tekście')+' · reguły 4–8 (czcionka, kontrast, ukrycie, 1 kliknięcie, responsywność) nie do sprawdzenia z tekstu'));if((c.extra||[]).length)AI.append(el('div','m','dodatkowo: '+c.extra.map(k=>(X.find(x=>x[0]===k)||[0,k])[1]).join(', ')))}
const vb=$('verdicts');vb.replaceChildren();V.forEach(([k,n],i)=>{const b=el('button','v'+(s.verdict===k?' on':'')+(c.verdict===k?' ai':''),(i+1)+'. '+n);b.onclick=()=>setV(k);vb.append(b)});
const xb=$('extra');xb.replaceChildren();X.forEach(([k,n])=>{const l=el('label'),c=el('input');c.type='checkbox';c.checked=(s.extra||[]).includes(k);c.onchange=()=>{const a=st(d.id);a.extra=c.checked?[...a.extra,k]:a.extra.filter(v=>v!==k);save()};l.append(c,document.createTextNode(' '+n));xb.append(l)});
$('note').value=s.note||'';window.scrollTo(0,0)}
function setV(k){const d=D[list[p]],a=st(d.id),was=a.verdict;a.verdict=was===k?null:k;save();if(!was&&a.verdict&&p<list.length-1){setTimeout(()=>{p++;render()},150)}render()}
$('prev').onclick=()=>{p--;render()};$('next').onclick=()=>{p++;render()};$('note').oninput=e=>{st(D[list[p]].id).note=e.target.value;save()};
$('filter').onchange=applyFilter;$('src').onchange=applyFilter;
document.addEventListener('keydown',e=>{if(/TEXTAREA|SELECT|INPUT/.test(e.target.tagName))return;if(e.key>='1'&&e.key<=String(V.length))setV(V[+e.key-1][0]);if(e.key==='Enter'){const d=D[list[p]];if(d.claude&&d.claude.verdict){const a=st(d.id);if(!a.verdict&&!a.extra.length)a.extra=[...(d.claude.extra||[])];if(a.verdict!==d.claude.verdict)setV(d.claude.verdict);else{p++;render()}}}if(e.key==='ArrowRight'){p++;render()}if(e.key==='ArrowLeft'){p--;render()}});
$('exp').onclick=()=>{const o=D.filter(d=>S[d.id]&&(S[d.id].verdict||S[d.id].note||(S[d.id].extra||[]).length)).map(d=>({id:d.id,url:d.url,folder:d.folder,claude:d.claude||null,agree:!!(d.claude&&S[d.id].verdict===d.claude.verdict),...S[d.id]}));
const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(o,null,1)],{type:'application/json'}));a.download='__EXPORT__';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)};render();
</script></body></html>"""


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=None)
    ap.add_argument("--out", default="zip_review.html")
    ap.add_argument("--key", default="investwatch_zip_review_v1")
    ap.add_argument("--modules", action="store_true", help="tylko M1/M2/M3/poza modułami")
    ap.add_argument("--export", default="zip_review_decisions.json")
    args = ap.parse_args()
    src = Path(args.input) if args.input else SKILL / ("zip_review_set.jsonl" if (SKILL / "zip_review_set.jsonl").exists() else "zip_clean.jsonl")
    rows = [json.loads(l) for l in src.read_text(encoding="utf-8").splitlines() if l.strip()]
    data = json.dumps(rows, ensure_ascii=True).replace("<", "\\u003c")
    out = SKILL / args.out
    full = [["M1", "M1: firma inwestycyjna reklamowana przez osobę trzecią / finfluencera"],
            ["M2_BAD", "M2: materiał firmy z brakami (ryzyko, oznaczenie, porównania)"],
            ["M2_OK", "M2: materiał firmy, wygląda poprawnie"],
            ["M3", "M3: doradztwo / zarządzanie / sygnały / płatna grupa"], ["SCAM", "Oszustwo inwestycyjne"],
            ["PUSH", "Namawianie / rekomendacja „kup X” (poza M1–M3)"], ["OK", "Neutralne: edukacja, news, opinia, ostrzeżenie"],
            ["NF", "Niefinansowe / nie o inwestycjach / nieczytelne"]]
    mods = [["M1", "M1: osoba trzecia reklamuje firmę inwestycyjną (współpraca, link/kod polecający, ranking)"],
            ["M2", "M2: materiał marketingowy samej firmy inwestycyjnej"],
            ["M3", "M3: usługi doradztwa / zarządzania / sygnałów / grup przez podmiot bez zezwolenia"],
            ["NONE", "Poza modułami: nie-inwestycje, edukacja, news, opinia, ostrzeżenie, inne"]]
    verdicts = mods if args.modules else full
    html = (HTML.replace("__DATA__", data).replace("__KEY__", args.key).replace("__EXPORT__", args.export)
            .replace("__VERDICTS__", json.dumps(verdicts, ensure_ascii=False)).replace("__N__", str(len(verdicts))))
    out.write_text(html, encoding="utf-8")
    print(len(rows), "->", out)


if __name__ == "__main__":
    main()
