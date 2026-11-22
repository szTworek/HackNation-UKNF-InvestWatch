"""Taksonomia etykiet InvestWatch.

Jedno źródło prawdy dla: promptu nauczyciela (Bielik), treningu klasyfikatorów, API i frontendu
(polskie nazwy wyświetlane). Opisy są pisane pod prompt – zwięźle, z przykładami z social mediów.
"""

from __future__ import annotations

from dataclasses import dataclass

TOPICS: dict[str, str] = {
    "NON_FINANCIAL": "treść niezwiązana z finansami",
    "FINANCIAL_OTHER": (
        "finanse, ale nie inwestowanie: kredyty, konta i lokaty bankowe, ubezpieczenia, budżet domowy, "
        "podatki ogólnie, ceny, płace, ogólna gospodarka"
    ),
    "INVESTMENT": (
        "inwestowanie: akcje, obligacje, fundusze, ETF, CFD/forex, kryptowaluty, trading, "
        "oferty zarabiania na rynkach, usługi inwestycyjne"
    ),
}

CONTENT_TYPES: dict[str, str] = {
    "NONE": "wpisz, gdy topic nie jest INVESTMENT",
    "NEWS_EDU": (
        "informacja, edukacja, ogólna analiza rynku, ostrzeżenie przed oszustami; "
        "nie promuje konkretnej firmy ani produktu"
    ),
    "OPINION_DISCUSSION": "prywatna opinia, pytanie, dyskusja, relacja z własnych inwestycji",
    "FIRM_OWN_MARKETING": (
        "reklama publikowana przez samą firmę lub markę (broker, TFI, bank, giełda krypto, platforma) "
        "o jej własnych produktach lub usługach"
    ),
    "THIRD_PARTY_PROMO": (
        "osoba trzecia (influencer, twórca, strona) promuje firmę lub produkt inwestycyjny: współpraca, "
        "„partnerem odcinka jest”, link afiliacyjny, kod polecający, bonus za rejestrację"
    ),
    "RECOMMENDATION": (
        "rekomendacja kupna, sprzedaży lub trzymania konkretnego instrumentu skierowana do ogółu odbiorców"
    ),
    "SERVICE_OFFER": (
        "oferta usługi inwestycyjnej: doradztwo, konsultacje, zarządzanie portfelem lub majątkiem, "
        "sygnały tradingowe, płatna grupa, mentoring, „opiekun konta”, platforma inwestycyjna"
    ),
}

# Kolejność ważności dla nadzoru – używana przy łączeniu wyników z kilku fragmentów dokumentu.
CONTENT_TYPE_PRIORITY: list[str] = [
    "SERVICE_OFFER",
    "THIRD_PARTY_PROMO",
    "FIRM_OWN_MARKETING",
    "RECOMMENDATION",
    "OPINION_DISCUSSION",
    "NEWS_EDU",
    "NONE",
]
TOPIC_PRIORITY: list[str] = ["INVESTMENT", "FINANCIAL_OTHER", "NON_FINANCIAL"]

INSTRUMENTS: dict[str, str] = {
    "CFD_FOREX": "CFD, forex, waluty z dźwignią",
    "STOCKS": "akcje, spółki giełdowe",
    "FUNDS_ETF": "fundusze inwestycyjne, ETF, TFI, PPK/IKE/IKZE w funduszach",
    "BONDS": "obligacje (skarbowe, korporacyjne)",
    "CRYPTO": "kryptowaluty, tokeny, NFT",
    "OTHER_DERIVATIVES": "opcje, kontrakty terminowe, inne instrumenty pochodne",
    "NON_INSTRUMENT": "złoto fizyczne, nieruchomości, „projekty”, udziały w biznesie, lokaty",
}


@dataclass(frozen=True)
class Flag:
    key: str
    group: str  # compliance | advisory | scam
    rules: tuple[str, ...]  # id reguł UKNF (kryteria oceny) lub modułu
    name_pl: str
    definition: str


