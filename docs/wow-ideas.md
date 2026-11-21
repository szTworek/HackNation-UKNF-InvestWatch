# InvestWatch: wyróżniki ponad core

Kontekst: 2 osoby, ~1–2 doby. Realny budżet to ~60 osobogodzin, z czego core (scraper, M1/M2/M3, dashboard, threshold, WebSocket) zajmie ~40–45 h. Na wyróżniki zostaje ~12–15 h, czyli dwa duże albo jeden duży i dwa małe.

Źródła: `UKNF/pliki_dc/markdown/Opis Wyzwania HackNation UKNF 19.11.md` (kryteria, wymagania) i `UKNF/pliki_dc/markdown/ZASÓB DLA UCZESTNIKÓW - InvestWatch - kryteria oceny informacji o ryzyku.md` (18 reguł).

Wagi jury: T = technologia/demo 30%, P = proces z asystentami AI 20%, A = architektura 20%, Z = zgodność ze specyfikacją 20%, W = atrakcyjność/zaskoczenie 10%.

## Ranking

| # | Wyróżnik | Co widzi jury | Kryteria | Koszt | Ryzyko |
|---|---|---|---|---|---|
| 1 | Wizualny audyt reguł 4/5/6/8 | screenshot strony z ramkami: „R4: 11 px vs 16 px = 0,69×”, „R5: kontrast 2,1:1”, przełącznik desktop/tablet/telefon | T, Z, W | 8–10 h | średnie |
| 2 | Karta dowodowa z wyjaśnieniem | cytat zdania podświetlony w treści, reguła i artykuł, SHA-256 i timestamp, eksport PDF, hash sprawdzany na żywo | Z, T, W | 5–6 h | niskie |
| 3 | Graf finfluencer → link/kod → firma | graf: kanał YouTube → `?ref=…` / kod „XYZ10” → domena brokera → status w rejestrze KNF albo na liście ostrzeżeń | Z, W | 7–8 h | średnie/wysokie (dane) |
| 4 | Transkrypcja wideo (faster-whisper) | rekord z filmu: „01:23 «gwarantuję 30% rocznie»”, reguły 3/14/15/17/18 na transkrypcji | T, W | 6–7 h | wysokie |
| 5 | Pętla analityka | przyciski „trafne / fałszywy alarm”, krzywa FP/FN w panelu kalibracji liczona z tych oznaczeń | Z, A | 4 h | niskie |

Poza rankingiem, do zrobienia niezależnie od wyboru: udokumentowany proces pracy z agentami AI (sekcja niżej). To kryterium P (20%) i kosztuje ~3 h, ale nie jest efektem wow, tylko punktami.

Odrzucone:
- Disclaimer mówiony vs pisany: wymaga #4 + OCR klatek + synchronizacji czasu, +6–8 h ponad #4 przy wysokim ryzyku; zostaje jako stretch #4.
- Aktywne uczenie z few-shot w prompcie: efekt niewidoczny w 3 min przy kilkunastu etykietach; tania część (krzywa z etykiet) jest w #5.
- Monitoring zmian w czasie (diff strony po ponownym crawlu): wymaga kilku przebiegów crawlera w czasie hackathonu, na demo słabo widoczny.
- Reguły jako YAML/config: to dobra decyzja architektoniczna dla core (kryterium A), a nie wow; warto ją przyjąć od początku, nie jako wyróżnik.
- Zewnętrzny znacznik czasu RFC 3161 (podpis czasu z zewnętrznego serwera TSA): łamie zasadę on-premise; w karcie wystarczy lokalny timestamp + łańcuch hashy.

## Rekomendacja: top 2

1. Wizualny audyt reguł 4/5/6/8. Większość zespołów zrobi reguły tekstowe na LLM. Reguły 4, 5, 6 i 8 dotyczą wyglądu i LLM ich nie sprawdzi, za to Playwright mierzy je deterministycznie z DOM. To unikat, który od razu widać na ekranie, a cztery z 18 reguł przestają być deklaracją.
2. Karta dowodowa z wyjaśnieniem (dwa kandydaci połączeni w jeden). Mówi językiem Urzędu: postępowanie potrzebuje dowodu, a nie samego score. Koszt jest niski, bo LLM i snapshot i tak są w core. Dochodzi tylko zapis, hash, weryfikacja cytatu i PDF.

Razem 13–16 h. Jeśli #1 utknie po 6 h, przycinamy do R4 + R8 (rozmiar czcionki + telefon), bo te dwie najmocniej wyglądają na ekranie.

## Szczegóły

### 1. Wizualny audyt reguł 4/5/6/8

Mechanizm: Playwright renderuje stronę w 3 viewportach (1440×900, 768×1024, 375×812). Skrypt w `page.evaluate` przechodzi po elementach z widocznym tekstem i zbiera `getComputedStyle` (font-size, color, opacity, visibility), `getBoundingClientRect`, tło (pierwszy nieprzezroczysty przodek) i `document.elementFromPoint` w środku boxa (czy coś go przykrywa).

