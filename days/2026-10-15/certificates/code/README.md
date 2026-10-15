# Kod do wydania #22 — Dowód spójności logu CT: jak monitor łapie log, który pokazuje dwie historie

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

Wymagania: **.NET 10 SDK** (sprawdzone na 10.0.400), `openssl` (sprawdzone na 3.0.2), Linux.
Opcjonalnie Python 3 (tylko stdlib) jako niezależny weryfikator.
**Bez sieci zewnętrznej i bez Dockera.**

> **Bezpieczeństwo:** klucz "logu CT" (ECDSA P-256) jest efemeryczny, w pamięci procesu. Na dysk (`work/`,
> ignorowane przez git) trafia tylko klucz **publiczny**, bajty STH, podpisy i `cases.json`. Żadnych sekretów.

## Fragment prasówki, którego dotyczy ten kod

> Podpis na STH mówi tylko "log to powiedział". Log, który podpisuje równolegle dwa różne drzewa tej samej
> wielkości, przechodzi każdą kontrolę podpisu. Chroni przed tym dowód spójności (RFC 6962 §2.1.2) i porównywanie
> STH między obserwatorami. Kod: generacja dowodu, weryfikacja iteracyjna (RFC 9162 §2.1.4.2), mutacje, split-view
> i prosty monitor jako maszyna stanów.

## Struktura

```
code/
├── dotnet/ConsistencyLab/   # Program.cs + csproj: drzewo Merkle, dowody, STH, monitor
├── verify_consistency.py    # niezależna weryfikacja (inny algorytm) na work/cases.json
└── work/                    # generowane (gitignored)
```

## Uruchomienie (każde polecenie osobno, z katalogu `code/`)

```bash
dotnet build dotnet/ConsistencyLab/ConsistencyLab.csproj -c Release
dotnet run --no-build -c Release --project dotnet/ConsistencyLab -- work
```

Program kończy się linią `niespelnione oczekiwania: 0` (kod wyjścia 0). Zmierzone: 4656/4656 par (m,n), 632692
mutacji → 0 przyjętych.

Kontrola niezależnymi narzędziami (po uruchomieniu programu):

```bash
python3 -I verify_consistency.py work/cases.json
openssl dgst -sha256 -verify work/log-pub.pem -signature work/sth25.sig work/sth25.bin
openssl dgst -sha256 -verify work/log-pub.pem -signature work/sth25.sig work/sth25-tampered.bin
```

Oczekiwane: Python — `przypadkow uczciwych zweryfikowanych: 325`, `bledy: 0`, fork odrzucony; pierwsze `openssl` —
`Verified OK`, drugie — `Verification failure`.

## Uwaga o środowisku

Żadnych skryptów `.sh`. Niezweryfikowane: prawdziwy log CT, protokół gossip (tylko reguła porównania STH), drzewa
większe niż 96 liści, Windows/macOS.
