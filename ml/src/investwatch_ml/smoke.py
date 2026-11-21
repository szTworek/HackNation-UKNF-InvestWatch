"""Fikcyjne przykłady do szybkiego sprawdzenia nauczyciela (nazwy firm i osób są zmyślone).

`expected` to oczekiwana etykieta – służy tylko do szybkiej kontroli sensowności promptu, nie do ewaluacji.
"""

from __future__ import annotations

from .schema import Doc

_SAMPLES: list[dict] = [
    {
        "id": "smoke-01-scam-celebrity",
        "platform": "facebook", "kind": "post", "author": "Wiadomości Dnia24",
        "text": (
            "SKANDAL NA WIZJI! 😱 Znany prezenter Tomasz Zieliński zdradził, jak zarabia 48 000 zł miesięcznie "
            "dzięki platformie QuantumProfit AI. Bank Centralny chciał zablokować ten wywiad! Sztuczna inteligencja "
            "handluje za Ciebie 24/7, zyski gwarantowane. Wystarczy wpłata 250 USD. Zostaw numer telefonu, "
            "nasz konsultant oddzwoni w ciągu 15 minut. Liczba miejsc ograniczona – rejestracja tylko do północy!"
        ),
        "expected": {"topic": "INVESTMENT", "content_type": "SERVICE_OFFER", "is_scam": True},
    },
    {
        "id": "smoke-02-legal-cfd-ad",
        "platform": "instagram", "kind": "post", "author": "Alfa Invest Dom Maklerski",
        "text": (
            "Handluj na ponad 5000 instrumentach z Alfa Invest DM S.A. 📈 Akcje, ETF i CFD w jednej aplikacji. "
            "Reklama. CFD są złożonymi instrumentami i wiążą się z dużym ryzykiem szybkiej utraty środków z powodu "
            "dźwigni finansowej. 74% rachunków inwestorów detalicznych odnotowuje straty w wyniku handlu CFD u tego "
            "dostawcy. Zastanów się, czy rozumiesz, jak działają CFD."
        ),
        "expected": {"topic": "INVESTMENT", "content_type": "FIRM_OWN_MARKETING", "is_scam": False},
    },
    {
        "id": "smoke-03-finfluencer-sponsor-asr",
        "platform": "youtube", "kind": "transcript", "author": "@inwestujzmarkiem",
        "title": "Jak zacząć inwestować mając 500 zł",
        "text": (
            "cześć witam was w kolejnym odcinku dzisiaj pogadamy o tym jak zacząć inwestować mając naprawdę małe "
            "kwoty ale zanim zaczniemy partnerem dzisiejszego odcinka jest broker beta markets u którego sam mam "
            "konto zero prowizji do stu tysięcy euro obrotu miesięcznie a z moim kodem marek100 dostajecie akcję "
            "za darmo link w opisie no i dobra wracając do tematu pierwsza rzecz to poduszka finansowa zanim "
            "wejdziecie w giełdę miejcie odłożone kilka pensji bo inwestycje to ryzyko i możecie stracić"
        ),
        "expected": {"topic": "INVESTMENT", "content_type": "THIRD_PARTY_PROMO", "is_scam": False},
    },
    {
        "id": "smoke-04-recommendation",
        "platform": "x", "kind": "post", "author": "@gieldowy_wilk",
        "text": (
            "Moim zdaniem Omega Games to teraz okazja dekady 🚀 Po premierze kurs pójdzie na 300 zł. Kupujcie póki "
            "tanio, ja dokładam do pozycji. #gpw #akcje"
        ),
        "expected": {"topic": "INVESTMENT", "content_type": "RECOMMENDATION", "is_scam": False},
    },
    {
        "id": "smoke-05-shadow-advisory",
        "platform": "facebook", "kind": "post", "author": "Kowalski Wealth Partners",
        "text": (
            "Masz oszczędności i nie wiesz, co z nimi zrobić? Jako niezależny doradca majątkowy przygotuję dla "
            "Ciebie indywidualny portfel akcji, obligacji i ETF dopasowany do Twojej sytuacji i celów. "
            "Konsultacja 1:1 online – 390 zł. Prowadzę też stałe zarządzanie portfelem dla klientów. "
            "Napisz wiadomość prywatną!"
        ),
        "expected": {"topic": "INVESTMENT", "content_type": "SERVICE_OFFER", "is_scam": False},
    },
    {
        "id": "smoke-06-scam-warning",
        "platform": "facebook", "kind": "post", "author": "Akademia Bezpiecznego Inwestowania",
        "text": (
            "⚠️ Uwaga na fałszywe reklamy! W sieci krążą wpisy z wizerunkiem znanych osób, które rzekomo zarabiają "
            "tysiące złotych dziennie na platformach z AI. To oszustwo. Żadna legalna inwestycja nie gwarantuje "
            "zysku. Sprawdzaj firmy na liście ostrzeżeń publicznych KNF i nie podawaj numeru telefonu nieznanym "
            "konsultantom."
        ),
        "expected": {"topic": "INVESTMENT", "content_type": "NEWS_EDU", "is_scam": False},
    },
    {
        "id": "smoke-07-non-financial",
        "platform": "instagram", "kind": "post", "author": "@kuchnia_ani",
        "text": "Niedzielny obiad gotowy 🍝 Makaron z pesto z czosnku niedźwiedziego, przepis w relacji! #obiad",
        "expected": {"topic": "NON_FINANCIAL", "content_type": "NONE", "is_scam": False},
    },
    {
        "id": "smoke-08-financial-other",
        "platform": "tiktok", "kind": "transcript", "author": "@kredytowa_mama",
        "text": (
            "słuchajcie porównałam oferty kredytów hipotecznych w trzech bankach i różnica w racie to prawie "
            "czterysta złotych miesięcznie więc naprawdę warto negocjować marżę i sprawdzić ubezpieczenie"
        ),
        "expected": {"topic": "FINANCIAL_OTHER", "content_type": "NONE", "is_scam": False},
    },
    {
        "id": "smoke-09-crypto-signals-vip",
        "platform": "tiktok", "kind": "transcript", "author": "@crypto_king_pl",
        "text": (
            "w zeszłym tygodniu moja grupa zrobiła trzysta procent na jednym coinie dołącz do mojej grupy vip na "
            "telegramie dostajesz sygnały kiedy kupić i kiedy sprzedać wejście tylko dziś za pół ceny ostatnie "
            "dziesięć miejsc link w bio"
        ),
        "expected": {"topic": "INVESTMENT", "content_type": "SERVICE_OFFER", "is_scam": True},
    },
    {
        "id": "smoke-10-fund-past-perf-knf",
        "platform": "facebook", "kind": "post", "author": "Gamma TFI",
        "text": (
            "Fundusz Gamma Akcji Polskich zarobił dla klientów 31,4% w 2024 roku! 🏆 Najlepszy wynik w swojej "
            "kategorii – lepiej niż lokata. Jesteśmy nadzorowani przez KNF, więc Twoje pieniądze są u nas w pełni "
            "bezpieczne. Wpłać w IKE i nie płać podatku Belki."
        ),
        "expected": {"topic": "INVESTMENT", "content_type": "FIRM_OWN_MARKETING", "is_scam": False},
    },
    {
        "id": "smoke-11-edu-etf",
        "platform": "youtube", "kind": "transcript", "author": "@finanse_bez_tajemnic",
        "title": "Czym jest ETF?",
        "text": (
            "etf to fundusz który odwzorowuje indeks na przykład s&p 500 kupując jedną jednostkę masz kawałek "
            "pięciuset spółek pamiętajcie że wartość może spadać i w krótkim terminie możecie być na minusie "
            "to nie jest rekomendacja tylko edukacja"
        ),
        "expected": {"topic": "INVESTMENT", "content_type": "NEWS_EDU", "is_scam": False},
    },
    {
        "id": "smoke-12-opinion",
        "platform": "reddit", "kind": "post", "author": "u/janek_1990",
        "title": "IKE na obligacjach czy na ETF?",
        "text": (
            "Mam 32 lata, odkładam 800 zł miesięcznie. Zastanawiam się czy IKE na obligacjach skarbowych "
            "czy jednak ETF na cały świat. Jak wy to rozwiązaliście?"
        ),
        "expected": {"topic": "INVESTMENT", "content_type": "OPINION_DISCUSSION", "is_scam": False},
    },
]


def smoke_docs() -> list[tuple[Doc, dict]]:
    out = []
    for s in _SAMPLES:
        s = dict(s)
        expected = s.pop("expected")
        out.append((Doc(source="smoke", **s), expected))
    return out
