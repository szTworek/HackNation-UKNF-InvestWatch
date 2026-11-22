"""Dokleja do findings.real.json fikcyjne rekordy demo (id `demo-*`, kampania `C-demo-*`).

Scenariusze pokazują to, czego w prawdziwym zbiorze jeszcze nie ma:
  * kampanię oszustwa z grafem powiązań (wspólny Telegram, telefon, domena, przekierowania),
  * post finfluencera, który po tygodniu zmieniono tak, że zaczął naruszać przepisy (pole `revisions`),
  * strony docelowe z podejrzanym łańcuchem przekierowań i zrzutami ekranu,
  * historię decyzji analityków.

Treść każdego rekordu przechodzi przez prawdziwe /ingest ai-service, więc flagi, reguły i ryzyko liczy model.
Marki, osoby i numery są wymyślone, a domeny leżą w zarezerwowanej strefie `.example` (RFC 2606).
Skrypt jest idempotentny: usuwa poprzednie rekordy demo i dopisuje je od nowa.

  python ml/scripts/add_demo_findings.py [--ai-url http://localhost:8000]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_findings import OUT, request, to_finding, write_atomic  # noqa: E402

DEMO_PREFIX = "demo-"
CAMPAIGN_ID = "C-demo-novaquant"
CAMPAIGN_NAME = "Fałszywa platforma AI „NovaQuant” (Telegram @novaquant_vip_pl, tel. +48 999 000 111)"

SCAM_HOST = "novaquant-pl.example"
SCAM_FORM = f"https://{SCAM_HOST}/rejestracja"
SCAM_LANDING_TEXT = (
    "Średni zysk naszych klientów: 1 840 zł dziennie.\n"
    "Algorytm AI handluje za Ciebie 24/7, nie musisz znać się na giełdzie.\n"
    "Platforma nadzorowana przez KNF, Twoje środki są w pełni bezpieczne.\n"
    "Wpłata startowa tylko 250 USD. Liczba miejsc ograniczona.\n"
    "Zostaw numer, konsultant oddzwoni w ciągu 15 minut."
)


def scam_landing(requested: str, hops: list[str]) -> dict[str, Any]:
    return {
        "requestedUrl": requested,
        "finalUrl": SCAM_FORM + "?utm_source=fb&aff=7731",
        "redirectChain": [requested, *hops, SCAM_FORM + "?utm_source=fb&aff=7731"],
        "title": "NovaQuant AI – zarabiaj z algorytmem nowej generacji",
        "text": SCAM_LANDING_TEXT,
        "hasContactForm": True,
        "domainFlags": ["NEW_DOMAIN", "IMPERSONATION"],
    }


KASIA_V1 = (
    "Mój portfel na listopad: 70% globalne ETF-y, 20% obligacje skarbowe, 10% gotówka. "
    "Nie ma tu żadnej magii, tylko regularne wpłaty i cierpliwość.\n"
    "Pamiętajcie: inwestowanie wiąże się z ryzykiem utraty części lub całości kapitału, "
    "a wyniki historyczne nie gwarantują przyszłych zysków.\n"
    "To nie jest rekomendacja, każdy musi ocenić swoją sytuację sam. #edukacja"
)
KASIA_V2 = (
    "Mój portfel na listopad: 70% globalne ETF-y, 20% obligacje skarbowe, 10% gotówka. "
    "Nie ma tu żadnej magii, tylko regularne wpłaty i cierpliwość.\n"
    "Od tygodnia część środków trzymam w NovaQuant AI: algorytm sam handluje i daje gwarantowany zysk 12% miesięcznie, bez ryzyka.\n"
    "Z moim kodem polecającym KASIA250 wystarczy 250 USD na start, link w bio, oferta wygasa w niedzielę! "
    "Pytania piszcie na Telegram @novaquant_vip_pl"
)

SCENARIOS: list[dict[str, Any]] = [
    {
        "id": "demo-fb-novaquant-1",
        "record": {
            "source": "meta_ad_library", "source_url": "https://www.facebook.com/ads/library/?id=demo-880011",
            "author": "Finanse Bez Tajemnic", "sponsor": "Finanse Bez Tajemnic", "content_type": "ad",
            "published_at": "2026-11-11T18:20:00+00:00", "fetched_at": "2026-11-12T07:05:00+00:00",
            "text": {"title": "Znany prezenter zdradził, jak zarabia na sztucznej inteligencji",
                     "ad_body": "Sztuczna inteligencja handluje za ciebie i zarabia nawet 30% miesięcznie. "
                                "Wystarczy wpłata 250 USD. Liczba miejsc ograniczona, nie czekaj! "
                                "Zostaw swój numer, konsultant oddzwoni. Kontakt: Telegram @novaquant_vip_pl"},
            "links": ["https://krotko.example/nq7"],
        },
        "landing": scam_landing("https://krotko.example/nq7", ["https://trk.adsredirect.example/c?id=19a7", f"https://{SCAM_HOST}/start"]),
        "indicators": [("brand", "NovaQuant"), ("person", "znany prezenter (wizerunek bez zgody)"), ("phone", "+48 999 000 111")],
        "history": [
            ("2026-11-13T08:41:00Z", "IN_REVIEW", "a.kowalska", "sprawdzam stronę docelową i łańcuch przekierowań"),
            ("2026-11-13T09:12:00Z", "CONFIRMED", "a.kowalska", "skrócony link prowadzi przez tracker do formularza zbierania numerów na novaquant-pl.example"),
            ("2026-11-14T11:30:00Z", "ESCALATED", "m.nowak", "zgłoszone do CERT Polska (domena) i do Meta (reklama)"),
        ],
        "blocked": True,
    },
    {
        "id": "demo-fb-novaquant-2",
        "record": {
            "source": "meta_ad_library", "source_url": "https://www.facebook.com/ads/library/?id=demo-880042",
            "author": "Codzienne Wiadomości 24", "sponsor": "Codzienne Wiadomości 24", "content_type": "ad",
            "published_at": "2026-11-15T06:00:00+00:00", "fetched_at": "2026-11-15T09:40:00+00:00",
            "text": {"title": "Skandal na wizji: wywiad, który usunięto po 2 godzinach",
                     "ad_body": "Banki nie chcą, żebyś to wiedział. Sztuczna inteligencja inwestuje na giełdzie za Polaków i zarabia nawet 1 840 zł dziennie na akcjach i kryptowalutach. "
                                "Zacznij od 250 USD, tylko dziś darmowa konfiguracja konta. Konsultant oddzwoni w 15 minut."},
            "links": ["https://krotko.example/nq9"],
        },
        "landing": scam_landing("https://krotko.example/nq9", ["https://news-pl24.example/artykul/ai-milioner", f"https://{SCAM_HOST}/start"]),
        "indicators": [("brand", "NovaQuant"), ("phone", "+48 999 000 111")],
        "history": [("2026-11-15T10:05:00Z", "IN_REVIEW", "m.nowak", "ten sam formularz co w demo-fb-novaquant-1, inny nadawca reklamy")],
        "blocked": True,
    },
    {
        "id": "demo-tt-novaquant",
        "record": {
            "source": "tiktok", "source_url": "https://www.tiktok.com/@zarabiaj.z.ai.pl/video/demo-7311",
            "author": "zarabiaj.z.ai.pl", "content_type": "video",
            "published_at": "2026-11-16T19:00:00+00:00", "fetched_at": "2026-11-17T06:30:00+00:00",
            "text": {"description": "Jak bot AI zarobił mi na wakacje #pasywnydochod #ai",
                     "transcript": "[TRANSKRYPCJA] Słuchajcie, od miesiąca nie dotykam wykresów. Bot AI handluje za mnie, "
                                   "zarabia jakieś 30% miesięcznie i nie da się stracić, bo algorytm zamyka straty. "
                                   "Link w bio, a jak macie pytania, piszcie na Telegram @novaquant_vip_pl."},
            "links": [f"https://{SCAM_HOST}/start"],
        },
        "landing": scam_landing(f"https://{SCAM_HOST}/start", []),
        "indicators": [("brand", "NovaQuant")],
        "history": [
            ("2026-11-17T08:00:00Z", "IN_REVIEW", "a.kowalska", "ten sam kanał Telegram co w reklamach NovaQuant"),
            ("2026-11-17T08:25:00Z", "CONFIRMED", "a.kowalska", "dołączone do kampanii NovaQuant"),
        ],
        "blocked": True,
    },
    {
        "id": "demo-yt-comment-novaquant",
        "record": {
            "source": "youtube", "source_url": "https://www.youtube.com/watch?v=demo-q9X&lc=demo-c1",
            "author": "Piotr W.", "content_type": "comment",
            "published_at": "2026-11-18T21:14:00+00:00", "fetched_at": "2026-11-19T06:00:00+00:00",
            "text": {"post": "Polecam NovaQuant, wypłaciłem już 12 000 zł w dwa tygodnie, zero ryzyka. "
                             "Opiekun konta pomoże ze wszystkim, WhatsApp +48 999 000 111"},
            "links": [],
        },
        "indicators": [("brand", "NovaQuant"), ("phone", "+48 999 000 111"), ("whatsapp", "+48 999 000 111")],
        "history": [],
    },
    {
        "id": "demo-web-novaquant",
        "kind": "page",
        "record": {
            "source": "web", "source_url": SCAM_FORM, "author": SCAM_HOST, "content_type": "page",
            "fetched_at": "2026-11-13T09:00:00+00:00",
            "text": {"title": "NovaQuant AI – zarabiaj z algorytmem nowej generacji", "post": SCAM_LANDING_TEXT},
            "links": [],
        },
        "landing": scam_landing(SCAM_FORM, []),
        "indicators": [("brand", "NovaQuant"), ("domain", SCAM_HOST)],
        "history": [("2026-11-14T11:31:00Z", "ESCALATED", "m.nowak", "domena zgłoszona do CERT Polska")],
        "blocked": True,
    },
    {
        "id": "demo-ig-kasia-v1",
        "record": {
            "source": "instagram", "source_url": "https://www.instagram.com/p/demo-Kx81/",
            "author": "inwestuj.z.kasia", "content_type": "post",
            "published_at": "2026-11-14T17:00:00+00:00", "fetched_at": "2026-11-14T20:00:00+00:00",
            "text": {"post": KASIA_V1}, "links": [],
        },
        "indicators": [],
        "history": [("2026-11-15T09:20:00Z", "DISMISSED", "a.kowalska", "edukacja z ostrzeżeniem o ryzyku, bez promocji konkretnej firmy")],
        "superseded_by": "demo-ig-kasia-v2",
    },
    {
        "id": "demo-ig-kasia-v2",
        "record": {
            "source": "instagram", "source_url": "https://www.instagram.com/p/demo-Kx81/",
            "author": "inwestuj.z.kasia", "content_type": "post",
            "published_at": "2026-11-14T17:00:00+00:00", "fetched_at": "2026-11-21T20:00:00+00:00",
            "text": {"post": KASIA_V2}, "links": ["https://krotko.example/nq-kasia"],
        },
        "landing": scam_landing("https://krotko.example/nq-kasia", [f"https://{SCAM_HOST}/start?ref=KASIA250"]),
        "indicators": [("brand", "NovaQuant")],
        "history": [
            ("2026-11-21T20:00:00Z", "NEW", "system",
             "ponowny skan: post edytowany po publikacji. Usunięto ostrzeżenie o ryzyku, dodano „gwarantowany zysk”, kod polecający i link do NovaQuant"),
            ("2026-11-22T08:10:00Z", "IN_REVIEW", "m.nowak", "wcześniejsza wersja była odrzucona jako edukacja; teraz kieruje do kampanii NovaQuant"),
        ],
        "revision_of": "demo-ig-kasia-v1",
        "blocked": True,
    },
    {
        "id": "demo-yt-akademia",
        "record": {
            "source": "youtube", "source_url": "https://www.youtube.com/watch?v=demo-Ak4",
            "author": "Akademia Inwestora Pro", "sponsor": "Akademia Inwestora Pro", "content_type": "ad",
            "published_at": "2026-11-19T12:00:00+00:00", "fetched_at": "2026-11-20T06:00:00+00:00",
            "text": {"title": "Darmowy kurs: inwestowanie na forex od zera",
                     "description": "Naucz się tradingu z mentorem. Po kursie otrzymasz indywidualny plan inwestycyjny dopasowany do Ciebie "
                                    "i dostęp do grupy VIP z sygnałami. Zapisz się, liczba miejsc ograniczona."},
            "links": ["https://akademia-inwestora.example/kurs"],
        },
        "landing": {
            "requestedUrl": "https://akademia-inwestora.example/kurs",
            "finalUrl": "https://fxglobal-markets.example/pl/open-account?partner=aip",
            "redirectChain": ["https://akademia-inwestora.example/kurs", "https://go.partnerlink.example/r/aip-pl",
                              "https://fxglobal-markets.example/pl/open-account?partner=aip"],
            "title": "FX Global Markets – otwórz konto z bonusem 100%",
            "text": "Otwórz rachunek CFD i odbierz bonus 100% od pierwszej wpłaty.\n"
                    "Dźwignia do 1:500 na walutach, złocie i kryptowalutach.\n"
                    "Twój opiekun konta zadzwoni i dobierze strategię.",
            "hasContactForm": True,
            "domainFlags": ["KNF_WARNING_LIST"],
        },
        "indicators": [("domain", "fxglobal-markets.example")],
        "history": [("2026-11-20T10:00:00Z", "IN_REVIEW", "a.kowalska", "„darmowy kurs” przekierowuje do otwarcia rachunku u brokera spoza rejestru")],
    },
]


def sentence_diff(old: str, new: str) -> tuple[list[str], list[str]]:
    split = lambda t: [s.strip() for s in t.replace("\n", " ").replace("! ", "!|").replace(". ", ".|").split("|") if s.strip()]  # noqa: E731
    a, b = split(old), split(new)
    return [s for s in b if s not in a], [s for s in a if s not in b]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ai-url", default=os.environ.get("AI_URL", "http://localhost:8000"))
    ap.add_argument("--file", type=Path, default=OUT)
    args = ap.parse_args()
    ai_url = args.ai_url.rstrip("/")
    data = json.loads(args.file.read_text(encoding="utf-8"))
    stats: Counter = Counter()

    demo: dict[str, dict[str, Any]] = {}
    for sc in SCENARIOS:
        # osobne wywołania: obie wersje posta mają ten sam URL, a /ingest odrzuca duplikaty w partii
        res = request("POST", f"{ai_url}/ingest", {"records": [sc["record"]]})["results"]
        if not res:
            print(f"/ingest odrzucił {sc['id']}", file=sys.stderr)
            return 1
        f = to_finding(res[0]["item"], res[0]["analysis"], sc["record"]["fetched_at"], set(), stats)
        f["id"] = sc["id"]
        f["demo"] = True
        if sc.get("kind"):
            f["kind"] = sc["kind"]
        known = {(i["type"], i["value"]) for i in f["indicators"]}
        f["indicators"] += [{"type": t, "value": v} for t, v in sc["indicators"] if (t, v) not in known]
        f["history"] = [{"at": f["fetchedAt"], "status": "NEW", "user": "system", "comment": "zaimportowano"}] if not any(
            h[2] == "system" for h in sc["history"]) else []
        f["history"] += [{"at": at, "status": st, "user": u, "comment": c} for at, st, u, c in sc["history"]]
        f["status"] = f["history"][-1]["status"]
        if sc.get("landing"):
            f["landingPages"] = [{**sc["landing"],
                                  "screenshotUrl": f"/api/assets/landing/{sc['id']}/0/desktop.svg",
                                  "mobileScreenshotUrl": f"/api/assets/landing/{sc['id']}/0/mobile.svg"}]
        if sc.get("blocked"):
            f["blockedUrls"] = sorted({*f["outboundLinks"], *(p["finalUrl"] for p in f["landingPages"])})
        if any(t == "brand" and v == "NovaQuant" for t, v in sc["indicators"]):
            f["campaignId"] = CAMPAIGN_ID
            if "IMPERSONATION" not in f["scam"]["signals"] and sc.get("landing", {}).get("domainFlags", []).count("IMPERSONATION"):
                f["scam"]["signals"].append("IMPERSONATION")
        demo[f["id"]] = f

    # wersje posta: nowsza wersja trzyma poprzednią treść i różnicę zdań
    for sc in SCENARIOS:
        if sc.get("revision_of"):
            new, old = demo[sc["id"]], demo[sc["revision_of"]]
            added, removed = sentence_diff(old["text"], new["text"])
            new["revisions"] = [{"findingId": old["id"], "fetchedAt": old["fetchedAt"], "text": old["text"],
                                 "added": added, "removed": removed,
                                 "riskLevel": old["riskLevel"], "modules": old["modules"]}]

    # powiązania: wspólne wskaźniki, przekierowania do strony oszustwa, poprzednia wersja posta
    for f in demo.values():
        rel: dict[str, dict[str, Any]] = {}
        mine = {(i["type"], i["value"]) for i in f["indicators"] if i["type"] != "author"}
        for g in demo.values():
            if g["id"] == f["id"]:
                continue
            shared = mine & {(i["type"], i["value"]) for i in g["indicators"]}
            if g["kind"] == "page" and any(SCAM_HOST in p["finalUrl"] for p in f["landingPages"]):
                rel[g["id"]] = {"findingId": g["id"], "reason": "REDIRECTS_TO", "detail": f"link prowadzi do {SCAM_HOST}", "score": 0.96}
            elif shared:
                t, v = sorted(shared)[0]
                rel[g["id"]] = {"findingId": g["id"], "reason": "SHARES_INDICATOR", "detail": f"wspólny wskaźnik ({t}): {v}",
                                "score": round(min(0.95, 0.7 + 0.08 * len(shared)), 3)}
        for sc in SCENARIOS:
            pair = {sc["id"], sc.get("revision_of") or sc.get("superseded_by")}
            if f["id"] in pair and None not in pair:
                other = (pair - {f["id"]}).pop()
                rel[other] = {"findingId": other, "reason": "SIMILAR_TEXT",
                              "detail": "ten sam post w innej wersji (edytowany po publikacji)", "score": 0.97}
        f["related"] = sorted(rel.values(), key=lambda r: -r["score"])[:5]

    findings = [f for f in data["findings"] if not f["id"].startswith(DEMO_PREFIX)] + list(demo.values())
    campaigns = [c for c in data.get("campaigns", []) if not str(c.get("id", "")).startswith("C-demo-")]
    members = [f for f in demo.values() if f.get("campaignId") == CAMPAIGN_ID]
    times = sorted(f["fetchedAt"] for f in members)
    campaigns.append({
        "id": CAMPAIGN_ID, "name": CAMPAIGN_NAME, "size": len(members),
        "scamShare": round(sum(f["scam"]["p"] >= 0.75 for f in members) / len(members), 3),
        "avgScam": round(sum(f["scam"]["p"] for f in members) / len(members), 3),
        "firstSeen": times[0], "lastSeen": times[-1],
        "platforms": sorted({f["platform"] for f in members}),
        "topIndicators": [{"type": "telegram", "value": "@novaquant_vip_pl"}, {"type": "phone", "value": "+48 999 000 111"},
                          {"type": "domain", "value": SCAM_HOST}],
        "status": "ACTIVE",
    })
    data["findings"], data["campaigns"] = findings, campaigns
    write_atomic(args.file, data)
    print(json.dumps({"demo": {f["id"]: [f["riskLevel"], f["modules"], round(f["scam"]["p"], 2), f["status"]] for f in demo.values()},
                      "total": len(findings)}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
