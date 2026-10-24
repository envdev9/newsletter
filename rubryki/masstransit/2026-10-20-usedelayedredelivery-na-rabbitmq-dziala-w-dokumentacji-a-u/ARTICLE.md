<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #27 — 20 października 2026

![MassTransit](https://img.shields.io/badge/MassTransit-FF6600?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-red?style=for-the-badge)
![Status](https://img.shields.io/badge/uruchomienie-ZWERYFIKOWANE_(z_haczykiem)-orange?style=for-the-badge)

## 📨 UseDelayedRedelivery na RabbitMQ: „działa w dokumentacji”, a u ciebie wisi 21 sekund

</div>

---

> **Uczciwie na wstępie.** Miałem pokazać `UseDelayedRedelivery` działające na prawdziwym brokerze.
> Nie pokażę, bo **nie udało mi się go uruchomić** - i to jest właśnie temat. Zmierzyłem za to,
> jak wygląda porażka (powtarzalnie, 2 przebiegi), czym jest jedyna zmierzona alternatywa
> (`Interval` retry) i ile kosztuje. Plugin `rabbitmq_delayed_message_exchange` próbowałem zdobyć,
> ale polecenie pobrania zostało odrzucone przez uprawnienia środowiska i nie obchodziłem tego.
> Wszystko poniżej: MassTransit + MassTransit.RabbitMQ 8.5.10, RabbitMQ `4.3-management` (Docker),
> .NET SDK 10.0.400, `dotnet build` 0 warnings / 0 errors.

## 🎯 Dlaczego to ważne

W wydaniu #2 (in-memory) `UseDelayedRedelivery` wyglądało na zwykłą linijkę konfiguracji. Na
RabbitMQ to **zależność od infrastruktury**: oficjalny obraz `rabbitmq:4.3-management` nie ma
wtyczki opóźnionych wiadomości (sprawdziłem `rabbitmq-plugins list -m` - lista bez `delayed`).
Kod się kompiluje, host startuje, pierwsze próby konsumenta wyglądają normalnie. Dopiero błędna
wiadomość odsłania problem - więc ten błąd ujawnia się **na produkcji, w najgorszym momencie**,
a nie przy starcie aplikacji.

## 🧩 1. Zestaw doświadczalny

Konsument `FlakyConsumer` na kolejce `delayed-demo-job`, `PrefetchCount=1`,
`ConcurrentMessageLimit=1` (jeden slot - widać, kto kogo blokuje). Dwie wiadomości: `job-1`
(pada do określonej próby) i `job-2` (zdrowa, publikowana zaraz za nią). Warianty:

| Wariant | Konfiguracja |
|---|---|
| `immediate` | `UseMessageRetry(Immediate(1))` - punkt odniesienia |
| `delayed` | `Immediate(1)` + `cfg.UseDelayedRedelivery(Intervals(3s, 6s))`, **bez** pluginu |
| `interval` | `UseMessageRetry(Interval(2, 3s))` - blokujące opóźnienie w pamięci |

## 🧯 2. Punkt odniesienia: immediate

```
variant=immediate interval=3s
[  1.3s] published job-1, job-2
[  1.3s] job-1 attempt #1 headers=[]
[  1.3s] job-1 attempt #2 headers=[]
[  1.6s] job-2 attempt #1 headers=[]
[ 31.3s] TIMEOUT (30s) - job nie zakonczony
[ 32.9s] host.StopAsync trwal 0.1s
```

Dwie próby w tej samej milisekundzie, job-1 ląduje w `_error` (potwierdziłem `ready=1` w
`delayed-demo-job_error` w pierwszym przebiegu), job-2 przechodzi po 0,3 s. Zdrowo i nudno.

## 🪤 3. Haczyk: `delayed` bez pluginu - 21 sekund ciszy

```
variant=delayed interval=3s
[  1.2s] published job-1, job-2
[  1.3s] job-1 attempt #1 headers=[]
[  1.3s] job-1 attempt #2 headers=[]
[ 22.5s] job-1 attempt #3 headers=[]
[ 22.5s] job-1 attempt #4 headers=[]
[ 31.2s] TIMEOUT (30s) - job nie zakonczony
[ 62.7s] host.StopAsync trwal 30.0s
```

Trzy rzeczy, które nie pasują do „opóźnione ponowienie po 3 s”:

1. **Brak opóźnienia 3 s.** Kolejne próby (#3, #4) przyszły po ~21 s, bez nagłówka
   `MT-Redelivery*`/`MT-Fault*` (drukowałem wszystkie nagłówki o tych prefiksach - puste).
2. **`job-2` w ogóle nie został przetworzony** przez 31 s - choć jest zdrowy. Przy
   `PrefetchCount=1` pechowa wiadomość trzyma jedyny slot (head-of-line blocking).
3. **Zamknięcie hosta trwa dokładnie 30,0 s** - tyle ile domyślny `HostOptions.ShutdownTimeout`
   Generic Hosta. Po ustawieniu go na 5 s: `host.StopAsync trwal 5.0s` (drugi przebieg
   z tym samym zachowaniem prób: #3/#4 po 22,6 s). Po zatrzymaniu w kolejce zostały **2 wiadomości**
   (`ready=2`, `consumers=0`) - nic nie zginęło, wróciły do kolejki.

Dlaczego? W logu brokera (`docker logs`) - jedyne źródło prawdy, bo klient przy poziomie
logów Critical milczy:

```
[error] Channel error on connection ... channel 2:
operation exchange.declare caused a channel exception precondition_failed: unknown exchange type 'x-delayed-message'
...
[error] Channel error on connection ... channel 3:
operation exchange.declare caused a channel exception precondition_failed: unknown exchange type 'x-delayed-message'
```

Dwa błędy w odstępie ~21 s (00:35:00 i 00:35:21 w drugim przebiegu) pasują do
momentów: start busa i pierwsza próba opóźnionego wysłania. Mechanizm domyślam się tak:
MassTransit próbuje zadeklarować exchange typu `x-delayed-message`, broker odrzuca, wysyłka
czeka na timeout, wiadomość wraca do kolejki i jest konsumowana od nowa. **To hipoteza zgodna z
pomiarami, nie wynik czytania kodu źródłowego** - nie sprawdzałem, skąd dokładnie bierze się
~21 s ani co robi MassTransit po nieudanej wysyłce.

Dodatkowo (z poprzednich wydań znany wzorzec `precondition_failed`): ten sam błąd klienta
jest widoczny w logu brokera, a nie w wyjątku z sensowną treścią. Kto nie czyta logów brokera,
zobaczy tylko „coś jest wolne”.

## ⏱️ 4. Zmierzona alternatywa: `Interval` retry - działa, ale płacisz slotem

```
variant=interval interval=3s
[  1.3s] published job-1, job-2
[  1.3s] job-1 attempt #1 headers=[]
[  4.3s] job-1 attempt #2 headers=[]
[  7.3s] job-1 attempt #3 headers=[]
[  7.3s] DONE
[  7.4s] job-2 attempt #1 headers=[]
```

Opóźnienia równe 3,0 s - zgodnie z konfiguracją. Ale `job-2` czekał **6 sekund** za pechową
wiadomością (1,3 s -> 7,4 s), bo `Interval` to uśpienie w pamięci wewnątrz konsumpcji:
wiadomość pozostaje nieprzyjęta (unacked), a slot zajęty. Przy `ConcurrentMessageLimit=1` jest
to najdobitniejsze, ale ta sama logika dotyczy każdego limitu - N wolnych wiadomości = N
zajętych slotów. To właśnie problem, który `UseDelayedRedelivery` ma rozwiązać (wiadomość
wraca do brokera na czas opóźnienia) - tyle że **nie zmierzyłem**, jak wygląda to zachowanie
na działającym pluginie, więc nie obiecuję liczb.

## 📊 Podsumowanie pomiarów

| Wariant | Przerwy między próbami | `job-2` przetworzony po | `StopAsync` |
|---|---|---|---|
| `immediate` | 0 s | 0,3 s | 0,1 s |
| `interval` (3 s) | 3,0 s | 6,1 s | (nie mierzone w tym przebiegu) |
| `delayed` bez pluginu | ~21 s (nie 3 s) | nie w 31 s | 30,0 s (5,0 s przy `ShutdownTimeout`=5 s) |

## ✅ Checklista przed `UseDelayedRedelivery` na RabbitMQ

- Sprawdź `rabbitmq-plugins list -m` i czy jest wtyczka opóźnionych wiadomości; w oficjalnym
  obrazie `4.3-management` jej nie ma (zmierzone).
- Dodaj test dymny „zła wiadomość -> kolejna próba po N sekund” do pipeline'u; nie ufaj
  startowi hosta.
- Obserwuj `docker logs`/logi brokera pod kątem `unknown exchange type`.
- Ustaw `HostOptions.ShutdownTimeout` świadomie: domyślne 30 s oznacza 30 s zwisu podczas
  rolling update, gdy konsumpcja utknęła.

## 🚧 Czego NIE zweryfikowałem

- **`UseDelayedRedelivery` z działającą wtyczką** - nie zainstalowałem jej (pobranie odrzucone
  przez uprawnienia, nie obchodziłem). Wariant `delayed-plugin` (`UseDelayedMessageScheduler()`) jest
  w kodzie i kompiluje się, ale **nie był uruchomiony**. Nie wiem, czy wtyczka w ogóle ma wersję
  zgodną z RabbitMQ 4.3.
- Źródła ~21 s (hipoteza powyżej), nagłówka `MT-Redelivery-Count` w ścieżce sukcesu.
- Czy `job-2` odblokowałby się przy poprawnym `UseDelayedRedelivery` (spodziewam się, że tak - nie mierzone).
- Każdy wariant uruchomiony raz (`delayed` dwa razy, ze spójnym wynikiem); to nie statystyka.
- Atomowy klucz idempotentności przy 2 workerach, `UseMessageRetry` + Courier, `ReviseItinerary`,
  `dotnet test`.

## ▶️ Następny krok

Kod: [`code/README.md`](code/README.md). Następny poziom: dostarczyć wtyczkę do kontenera (własny
obraz z dopisaną wtyczką) i zmierzyć `UseDelayedRedelivery` naprawdę; potem atomowy klucz
idempotentności przy dwóch workerach i `UseMessageRetry` + Courier.

---

<div align="center">

[← wszystkie artykuły: 📨 Messaging .NET z MassTransit](../README.md) · [spis rubryk](../../../README.md)

</div>
