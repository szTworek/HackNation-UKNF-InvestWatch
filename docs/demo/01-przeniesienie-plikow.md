# Etap 1: przeniesienie plików do jednego repo

**Cel:** cała dalsza praca odbywa się w `HackNation-UKNF-InvestWatch`, a stare repo `UKNF` zostaje tylko jako kopia zapasowa.
**Czas:** około 30 minut pracy, ale krok 3 wolno wykonać dopiero po zakończeniu automatu (około 2:30).
**Kolejność:** kroki 1 i 2 robimy przed etapami 2 i 3. Kroki 3–5 nie blokują tych etapów.

W poleceniach:

```bash
A="c:/Users/macie/Documents/GitHub/UKNF"
B="c:/Users/macie/Documents/GitHub/HackNation-UKNF-InvestWatch"
```

## Zasady

- **Kod w `B` jest nowszy i jest źródłem prawdy.** Nie kopiuj z `A` do `B` tych plików: `ml/src/investwatch_ml/api.py`, `heuristics.py`, `scoring.py`, `ml/Dockerfile`, `ml/.gitignore`, `compose*.yaml`, `deploy/*`, `.github/*`, `docs/deployment.md`.
- **Nie zatrzymuj procesów w `A`.** Działają tam etykietowanie, transkrypcja YouTube, tłumaczenie i automat treningu (`scripts/autopilot.sh`).
- **Niczego nie usuwaj z `A`** i nie rób commitów bez wyraźnej prośby.
- **Nie kopiuj ani nie wypisuj sekretów.** `B/.env` i `B/ml/.env` już istnieją i muszą pozostać poza gitem.
- `ml/data`, `ml/models` i `ml/logs` są ignorowane przez git i tak ma zostać.

## Stan różnic

| Co | Gdzie jest nowsze | Działanie |
|---|---|---|
| `ml/scripts/collect_m3.py` | tylko `A` | skopiować teraz |
| `ml/src/investwatch_ml/{ingest,knf}.py`, `knf_register.json` | tylko `B` | zostawić |
| `ml/scripts/build_knf_register.py` | tylko `B` | zostawić |
| `api.py`, `heuristics.py`, `scoring.py` | `B` | zostawić |
| `ml/data/{pool,silver,gold,review,raw}` | `A`, nadal rośnie | zsynchronizować po automacie |
| `ml/models`, `ml/models_candidate` | `A` | skopiować po automacie, opis w etapie 3 |
| `frontend/src` | identyczne | nic |
| `ml/data/audio_tmp`, `ml/logs` | `A` | nie kopiować |

## Krok 1: sprawdzenie stanu

```bash
cd "$B" && git status --short
git check-ignore ml/data/pool/x.jsonl ml/models/heads.joblib .env ml/.env
```

Wszystkie cztery ścieżki muszą być ignorowane. Jeśli nie są, przerwij i napraw `.gitignore`.

## Krok 2: brakujący kod

```bash
cp -n "$A/ml/scripts/collect_m3.py" "$B/ml/scripts/"
diff -rq "$A/ml/scripts" "$B/ml/scripts" | grep -v __pycache__
```

Po tym kroku `diff` może pokazać tylko `build_knf_register.py` jako plik obecny wyłącznie w `B`.

## Krok 3: dane, dopiero po automacie

Sprawdź, czy na końcu logu jest `koniec`, a trening nie zgłosił błędu:

```bash
tail -n 8 "$A/ml/logs/autopilot.log"
```

Następnie skopiuj dane, nadpisując tylko pliki starsze:

```bash
for d in pool silver gold review raw; do
  mkdir -p "$B/ml/data/$d"
  cp -ru "$A/ml/data/$d/." "$B/ml/data/$d/"
done
```

Jeśli etykietowanie albo transkrypcja nadal pracują, kopia będzie tylko migawką. Przed finalnym przeliczeniem demo powtórz tę pętlę.

Kontrola:

```bash
for f in pool/scraper.jsonl pool/m3_youtube.jsonl silver/teacher.jsonl gold/edge_cases.jsonl; do
  echo "$f A=$(wc -l < "$A/ml/data/$f") B=$(wc -l < "$B/ml/data/$f")"
done
```

## Krok 4: model

Skopiuj wyłącznie po udanym treningu:

```bash
grep -q "trening: exit 0" "$A/ml/logs/autopilot.log" && \
  mkdir -p "$B/ml/models" && cp -r "$A/ml/models/." "$B/ml/models/"
```

Jeśli trening się nie udał, użyj kandydata:

```bash
mkdir -p "$B/ml/models" && cp -r "$A/ml/models_candidate/." "$B/ml/models/"
```

## Krok 5: przełączenie pracy

- Od tego momentu nowe skrypty uruchamiamy z `B/ml`.
- Kolejne zbieranie i trening startują dopiero po zakończeniu procesów w `A`, żeby dwa labelery nie etykietowały tych samych danych.
- W `B/docs/opis-projektu.md` popraw status: rejestr KNF już istnieje (744 podmioty).

## Gotowe, gdy

- [ ] `collect_m3.py` jest w `B`, a pliki wymienione w zasadach nie zostały nadpisane.
- [ ] Liczby wierszy danych w `A` i `B` zgadzają się dla migawki.
- [ ] `B/ml/models` zawiera `heads.joblib`, `metrics.json` i `eval_set.json`.
- [ ] `git status` w `B` nie pokazuje danych, modeli ani sekretów.
