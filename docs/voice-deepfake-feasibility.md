# Syntetyczny głos w wideo: wykonalność

## Werdykt

1. Da się dodać **słaby sygnał „możliwy syntetyczny głos”**, czyli score na każde 4 s audio z otwartego modelu NII MMS-300M AntiDeepfake. Działa na CPU w ok. 10 s na minutę audio. W naszym teście rozdzielił 10/10 próbek polskiego TTS (score ≥ 0,83) od 7/7 prawdziwych nagrań (≤ 0,07), z wyjątkiem 1 klipu o nieznanym statusie.
2. Werdyktu „to deepfake” **nie da się uczciwie wystawić**. Otwarte detektory na treściach z sieci z 2024 r. tracą średnio ok. 48% AUC. Muzyka w tle i nowe syntezatory (ElevenLabs, klonowanie głosu) obniżają score. Ten sygnał wspiera analityka i podnosi priorytet razem z kontekstem scamu. Nie jest dowodem.
3. Haczyk prawny: wagi NII mają licencję **CC BY-NC-SA 4.0** (tylko użycie niekomercyjne). Na hackathon i do pilota w UKNF (organ publiczny, bez sprzedaży) to raczej OK, ale trzeba to potwierdzić. Licencje Apache/MIT mają tylko słabsze modele.

Koszt wdrożenia w pipeline: **ok. 6–8 h** (sekcja 5).

## 1. Stan w repo (sprawdzone)

| Miejsce | Co jest |
|---|---|
| `C:\Users\szymo\Documents\projects\hacknation\inwestwatch\inwestwatch\ml\src\investwatch_ml\api.py:249-253` | `POST /enrich/media` to zaślepka: `{"active": false, ..., "syntheticVoice": null}`. Detektora nie ma. |
| `C:\Users\szymo\Documents\projects\hacknation\inwestwatch\inwestwatch\docs\backend-integration.md:121-128` | kontrakt `MediaAnalysis.syntheticVoice = {score, model, segments[{startS,endS,score}], experimental}` |
| `C:\Users\szymo\Documents\projects\hacknation\inwestwatch\inwestwatch\docs\backend-integration.md:188` | kolumna `synthetic_voice jsonb` |
| `C:\Users\szymo\Documents\projects\hacknation\inwestwatch\inwestwatch\docs\plan-model.md:53,78-80` | detektor zaplanowany jako „eksperymentalny, słaba cecha z niską wagą” |
| `C:\Users\szymo\Documents\projects\hacknation\inwestwatch\inwestwatch\docs\demo\03-model-i-funkcje-ai.md:96` | decyzja: usunąć losowy score i zwracać `null` |
| `C:\Users\szymo\Documents\projects\hacknation\inwestwatch\inwestwatch\frontend\src\api\types.ts:91` i `C:\Users\szymo\Documents\projects\hacknation\inwestwatch\inwestwatch\frontend\src\components\Enrichment.tsx:160-175` | UI gotowe: panel „Syntetyczny głos” z badge „Sygnał eksperymentalny – wymaga weryfikacji” i wykresem segmentów |

Wniosek: kontrakt i UI już są. Brakuje tylko implementacji w ai-service. Nic nie dublujemy.

## 2. Opcje

