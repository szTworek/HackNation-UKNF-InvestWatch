# Wytyczne scrapowania: czego szukać i co zapisywać

Dla osoby rozwijającej kolektory. Uzupełnia `docs/DECYZJE.md` (format rekordu) i `docs/sources-poc-analysis.md` (stan kolektorów).

## Najważniejsza zmiana: szukać po hasłach, nie po firmach

W paczce z 21.11 (288 polskich rekordów) **około 200 to reklamy dużych, licencjonowanych firm** (XTB, mBank, DM BOŚ, Revolut, Plus500), a około 75 w ogóle nie dotyczy inwestycji (bilety na „XTB KSW”, konta, kredyty). Oszustwa: 3 rekordy, doradztwo (M3): 2. Powód: zapytania były nazwami lub domenami znanych firm (`xtb.com`, „kod polecający XTB”).

Takie dane dobrze uczą modułu M2 (czy marketing licencjonowanej firmy spełnia reguły), ale prawie nic nie dają dla oszustw, M3 i namawiania. Do tego potrzebne są **zapytania opisujące obietnicę lub ofertę**, a nie markę.

## Hasła, które trafiają (pomiar 22.11)

Liczba rekordów, które ocena regułowa uznała za podejrzane, na liczbę nowych wyników. Ocena regułowa jest zgrubna (część trafień to szum), więc to ranking skuteczności haseł, a nie liczba oszustw. Pełne dane: `ml/data/skill/keyword_hits.json`, aktualizowane przez `ml/scripts/hunt_keywords.py`.

| Hasło | Podejrzane / nowe | Źródło |
|---|---|---|
| apartament inwestycyjny gwarantowany zysk | 19 / 22 | Meta |
| giełda papierów wartościowych | 14 / 24 | Meta |
| pko inwestycje | 8 / 20 | Meta |
| zysk bez ryzyka | 8 / 46 | Meta, YouTube |
| gwarantowany zysk | 6 / 25 | YouTube |
| pasywny dochód inwestycja | 6 / 17 | Meta |
| grupa vip trading | 5 / 9 | Meta |
| typy giełdowe | 5 / 5 | Meta |
| mbank inwestycje | 4 / 15 | Meta |
| flip mieszkania zysk | 3 / 18 | Meta |

Słabo trafiają: „konsultacje inwestycyjne”, „mentoring tradingowy”, „zarządzanie kapitałem” (głównie legalne szkolenia), „inwestycja w ropę”, „baltic pipe inwestycja”, „podwój swoje pieniądze”. Hasła z nazwą marki i słowem „inwestycje” („pko inwestycje”, „mbank inwestycje”) dobrze łapią podszycia.

## Gdzie szukać, według celu

| Cel | Źródło | Jak |
|---|---|---|
| Oszustwa | Meta Ad Library (PL, wszystkie reklamy) | hasła z obietnicą: „gwarantowany zysk”, „pasywny dochód”, „bot inwestycyjny”, „program inwestycyjny dla Polaków”, nazwy znanych osób + „inwestycja” |
| Podszycia | Meta, TikTok | marka + „inwestycje”, „społeczność”, „akademia”; zapisuj reklamodawców z marką w nazwie, ale spoza oficjalnych profili |
| Lista ostrzeżeń KNF | Meta, Google, TikTok | nazwy podmiotów z listy ostrzeżeń publicznych KNF jako zapytania |
| M3 | TikTok, YouTube, Instagram, Meta | „grupa vip”, „sygnały”, „typy giełdowe”, „kopiuj moje transakcje”, „napisz na priv”, „konsultacja 1:1”; wejście na profil autora i jego starsze materiały |
| M1 | YouTube, TikTok | „kod polecający”, „link w opisie”, „bonus na start”, „#współpraca”, nazwy brokerów i giełd krypto |
| M2 | Google Ads Transparency, Bing, strony firm | domeny i nazwy firm z rejestru KNF (obecne podejście jest tu dobre) |