Disclaimer, czyli fragment z informacją o ryzyku, wykrywamy regexem (np. „rachunków inwestorów detalicznych odnotowuje straty”, „ryzyk”, „możesz stracić”), a gdy regex nie trafi, pytamy LLM.

| Reguła | Pomiar | Próg |
|---|---|---|
| 4 Rozmiar czcionki | font-size disclaimera ÷ przeważający font-size (moda ważona liczbą znaków) | < 1,0 → naruszenie. Rozporządzenie wymaga czcionki co najmniej równej przeważającej (art. 44 ust. 2 lit. c; brzmienie do potwierdzenia na EUR-Lex, CELEX 32017R0565) |
| 5 Kontrast / przesłonięcie | kontrast wg wzoru WCAG; `elementFromPoint` ≠ disclaimer | WCAG 4,5:1 jako proxy, próg w panelu kalibracji (prawo nie podaje liczby) |
| 6 Ukrywanie | pozycja Y ÷ wysokość strony, wewnątrz `<footer>` / sekcji „Legal”, odległość od twierdzenia o zysku | konfigurowalny |
| 8 Responsywność | na 375 px: font-size < 12 px, `scrollWidth > clientWidth` przy `overflow:hidden`, element poza viewportem | konfigurowalny |

Wynik: screenshot z wstrzykniętymi ramkami (absolutnie pozycjonowane `div` z etykietą) plus JSON z pomiarami. Pomiary trafiają do karty dowodowej (#2).

Zależności: scraper na Playwright (core), tabela reguł z podstawą prawną.

Ryzyka i mitygacja:
- Baner cookies przykrywa disclaimer i daje fałszywe R5. Przed pomiarem usuwamy elementy `position:fixed` z najwyższym z-index.
- Tło jako obraz albo gradient psuje pomiar kontrastu. Oznaczamy wtedy wynik jako „niepewny”, nie jako naruszenie.
- Kreacje graficzne z social mediów nie mają DOM. Poza zakresem, stretch: OCR (PaddleOCR) i wysokość boxa jako proxy czcionki.
- Na demo: 3 własne strony testowe z zadanymi naruszeniami. Służą też jako zestaw testowy reguł (patrz sekcja o procesie).

### 2. Karta dowodowa z wyjaśnieniem

Przy każdej fladze zapisujemy niezmienny rekord:

```json
{
  "card_id": "c-000142",
  "captured_at": "2026-11-21T14:02:11Z",
  "url": "https://example-broker.pl/promocja",
  "final_url": "https://example-broker.pl/promocja?lang=pl",
  "module": "M2",
  "rule": { "id": "3", "name": "Informacja o ryzyku", "legal_basis": "art. 44 ust. 2 lit. b rozporządzenia del. 2017/565" },
  "verdict": "violation",
  "confidence": 0.87,
  "evidence": { "quote": "Zarabiaj nawet 12% rocznie bez wysiłku", "char_start": 1840, "char_end": 1879, "quote_verified": true },
  "measurements": { "R4_font_ratio": 0.69, "R5_contrast": 2.1 },
  "artifacts": {
    "html_sha256": "9f2c…", "screenshot_sha256": "41ab…", "screenshot_path": "s3://evidence/c-000142/full.png"
  },
  "model": { "name": "gemma3:12b", "prompt_sha256": "77d0…" },
  "prev_card_sha256": "e3b0…"
}
```

- `quote_verified` sprawdza, że cytat zwrócony przez LLM występuje dosłownie w znormalizowanym tekście. Bez dosłownego trafienia werdykt spada do „do weryfikacji”. To blokada halucynacji, którą warto pokazać jury jednym zdaniem.
- `prev_card_sha256` to łańcuch hashy: każda karta zawiera hash poprzedniej, więc podmiana jednej karty wychodzi przy sprawdzeniu łańcucha. Koszt ~1 h.
- Wersja modelu i hash promptu pozwalają odtworzyć decyzję.
- Na zielonym rekordzie (strona zgodna) UI też pokazuje, którym zdaniem reguła została spełniona.
- PDF generuje `page.pdf()` z Playwright, bo jest już w stosie.

Zależności: core LLM musi zwracać JSON z `evidence.quote`; Object Storage (MinIO) z core.
Ryzyko: niskie. Jedyne miejsce, gdzie może się wysypać, to normalizacja tekstu przy dopasowaniu cytatu (spacje, myślniki, nbsp).

### 3. Graf finfluencer → link/kod → firma

Ekstrakcja z opisów filmów i postów: linki (rozwijamy przekierowania bit.ly, linktr.ee), parametry afiliacyjne (`ref=`, `affid=`, `utm_source=`), kody promocyjne (regex „kod …”), wzmianki @. Domena docelowa jest dopasowywana do rejestru firm inwestycyjnych KNF (zależność od pracy nad rejestrem) i do listy ostrzeżeń publicznych KNF. Wizualizacja: Cytoscape.js.

Wartość: wprost odpowiada na korzyść z M1 („weryfikacja zasad współpracy pomiędzy firmą inwestycyjną a podmiotami reklamującymi”). Węzeł firmy spoza rejestru łączy M1 z M3.
Ryzyko: Instagram i TikTok trudno scrapować, więc graf może być pusty. Najpewniejsze źródło to opisy filmów YouTube, gdzie linki afiliacyjne są jawne.

### 4. Transkrypcja wideo

yt-dlp ściąga audio, faster-whisper (model `small` lub `medium`) robi transkrypcję z timestampami, a na segmentach działają te same reguły tekstowe co w M2/M1. Karta cytuje „01:23–01:31”.
Ryzyko: blokady TikToka, czas transkrypcji na CPU (film 10 min to kilka minut na `small`), brak GPU na sali. Na demo filmy pobrane wcześniej.

### 5. Pętla analityka

Na rekordzie przyciski „trafne / fałszywy alarm” zapisują etykietę. Panel kalibracji liczy FP/FN/precision/recall dla każdego progu z tych etykiet i rysuje krzywą (Recharts). Wzmacnia punkt walidacji jury „wpływ zmian parametrów progowych na wyniki”: zamiast deklaracji widać liczby.
Ryzyko: niskie; przed demo trzeba oznaczyć ~30–50 rekordów.

### Proces z agentami AI (kryterium P, obowiązkowo)

- W repo: `CLAUDE.md` / instrukcje dla agentów, `docs/adr/` (decyzje architektoniczne, po 5–10 linii), prompty reguł wersjonowane w plikach.
- Zestaw testowy reguł (strony z #1 + 20–30 ręcznie oznaczonych tekstów) uruchamiany w CI. Wynik precision/recall per reguła w README to dowód, że kod pisany z agentami jest sprawdzany, a nie wierzony.
- pip-audit / npm audit / Snyk w CI (wymóg specyfikacji, punkt „Weryfikowalny łańcuch dostaw”).
- Krótki log sesji: który agent robił co, gdzie człowiek odrzucił wynik. 1 slajd w PDF.

## Scenariusz demo (3 min)

| Czas | Co pokazujemy | Wyróżnik / core |
|---|---|---|
| 0:00–0:20 | Problem jednym zdaniem. Slajd architektury: `docker compose up` → scraper, kolejka, AI (Ollama), API, dashboard, MinIO, Postgres | core, A |
| 0:20–0:50 | Dashboard: liczniki M1/M2/M3, wykres trendu, filtry. Przesuwamy threshold: liczby rekordów i krzywa FP/FN zmieniają się na żywo | core, #5 jeśli jest |
| 0:50–1:35 | Wklejamy URL strony testowej. Zadanie wchodzi do kolejki, po ~30 s wyskakuje alert WebSocket „wysokie ryzyko”. Otwieramy rekord: screenshot z ramkami R4 „0,69×”, R5 „2,1:1”; przełączamy na telefon: ramka R8 „tekst ucięty” | #1, core WebSocket |
| 1:35–2:15 | Karta dowodowa: podświetlony cytat „Zarabiaj nawet 12% rocznie”, reguła 3 i art. 44 ust. 2 lit. b; drugi cytat „nadzorowani przez KNF, Twoje środki są bezpieczne” → reguła 18 i art. 44 ust. 8. Eksport PDF, w terminalu `sha256sum` pobranego screenshotu zgadza się z kartą | #2 |
| 2:15–2:40 | M1: rekord finfluencera z firmą z rejestru KNF i URL-em. M3: oferta „ułożymy Ci portfel, powiemy co kupić” od podmiotu spoza rejestru | core M1, M3 |
| 2:40–3:00 | Proces: repo, ADR, wynik zestawu testowego w CI, czysty audyt zależności. Zamknięcie: co Urząd dostaje jutro | P |

Zabezpieczenia demo:
- Strona testowa serwowana lokalnie, więc bez zależności od Wi-Fi.
- Wyniki z wcześniejszego przebiegu w bazie, gdyby LLM odpowiadał zbyt wolno.
- Nagrany film do 3 min (dopuszczony w wymaganiach formalnych) jako plan B.

## Co jest sprawdzone, a co nie

- Sprawdzone w materiałach: kryteria i wagi jury, 18 reguł z podstawami prawnymi, wymagania core (threshold, WebSocket, on-premise).
- Wnioskowane, niezweryfikowane: koszty w godzinach (szacunek bez kodu, repo nie ma jeszcze implementacji), brzmienie art. 44 ust. 2 lit. c („co najmniej równa wielkość czcionki”, z pamięci, do potwierdzenia na EUR-Lex), czas faster-whisper na CPU, dostępność danych afiliacyjnych na YouTube.
