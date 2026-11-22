# Strategia modelu: dotrenowanie vs LLM + scoring

Status: propozycja do rozmowy. Legenda: **[S]** sprawdzone (źródło obok), **[W]** wnioskowane lub szacowane, do potwierdzenia testem.

## 1. Co mówi zadanie

Źródło: `C:\Users\szymo\Documents\projects\hacknation\inwestwatch\inwestwatch\pliki_dc\markdown\Opis Wyzwania HackNation UKNF 19.11.md`

| temat | treść (parafraza) | linia |
|---|---|---|
| silnik | dowolny: vllm, llama.cpp albo ollama | 51 |
| model | model open source (np. Gemma4) **lub** klasyfikator (np. BERT) | 52 |
| scoring | „Klasyfikacja ryzyka poprzez funkcje scoringowe, która na podstawie warstwy wyjściowej przypisuje materiał do kategorii” | 53 |
| preprocessing | reprezentacja wektorowa: tokeny i embeddingi | 47-48 |
| próg | panel kalibracji: zmiana progu zmienia liczbę FP vs FN | 66-67 |
| stos | tylko darmowe modele (np. Ollama, vLLM), zero płatnych API, on-premise, Docker Compose | 99-100 |
| ocena jury | trafność klasyfikacji modułów AI i wpływ progu na wyniki w panelu kalibracji | 109 |
| kryteria | m.in. zgodność ze specyfikacją i preferowanymi technologiami (20%) | 125 |

Wniosek **[S]**: trenowanie nie jest wymagane. Zadanie stawia LLM i klasyfikator jako alternatywy („lub”). Wymagane są: ciągły score z wyjścia modelu, próg w panelu i pokazanie, jak próg przesuwa FP/FN. Embeddingi są wymagane w preprocessingu (l. 48), więc wariant (c) i tak korzysta z czegoś, co musimy mieć.

## 2. Sprzęt i środowisko

| element | wartość | źródło |
|---|---|---|
| CPU | Intel i5-12500H, 12 rdzeni / 16 wątków | **[S]** `Get-CimInstance Win32_Processor` |
| RAM | 16 GB, wolne w chwili pomiaru ~2,5 GB | **[S]** `Win32_ComputerSystem`, `FreePhysicalMemory` |
| GPU | Intel Iris Xe (zintegrowana), brak NVIDIA | **[S]** `Win32_VideoController`; `nvidia-smi: command not found` |
| dysk C: | 38,9 GB wolne | **[S]** `Get-PSDrive C` |
| Ollama | niezainstalowana | **[S]** `which ollama` brak, brak `%LOCALAPPDATA%\Programs\Ollama\ollama.exe` |
| Docker | klient jest, silnik nie działa (Docker Desktop wyłączony) | **[S]** `docker info` → brak `dockerDesktopLinuxEngine` |
| Python | 3.13 (domyślny), 3.12, 3.10 | **[S]** `py -0` |

Konsekwencja **[W]**: fine-tuning na GPU odpada. Gemma 3 4B w kwantyzacji Q4 zajmuje ~3,3 GB, więc mieści się w 16 GB po zamknięciu innych aplikacji. Przy obecnych 2,5 GB wolnego RAM się nie zmieści.

## 3. Testy wykonalności

Nie wykonane. Przerwałem je na prośbę Szymona: najpierw propozycja, pobieranie później. Liczby czasu poniżej to szacunki **[W]**, nie pomiary.

| test | stan | jak wykonać (po zgodzie) |
|---|---|---|
| ocena 1 reguły przez Gemmę na 3 rekordach | nie wykonany: brak Ollamy; próba instalacji `llama-cpp-python` przerwana | zainstalować Ollamę albo uruchomić Docker Desktop + `ollama/ollama`; `ollama pull gemma3:4b` (~3,3 GB); zmierzyć `eval_duration` z `/api/generate` |
| embedding 100 rekordów | nie wykonany: instalacja torch w venv w scratchpadzie przerwana (exit 2) | venv poza repo, `pip install torch --index-url https://download.pytorch.org/whl/cpu sentence-transformers`, model `intfloat/multilingual-e5-small` (~0,5 GB) |