**Śnieżna kula:** każdego reklamodawcę z podejrzanym rekordem odpytaj ponownie po nazwie i domenie strony docelowej. Oszuści prowadzą wiele kampanii naraz; graf kampanii w ai-service łączy je po wspólnych domenach, telefonach i komunikatorach.

## Co zapisywać w rekordzie (poza kopertą z D2)

1. **Strony docelowe** (`links`) – dla oszustw to najważniejszy dowód. Nie odwiedzaj żywych domen z podejrzanych reklam z firmowej sieci; zapisz adres i, jeśli to możliwe, kopię z archiwum.
2. **Grafika reklamy i OCR z ramkami.** Teraz `source_meta.ocr` ma tylko tekst. Dopisz dla każdej linii wysokość ramki w pikselach i wymiary obrazu, np. `ocr.lines: [{"text": ..., "h": 14, "y": 820}]`, `ocr.image: {"w": 1080, "h": 1080}`. Wtedy ai-service oceni regułę 4 (wielkość czcionki ostrzeżenia) także dla reklam obrazkowych. Bez tego reguły 4–8 dla grafik zostają `NOT_CHECKED`.
3. **Pomiary wizualne stron** (`risk_by_viewport`, D3) – już działają dla stron firm i są używane przez ai-service w regułach 4–8. Warto je zbierać także dla stron docelowych reklam. Uwaga: wykrywanie przesłonięcia (`occluded`) daje fałszywe alarmy, np. na każdej stronie Revolutu, a kontrast z CSS bywa błędny (XTB: 1,04 wobec 14 z pikseli), dlatego używamy `contrast_px`.
4. **Pełny tekst reklamy z Mety.** Tekst z biblioteki często nie zawiera ostrzeżenia, które jest na grafice. Bez grafiki lub OCR reguła 3 dla Mety zawsze wymaga weryfikacji przez człowieka.
5. **Transkrypcja wideo**, gdy opis jest krótki. Uwaga na halucynacje Whispera przy muzyce („Dziękuję za oglądanie”): odrzucaj transkrypcje z mniej niż 15 słowami lub wysokim `no_speech_prob`, nie wymuszaj języka.
6. **Identyfikatory reklamodawcy** (`advertiser_id`, `page_id`, nazwa płatnika z Meta `beneficiary_payers`) – do łączenia kampanii i sprawdzania w rejestrze KNF.
7. **Język** (`lang`) – w paczce 21.11 aż 660 z 1047 rekordów nie było po polsku (Google i Bing nie filtrują regionu szczelnie). Odfiltruj wcześnie albo oznacz.

## Higiena danych

- **Duplikaty:** D1 (`url_key` + `content_sha256`) jest dobre; ten sam tekst kreacji pod różnymi URL-ami też deduplikuj po treści (w Mecie 52 z 234 rekordów to powtórzenia).
- **Szum marki:** wycinaj od razu oczywiste NF (bilety, oferty pracy, kupony z marką w tytule), żeby nie zjadały limitów modelu.
- **Tempo:** Microsoft Ad Library zwraca 429 przy częstszych zapytaniach niż co ~20 s i nie znajduje fraz wielowyrazowych (tylko pojedyncze słowa). YouTube Data API: 10 000 jednostek dziennie, wyszukiwanie kosztuje 100.
- **Regulamin Mety:** automatyczne zbieranie dopuszcza tylko oficjalne Ad Library API. Kolektor WWW jest próbą wykonalności; w wersji produkcyjnej API z tokenem (`META_ACCESS_TOKEN`).
- **Dane osobowe:** rekordy zawierają nazwy autorów. Nie publikuj surowych eksportów, a w demo i repo maskuj osoby prywatne.

## Kolejność prac (propozycja)

1. Zapytania hasłowe w Mecie (lista wyżej) + śnieżna kula po reklamodawcach.
2. Ramki OCR w `source_meta.ocr` (reguła 4 dla grafik).
3. Lista ostrzeżeń KNF jako źródło zapytań.
4. TikTok i YouTube: profile finfluencerów z płatnymi grupami (M3).
5. Pomiary wizualne dla stron docelowych reklam.
