# InvestWatch: co budujemy

InvestWatch to wewnętrzne narzędzie dla analityków UKNF. Przegląda publiczne treści z mediów społecznościowych i bibliotek reklam, a następnie wskazuje te, które mogą naruszać przepisy lub być oszustwem inwestycyjnym. Analityk dostaje ocenę ryzyka razem z dowodem: konkretnym cytatem i powodem oznaczenia.

System **wspiera** analityka i nie wydaje rozstrzygnięć prawnych. Działa w języku polskim, a finalna aplikacja ma działać lokalnie, bez płatnych i zewnętrznych API.

## Jaki problem rozwiązujemy

Nie szukamy wyłącznie czystych scamów. Interesują nas cztery obszary:

| Obszar | Czego szukamy | Przykład |
|---|---|---|
| **M1: reklama przez osoby trzecie** | finfluencer promuje firmę inwestycyjną, często bez oznaczenia współpracy | „Załóż konto z mojego linka, bonus na start” |
| **M2: informacja o ryzyku** | materiał firmy mówi o zyskach, ale pomija ryzyko lub wymagane zastrzeżenia | „Fundusz zarobił 31%” bez informacji o ryzyku |
| **M3: ukryte doradztwo** | ktoś oferuje spersonalizowane porady lub zarządzanie, być może bez zezwolenia | „Napisz ile masz, dobiorę Ci portfel” |
| **Oszustwa inwestycyjne** | fałszywe platformy, boty AI, deepfake znanych osób, nierealne zyski | „Wpłać 1000 zł, algorytm zarobi 12 000 zł” |

Osobno rozpoznajemy też nieuprawnione namawianie do kupna konkretnych instrumentów („kupujcie teraz akcje X”). Ta ścieżka nie jest jeszcze w pełni podpięta pod moduły i scoring.

## Jak działa system

```text
Scraper (reklamy, posty, wideo)
        │
        ▼
Triage: czy to w ogóle o inwestycjach?
        │
        ▼
Wzbogacenie: transkrypcja, OCR, strona docelowa, analiza głosu
        │
        ▼
Klasyfikacja: temat, typ treści, instrumenty, 23 flagi, scam
        │
        ▼
Scoring: reguły UKNF, moduły M1–M3, poziom ryzyka
        │
        ▼
Graf powiązań: te same domeny, kontakty i kampanie
        │
        ▼
Panel analityka: lista, dowody, suwak czułości
```

Suwak progów pozwala analitykowi wybrać, czy woli wykryć więcej przypadków kosztem fałszywych alarmów, czy dostawać mniej, ale pewniejszych wskazań.

## Jak uczymy model

Nie mamy gotowego polskiego zbioru z takimi etykietami, dlatego budujemy go w kilku krokach:

1. **Zbieramy dane:** Reddit, YouTube (także z transkrypcją audio), archiwalne strony oszustów z listy CERT, biblioteki reklam Google, Bing i Meta.
2. **Uzupełniamy rzadkie klasy:** tłumaczymy zagraniczne zbiory o oszustwach i rekomendacjach finfluencerów oraz dodajemy 100 ręcznie napisanych trudnych przypadków. Te dane służą tylko do treningu, nigdy do testu.
3. **Etykietujemy przez modele-nauczycieli:** głównie lokalny Bielik, pomocniczo Groq i Gemini. Zewnętrzne modele służą wyłącznie do przygotowania danych i nie są częścią aplikacji.
4. **Trenujemy lekki klasyfikator:** embeddingi `bge-m3` i proste głowy klasyfikacyjne. Działa lokalnie, szybko i wskazuje fragment tekstu odpowiedzialny za flagę.
5. **Sprawdzamy jakość:** model zastępuje reguły słownikowe dopiero po przejściu bramki jakości. Docelowo oceniamy go na danych sprawdzonych przez człowieka.

## Stan na 21.11.2026, 22:30

| Element | Stan |
|---|---|
| Dokumenty w puli | 8032 |
| Dokumenty z etykietą | 3662, w tym 2518 realnych |
| Realne przykłady oznaczone jako scam | 115 (etykiety modeli, niezweryfikowane) |
| Dane sprawdzone przez człowieka | 0 |
| Model w aplikacji | reguły słownikowe; obecny model nie przeszedł bramki jakości |
| Trening nowego modelu | zaplanowany automatycznie po tłumaczeniu i etykietowaniu |
| API ai-service, scoring, kontrakt z backendem | jest pierwsza wersja |
| Rejestr KNF, graf kampanii, analiza mediów | do zrobienia (na razie zaślepki) |

## Największe ryzyka

- **Brak weryfikacji przez człowieka.** Obecne metryki mierzą zgodność z etykietami modeli, a nie prawdę.
- **Mało przykładów M3 i rekomendacji.** To najsłabiej pokryte klasy.
- **Brak sprawdzania rejestru KNF.** Bez niego system nie odróżni firmy z zezwoleniem od podmiotu bez zezwolenia.
- **Regulamin Mety.** Zbieranie ze strony biblioteki reklam to tylko próba, a wersja produkcyjna powinna używać oficjalnego API.
- **Licencje danych.** Część zbiorów ma licencje niekomercyjne, a Fraud-R1 nie podaje licencji. Przed wdrożeniem trzeba je usunąć lub wyjaśnić.

## Co dalej

1. Przetrenować model i porównać go z regułami słownikowymi.
2. Ocenić ręcznie 200–300 przypadków na stronie przeglądu i użyć ich jako wiarygodnego testu.
3. Dodać sprawdzanie podmiotów w rejestrze KNF i na liście ostrzeżeń.
4. Podpiąć ścieżkę rekomendacji pod scoring.
5. Zbudować graf kampanii i wzbogacanie treści (strona docelowa, OCR, głos).
6. Połączyć scraper, backend i frontend, a na końcu spakować całość w Dockerze.

## Powiązane dokumenty

- [Plan modelu](plan-model.md)
- [Integracja z backendem](backend-integration.md)
- [Specyfikacja frontendu](frontend-agent.md)
- [Strategia scrapingu](scraping-strategy.md)
- [Wdrożenie](deployment.md)
