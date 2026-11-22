# 18 reguł oceny komunikacji marketingowej (M1, M2)

Podstawa: art. 44 rozporządzenia delegowanego 2017/565 i art. 24 ust. 3 MiFID II. Reguły stosuje się tylko do **komunikacji marketingowej** (reklama, strona produktu, sponsorowany materiał). Dla edukacji, newsów i prywatnych opinii wszystkie reguły mają `NOT_APPLICABLE`.

Statusy: `VIOLATION` (naruszenie do weryfikacji), `OK`, `NOT_APPLICABLE` (reguła nie dotyczy), `NOT_CHECKED` (brak danych do oceny).

| id | Reguła | Jak sprawdzić w tekście | Kiedy `NOT_CHECKED` |
|---|---|---|---|
| 1 | Identyfikacja firmy | Czy pada oficjalna nazwa firmy inwestycyjnej (np. „XTB S.A.”, „Dom Maklerski BOŚ S.A.”). Sama nazwa handlowa lub logo z OCR to słaby dowód. | – |
| 2 | Oznaczenie reklamy | Czy materiał jest oznaczony: „reklama”, „materiał sponsorowany”, „#współpraca”, „partnerem jest”, „link afiliacyjny”. Płatną reklamę z biblioteki reklam platforma oznacza sama, więc dla niej `NOT_CHECKED`. Dla influencera brak oznaczenia to `VIOLATION`. | płatna reklama z biblioteki reklam |
| 3 | Informacja o ryzyku | Gdy jest twierdzenie o zysku („zarabiaj”, „pozwól pieniądzom pracować”, „4,1% odsetek”, „zysk 12%”), musi mu bezpośrednio towarzyszyć informacja o istotnym ryzyku („możesz stracić część lub całość kapitału”, „X% rachunków CFD traci pieniądze”). Samo „inwestuj odpowiedzialnie” jest słabe. Brak twierdzenia o zysku → `NOT_APPLICABLE`. | – |
| 4 | Rozmiar czcionki ryzyka | Ostrzeżenie ≥ 80% przeważającej czcionki (`riskByViewport.disclaimer.font_ratio`). | brak pomiarów i zrzutu |
| 5 | Ekspozycja i kontrast | Kontrast ostrzeżenia ≥ 4,5:1 (`contrast_px`), nie na grafice, nie przesłonięte. | brak pomiarów i zrzutu |
| 6 | Ukrywanie ryzyka | Ostrzeżenie nie może być tylko w stopce, przypisie, sekcji „Legal” ani dopiero pod treściami o zyskach. | brak pomiarów i zrzutu |
| 7 | Dostępność za 1 kliknięciem | Ostrzeżenie widoczne bez rozwijania, klikania, przechodzenia dalej; obecne na każdej szerokości ekranu. | brak pomiarów i zrzutu |
| 8 | Responsywność | Na 1440/768/375 px tekst nie jest ucięty, nie wychodzi poza ekran, czcionka na telefonie ≥ 12 px. | brak pomiarów i zrzutu |
| 9 | Zrozumiałość | Ostrzeżenie prostym językiem dla grupy docelowej; żargon bez wyjaśnienia lub prawniczy blok tekstu to sygnał naruszenia. | – |
| 10 | Spójność językowa | Ostrzeżenie w tym samym języku co główny przekaz (polska reklama z ostrzeżeniem tylko po angielsku → `VIOLATION`). Angielskie przyciski CTA („Sign Up”) nie są naruszeniem. | – |
| 11 | Porównania | Porównania z innymi produktami lub firmami („najlepsze IKZE”, „najniższe spready na rynku”, „lepsze niż lokata”, rankingi) muszą mieć źródło i założenia. Brak źródła → `VIOLATION`. | – |
| 12a | Wyniki historyczne: okres | Wyniki obejmują ostatnie 5 lat (lub cały okres istnienia, jeśli krótszy), w pełnych okresach 12-miesięcznych, ze wskazaniem okresu i źródła. | brak wyników → `NOT_APPLICABLE` |
| 12b | Wyniki historyczne: waluta i koszty | Ostrzeżenie o wpływie kursu walut (np. indeks w USD dla polskiego klienta) i o wpływie prowizji i opłat. | jw. |
| 13 | Dominacja wyników | Wyniki historyczne nie mogą być najbardziej wyeksponowanym elementem (np. tytuł „+300% w 14 lat”). | jw. |
| 14 | Ostrzeżenie przy wynikach | Wyraźne zastrzeżenie, że wyniki historyczne nie są wiarygodnym wskaźnikiem przyszłych. | jw. |
| 15 | Prognozy | Prognoza („dojdzie do 200 tys.”, „zarobisz 15% w przyszłym roku”) wymaga zastrzeżenia, że nie jest wiarygodnym wskaźnikiem przyszłych wyników. Zgłaszaj każdą wykrytą prognozę. | brak prognozy → `NOT_APPLICABLE` |
| 16 | Informacja podatkowa | Odwołanie do podatków („bez podatku Belki”, „zwolnienie z 19% podatku” na IKE/IKZE, „zwrot podatku”) wymaga informacji, że traktowanie podatkowe zależy od indywidualnej sytuacji klienta i może się zmienić. | brak odwołania → `NOT_APPLICABLE` |
| 17 | Sugerowanie aprobaty organu | Odwołanie do KNF lub innego organu nie może sugerować, że zatwierdził produkt. | – |
| 18 | Nadzór jako argument bezpieczeństwa | „Jesteśmy nadzorowani przez KNF, więc twoje pieniądze są bezpieczne” → `VIOLATION`. Neutralna informacja o nadzorze z zastrzeżeniem, że nie gwarantuje wyniku, jest `OK`. | – |

## Reguły modułów

| id | Reguła | Jak sprawdzić |
|---|---|---|
| M1_PROMO | Reklama firmy przez osobę trzecią | Osoba trzecia promuje firmę inwestycyjną: czy jest oznaczenie współpracy (reguła 2) i informacja o ryzyku przy zyskach (reguła 3). Zgłoś też, jeśli promowany podmiot nie jest w rejestrze KNF. |
| M3_ADVISORY | Możliwe doradztwo bez zezwolenia | Spersonalizowana porada lub zarządzanie portfelem (akcje, obligacje, fundusze, ETF, CFD, pochodne) przez podmiot spoza rejestru KNF. Licencjonowany doradca z numerem wpisu → `OK`, ale do weryfikacji. |
| M3_RECOMMENDATION | Rekomendacja do weryfikacji | Wezwanie do kupna/sprzedaży konkretnego instrumentu skierowane do ogółu. Prywatna relacja z własnej transakcji się nie liczy. Status zawsze `NOT_CHECKED` (do weryfikacji), nie `VIOLATION`. |

## Zasady dowodów

- Cytat to dosłowny fragment rekordu, najkrócej jak się da (zwykle 3–15 słów).
- Brak czegoś (np. brak ostrzeżenia) opisz w `comment`, a jako `quote` podaj twierdzenie, które wymaga ostrzeżenia.
- Jeśli materiał jest ucięty (np. tekst reklamy z biblioteki Mety bez grafiki), napisz to w `comment` i ustaw `needs_human: true`.