Szacunki **[W]** do potwierdzenia testem:
- Gemma 3 4B Q4 na tym CPU: ~5–15 s na jedno wywołanie (prompt ~500 tokenów i krótka odpowiedź JSON). Przy ~300 rekordach i 13 regułach tekstowych M2 wywołanie per reguła daje ~4000 wywołań, czyli kilka do kilkunastu godzin. Dlatego w (b) potrzebny jest prefiltr regexowy i jedno wywołanie na rekord dla wielu reguł.
- multilingual-e5-small, 100 krótkich tekstów na CPU: rząd kilkunastu sekund do minuty.

## 4. Warianty

| | (a) fine-tuning HerBERT/BERT | (b) Gemma przez Ollamę + regexy → scoring | (c) embeddingi + regresja logistyczna | (d) hybryda b+c |
|---|---|---|---|---|
| nakład [W] | 12–20 h (etykiety, trening, ewaluacja, serwowanie) | 6–10 h (prompty per reguła, regexy, agregacja) | 3–5 h | 9–14 h (b + c + warstwa łącząca) |
| etykiety | setki per klasa; M2 per reguła daje >1000 | 0 do działania, 60–100 do kalibracji progu | 60–100 per moduł (binarnie na materiał) | 60–100 na materiał; LLM daje cechy per reguła |
| sprzęt | trening na CPU możliwy dla base, ale wolny; brak GPU **[S]** | CPU, ~4 GB RAM na model 4B **[W]**, czas wywołań to główne ryzyko | CPU, <1 GB **[W]** | jak (b) |
| ryzyko | brak danych: ~300 rekordów bez etykiet **[S]**, przeuczenie, nie zdążymy | wolne wywołania, halucynacje, score z „pewności słownej” słabo skalibrowany | za mało pozytywów; nie rozróżnia reguł M2 | złożoność; mniejsze niż (a) |
| score pod próg | sigmoid/softmax na wyjściu klasyfikatora | logprob tokenu „TAK/NIE” (llama.cpp `n_probs`; logprobs w Ollamie do sprawdzenia **[W]**) albo ważona suma flag reguł | `predict_proba` | `predict_proba` z LR na [cechy LLM + regexy + embedding] |
| demo | jedna liczba bez uzasadnienia | per materiał lista reguł z cytatem fragmentu i werdyktem | krzywa PR, suwak progu, FP/FN na żywo | uzasadnienie per reguła + skalibrowany score + suwak FP/FN |
| zgodność z l. 52-53 | tak (BERT) | tak (Gemma, Ollama) | częściowo (embeddingi z l. 48, klasyfikator nie-BERT) | tak, oba człony z listy |

Odrzucone:
- (a) fine-tuning: nie ma danych na ~18 reguł, a bez GPU ryzyko czasowe jest największe.
- (c) jako jedyny wariant: daje dobry suwak, ale nie mówi, którą regułę M2 materiał łamie, a o to pyta zadanie (l. 19-20).
- (b) jako jedyny wariant: działa, ale score z LLM bez kalibracji na etykietach słabo uzasadnia ruch progu.

## 5. Rekomendacja

Wariant (d): Gemma 3 4B przez Ollamę ocenia reguły tekstowe M2 oraz pytania M1/M3 (doradztwo, promocja przez podmiot trzeci), regexy i pomiary D3 (pomiary wizualne) obsługują reguły 4–8 i 13, a regresja logistyczna na tych cechach i embeddingu daje jeden score na moduł. Próg w panelu działa na `predict_proba`, a FP/FN liczymy na odłożonych etykietach, więc jury widzi realny ruch suwaka. Komponent „trenowany” to regresja logistyczna, trenowana w sekundy na 60–100 etykietach, bez fine-tuningu sieci.