FLAGS: list[Flag] = [
    # --- zgodność informacji o ryzyku (moduł 2, częściowo 1) ---
    Flag("PROFIT_CLAIM", "compliance", ("3",), "Obietnica / twierdzenie o zysku",
         "twierdzenie o możliwych lub osiągniętych zyskach, stopie zwrotu, zarobku („zarabiaj”, „zysk 12% rocznie”)"),
    Flag("RISK_WARNING", "compliance", ("3", "6"), "Ostrzeżenie o ryzyku",
         "informacja o ryzyku lub możliwości straty pieniędzy, np. „X% rachunków inwestorów detalicznych traci "
         "pieniądze”, „możesz stracić część lub całość kapitału”; samo „to nie jest porada inwestycyjna” się NIE liczy"),
    Flag("AD_DISCLOSURE", "compliance", ("2",), "Oznaczenie reklamy / współpracy",
         "oznaczenie materiału jako reklama lub współpraca: „reklama”, „materiał sponsorowany”, „#ad”, "
         "„#współpraca”, „partnerem odcinka jest”, „link afiliacyjny”, „kod polecający”"),
    Flag("PAST_PERFORMANCE", "compliance", ("12a", "12b", "13"), "Wyniki historyczne",
         "prezentacja historycznych wyników produktu, funduszu lub strategii („fundusz zarobił 25% w 2023”)"),
    Flag("PAST_PERF_DISCLAIMER", "compliance", ("14",), "Zastrzeżenie przy wynikach historycznych",
         "zastrzeżenie, że wyniki historyczne nie gwarantują ani nie są wskaźnikiem przyszłych wyników"),
    Flag("FORECAST", "compliance", ("15",), "Prognoza wyników",
         "prognoza przyszłych cen lub wyników („BTC dojdzie do 200 tys.”, „zarobisz 15% w przyszłym roku”)"),
    Flag("FORECAST_DISCLAIMER", "compliance", ("15",), "Zastrzeżenie przy prognozie",
         "zastrzeżenie, że prognoza nie jest wiarygodnym wskaźnikiem przyszłych wyników"),
    Flag("TAX_CLAIM", "compliance", ("16",), "Odwołanie do podatków",
         "odwołanie do korzyści lub traktowania podatkowego („bez podatku Belki”, „ulga w IKZE”)"),
    Flag("PRODUCT_COMPARISON", "compliance", ("11",), "Porównanie produktów / usług",
         "porównanie z innymi produktami, usługami lub firmami („lepsze niż lokata”, „najniższe prowizje na rynku”)"),
    Flag("SUPERVISOR_AS_SAFETY", "compliance", ("17", "18"), "Nadzór KNF jako argument bezpieczeństwa",
         "odwołanie do KNF, nadzoru, licencji lub regulacji sugerujące bezpieczeństwo lub aprobatę produktu"),
    # --- doradztwo (moduł 3) ---
    Flag("PERSONALIZED_ADVICE", "advisory", ("M3",), "Porada dopasowana do klienta",
         "oferowanie lub udzielanie porady dopasowanej do sytuacji konkretnej osoby („dobiorę portfel do Twoich "
         "potrzeb”, „napisz ile masz, powiem w co wejść”)"),
    Flag("PAID_ADVISORY_SERVICE", "advisory", ("M3",), "Płatna usługa doradcza / zarządzania",
         "płatna usługa doradztwa, zarządzania portfelem lub majątkiem, sygnałów, grupy VIP, mentoringu "
         "(„konsultacje 1:1”, „zarządzam portfelami klientów”, „grupa premium z sygnałami”)"),
    Flag("SPECIFIC_INSTRUMENT_CALL", "advisory", ("M3",), "Wezwanie do kupna/sprzedaży instrumentu",
         "wezwanie do kupna, sprzedaży lub trzymania konkretnego instrumentu („kupujcie teraz akcje X”)"),
    # --- oszustwa ---
    Flag("GUARANTEED_PROFIT", "scam", ("SCAM",), "Gwarantowany zysk",
         "zapewnienie, że zysk jest pewny lub gwarantowany"),
    Flag("NO_RISK_CLAIM", "scam", ("SCAM",), "Twierdzenie o braku ryzyka",
         "twierdzenie, że inwestycja jest bez ryzyka, w 100% bezpieczna, że nie można stracić"),
    Flag("UNREALISTIC_RETURNS", "scam", ("SCAM",), "Nierealne stopy zwrotu",
         "obietnica nierealnie wysokich zysków (np. kilka % dziennie, kilkadziesiąt % miesięcznie, "
         "„z 1000 zł zrobisz 20 000 zł”)"),
    Flag("URGENCY_PRESSURE", "scam", ("SCAM",), "Presja czasu",
         "presja na szybką decyzję: „tylko dziś”, „ostatnie miejsca”, „oferta wygasa”"),
    Flag("CELEBRITY_OR_BRAND_ENDORSEMENT", "scam", ("SCAM",), "Rzekome poparcie znanej osoby / marki",
         "znana osoba, firma, bank lub instytucja rzekomo poleca inwestycję lub za nią stoi"),
    Flag("AUTOMATED_PROFIT", "scam", ("SCAM",), "Bot / AI zarabia za Ciebie",
         "bot, sztuczna inteligencja, algorytm lub platforma ma zarabiać automatycznie za użytkownika"),
    Flag("LOW_ENTRY_DEPOSIT", "scam", ("SCAM",), "Niska kwota startowa",
         "zachęta niską kwotą na start („zacznij od 250 USD”, „wystarczy 1000 zł”)"),
    Flag("OFF_PLATFORM_CONTACT", "scam", ("SCAM",), "Kontakt poza platformą",
         "przeniesienie kontaktu: „zostaw numer, konsultant oddzwoni”, WhatsApp, Telegram, „napisz na priv”"),
    Flag("SECRECY_CONSPIRACY", "scam", ("SCAM",), "Sekretna metoda / spisek",
         "„banki to ukrywają”, „rząd nie chce, żebyś wiedział”, sekretna metoda bogacenia się"),
    Flag("FAKE_NEWS_FORMAT", "scam", ("SCAM",), "Forma fałszywego artykułu / wywiadu",
         "treść udaje artykuł, wywiad lub materiał znanego medium („skandal na wizji”, „wywiad, który usunięto”)"),
]

FLAG_KEYS: list[str] = [f.key for f in FLAGS]
FLAGS_BY_KEY: dict[str, Flag] = {f.key: f for f in FLAGS}

ENTITY_ROLES: dict[str, str] = {
    "investment_firm": "firma lub marka finansowa: broker, dom maklerski, TFI, bank, giełda krypto, platforma inwestycyjna",
    "advertiser": "osoba lub konto promujące produkt lub firmę (influencer, autor reklamy)",
    "advisor": "osoba lub podmiot oferujący doradztwo, zarządzanie lub sygnały",
    "public_figure": "znana osoba wymieniona w treści (np. rzekomo polecająca inwestycję)",
    "other": "inny istotny podmiot",
}

SCAM_CONFIDENCE: list[str] = ["low", "medium", "high"]
