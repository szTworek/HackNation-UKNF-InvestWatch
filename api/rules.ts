import type { RuleDef } from '../frontend/src/api/types';

// 18 reguł z „ZASÓB DLA UCZESTNIKÓW – kryteria oceny informacji o ryzyku” + reguły modułów 1 i 3.
export const RULES: RuleDef[] = [
  {
    id: '1',
    name: 'Identyfikacja firmy',
    description: 'Sprawdza, czy materiał zawiera oficjalną nazwę firmy inwestycyjnej.',
    legalBasis: 'art. 44 ust. 2 lit. a rozporządzenia del. 2017/565',
    detectableByText: true,
    module: null,
  },
  {
    id: '2',
    name: 'Oznaczenie reklamy',
    description: 'Weryfikuje, czy materiał reklamowy/promocyjny jest jednoznacznie oznaczony jako taki.',
    legalBasis: 'art. 24 ust. 3 MiFID II',
    detectableByText: true,
    module: null,
  },
  {
    id: '3',
    name: 'Informacja o ryzyku',
    description:
      'Wykrywa twierdzenia o potencjalnych zyskach i sprawdza, czy bezpośrednio towarzyszy im informacja o istotnym ryzyku.',
    legalBasis: 'art. 44 ust. 2 lit. b rozporządzenia del. 2017/565',
    detectableByText: true,
    module: null,
  },
  {
    id: '4',
    name: 'Rozmiar czcionki ryzyka',
    description: 'Porównuje wielkość czcionki informacji o ryzyku z przeważającą wielkością czcionki materiału.',
    legalBasis: 'art. 44 ust. 2 lit. c rozporządzenia del. 2017/565',
    detectableByText: false,
    module: null,
  },
  {
    id: '5',
    name: 'Ekspozycja i kontrast ryzyka',
    description:
      'Analizuje umiejscowienie informacji o ryzyku pod kątem kontrastu, przesłonięcia przez inne elementy oraz czytelności.',
    legalBasis: 'art. 44 ust. 2 lit. c i e rozporządzenia del. 2017/565',
    detectableByText: false,
    module: null,
  },
  {
    id: '6',
    name: 'Zakrywanie / ukrywanie ryzyka',
    description: 'Wykrywa m.in. ryzyko ukryte w przypisach, sekcji „Legal”, lub w miejscach o niskiej widoczności.',
    legalBasis: 'art. 44 ust. 2 lit. e rozporządzenia del. 2017/565',
    detectableByText: true,
    module: null,
  },
  {
    id: '7',
    name: 'Dostępność za 1 kliknięciem',
    description:
      'Sprawdza, czy wyświetlanie informacji o ryzyku wymaga rozwinięcia, kliknięcia linku lub przejścia na inną warstwę.',
    legalBasis: 'art. 44 ust. 2 lit. b i e rozporządzenia del. 2017/565',
    detectableByText: false,
    module: null,
  },
  {
    id: '8',
    name: 'Responsywność (różne urządzenia)',
    description:
      'Symuluje wyświetlenie materiału na ekranach o różnych wielkościach i sprawdza, czy tekst nie jest ucinany lub skalowany poniżej czytelności.',
    legalBasis: 'art. 44 ust. 2 lit. g rozporządzenia del. 2017/565',
    detectableByText: false,
    module: null,
  },
  {
    id: '9',
    name: 'Zrozumiałość dla grupy docelowej',
    description:
      'Ocenia, czy ostrzeżenie o ryzyku jest przedstawione językiem zrozumiałym dla przeciętnego odbiorcy grupy docelowej.',
    legalBasis: 'art. 44 ust. 2 lit. d rozporządzenia del. 2017/565',
    detectableByText: true,
    module: null,
  },
  {
    id: '10',
    name: 'Spójność językowa',
    description: 'Weryfikuje, czy informacje o ryzyku nie są podane w innym języku niż główny przekaz materiału.',
    legalBasis: 'art. 44 ust. 2 lit. f rozporządzenia del. 2017/565',
    detectableByText: true,
    module: null,
  },
  {
    id: '11',
    name: 'Porównania produktów / usług',
    description:
      'Wykrywa porównania produktów i usług, weryfikuje źródło informacji, przyjęte założenia i flaguje naruszenia w raporcie.',
    legalBasis: 'art. 44 ust. 3 rozporządzenia del. 2017/565',
    detectableByText: true,
    module: null,
  },
  {
    id: '12a',
    name: 'Wyniki historyczne – okres i zakres',
    description:
      'Sprawdza, czy prezentowane wyniki historyczne obejmują okres ostatnich 5 lat, są oparte o pełne okresy 12-miesięczne oraz czy wskazano okres referencyjny i źródło.',
    legalBasis: 'art. 44 ust. 4 rozporządzenia del. 2017/565',
    detectableByText: true,
    module: null,
  },
  {
    id: '12b',
    name: 'Wyniki historyczne – warunki i waluta',
    description:
      'Weryfikuje, czy zawarto ostrzeżenie o wpływie zmian kursów walutowych oraz czy wskazano wpływ prowizji, opłat i obciążeń na wyniki.',
    legalBasis: 'art. 44 ust. 4 rozporządzenia del. 2017/565',
    detectableByText: true,
    module: null,
  },
  {
    id: '13',
    name: 'Dominacja wyników historycznych',
    description: 'Sprawdza, czy wyniki historyczne nie stanowią najbardziej wyeksponowanego elementu informacji.',
    legalBasis: 'art. 44 ust. 4 lit. a rozporządzenia del. 2017/565',
    detectableByText: true,
    module: null,
  },
  {
    id: '14',
    name: 'Ostrzeżenie przy wynikach historycznych',
    description:
      'Weryfikuje obecność wyraźnego zastrzeżenia, że wyniki historyczne nie stanowią wiarygodnego wskaźnika przyszłych wyników.',
    legalBasis: 'art. 44 ust. 4 lit. d rozporządzenia del. 2017/565',
    detectableByText: true,
    module: null,
  },
  {
    id: '15',
    name: 'Prognozy przyszłych wyników',
    description:
      'Rozpoznaje prognozy i sprawdza, czy zawarto wyraźne ostrzeżenie, że prognoza nie jest wiarygodnym wskaźnikiem przyszłych wyników.',
    legalBasis: 'art. 44 ust. 6 rozporządzenia del. 2017/565',
    detectableByText: true,
    module: null,
  },
  {
    id: '16',
    name: 'Informacja podatkowa',
    description:
      'Jeśli reklama odwołuje się do traktowania podatkowego, sprawdza obecność wyraźnej informacji o zależności od indywidualnej sytuacji klienta i możliwości zmian.',
    legalBasis: 'art. 44 ust. 7 rozporządzenia del. 2017/565',
    detectableByText: true,
    module: null,
  },
  {
    id: '17',
    name: 'Zakaz sugerowania aprobaty organu nadzoru',
    description:
      'Identyfikuje odwołania do KNF lub innego właściwego organu oraz sprawdza, czy są używane do sugerowania zatwierdzenia lub aprobaty produktu/usługi.',
    legalBasis: 'art. 44 ust. 8 rozporządzenia del. 2017/565',
    detectableByText: true,
    module: null,
  },
  {
    id: '18',
    name: 'Nadzór jako argument bezpieczeństwa',
    description:
      'Wykrywa odwołania do organu nadzoru, które mają sugerować bezpieczeństwo inwestycji, np. „spełniamy rygorystyczne wymogi nadzorcze KNF”.',
    legalBasis: 'art. 44 ust. 8 rozporządzenia del. 2017/565',
    detectableByText: true,
    module: null,
  },
  {
    id: 'M1_PROMO',
    name: 'Reklama firmy inwestycyjnej przez osobę trzecią',
    description:
      'Materiał osoby trzeciej promuje zarejestrowaną firmę inwestycyjną bez oznaczenia reklamy albo z obietnicą zysku bez informacji o ryzyku.',
    legalBasis: 'art. 24 ust. 3 MiFID II; art. 44 rozporządzenia del. 2017/565',
    detectableByText: true,
    module: 1,
  },
  {
    id: 'M3_ADVISORY',
    name: 'Doradztwo inwestycyjne bez zezwolenia',
    description:
      'Podmiot spoza rejestru KNF oferuje spersonalizowane rekomendacje dotyczące instrumentów finansowych.',
    legalBasis: 'art. 69 ust. 2 pkt 5 i art. 76 ustawy o obrocie instrumentami finansowymi',
    detectableByText: true,
    module: 3,
  },
];

export const VISUAL_RULES = new Set(['4', '5', '7', '8']);