Kolejność: najpierw (c) jako szkielet scoringu i panelu (najtańszy, od razu daje FP/FN), potem (b) jako cechy, które wpinamy do tej samej LR.

## 6. Argumenty do rozmowy z kolegą

- Zadanie nie wymaga trenowania: „model open source **lub** klasyfikator” (l. 52). Punktuje trafność i ruch progu (l. 109), nie to, że model był trenowany.
- Fine-tuning potrzebuje etykiet, których nie mamy: ~300 rekordów bez etykiet **[S]**. 18 reguł M2 przy kilku pozytywach każda to za mało, żeby BERT nauczył się czegoś poza szumem.
- Brak GPU **[S]**: trening HerBERT-base na CPU z kilkoma epokami i strojeniem zjada dzień hackathonu.
- Jego wkład zostaje trenowaniem: regresja logistyczna (albo mały MLP) na embeddingach i cechach LLM to uczciwy model uczony, z krzywą PR i kalibracją na demo.
- Furtka: jeśli do niedzieli dojdzie >500 etykiet, ten sam zbiór i ten sam panel przyjmą fine-tuned HerBERT jako kolejny wiersz cech. Architektura (d) tego nie blokuje.
- Ryzyko wolnej Gemmy na CPU **[W]** ograniczamy prefiltrem regexowym: reguła 14 (ostrzeżenie przy wynikach historycznych) odpala LLM tylko wtedy, gdy regex znajdzie wyniki historyczne.

## 7. Plan etykietowania pod kalibrację progu

Jeden rekord może mieć etykiety w kilku modułach. Dane: `C:\Users\szymo\Documents\projects\hacknation\inwestwatch\inwestwatch\data\export\` (google_ads 270, meta 16, bing 10, youtube 5, tiktok 6 **[S]** `data/export/README.md`).

| moduł | rekordy | etykiety | skąd rekordy |
|---|---|---|---|
| M1 (firma z rejestru KNF reklamowana przez podmiot trzeci) | 40 | `third_party_promo`: yes/no; `firm`: nazwa z rejestru KNF albo null | youtube, tiktok, meta, gdzie `author` ≠ firma, plus reklamy, w których reklamodawca ≠ marka |
| M2 (informacja o ryzyku) | 60 | per reguła tekstowa 1, 2, 3, 9, 10, 11, 12a, 12b, 14, 15, 16, 17, 18: `violation` / `ok` / `na`; do tego `overall`: flag/ok | google_ads i bing od firm z rejestru (np. `query_keywords` = domena firmy); reguły 4–8 i 13 = `na` dla OCR, bo wymagają pomiarów D3 |
| M3 (doradztwo bez zezwolenia) | 40 | `advisory_offer`: yes/no; `authorized`: yes/no/unknown | youtube, tiktok, meta (finfluencerzy, „sygnały”, „kursy”) |

- Razem ~100–120 unikalnych rekordów **[W]**. Czas: M1/M3 ~1 min na rekord, M2 ~3 min, razem ~5 roboczogodzin na 2 osoby.
- Podział: 20 rekordów etykietują obie osoby, żeby sprawdzić zgodność (procent zgodności na `overall`). Rozbieżności rozstrzygamy razem i zapisujemy jako doprecyzowanie reguły.
- Ewaluacja: ~60% etykiet do kalibracji i treningu LR, ~40% odłożone. FP/FN w panelu liczymy na odłożonych, żeby suwak nie pokazywał wyników na danych treningowych.
- Ryzyko **[W]**: w próbkach od dużych firm może być mało naruszeń M2. Wtedy trzeba celowo dobrać materiały z naruszeniami, np. reklamy z obietnicą zysku bez ostrzeżenia.
- Format: JSONL obok eksportu, `{source_url, module, rule, label, annotator}`. To propozycja, do potwierdzenia z autorem kontraktu D11 (forma kontraktu).
