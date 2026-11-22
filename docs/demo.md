# Dane demo InvestWatch

Osiem fikcyjnych rekordów do prezentacji historii, grafu zależności, zmiany treści posta i podejrzanych przekierowań.

**To nie są dane ze scrapera.** Marki, osoby i numery są wymyślone, a domeny leżą w zarezerwowanej strefie `.example`, więc linki nigdzie nie prowadzą. Wyniki ryzyka dla treści liczy prawdziwy ai-service. Przekierowania, wpisy historii i sygnał podszywania się dopisuje skrypt, a zrzuty stron to makiety SVG.

Źródłem danych jest [`ml/scripts/add_demo_findings.py`](../ml/scripts/add_demo_findings.py). Zmiany w treści wprowadzaj tam, nie w tym pliku.

## Jak wczytać dane

Stack musi działać (`docker compose up -d`, `DATA_MODE=real`).

```bash
python ml/scripts/add_demo_findings.py
docker compose restart api
```

Skrypt dokleja rekordy do `frontend/mock-server/data/findings.real.json` i można go uruchamiać wielokrotnie. **Każde uruchomienie `build_findings.py` usuwa rekordy demo**, więc po przebudowie danych powtórz obie komendy.

## Co pokazać

| Temat | Gdzie |
|---|---|
| Post zmieniony po publikacji | [demo-ig-kasia-v2](http://localhost:8080/#/findings/demo-ig-kasia-v2), zakładka Historia |
| Graf zależności | [demo-fb-novaquant-1](http://localhost:8080/#/findings/demo-fb-novaquant-1), zakładka Powiązania |
| Ścieżka przekierowań i zrzuty | ten sam rekord, zakładka Strona docelowa |
| Ukryte przekierowanie do brokera | [demo-yt-akademia](http://localhost:8080/#/findings/demo-yt-akademia), zakładka Strona docelowa |
| Decyzje analityków | [Historia](http://localhost:8080/#/history) |
| Lista rekordów oszustw | [Podejrzenia oszustw](http://localhost:8080/#/modules/scam) |

Rekordy z wysokim wynikiem oszustwa są w widoku oszustw, a nie w modułach 1–3.

## Scenariusz 1: kampania NovaQuant (graf zależności)

### `demo-fb-novaquant-1`

- **Platforma i autor:** facebook, Finanse Bez Tajemnic
- **Adres:** `https://www.facebook.com/ads/library/?id=demo-880011`
- **Opublikowano:** 2026-11-11 18:20 UTC
- **Pobrano:** 2026-11-12 07:05 UTC
- **Wynik:** ryzyko CRITICAL, oszustwo 0.80, status ESCALATED
- **Linki w treści:** `https://krotko.example/nq7`
- **Wskaźniki:** brand: `NovaQuant`; person: `znany prezenter (wizerunek bez zgody)`; phone: `+48 999 000 111`

**Tytuł:**

> Znany prezenter zdradził, jak zarabia na sztucznej inteligencji

**Treść reklamy:**

> Sztuczna inteligencja handluje za ciebie i zarabia nawet 30% miesięcznie. Wystarczy wpłata 250 USD. Liczba miejsc ograniczona, nie czekaj! Zostaw swój numer, konsultant oddzwoni. Kontakt: Telegram @novaquant_vip_pl

**Ścieżka przekierowań:**

```text
https://krotko.example/nq7
  -> https://trk.adsredirect.example/c?id=19a7
  -> https://novaquant-pl.example/start
  -> https://novaquant-pl.example/rejestracja?utm_source=fb&aff=7731
```

**Strona docelowa:** NovaQuant AI – zarabiaj z algorytmem nowej generacji (flagi: NEW_DOMAIN, IMPERSONATION, formularz kontaktowy: tak)

> Średni zysk naszych klientów: 1 840 zł dziennie.
> Algorytm AI handluje za Ciebie 24/7, nie musisz znać się na giełdzie.
> Platforma nadzorowana przez KNF, Twoje środki są w pełni bezpieczne.
> Wpłata startowa tylko 250 USD. Liczba miejsc ograniczona.
> Zostaw numer, konsultant oddzwoni w ciągu 15 minut.

**Historia:**

| Kiedy (UTC) | Status | Kto | Komentarz |
|---|---|---|---|
| 2026-11-13 08:41 | IN_REVIEW | a.kowalska | sprawdzam stronę docelową i łańcuch przekierowań |
| 2026-11-13 09:12 | CONFIRMED | a.kowalska | skrócony link prowadzi przez tracker do formularza zbierania numerów na novaquant-pl.example |
| 2026-11-14 11:30 | ESCALATED | m.nowak | zgłoszone do CERT Polska (domena) i do Meta (reklama) |

### `demo-fb-novaquant-2`

- **Platforma i autor:** facebook, Codzienne Wiadomości 24
- **Adres:** `https://www.facebook.com/ads/library/?id=demo-880042`
- **Opublikowano:** 2026-11-15 06:00 UTC
- **Pobrano:** 2026-11-15 09:40 UTC
- **Wynik:** ryzyko CRITICAL, oszustwo 0.89, status IN_REVIEW
- **Linki w treści:** `https://krotko.example/nq9`
- **Wskaźniki:** brand: `NovaQuant`; phone: `+48 999 000 111`

**Tytuł:**

> Skandal na wizji: wywiad, który usunięto po 2 godzinach

**Treść reklamy:**

> Banki nie chcą, żebyś to wiedział. Sztuczna inteligencja inwestuje na giełdzie za Polaków i zarabia nawet 1 840 zł dziennie na akcjach i kryptowalutach. Zacznij od 250 USD, tylko dziś darmowa konfiguracja konta. Konsultant oddzwoni w 15 minut.

**Ścieżka przekierowań:**

```text
https://krotko.example/nq9
  -> https://news-pl24.example/artykul/ai-milioner
  -> https://novaquant-pl.example/start
  -> https://novaquant-pl.example/rejestracja?utm_source=fb&aff=7731
```

**Strona docelowa:** NovaQuant AI – zarabiaj z algorytmem nowej generacji (flagi: NEW_DOMAIN, IMPERSONATION, formularz kontaktowy: tak)

> Średni zysk naszych klientów: 1 840 zł dziennie.
> Algorytm AI handluje za Ciebie 24/7, nie musisz znać się na giełdzie.
> Platforma nadzorowana przez KNF, Twoje środki są w pełni bezpieczne.
> Wpłata startowa tylko 250 USD. Liczba miejsc ograniczona.
> Zostaw numer, konsultant oddzwoni w ciągu 15 minut.

**Historia:**

| Kiedy (UTC) | Status | Kto | Komentarz |
|---|---|---|---|
| 2026-11-15 10:05 | IN_REVIEW | m.nowak | ten sam formularz co w demo-fb-novaquant-1, inny nadawca reklamy |

### `demo-tt-novaquant`

- **Platforma i autor:** tiktok, zarabiaj.z.ai.pl
- **Adres:** `https://www.tiktok.com/@zarabiaj.z.ai.pl/video/demo-7311`
- **Opublikowano:** 2026-11-16 19:00 UTC
- **Pobrano:** 2026-11-17 06:30 UTC
- **Wynik:** ryzyko CRITICAL, oszustwo 0.80, status CONFIRMED
- **Linki w treści:** `https://novaquant-pl.example/start`
- **Wskaźniki:** brand: `NovaQuant`

**Opis:**

> Jak bot AI zarobił mi na wakacje #pasywnydochod #ai

**Transkrypcja:**

> Słuchajcie, od miesiąca nie dotykam wykresów. Bot AI handluje za mnie, zarabia jakieś 30% miesięcznie i nie da się stracić, bo algorytm zamyka straty. Link w bio, a jak macie pytania, piszcie na Telegram @novaquant_vip_pl.

**Ścieżka przekierowań:**

```text
https://novaquant-pl.example/start
  -> https://novaquant-pl.example/rejestracja?utm_source=fb&aff=7731
```

**Strona docelowa:** NovaQuant AI – zarabiaj z algorytmem nowej generacji (flagi: NEW_DOMAIN, IMPERSONATION, formularz kontaktowy: tak)

> Średni zysk naszych klientów: 1 840 zł dziennie.
> Algorytm AI handluje za Ciebie 24/7, nie musisz znać się na giełdzie.
> Platforma nadzorowana przez KNF, Twoje środki są w pełni bezpieczne.
> Wpłata startowa tylko 250 USD. Liczba miejsc ograniczona.
> Zostaw numer, konsultant oddzwoni w ciągu 15 minut.

**Historia:**

| Kiedy (UTC) | Status | Kto | Komentarz |
|---|---|---|---|
| 2026-11-17 08:00 | IN_REVIEW | a.kowalska | ten sam kanał Telegram co w reklamach NovaQuant |
| 2026-11-17 08:25 | CONFIRMED | a.kowalska | dołączone do kampanii NovaQuant |

### `demo-yt-comment-novaquant`

- **Platforma i autor:** youtube, Piotr W.
- **Adres:** `https://www.youtube.com/watch?v=demo-q9X&lc=demo-c1`
- **Opublikowano:** 2026-11-18 21:14 UTC
- **Pobrano:** 2026-11-19 06:00 UTC
- **Wynik:** ryzyko CRITICAL, oszustwo 0.87, status NEW
- **Wskaźniki:** brand: `NovaQuant`; phone: `+48 999 000 111`; whatsapp: `+48 999 000 111`

**Treść:**

> Polecam NovaQuant, wypłaciłem już 12 000 zł w dwa tygodnie, zero ryzyka. Opiekun konta pomoże ze wszystkim, WhatsApp +48 999 000 111

### `demo-web-novaquant`

- **Platforma i autor:** web, novaquant-pl.example
- **Adres:** `https://novaquant-pl.example/rejestracja`
- **Pobrano:** 2026-11-13 09:00 UTC
- **Wynik:** ryzyko CRITICAL, oszustwo 0.94, status ESCALATED
- **Wskaźniki:** brand: `NovaQuant`; domain: `novaquant-pl.example`

**Tytuł:**

> NovaQuant AI – zarabiaj z algorytmem nowej generacji

**Treść:**

> Średni zysk naszych klientów: 1 840 zł dziennie.
> Algorytm AI handluje za Ciebie 24/7, nie musisz znać się na giełdzie.
> Platforma nadzorowana przez KNF, Twoje środki są w pełni bezpieczne.
> Wpłata startowa tylko 250 USD. Liczba miejsc ograniczona.
> Zostaw numer, konsultant oddzwoni w ciągu 15 minut.

**Ścieżka przekierowań:**

```text
https://novaquant-pl.example/rejestracja
  -> https://novaquant-pl.example/rejestracja?utm_source=fb&aff=7731
```

**Strona docelowa:** NovaQuant AI – zarabiaj z algorytmem nowej generacji (flagi: NEW_DOMAIN, IMPERSONATION, formularz kontaktowy: tak)

> Średni zysk naszych klientów: 1 840 zł dziennie.
> Algorytm AI handluje za Ciebie 24/7, nie musisz znać się na giełdzie.
> Platforma nadzorowana przez KNF, Twoje środki są w pełni bezpieczne.
> Wpłata startowa tylko 250 USD. Liczba miejsc ograniczona.
> Zostaw numer, konsultant oddzwoni w ciągu 15 minut.

**Historia:**

| Kiedy (UTC) | Status | Kto | Komentarz |
|---|---|---|---|
| 2026-11-14 11:31 | ESCALATED | m.nowak | domena zgłoszona do CERT Polska |

## Scenariusz 2: post zmieniony po publikacji

### `demo-ig-kasia-v1`

- **Platforma i autor:** instagram, inwestuj.z.kasia
- **Adres:** `https://www.instagram.com/p/demo-Kx81/`
- **Opublikowano:** 2026-11-14 17:00 UTC
- **Pobrano:** 2026-11-14 20:00 UTC
- **Wynik:** ryzyko LOW, oszustwo 0.01, status DISMISSED

**Treść:**

> Mój portfel na listopad: 70% globalne ETF-y, 20% obligacje skarbowe, 10% gotówka. Nie ma tu żadnej magii, tylko regularne wpłaty i cierpliwość.
> Pamiętajcie: inwestowanie wiąże się z ryzykiem utraty części lub całości kapitału, a wyniki historyczne nie gwarantują przyszłych zysków.
> To nie jest rekomendacja, każdy musi ocenić swoją sytuację sam. #edukacja

**Historia:**

| Kiedy (UTC) | Status | Kto | Komentarz |
|---|---|---|---|
| 2026-11-15 09:20 | DISMISSED | a.kowalska | edukacja z ostrzeżeniem o ryzyku, bez promocji konkretnej firmy |

### `demo-ig-kasia-v2`

- **Platforma i autor:** instagram, inwestuj.z.kasia
- **Adres:** `https://www.instagram.com/p/demo-Kx81/`
- **Opublikowano:** 2026-11-14 17:00 UTC
- **Pobrano:** 2026-11-21 20:00 UTC
- **Wynik:** ryzyko CRITICAL, oszustwo 0.86, status IN_REVIEW
- **Linki w treści:** `https://krotko.example/nq-kasia`
- **Wskaźniki:** brand: `NovaQuant`

**Treść:**

> Mój portfel na listopad: 70% globalne ETF-y, 20% obligacje skarbowe, 10% gotówka. Nie ma tu żadnej magii, tylko regularne wpłaty i cierpliwość.
> Od tygodnia część środków trzymam w NovaQuant AI: algorytm sam handluje i daje gwarantowany zysk 12% miesięcznie, bez ryzyka.
> Z moim kodem polecającym KASIA250 wystarczy 250 USD na start, link w bio, oferta wygasa w niedzielę! Pytania piszcie na Telegram @novaquant_vip_pl

**Ścieżka przekierowań:**

```text
https://krotko.example/nq-kasia
  -> https://novaquant-pl.example/start?ref=KASIA250
  -> https://novaquant-pl.example/rejestracja?utm_source=fb&aff=7731
```

**Strona docelowa:** NovaQuant AI – zarabiaj z algorytmem nowej generacji (flagi: NEW_DOMAIN, IMPERSONATION, formularz kontaktowy: tak)

> Średni zysk naszych klientów: 1 840 zł dziennie.
> Algorytm AI handluje za Ciebie 24/7, nie musisz znać się na giełdzie.
> Platforma nadzorowana przez KNF, Twoje środki są w pełni bezpieczne.
> Wpłata startowa tylko 250 USD. Liczba miejsc ograniczona.
> Zostaw numer, konsultant oddzwoni w ciągu 15 minut.

**Historia:**

| Kiedy (UTC) | Status | Kto | Komentarz |
|---|---|---|---|
| 2026-11-21 20:00 | NEW | system | ponowny skan: post edytowany po publikacji. Usunięto ostrzeżenie o ryzyku, dodano „gwarantowany zysk”, kod polecający i link do NovaQuant |
| 2026-11-22 08:10 | IN_REVIEW | m.nowak | wcześniejsza wersja była odrzucona jako edukacja; teraz kieruje do kampanii NovaQuant |

**Zmiany względem wersji z 2026-11-14:**

```diff
- Pamiętajcie: inwestowanie wiąże się z ryzykiem utraty części lub całości kapitału, a wyniki historyczne nie gwarantują przyszłych zysków.
- To nie jest rekomendacja, każdy musi ocenić swoją sytuację sam.
- #edukacja
+ Od tygodnia część środków trzymam w NovaQuant AI: algorytm sam handluje i daje gwarantowany zysk 12% miesięcznie, bez ryzyka.
+ Z moim kodem polecającym KASIA250 wystarczy 250 USD na start, link w bio, oferta wygasa w niedzielę!
+ Pytania piszcie na Telegram @novaquant_vip_pl
```

## Scenariusz 3: „darmowy kurs” z ukrytym przekierowaniem

### `demo-yt-akademia`

- **Platforma i autor:** youtube, Akademia Inwestora Pro
- **Adres:** `https://www.youtube.com/watch?v=demo-Ak4`
- **Opublikowano:** 2026-11-19 12:00 UTC
- **Pobrano:** 2026-11-20 06:00 UTC
- **Wynik:** ryzyko CRITICAL, oszustwo 0.62, status IN_REVIEW
- **Linki w treści:** `https://akademia-inwestora.example/kurs`
- **Wskaźniki:** domain: `fxglobal-markets.example`

**Tytuł:**

> Darmowy kurs: inwestowanie na forex od zera

**Opis:**

> Naucz się tradingu z mentorem. Po kursie otrzymasz indywidualny plan inwestycyjny dopasowany do Ciebie i dostęp do grupy VIP z sygnałami. Zapisz się, liczba miejsc ograniczona.

**Ścieżka przekierowań:**

```text
https://akademia-inwestora.example/kurs
  -> https://go.partnerlink.example/r/aip-pl
  -> https://fxglobal-markets.example/pl/open-account?partner=aip
```

**Strona docelowa:** FX Global Markets – otwórz konto z bonusem 100% (flagi: KNF_WARNING_LIST, formularz kontaktowy: tak)

> Otwórz rachunek CFD i odbierz bonus 100% od pierwszej wpłaty.
> Dźwignia do 1:500 na walutach, złocie i kryptowalutach.
> Twój opiekun konta zadzwoni i dobierze strategię.

**Historia:**

| Kiedy (UTC) | Status | Kto | Komentarz |
|---|---|---|---|
| 2026-11-20 10:00 | IN_REVIEW | a.kowalska | „darmowy kurs” przekierowuje do otwarcia rachunku u brokera spoza rejestru |
