# Przykłady (prawdziwe rekordy ze scrapera, listopad 2026)

Status: **propozycje Claude, czekają na weryfikację przez człowieka** (`ml/data/skill/zip_review.html`, `suspicious_review.html`). Po weryfikacji zostaw tylko potwierdzone. Teksty skrócone, nazwy firm zachowane, autorów prywatnych nie podajemy.

Format: wynik dla `M1 / M2 / M3` (resztę do 1 stanowi `NONE`; moduły się wykluczają), poziom ryzyka, reguły.

## M1: reklama przez osobę trzecią

**Poprawne M1** (TikTok, twórca)
> [współpraca z XTB] Złoto fizyczne czy ETC na złoto? … Materiał edukacyjny, nie stanowi rekomendacji inwestycyjnej. Inwestowanie jest ryzykowne. Inwestuj odpowiedzialnie.

`0,95 / 0,05 / 0,05`, LOW. Reguła 2 OK (oznaczenie), 3 OK.

**M1 z brakami** (YouTube, link polecający Trading 212)
> KLIKASZ W LINK NIŻEJ, zakładasz konto, wpłacasz 50 zł, czekasz… dostaniesz za free do 100$ w akcjach… ŁATWE 450 zł do przodu

`0,90 / 0,05 / 0,05`, HIGH. Reguła 2 VIOLATION (brak oznaczenia przy linku polecającym), 3 VIOLATION („łatwe 450 zł do przodu”).

**Serwis porównawczy** (Bing, „Digital money srl”)
> 2 Top Brokerzy Online 2026. Odkryj najlepsze Xtb. Porównaj top brokerów w Polsce teraz.

`0,75 / 0,05 / 0,05`, MEDIUM. Reguła 3 VIOLATION, ranking bez źródła (reguła 11 jako uwaga).

**Twórca bez oznaczenia** (TikTok)
> Sam rachunek maklerski, tak samo jak też IKE, mam założone w XTB. Bardzo prosta, przyjemna w użytkowaniu aplikacja… Po pierwsze, pobierasz sobie aplikację XTB.

`0,65 / 0,05 / 0,05`, MEDIUM, `needs_human`. Reguła 2 VIOLATION, jeśli to współpraca – z tekstu nie wiadomo.

## M2: marketing firmy

**Poprawne** (Bing, Plus500)
> Plus500™: Inwestowanie Online. 82% kont detalicznych CFD odnotowuje straty. Handel CFD: Akcje, Forex, Indeksami, Towarami.

`0,05 / 0,95 / 0,00`, LOW. Reguła 3 OK, 4–8 NOT_CHECKED.

**Zysk bez ryzyka** (Meta, XTB)
> W XTB nawet gdy czekasz na okazję inwestycyjną, Twoje pieniądze mogą pracować i zarabiać odsetki. 4.1% 3.9% 2.3%

`0,05 / 0,95 / 0,00`, HIGH, `needs_human` (ostrzeżenie mogło być na grafice). Reguła 3 VIOLATION.

**Porównanie i podatek** (Google, DM BOŚ)
> Najlepsze wg Inwestomatu – IKE czy IKZE? Czemu nie oba? Jeśli IKE, IKZE i ETF z GPW i zagranicy to DM BOŚ… Brak podatku od…

`0,05 / 0,90 / 0,00`, HIGH. Reguły 3, 11 (ranking, założenia nieopisane), 16 (podatek bez zastrzeżenia o sytuacji klienta) VIOLATION.

**Poprawna informacja podatkowa** (Google, DM BOŚ)
> ETF na IKE i IKZE bez prowizji na start. Inwestowanie jest ryzykowne. Zwolnienie podatkowe zależy od spełnienia warunków ustawowych. REKLAMA

`0,05 / 0,95 / 0,00`, LOW. Reguły 2, 3, 16 OK.

**Wyniki historyczne** (TikTok, XTB)
> Od Euro 2012 minęło już 14 lat, a Dow Jones wzrósł w tym czasie o blisko 300%! Historia pokazuje, jak ważne w inwestowaniu mogą być czas i cierpliwość

`0,05 / 0,90 / 0,00`, HIGH. Reguły 12a (brak pełnych okresów rocznych i źródła), 12b (indeks w USD, brak ostrzeżenia walutowego), 13 (wynik jako główny przekaz) VIOLATION.

**Strona produktu z ostrzeżeniem w stopce** (strona eToro, pomiary wizualne)
> eToro to wieloaktywowa platforma inwestycyjna… (ostrzeżenie CFD tylko w stopce na 1440/768/375 px)

`0,00 / 0,95 / 0,00`, MEDIUM. Reguła 6 VIOLATION z pomiarów.

## M3: usługi bez zezwolenia

**Podszycie i grupa z typami** (Meta, profil „XTB Społeczność”)
> W październiku opublikowaliśmy analizę interesującej okazji inwestycyjnej, gdy cena akcji wynosiła 10,09 zł… wzrost o 134,9%. W naszej społeczności regularnie dzielimy się analizami… Kliknij i dodaj nas na WhatsApp

`0,05 / 0,05 / 0,85`, CRITICAL. Nie M2: profil nie jest kontem XTB. Sygnały: podszycie, wynik jako wabik, kontakt na WhatsApp.

**Grupa z codziennymi typami** (Meta, ten sam profil)
> Odbierz listę wybranych akcji na WhatsApp. Codziennie analizujemy rynek i wybieramy spółki, które warto obserwować… Dołącz bezpłatnie

`0,00 / 0,05 / 0,80`, CRITICAL.

**Kurs i „challenge” – granica** (Bing, firma szkoleniowa)
> Poznaj podstawy tradingu Forex i strategię PSMD oraz zapisz się na nasz Challenge… Kup teraz. Zobacz, jaki bonus dajemy na start

`0,00 / 0,00 / 0,35`, MEDIUM, `needs_human`. Edukacja, chyba że obejmuje wskazywanie transakcji.

**Zarządzanie majątkiem przez licencjonowany bank** (Google, mBank)
> private banking: realizuj ambitne cele dzięki wsparciu w zarządzaniu majątkiem, otwórz konto

`0,00 / 0,85 / 0,05`, LOW. Autoryzowany podmiot: to M2, nie M3.

## Poza modułami

**Ostrzeżenie** (Meta, Bankier.pl)
> To nie Policja. To quishing… Policja nigdy nie zostawia wezwań do zapłaty w takiej formie

`0,00 / 0,00 / 0,00`, LOW.

**Gwarantowany zysk w krypto** (YouTube)
> Kopiując portfel tego deva masz gwarantowany zysk. GMGN SniperBot: https://…

`0,05 / 0,00 / 0,10`, MEDIUM. Kryptowaluty i boty spoza firm inwestycyjnych; sygnał ryzyka: gwarantowany zysk.

**Grupowe flipy nieruchomości** (Meta)
> Chcesz zarabiać ponad 100 tysięcy PLN w rok na flipach grupowych… zyskiwać do 50 tys. €

`0,00 / 0,00 / 0,10`, MEDIUM. Nieruchomości nie są instrumentem; sygnał: nierealna stopa zwrotu.

**Sponsor wydarzenia** (Bing)
> XTB KSW 123 – 21.11 Szczecin. Kup bilet.

`0,00 / 0,02 / 0,00`, LOW.

**Produkt bankowy** (Google, mBank)
> Twoje konto z bonusem 1000 zł i 5,3% na oszczędnościach w skali roku.

`0,00 / 0,03 / 0,00`, LOW.