| Opcja | Dojrzałość | Licencja | Koszt | Polski | Słabe punkty |
|---|---|---|---|---|---|
| **NII MMS-300M AntiDeepfake** (wav2vec2/MMS + warstwa liniowa, 18 tys. h fake + 56 tys. h real) [HF](https://huggingface.co/nii-yamagishilab/mms-300m-anti-deepfake), [ONNX](https://huggingface.co/SpeechAntiSpoofingBenchmarks/MMS-300M-AntiDeepfake), [paper](https://arxiv.org/abs/2506.21090) | badawczy, 2025, EER 4,8% na In-the-Wild (wg Arena) | CC BY-NC-SA 4.0 | CPU ok. 10 s/min (zmierzone), 1,2 GB | backbone MMS jest wielojęzyczny, w treningu MLAAD (ma polski, [MLAAD](https://arxiv.org/abs/2401.09512)) | muzyka/drugi głos w tle, nowe TTS, brak danych o fałszywych alarmach na polskim YouTube |
| większe warianty NII (XLS-R-1B/2B, MMS-1B) | j.w. | CC BY-NC-SA 4.0 | GPU, 4–8 GB | j.w. | lepsze w benchmarkach, za ciężkie na CPU |
| HF „Deepfake-audio-detection-V2” (MelodyMachine, wav2vec2-base) [HF](https://huggingface.co/MelodyMachine/Deepfake-audio-detection-V2) | hobbystyczny, karta bez danych treningowych | Apache-2.0 | CPU ok. 6 s/min | brak | **w naszym teście bezużyteczny**: 0,00 na wszystkich próbkach TTS i 0,87–1,0 na prawdziwych |
| AASIST / RawNet2 (ASVspoof 2019) | klasyka, kod MIT | MIT | tani | brak | według Deepfake-Eval-2024 bliski losowości na danych z sieci ([arXiv 2503.02857](https://arxiv.org/abs/2503.02857)) |
| Watermark AudioSeal (Meta) [repo](https://github.com/facebookresearch/audioseal) | dojrzały | MIT (od 04.2024) | bardzo tani | nie dotyczy | wykrywa tylko znak wodny AudioSeal. Oszuści go nie używają, więc dla nas wynik ≈ zawsze 0 |
| Watermark i klasyfikator ElevenLabs [docs](https://elevenlabs.io/docs/product-guides/audio-tools/ai-speech-classifier) | produkcyjny | zamknięty, chmura | — | — | wykrywa tylko ElevenLabs, nie ma publicznego API detekcji, łamie zasadę on-prem. Najwyżej do ręcznego sprawdzenia przez analityka |
| Etykiety platform / C2PA (manifest pochodzenia treści) | YouTube i TikTok pokazują etykietę „AI” ([YT](https://support.google.com/youtube/answer/14328491), [TikTok](https://www.tiktok.com/transparency/en/supporting-responsible-transparent-ai-generated-content/)) | — | darmowe | — | w `info.json` z yt-dlp dla 7 naszych klipów nie ma takiego pola (sprawdzone). Oszust nie oznacza deepfake'a, a re-encode usuwa C2PA |
| Lip-sync (rozjazd ruchu ust i dźwięku): LipFD [repo](https://github.com/AaronComo/LipFD), LIPINC | kod badawczy | licencja nieokreślona | GPU, detekcja twarzy | niezależny od języka | wymaga twarzy w kadrze, brak licencji, kilka godzin integracji. Poza zakresem hackathonu |

## 3. Spektrum

| Status | Co |
|---|---|
| Wykonalne | score per 4 s z NII MMS-300M, `max` i `mean` na wideo. Wyświetlany jako „możliwy syntetyczny głos” i używany jako jedna cecha obok kontekstu scamu (celebryta + „platforma AI” + formularz telefonu). Typowy lektor TTS w spamie (Edge/Piper i podobne) wychodzi wyraźnie |
| Chwiejne | klonowany głos znanej osoby (ElevenLabs, XTTS), głos pod muzyką (separacja demucs pomaga częściowo, ale kosztuje ok. 52 s CPU na minutę), wideo, w którym prawdziwy głos przeplata się z syntetycznym, liczba fałszywych alarmów na polskim YouTube (nie mamy etykiet) |
| Niewykonalne do obrony | „ten głos jest deepfake'iem X”, wartości procentowe pewności przedstawiane jako dowód, wykrycie generatora, którego nie było w treningu |

Prezentacja i prawo: system **wspiera analityka**, a nie wydaje werdyktu. Score nie trafia do uzasadnienia naruszenia. Jest powodem, żeby człowiek odsłuchał nagranie. Tak samo traktuje to `plan-model.md:78-80`.

## 4. Test (prototyp `C:\Users\szymo\Documents\projects\hacknation\inwestwatch\inwestwatch\prototypes\voice_spoof\`)

Warunki: CPU i5-12500H, onnxruntime i torch w wersji CPU, okna 4 s, `p_fake` = softmax z logitu „fake”. Skrypt: `C:\Users\szymo\Documents\projects\hacknation\inwestwatch\inwestwatch\prototypes\voice_spoof\score.py`, wyniki: `C:\Users\szymo\Documents\projects\hacknation\inwestwatch\inwestwatch\prototypes\voice_spoof\results.json`. Prawdziwe klipy to pierwsze 60 s nagrania, pobrane przez yt-dlp z URL-i z `data/export/*/records.jsonl`. Próbki syntetyczne to ten sam polski tekst scamowy z Edge TTS (Marek, Zofia) i Piper (gosia, lokalny).

| Klip | Status | NII mean / max | MelodyMachine mean |
|---|---|---|---|
| YT LCp99VpLc-4 (Tomasz Pawlik) | człowiek | 0,001 / 0,003 | 0,07 |
| YT tYjoxXDk03Q (Perbon) | człowiek (zakładam) | 0,010 / 0,069 | 0,00 |
| YT _8MyZBguIdA (Najlepsze Pomysły Finansowe) | człowiek (zakładam) | 0,000 / 0,001 | 0,999 |
| TikTok xtbpl 7709134323953290518 | człowiek (zakładam) | 0,001 / 0,002 | 0,87 |
| TikTok mr_pankracy 7709950281424882966 | człowiek (zakładam) | 0,000 / 0,001 | 0,67 |
| TikTok kacper_snela 7709883447644359969 | człowiek (zakładam) | 0,000 / 0,001 | 0,00 |
| YT ya9Q0A8UB4U („XTB code”, kanał z kodami polecającymi) | **nieznany** | 0,13 / **0,97** (0–8 s), po demucs 0,36 / 0,99 | 0,00 |
| Edge Marek / Zofia (wav) | TTS | 0,996 / 0,992 | 0,00 |
| Edge Marek / Zofia → AAC 48 kbps | TTS | 0,997 / 0,974 | 0,00 |
| Edge Marek → Opus 24 kbps | TTS | 0,998 | 0,00 |
| Edge Marek → pasmo telefoniczne 8 kHz | TTS | 0,950 | 0,00 |
| Piper gosia (wav / AAC 48k) | TTS | 0,831 / 0,830 | 0,00 |
| Edge Marek + prawdziwy głos w tle (35%) | TTS + mowa | **0,19** / 0,75 | 0,00 |
| j.w. po separacji demucs | TTS + mowa | 0,12 / 0,45 | 0,01 |

Czas na minutę audio (CPU): NII 9–15 s, MelodyMachine 5–11 s, demucs ok. 52 s.

Co wynika (wniosek, nie pomiar):
- Kompresja platform (AAC, Opus, pasmo telefoniczne) prawie nie szkodzi NII. Szkodzi mu nakładanie się innego dźwięku.
- ya9Q0A8UB4U: pierwsze 8 s mają score 0,97. Po odcięciu tła rosną też inne segmenty (0,74 w 40–44 s). Może to być lektor TTS pod muzyką, ale tego nie wiem. Trzeba odsłuchać.
- Test jest mały: 7 klipów prawdziwych i łatwy TTS. Klonowania głosu (ElevenLabs/XTTS) nie testowałem, więc nie mamy danych o skuteczności na głównym wektorze ataku.
- MelodyMachine odpada. Nie bierzemy też modeli z HF tylko po licencji Apache bez testu.

## 5. Rekomendowany projekt

```
collector (yt-dlp, audio)              -> objectKey w MinIO
  -> ai-service POST /enrich/media      (kolejka, wolne)
       ffmpeg -> 16 kHz mono
       [opcja] demucs vocals, gdy wykryto muzykę (wyłączone w CPU baseline)
       NII MMS-300M ONNX, okna 4 s, max 5 min audio
       -> syntheticVoice
  -> /analyze: cecha `synthetic_voice_max` o niskiej wadze, tylko podnosi priorytet
  -> UI: istniejący panel Enrichment.tsx:160
```

Kształt (zgodny z `backend-integration.md:126`, dopisane 2 pola):

```jsonc
"syntheticVoice": {
  "score": 0.97,                 // max po segmentach
  "meanScore": 0.13,             // nowe
  "model": "nii-mms-300m-anti-deepfake@onnx",
  "segments": [ { "startS": 0, "endS": 4, "score": 0.97 }, { "startS": 4, "endS": 8, "score": 0.96 } ],
  "experimental": true,
  "confidenceNote": "Sygnał pomocniczy. Muzyka w tle i klonowanie głosu obniżają wykrywalność; nie jest dowodem."  // nowe
}
```

UI: badge „Możliwy syntetyczny głos” tylko wtedy, gdy `score ≥ 0.9` w ≥ 2 kolejnych segmentach (próg roboczy, do kalibracji). Pod badge stały dopisek z `confidenceNote` i wykres segmentów, który już istnieje. Na liście rekordów nie ma osobnego filtra „deepfake”.

Szacunek pracy:

| Krok | h |
|---|---|
| ONNX w obrazie ai-service (1,2 GB, onnxruntime CPU) + ffmpeg | 1,5 |
| `/enrich/media`: okna, score, segmenty | 2 |
| collector: pobranie audio do MinIO (yt-dlp `-x`, już używany) | 1–2 |
| cecha w `/analyze` + próg | 1 |
| UI: badge i próg (panel już jest) | 0,5 |
| ręczna kalibracja na ok. 30 naszych klipach | 1 |
| razem | **6–8** |

Opcjonalnie GPU (`compose.gpu.yaml`): `CUDAExecutionProvider` albo wariant XLS-R-1B. Demucs tylko na GPU.

Do decyzji: licencja CC BY-NC-SA wag NII (dopuszczalna w demo i pilocie UKNF? alternatywy z licencją permisywną w teście wypadły źle).
