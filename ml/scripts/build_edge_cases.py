"""Ręcznie napisane trudne przypadki (granice klas) -> data/gold/edge_cases.jsonl.

Wszystkie firmy, osoby i kwoty są fikcyjne. To dane syntetyczne: tylko do treningu, nigdy do testu.
Etykiety są pewne (autor zna intencję), a cytaty flag są sprawdzane względem tekstu.

  uv run python scripts/build_edge_cases.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from investwatch_ml.labels import CONTENT_TYPES, FLAG_KEYS, INSTRUMENTS, TOPICS

ML_DIR = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8")
T = {"I": "INVESTMENT", "F": "FINANCIAL_OTHER", "N": "NON_FINANCIAL"}
C = {"NE": "NEWS_EDU", "OP": "OPINION_DISCUSSION", "FM": "FIRM_OWN_MARKETING", "TP": "THIRD_PARTY_PROMO",
     "RC": "RECOMMENDATION", "SO": "SERVICE_OFFER", "NO": "NONE"}
K = {"CFD": "CFD_FOREX", "STK": "STOCKS", "ETF": "FUNDS_ETF", "BND": "BONDS", "CRY": "CRYPTO",
     "DER": "OTHER_DERIVATIVES", "NON": "NON_INSTRUMENT"}

# (grupa, temat, typ, instrumenty, scam, tekst, [(flaga, cytat), ...])
CASES = [
    # ostrzeżenia i edukacja cytujące język oszustów: NIE scam
    ("warning", "I", "NE", "CRY", 0, "Uwaga na reklamy typu „zarabiaj 5000 zł dziennie z botem AI”. To klasyczny schemat oszustwa, nie wpłacajcie nikomu pieniędzy.", []),
    ("warning", "I", "NE", "CFD", 0, "Jak rozpoznać fałszywego brokera? Dzwoni „opiekun konta”, obiecuje gwarantowany zysk i każe zainstalować AnyDesk. Jeśli to słyszysz, rozłącz się i sprawdź firmę na liście ostrzeżeń KNF.", []),
    ("warning", "I", "NE", "NON", 0, "Piramida finansowa działa tak: wypłaty starych uczestników pochodzą z wpłat nowych. Dlatego obietnica 3% dziennie powinna od razu zapalić czerwoną lampkę.", []),
    ("warning", "I", "OP", "CRY", 0, "straciłem 14 tysięcy przez gościa z telegrama, obiecywał że nie da się stracić. nie róbcie tego co ja, serio", []),
    ("warning", "I", "NE", "CRY", 0, "W sieci krąży film, na którym znany prezenter rzekomo poleca platformę krypto. To deepfake. Prezenter nie ma z tym nic wspólnego, a strona wyłudza dane kart.", []),
    ("warning", "I", "OP", "CFD", 0, "Ktoś kojarzy firmę Trevanta? Dzwonili do mojej mamy że ma „zainwestować od 250 euro”. Dla mnie to śmierdzi na kilometr, zgłaszam na CERT.", []),
    ("warning", "I", "NE", "ETF", 0, "Nie istnieje inwestycja z gwarancją zysku i bez ryzyka. Im wyższa obiecywana stopa zwrotu, tym większe ryzyko, że stracisz kapitał.", [("RISK_WARNING", "ryzyko, że stracisz kapitał")]),
    ("warning", "I", "NE", "CRY", 0, "Dziś w odcinku rozkładamy na czynniki pierwsze scam „rug pull”: twórcy tokena wyciągają płynność i znikają z pieniędzmi inwestorów.", []),
    ("warning", "I", "OP", "CRY", 0, "hahaha „1000% w tydzień gwarantowane” jasne, a ja jestem królową Anglii. ludzie ogarnijcie się", []),
    ("warning", "F", "NO", "", 0, "Oszuści podszywają się pod bank i wysyłają SMS o blokadzie konta. Nie klikaj w link, zadzwoń na infolinię z karty.", []),
    # legalny marketing firmy: z ryzykiem i z brakami
    ("firm_ok", "I", "FM", "CFD", 0, "Handluj na ponad 60 parach walut w Nordtradix. Kontrakty CFD są złożonymi instrumentami i wiążą się z dużym ryzykiem szybkiej utraty środków z powodu dźwigni finansowej. 74% rachunków inwestorów detalicznych traci pieniądze.", [("RISK_WARNING", "74% rachunków inwestorów detalicznych traci pieniądze")]),
    ("firm_ok", "I", "FM", "ETF", 0, "Bursztynowe TFI: fundusz obligacji zarobił 6,2% w 2024 r. Wyniki historyczne nie gwarantują osiągnięcia podobnych wyników w przyszłości. Inwestowanie wiąże się z ryzykiem utraty części kapitału.", [("PAST_PERFORMANCE", "zarobił 6,2% w 2024 r."), ("PAST_PERF_DISCLAIMER", "Wyniki historyczne nie gwarantują"), ("RISK_WARNING", "ryzykiem utraty części kapitału")]),
    ("firm_bad", "I", "FM", "ETF", 0, "Bursztynowe TFI: nasz fundusz akcji zarobił 31% w zeszłym roku! Dołącz do zadowolonych klientów i pozwól pieniądzom pracować.", [("PAST_PERFORMANCE", "zarobił 31% w zeszłym roku"), ("PROFIT_CLAIM", "pozwól pieniądzom pracować")]),
    ("firm_bad", "I", "FM", "CFD", 0, "Nordtradix: najniższe spready na rynku, lepiej niż u konkurencji. Zarabiaj na wzrostach i spadkach kursu euro już dziś.", [("PRODUCT_COMPARISON", "najniższe spready na rynku"), ("PROFIT_CLAIM", "Zarabiaj na wzrostach i spadkach")]),
    ("firm_bad", "I", "FM", "STK", 0, "DM Orlikowski jest nadzorowany przez KNF, więc Twoje pieniądze są u nas całkowicie bezpieczne. Otwórz rachunek maklerski w 5 minut.", [("SUPERVISOR_AS_SAFETY", "nadzorowany przez KNF, więc Twoje pieniądze są u nas całkowicie bezpieczne"), ("NO_RISK_CLAIM", "całkowicie bezpieczne")]),
    ("firm_ok", "I", "FM", "STK", 0, "DM Orlikowski podlega nadzorowi KNF. Nadzór nie oznacza gwarancji wyniku ani bezpieczeństwa inwestycji. Inwestowanie w akcje wiąże się z ryzykiem utraty kapitału.", [("RISK_WARNING", "ryzykiem utraty kapitału")]),
    ("firm_bad", "I", "FM", "ETF", 0, "Oszczędzaj z IKZE w Bursztynowym TFI i odzyskaj nawet kilka tysięcy złotych w podatku. Lepsze niż lokata!", [("TAX_CLAIM", "odzyskaj nawet kilka tysięcy złotych w podatku"), ("PRODUCT_COMPARISON", "Lepsze niż lokata")]),
    ("firm_ok", "I", "FM", "BND", 0, "Nowa emisja obligacji Finmostek S.A., oprocentowanie 9% w skali roku. Obligacje korporacyjne niosą ryzyko niewypłacalności emitenta i utraty zainwestowanych środków. Szczegóły w prospekcie.", [("PROFIT_CLAIM", "oprocentowanie 9% w skali roku"), ("RISK_WARNING", "ryzyko niewypłacalności emitenta i utraty zainwestowanych środków")]),
    ("firm_bad", "I", "FM", "CRY", 0, "Kryptolia: kupuj bitcoina bez prowizji przez 30 dni! Promocja tylko do niedzieli. BTC w tym roku dojdzie do nowych szczytów.", [("URGENCY_PRESSURE", "Promocja tylko do niedzieli"), ("FORECAST", "BTC w tym roku dojdzie do nowych szczytów")]),
    ("firm_ok", "I", "FM", "ETF", 0, "Prognoza zakłada wzrost funduszu o 5% w 2027 r. Prognozy nie są wiarygodnym wskaźnikiem przyszłych wyników, a wartość jednostek może spaść.", [("FORECAST", "wzrost funduszu o 5% w 2027 r."), ("FORECAST_DISCLAIMER", "Prognozy nie są wiarygodnym wskaźnikiem przyszłych wyników"), ("RISK_WARNING", "wartość jednostek może spaść")]),
    # influencer / osoba trzecia: M1
    ("promo", "I", "TP", "CFD", 0, "Partnerem dzisiejszego odcinka jest Nordtradix. Z moim linkiem masz zero prowizji na start, link w opisie. Pamiętaj, że CFD są ryzykowne i możesz stracić pieniądze.", [("AD_DISCLOSURE", "Partnerem dzisiejszego odcinka jest Nordtradix"), ("RISK_WARNING", "możesz stracić pieniądze")]),
    ("promo", "I", "TP", "CRY", 0, "ja wszystko trzymam na kryptolii, wpisz kod MACIEK10 przy rejestracji i masz 10% taniej na opłatach, sztos", []),
    ("promo", "I", "TP", "CFD", 0, "Od roku gram na Nordtradix i nie wyobrażam sobie innej platformy. Zakładajcie konto z linka w bio, dostaniecie bonus 50 dolarów na start!", [("PROFIT_CLAIM", "bonus 50 dolarów na start")]),
    ("promo", "I", "TP", "STK", 0, "#współpraca Testuję aplikację DM Orlikowski i kupiłam pierwsze akcje za 100 zł. Prosty interfejs, polecam sprawdzić. Inwestowanie niesie ryzyko straty.", [("AD_DISCLOSURE", "#współpraca"), ("LOW_ENTRY_DEPOSIT", "za 100 zł"), ("RISK_WARNING", "Inwestowanie niesie ryzyko straty")]),
    ("promo", "I", "TP", "CRY", 0, "materiał sponsorowany przez Kryptolia. pokażę wam jak w 3 minuty kupić pierwsze ethereum, a na końcu kod na bonus", [("AD_DISCLOSURE", "materiał sponsorowany")]),
    ("promo", "I", "TP", "CFD", 0, "Zrobiłem 4200 zł w tydzień na złocie na tej platformie, zobaczcie screena. Kto chce tak samo, klik w link poniżej i rejestracja zajmuje minutę.", [("PROFIT_CLAIM", "Zrobiłem 4200 zł w tydzień")]),
    ("promo", "I", "TP", "ETF", 0, "Link afiliacyjny: jeśli otworzysz IKE przez ten link, dostanę małą prowizję, a Ty nic nie dopłacasz. Fundusze mogą tracić na wartości.", [("AD_DISCLOSURE", "Link afiliacyjny"), ("TAX_CLAIM", "IKE"), ("RISK_WARNING", "Fundusze mogą tracić na wartości")]),
    ("promo", "I", "TP", "CFD", 0, "no i słuchajcie ten broker to jest coś co ja używam codziennie dajcie sobie szansę wchodzicie w link w opisie rejestrujecie się wpłacacie dwieście złotych i lecimy", [("LOW_ENTRY_DEPOSIT", "wpłacacie dwieście złotych")]),
    ("promo", "I", "TP", "CRY", 0, "Ranking 3 najlepszych giełd krypto 2026. Miejsce pierwsze: Kryptolia, bo ma najniższe opłaty. Linki polecające znajdziesz pod filmem.", [("PRODUCT_COMPARISON", "najniższe opłaty"), ("AD_DISCLOSURE", "Linki polecające")]),
    ("promo", "F", "NO", "", 0, "#reklama Założyłem konto osobiste w banku Finmostek, 0 zł za kartę i 200 zł premii. Link w opisie.", []),
    # rekomendacje dla ogółu vs opinia
    ("reco", "I", "RC", "STK", 0, "Kupujcie teraz akcje Polmetalu, zanim wszyscy się zorientują. Cel 85 zł do końca roku.", [("SPECIFIC_INSTRUMENT_CALL", "Kupujcie teraz akcje Polmetalu"), ("FORECAST", "Cel 85 zł do końca roku")]),
    ("reco", "I", "RC", "CRY", 0, "SOL poniżej 90 dolarów to prezent. Ładujcie ile się da, za pół roku będzie trzy razy więcej.", [("SPECIFIC_INSTRUMENT_CALL", "Ładujcie ile się da"), ("FORECAST", "za pół roku będzie trzy razy więcej")]),
    ("reco", "I", "RC", "STK", 0, "Sprzedajcie Medikor póki jeszcze można, po wynikach poleci w dół o 20%. To nie jest porada inwestycyjna.", [("SPECIFIC_INSTRUMENT_CALL", "Sprzedajcie Medikor"), ("FORECAST", "poleci w dół o 20%")]),
    ("reco", "I", "RC", "CFD", 0, "EURPLN short z 4,32, stop 4,36, target 4,25. Kto wchodzi, wchodzi teraz.", [("SPECIFIC_INSTRUMENT_CALL", "EURPLN short z 4,32"), ("FORECAST", "target 4,25")]),
    ("reco", "I", "RC", "ETF", 0, "Jedyny ETF, który powinniście mieć w portfelu, to ETF na światowe akcje. Kupujcie co miesiąc i nie patrzcie na wykres.", [("SPECIFIC_INSTRUMENT_CALL", "Kupujcie co miesiąc")]),
    ("reco", "I", "RC", "DER", 0, "Opcje call na WIG20 na marzec to teraz najlepszy zakład. Brać zanim zmienność wzrośnie.", [("SPECIFIC_INSTRUMENT_CALL", "Opcje call na WIG20 na marzec")]),
    ("opinion", "I", "OP", "STK", 0, "Kupiłem wczoraj trochę Polmetalu, bo podoba mi się ich dywidenda. Nie wiem czy to dobry moment, zobaczymy.", []),
    ("opinion", "I", "OP", "CRY", 0, "Myślicie że BTC jeszcze spadnie? Ja trzymam swoje od 2021 i się nie stresuję, ale nikomu nic nie radzę.", []),
    ("opinion", "I", "OP", "ETF", 0, "Moje IKE po 5 latach: +38%. Same ETF-y, zero kombinowania. Dzielę się tylko wynikiem, każdy ma swoją strategię.", [("PAST_PERFORMANCE", "Moje IKE po 5 latach: +38%")]),
    ("opinion", "I", "OP", "STK", 0, "Zarząd Medikoru znowu rozwadnia akcjonariuszy, trzeci raz w dwa lata. Dla mnie to czerwona flaga, wyszedłem z pozycji.", []),
    ("opinion", "I", "OP", "CFD", 0, "pierwszy miesiąc na forexie -40% konta xd chyba to nie dla mnie, wracam do etfów", []),
    ("opinion", "I", "OP", "BND", 0, "Czy obligacje skarbowe indeksowane inflacją mają jeszcze sens przy spadającym CPI? Pytam, bo kończą mi się czteroletnie.", []),
    ("news", "I", "NE", "STK", 0, "WIG20 zakończył sesję wzrostem o 1,2%. Najmocniej zyskały banki, a obroty wyniosły 1,4 mld zł.", []),
    ("news", "I", "NE", "ETF", 0, "Czym różni się ETF akumulujący od dystrybuującego? Pierwszy reinwestuje dywidendy, drugi wypłaca je inwestorom.", []),
    ("news", "I", "NE", "CFD", 0, "Dźwignia 1:30 oznacza, że wpłacając 1000 zł kontrolujesz pozycję 30 000 zł. Strata również liczona jest od pełnej wartości pozycji.", [("RISK_WARNING", "Strata również liczona jest od pełnej wartości pozycji")]),
    ("news", "I", "NE", "BND", 0, "Ministerstwo Finansów ogłosiło oprocentowanie obligacji oszczędnościowych na grudzień. Roczne wynoszą 4,5%.", []),
    # ukryte doradztwo i usługi: M3
    ("advisory", "I", "SO", "ETF", 0, "Napisz mi ile masz odłożone i na jak długo, a dobiorę Ci portfel pod Twoją sytuację. Konsultacja 1:1 to 299 zł.", [("PERSONALIZED_ADVICE", "dobiorę Ci portfel pod Twoją sytuację"), ("PAID_ADVISORY_SERVICE", "Konsultacja 1:1 to 299 zł"), ("OFF_PLATFORM_CONTACT", "Napisz mi")]),
    ("advisory", "I", "SO", "STK", 0, "Zarządzam portfelami kilkunastu klientów, biorę 20% od zysku. Wolne jeszcze dwa miejsca, pisz na priv.", [("PAID_ADVISORY_SERVICE", "Zarządzam portfelami kilkunastu klientów"), ("URGENCY_PRESSURE", "Wolne jeszcze dwa miejsca"), ("OFF_PLATFORM_CONTACT", "pisz na priv")]),
    ("advisory", "I", "SO", "CFD", 0, "Grupa VIP z sygnałami na złoto i EURUSD, 3-5 sygnałów dziennie. Abonament 149 zł miesięcznie, dostęp przez Telegram.", [("PAID_ADVISORY_SERVICE", "Grupa VIP z sygnałami"), ("OFF_PLATFORM_CONTACT", "dostęp przez Telegram")]),
    ("advisory", "I", "SO", "CRY", 0, "Prześlij screena swojego portfela krypto, a powiem Ci co sprzedać, a co dokupić. Audyt portfela 199 zł.", [("PERSONALIZED_ADVICE", "powiem Ci co sprzedać, a co dokupić"), ("PAID_ADVISORY_SERVICE", "Audyt portfela 199 zł")]),
    ("advisory", "I", "OP", "ETF", 0, "@kasia_87 przy Twoim wieku i 50 tys. na koncie wrzuciłbym 70% w ETF na świat i 30% w obligacje indeksowane, a IKE otwórz jeszcze w tym roku.", [("PERSONALIZED_ADVICE", "przy Twoim wieku i 50 tys. na koncie wrzuciłbym 70% w ETF"), ("TAX_CLAIM", "IKE")]),
    ("advisory", "I", "SO", "STK", 0, "Pomagam przedsiębiorcom ułożyć strategię inwestowania nadwyżek firmowych. Indywidualny plan, konkretne spółki, stała opieka. Umów bezpłatną rozmowę.", [("PERSONALIZED_ADVICE", "Indywidualny plan, konkretne spółki"), ("PAID_ADVISORY_SERVICE", "stała opieka")]),
    ("advisory", "I", "SO", "CFD", 0, "Mentoring tradingowy 12 tygodni: analizujemy Twoje pozycje na żywo i mówię Ci kiedy wejść i wyjść. Cena 4900 zł.", [("PAID_ADVISORY_SERVICE", "Mentoring tradingowy 12 tygodni"), ("PERSONALIZED_ADVICE", "mówię Ci kiedy wejść i wyjść")]),
    ("advisory", "I", "SO", "CRY", 0, "Daj mi dostęp API do swojego konta na giełdzie, będę handlował za Ciebie. Rozliczamy się 30/70 z wypracowanego zysku.", [("PAID_ADVISORY_SERVICE", "będę handlował za Ciebie"), ("PROFIT_CLAIM", "wypracowanego zysku")]),
    ("advisory", "I", "SO", "ETF", 0, "Licencjonowany doradca inwestycyjny, wpis na listę KNF nr 123. Opracuję rekomendację dopasowaną do Twojego profilu ryzyka. Inwestowanie wiąże się z ryzykiem straty.", [("PERSONALIZED_ADVICE", "rekomendację dopasowaną do Twojego profilu ryzyka"), ("PAID_ADVISORY_SERVICE", "Licencjonowany doradca inwestycyjny"), ("RISK_WARNING", "ryzykiem straty")]),
    ("advisory", "I", "OP", "STK", 0, "Pytanie do doświadczonych: mam 30 lat i 20 tys., od czego zaczynać? Nie szukam płatnych usług, chcę poczytać wasze doświadczenia.", []),
    ("advisory", "I", "NE", "ETF", 0, "Prowadzę bezpłatny kurs o podstawach inwestowania: czym jest dywersyfikacja, jak czytać KID, jak liczyć koszty. Nie mówię, co kupić.", []),
    ("advisory", "I", "SO", "CFD", 0, "kopiuj moje pozycje 1:1 przez copy trading, wszystko leci automatem na twoim koncie, opłata 15% od zysku", [("PAID_ADVISORY_SERVICE", "kopiuj moje pozycje 1:1"), ("AUTOMATED_PROFIT", "wszystko leci automatem")]),
    # oszustwa wprost
    ("scam", "I", "SO", "CRY", 1, "Marek Zawiślak ujawnił na wizji metodę, którą banki próbowały ukryć! Wpłać 1000 zł, a algorytm AI zarobi dla Ciebie 12 000 zł w miesiąc. Zostaw numer, konsultant oddzwoni.", [("CELEBRITY_OR_BRAND_ENDORSEMENT", "Marek Zawiślak ujawnił"), ("SECRECY_CONSPIRACY", "banki próbowały ukryć"), ("LOW_ENTRY_DEPOSIT", "Wpłać 1000 zł"), ("AUTOMATED_PROFIT", "algorytm AI zarobi dla Ciebie"), ("UNREALISTIC_RETURNS", "12 000 zł w miesiąc"), ("OFF_PLATFORM_CONTACT", "Zostaw numer, konsultant oddzwoni")]),
    ("scam", "I", "SO", "CFD", 1, "SKANDAL NA ŻYWO! Wywiad, który usunięto z telewizji: minister przyznaje, że Polacy mogą zarabiać 3% dziennie na platformie Vexorra. Gwarantowany zysk, zero ryzyka.", [("FAKE_NEWS_FORMAT", "Wywiad, który usunięto z telewizji"), ("CELEBRITY_OR_BRAND_ENDORSEMENT", "minister przyznaje"), ("UNREALISTIC_RETURNS", "3% dziennie"), ("GUARANTEED_PROFIT", "Gwarantowany zysk"), ("NO_RISK_CLAIM", "zero ryzyka")]),
    ("scam", "I", "SO", "NON", 1, "Państwowy program inwestycyjny dla Polaków. Spółka paliwowa dzieli się zyskiem: zainwestuj 250 euro i otrzymuj stały dochód co tydzień. Liczba miejsc ograniczona!", [("CELEBRITY_OR_BRAND_ENDORSEMENT", "Państwowy program inwestycyjny"), ("LOW_ENTRY_DEPOSIT", "zainwestuj 250 euro"), ("PROFIT_CLAIM", "stały dochód co tydzień"), ("URGENCY_PRESSURE", "Liczba miejsc ograniczona")]),
    ("scam", "I", "SO", "CRY", 1, "Bot Trevanta AI handluje 24/7 za Ciebie. Nasi użytkownicy zarabiają średnio 800 zł dziennie bez żadnej wiedzy. Rejestracja zamyka się o północy.", [("AUTOMATED_PROFIT", "handluje 24/7 za Ciebie"), ("UNREALISTIC_RETURNS", "800 zł dziennie"), ("URGENCY_PRESSURE", "zamyka się o północy")]),
    ("scam", "I", "SO", "CRY", 1, "Cześć, widziałam Twój komentarz o krypto. Mój mentor pokazał mi platformę, na której w miesiąc podwoiłam oszczędności. Przejdźmy na WhatsApp, wszystko Ci wytłumaczę.", [("UNREALISTIC_RETURNS", "w miesiąc podwoiłam oszczędności"), ("OFF_PLATFORM_CONTACT", "Przejdźmy na WhatsApp")]),
    ("scam", "I", "SO", "CFD", 1, "Dzień dobry, tu dział inwestycji. Pana środki na platformie urosły do 48 000 zł, ale do wypłaty musi Pan najpierw opłacić podatek 6 000 zł przelewem na wskazane konto.", [("PROFIT_CLAIM", "urosły do 48 000 zł")]),
    ("scam", "I", "SO", "CRY", 1, "Straciłeś pieniądze na fałszywej platformie? Nasza kancelaria odzyska 100% Twoich środków z blockchaina. Płatność z góry, kontakt tylko przez Telegram.", [("GUARANTEED_PROFIT", "odzyska 100% Twoich środków"), ("OFF_PLATFORM_CONTACT", "kontakt tylko przez Telegram")]),
    ("scam", "I", "SO", "CRY", 1, "airdrop tylko dla pierwszych 500 osob!! podlacz portfel i odbierz tokeny warte 2000$ zanim skoncza sie miejsca", [("URGENCY_PRESSURE", "tylko dla pierwszych 500 osob"), ("UNREALISTIC_RETURNS", "tokeny warte 2000$")]),
    ("scam", "I", "SO", "NON", 1, "Inwestycja w złoto z gwarantowanym zwrotem 40% rocznie. Wpłacasz dziś, skup odkupi od Ciebie po wyższej cenie. Bez ryzyka, umowa notarialna gratis.", [("GUARANTEED_PROFIT", "gwarantowanym zwrotem"), ("UNREALISTIC_RETURNS", "40% rocznie"), ("NO_RISK_CLAIM", "Bez ryzyka")]),
    ("scam", "I", "SO", "CRY", 1, "pompujemy $MOONKA dziś o 20:00 czasu polskiego, kupujesz w sekundzie sygnału i trzymasz do x5. link do kanału w bio", [("SPECIFIC_INSTRUMENT_CALL", "kupujesz w sekundzie sygnału"), ("UNREALISTIC_RETURNS", "do x5"), ("OFF_PLATFORM_CONTACT", "link do kanału w bio")]),
    ("scam", "I", "SO", "CFD", 1, "Firma Vexorra posiada licencję KNF i gwarancję Unii Europejskiej. Twoje środki są w 100% chronione, a zyski wypłacamy codziennie.", [("SUPERVISOR_AS_SAFETY", "posiada licencję KNF"), ("NO_RISK_CLAIM", "w 100% chronione"), ("GUARANTEED_PROFIT", "zyski wypłacamy codziennie")]),
    ("scam", "I", "SO", "NON", 1, "Nie musisz nic umieć. Klub inwestorów płaci 2% tygodniowo, a za każdą poleconą osobę dostajesz dodatkowo 10% jej wpłaty.", [("UNREALISTIC_RETURNS", "2% tygodniowo")]),
    ("scam", "I", "SO", "CRY", 1, "Mama trójki dzieci z Radomia zarabia 15 tys. miesięcznie, nie wychodząc z domu. Rząd nie chce, żebyś poznał ten sposób. Zobacz, zanim usuną ten artykuł.", [("UNREALISTIC_RETURNS", "zarabia 15 tys. miesięcznie"), ("SECRECY_CONSPIRACY", "Rząd nie chce, żebyś poznał"), ("FAKE_NEWS_FORMAT", "zanim usuną ten artykuł")]),
    ("scam", "I", "SO", "CFD", 1, "wystarczy 200 zl na start a nasz doradca poprowadzi cie krok po kroku. pierwsza wyplata juz po 24h. zostaw telefon", [("LOW_ENTRY_DEPOSIT", "wystarczy 200 zl na start"), ("PROFIT_CLAIM", "pierwsza wyplata juz po 24h"), ("OFF_PLATFORM_CONTACT", "zostaw telefon")]),
    ("scam", "I", "SO", "CRY", 1, "Poznaliśmy się na portalu randkowym, a teraz chcę Ci pomóc. Mój wujek pracuje na giełdzie i zna kursy z wyprzedzeniem. Wpłać na tę aplikację, razem zarobimy 30% w tydzień.", [("UNREALISTIC_RETURNS", "30% w tydzień")]),
    ("scam", "I", "SO", "CFD", 1, "Opiekun konta: proszę zainstalować aplikację do zdalnego pulpitu, pomogę Panu wykonać pierwszą transakcję i dopłacić depozyt, żeby nie stracił Pan dzisiejszej okazji.", [("URGENCY_PRESSURE", "żeby nie stracił Pan dzisiejszej okazji")]),
    ("advisory", "I", "SO", "BND", 0, "Masz 200 tys. po sprzedaży mieszkania? Na spotkaniu rozpiszę Ci, które obligacje i fundusze kupić pod Twój wiek i cel. Honorarium 800 zł.", [("PERSONALIZED_ADVICE", "które obligacje i fundusze kupić pod Twój wiek i cel"), ("PAID_ADVISORY_SERVICE", "Honorarium 800 zł")]),
    ("advisory", "I", "SO", "STK", 0, "W newsletterze premium co tydzień wysyłam listę spółek do kupienia z ceną wejścia. Subskrypcja 79 zł miesięcznie.", [("PAID_ADVISORY_SERVICE", "newsletterze premium"), ("SPECIFIC_INSTRUMENT_CALL", "listę spółek do kupienia z ceną wejścia")]),
    ("advisory", "I", "OP", "CRY", 0, "ty masz 5k to nie pchaj wszystkiego w alty, daj 60% btc 30 eth a resztę trzymaj w stable, ja bym tak zrobił na twoim miejscu", [("PERSONALIZED_ADVICE", "ja bym tak zrobił na twoim miejscu")]),
    ("promo", "I", "TP", "CFD", 0, "Nie jestem doradcą, ale powiem tak: każdy kto chce zacząć, niech rejestruje się u Nordtradix przez mój kod TRADER7. Bez tego nawet nie zaczynajcie.", []),
    ("firm_bad", "I", "FM", "CFD", 0, "Altavesto Markets: inwestuj jak profesjonalista. Dźwignia do 1:500, bonus 100% od depozytu i wypłaty w 24 godziny.", [("LOW_ENTRY_DEPOSIT", "bonus 100% od depozytu")]),
    ("news", "I", "NE", "CFD", 0, "KNF dodała do listy ostrzeżeń publicznych kolejny podmiot oferujący handel CFD bez zezwolenia. Przed wpłatą warto sprawdzić firmę w rejestrze.", []),
    # szara strefa: agresywnie, ale nie oszustwo
    ("gray", "I", "SO", "CFD", 0, "Mój kurs price action za 997 zł. Nauczysz się czytać wykres. Ostatnie 10 miejsc w tej cenie, potem 1497 zł.", [("PAID_ADVISORY_SERVICE", "Mój kurs price action za 997 zł"), ("URGENCY_PRESSURE", "Ostatnie 10 miejsc")]),
    ("gray", "I", "OP", "CRY", 0, "Zrobiłem x4 na altcoinie w 2 miesiące, ale równie dobrze mogłem stracić wszystko. To był fart, nie strategia.", [("PAST_PERFORMANCE", "x4 na altcoinie w 2 miesiące"), ("RISK_WARNING", "mogłem stracić wszystko")]),
    ("gray", "I", "FM", "NON", 0, "Apartamenty inwestycyjne nad morzem. Prognozowany zwrot 7% rocznie z najmu, operator zajmuje się wszystkim. Wynik zależy od obłożenia i nie jest gwarantowany.", [("FORECAST", "Prognozowany zwrot 7% rocznie"), ("FORECAST_DISCLAIMER", "nie jest gwarantowany")]),
    ("gray", "I", "FM", "NON", 0, "Apartament pod wynajem w górach z gwarantowanym czynszem 6% przez 5 lat na podstawie umowy z operatorem. Ostatnie lokale w tej cenie.", [("GUARANTEED_PROFIT", "gwarantowanym czynszem 6%"), ("URGENCY_PRESSURE", "Ostatnie lokale w tej cenie")]),
    ("gray", "I", "FM", "CRY", 0, "Staking na Kryptolii: do 8% rocznie w ETH. Stawka może się zmieniać, a wartość kryptowalut może gwałtownie spaść.", [("PROFIT_CLAIM", "do 8% rocznie w ETH"), ("RISK_WARNING", "wartość kryptowalut może gwałtownie spaść")]),
    ("gray", "I", "SO", "CFD", 0, "Prop firm Altavesto: zdaj wyzwanie za 390 zł i handluj naszym kapitałem do 100 tys. dolarów. Większość uczestników nie przechodzi etapu oceny.", [("PAID_ADVISORY_SERVICE", "zdaj wyzwanie za 390 zł"), ("RISK_WARNING", "Większość uczestników nie przechodzi")]),
    ("gray", "I", "TP", "NON", 0, "Współpraca: pokazuję Wam projekt udziałowy winnicy. Można wejść od 5000 zł. To inwestycja niepłynna i można stracić całość.", [("AD_DISCLOSURE", "Współpraca"), ("LOW_ENTRY_DEPOSIT", "od 5000 zł"), ("RISK_WARNING", "można stracić całość")]),
    # finanse, ale nie inwestycje
    ("fin_other", "F", "NO", "", 0, "Lokata 6 miesięcy na 5,5% dla nowych klientów banku. Środki objęte gwarancją BFG do 100 tys. euro.", []),
    ("fin_other", "F", "NO", "", 0, "Jak spłacić kredyt hipoteczny szybciej? Nadpłata co miesiąc skraca okres spłaty i zmniejsza odsetki.", []),
    ("fin_other", "F", "NO", "", 0, "Chwilówka do 5000 zł w 15 minut, bez BIK! Sprawdź ofertę, pierwsza pożyczka za darmo.", []),
    ("fin_other", "F", "NO", "", 0, "Inflacja w październiku wyniosła 3,1% rok do roku. Najbardziej podrożała żywność i energia.", []),
    ("fin_other", "F", "NO", "", 0, "ile wam schodzi na zakupy miesięcznie? u nas we dwoje 1800 zł i mam wrażenie że to dużo", []),
    ("fin_other", "F", "NO", "", 0, "Ubezpieczenie na życie z gwarantowaną sumą 200 tys. zł. Składka od 39 zł miesięcznie.", []),
    # słowa-pułapki, nic o finansach
    ("trap", "N", "NO", "", 0, "Najlepsza inwestycja w życiu to zdrowie. Codzienny spacer i sen zwracają się z nawiązką.", []),
    ("trap", "N", "NO", "", 0, "Polacy zdobyli złoto w sztafecie! Co za finisz, gwarantowane ciarki.", []),
    ("trap", "N", "NO", "", 0, "Akcja ratunkowa w Tatrach trwała sześć godzin, turystę udało się bezpiecznie sprowadzić.", []),
    ("trap", "N", "NO", "", 0, "Bot w tej grze farmi złoto za mnie, a ja idę spać. Serwer i tak jest martwy.", []),
    ("trap", "N", "NO", "", 0, "Kurs tańca dla początkujących, ostatnie miejsca! Zapisz się dziś, pierwsza lekcja gratis.", []),
    ("trap", "N", "NO", "", 0, "Bitcoin, mój kot, znowu zrzucił doniczkę z parapetu. Zero ryzyka, że się czegoś nauczy.", []),
    ("trap", "N", "NO", "", 0, "Pralka ma 5 lat gwarancji i zwrot pieniędzy w 30 dni, jeśli nie będziesz zadowolony.", []),
]


def main() -> None:
    rows, errors = [], 0
    for n, (group, topic, ctype, instr, scam, text, flags) in enumerate(CASES, 1):
        hits = []
        for flag, quote in flags:
            start = text.find(quote)
            if flag not in FLAG_KEYS or start < 0:
                print(f"BŁĄD #{n} {flag}: {quote}")
                errors += 1
                continue
            hits.append({"flag": flag, "quote": quote, "start": start, "end": start + len(quote), "align_score": 1.0})
        label = {"rationale": f"przypadek graniczny: {group}", "topic": T[topic], "content_type": C[ctype],
                 "instruments": [K[x] for x in instr.split(",") if x] if topic == "I" else [], "is_scam": bool(scam),
                 "scam_confidence": "high" if scam else "low", "flags": hits, "entities": []}
        assert label["topic"] in TOPICS and label["content_type"] in CONTENT_TYPES
        assert all(i in INSTRUMENTS for i in label["instruments"])
        assert (topic == "I") == (ctype != "NO"), f"#{n}"
        rows.append({"doc": {"id": f"edge:{n:03d}", "source": "edge", "platform": "other", "kind": "post", "text": text,
                             "meta": {"synthetic": True, "edge_group": group}}, "label": label})
    if errors:
        raise SystemExit(f"{errors} błędnych cytatów")
    out = ML_DIR / "data/gold/edge_cases.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"{len(rows)} przypadków -> {out}")
    print("grupy:", dict(Counter(c[0] for c in CASES)))
    print("scam:", sum(c[4] for c in CASES), "| typy:", dict(Counter(c[2] for c in CASES)))
    print("flagi:", dict(Counter(f for c in CASES for f, _ in c[6])))


if __name__ == "__main__":
    main()
