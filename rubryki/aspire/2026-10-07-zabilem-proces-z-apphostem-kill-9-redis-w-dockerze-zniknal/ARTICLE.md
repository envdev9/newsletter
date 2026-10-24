<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #14 — 7 października 2026

![.NET Aspire](https://img.shields.io/badge/.NET_Aspire-512BD4?style=for-the-badge)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-red?style=for-the-badge)

## Zabiłem proces z AppHostem `kill -9`. Redis w Dockerze zniknął po 12 sekundach — a potem zabiłem też siatkę bezpieczeństwa

</div>

---

> _"Dwa wydania temu napisaliśmy: 'wywalony test nie zostawia kontenera, ale twardego zabicia
> procesu nie testowaliśmy'. Dziś testujemy."_

W #13 sprawdziliśmy łagodną ścieżkę: test pada, `DisposeAsync` działa, kontener znika. Zostało
pytanie, które zadaje każdy, kto kiedykolwiek zobaczył w CI `Killed` albo `exit code 137`:
**co zostaje w Dockerze i w systemie, gdy proces hostujący AppHosta umiera bez żadnego
sprzątania?** Zmierzyliśmy to na prawdziwym AppHoście (Redis w kontenerze + `CacheApi`),
siedmioma sposobami umierania. Środowisko: Docker Engine `29.1.3`, Aspire `13.5.2`,
.NET SDK `10.0.400`, Linux.

**Dlaczego to ważne:** jeśli odpowiedź brzmi "zostają sieroty", to każdy przerwany build, OOM-kill
albo zatrzymany runner CI po cichu zaśmieca współdzieloną maszynę (porty, RAM, kontenery).
Jeśli brzmi "nie zostają" — warto wiedzieć, **dzięki czemu** i kiedy ta gwarancja przestaje działać.

---

### 1. Metoda: proces potomny, który umiera na zlecenie

Mały program `Orphan.Probe` działa w dwóch rolach. **Potomek** stawia prawdziwego AppHosta
(`DistributedApplicationTestingBuilder`, jak w #12/#13), czeka aż `cache-api` będzie zdrowe,
melduje `READY` i umiera w wybrany sposób. **Rodzic** robi migawkę kontenerów, sieci, woluminów
i procesów systemowych *przed* startem, a potem co 500 ms (do 90 s) mierzy, co jeszcze żyje:

| tryb | jak umiera potomek |
|---|---|
| `clean` | `StopAsync` + `DisposeAsync` (punkt odniesienia) |
| `exit` | `Environment.Exit(0)` — bez żadnego sprzątania |
| `crash` | `Environment.FailFast` (SIGABRT, kod 134) |
| `sigterm` / `sigint` | rodzic wysyła `kill -TERM` / `kill -INT` |
| `sigkill` | `kill -KILL` (kod 137) — procesu nie da się przechwycić |
| `sigkill-all` | `kill -KILL` hosta **i** wszystkich procesów `dcp*` naraz (o nich niżej) |

Sprzątanie po pomiarze dotyczy wyłącznie tego, co pojawiło się po starcie potomka.

### 2. Wynik #1: siedem sposobów umierania, jedna odpowiedź

Prawdziwy wynik jednego przebiegu (czasy liczone od "wyzwalacza": wysłania sygnału albo
chwili `READY`; w `clean` potomek sam wykonuje sprzątanie):

```
| tryb        | kod wyjścia | potomek kończy się po | kontener Redis znika po | procesy DCP/CacheApi znikają po |
|-------------|-------------|-----------------------|-------------------------|---------------------------------|
| clean       | 0           | 13.9 s                | 11.8 s                  | 14.9 s                          |
| exit        | 0           | 0.0 s                 | 12.7 s                  | 15.3 s                          |
| crash       | 134         | 0.0 s                 | 12.1 s                  | 15.2 s                          |
| sigterm     | (żyje)      | NIE (90 s)            | 12.4 s                  | 15.5 s                          |
| sigint      | (żyje)      | NIE (90 s)            | 12.2 s                  | 15.3 s                          |
| sigkill     | 137         | 0.7 s                 | 12.0 s                  | 15.1 s                          |
```

Co z tego wynika:

- **Nawet `kill -9` nie zostawia kontenera.** Redis znikał po ok. 12 s, a procesy `dcp`,
  `CacheApi` (i `dotnet`, który go hostuje) po ok. 15 s — **tak samo szybko jak przy czystym
  `DisposeAsync`**. Sieć Dockera `aspire-session-network-*` też znikała. Czas jest praktycznie
  identyczny we wszystkich sześciu trybach i w dwóch pełnych przebiegach z tą samą metryką (zakres
  11,6–14,0 s dla kontenera), więc to nie szczęście, tylko osobna ścieżka sprzątania.
- **Za sprzątanie po zabitym hoście odpowiada nie Twój kod, tylko DCP** — własny
  orkiestrator Aspire (procesy `dcp`, w których siedzi logika uruchamiania kontenerów
  i projektów). Przeżywa on śmierć hosta i sam dokańcza robotę. Zachowanie jest zmierzone;
  *jak dokładnie* DCP wykrywa śmierć rodzica — nie badaliśmy kodu źródłowego (patrz punkt 4,
  gdzie widać ślad).
- **`sigterm`/`sigint`: potomek nie wyszedł przez 90 s, a mimo to kontener zniknął po ok. 12 s.**
  Host Aspire przechwytuje te sygnały i zaczyna sprzątać zasoby, ale `Main` naszego probe'a stał
  na `Task.Delay(Timeout.Infinite)`, więc proces nie wrócił. Wniosek praktyczny: **sygnał
  uruchamia sprzątanie, ale nie gwarantuje, że Twój proces się zakończy** — w CI to różnica
  między "kontener posprzątany" a "job wisi do timeoutu". (Że za przechwycenie odpowiada
  standardowy `ConsoleLifetime` hosta .NET — to hipoteza, nie sprawdzałem.)
- **`crash` (SIGABRT) = `exit` = `sigkill`**: żaden z nich nie zostawił niczego po ~15 s.
- Woluminów Dockera przez cały eksperyment **nie przybyło** (ani jeden w żadnym z trybów) — to
  zamyka wątek "anonimowe woluminy Redisa" otwarty w #13, ale tylko dla tego obrazu i tej wersji.

### 3. Haczyk zmierzony #1: gwarancja jest sprzątaniem, nie natychmiastowym zwolnieniem

Po `kill -9` hosta zasoby żyją **jeszcze 12–15 s**. Jeśli skrypt CI zabija proces i od razu
startuje kolejny build, ten drugi widzi jeszcze stary kontener, zajętą sieć i porty. To okno
jest powtarzalne (ten sam rząd wielkości w każdym trybie), więc daj kolejnemu przebiegowi
bufor albo poczekaj na zniknięcie `docker ps --filter name=cache-`.

### 4. Haczyk zmierzony #2: zabij też siatkę bezpieczeństwa

Tryb `sigkill-all` zabija w jednym poleceniu `kill -KILL` hosta **i** procesy `dcp*` — czyli to,
co normalnie sprząta. Odzwierciedla np. zabicie całej grupy procesów lub cgroupy runnera.
Wynik z tego samego, siedmiotrybowego przebiegu:

```
| sigkill-all | 137 | 0.6 s | NIE (90 s) | NIE (90 s) |
  sieć zostaje: 1; sieroty: containerd-shim, sh, docker-proxy x2, redis-server, pickup, qmgr, dotnet, CacheApi
```

Teraz nic nie sprząta: **kontener `cache-*` żyje, sieć `aspire-session-network-*` żyje, a
`CacheApi` (z procesem `dotnet`) dalej działa jako sierota** — po 90 s nadal. Powtórzone trzy
razy (dwa przebiegi samego trybu i przebieg całościowy), identycznie. To scenariusz "twardego zabicia całości",
którego nie da się zrealizować z poziomu własnego kodu — tu nie ma kto posprzątać.

Najciekawsze: kontener ma w etykietach m.in. `com.microsoft.developer.usvc-dev.creatorProcessId`
i `...creatorProcessStartTime` (pełną listę kluczy wypisuje probe na stderr; wartości
pomijam). To mocny ślad, że DCP zapisuje, *kto* kontener utworzył, i potrafi później rozpoznać
sierotę. Że właśnie te etykiety są mechanizmem — to wniosek z nazw, nie zbadany fakt.

### 5. Haczyk zmierzony #3: następny AppHost sprząta sierotę po poprzednim — ale tylko kontener i sieć

Po `sigkill-all` probe odpala zwykły przebieg `clean` (nowa sesja AppHosta) i sprawdza stan
po jego zakończeniu:

```
| (po sigkill-all) następny AppHost clean | 0 | | sierota po nim: ZNIKNĘŁA | | sieć: znikła; procesy sieroty: dotnet(743516), CacheApi(743557) |
```

- Osierocony **kontener Redis zniknął** i **sieć zniknęła** — nowy DCP posprzątał pozostałość
  po starym (trzy przebiegi, ten sam efekt).
- **Procesy `dotnet`/`CacheApi` przeżyły** także po tym sprzątaniu. Kontenery i sieci mają
  etykiety, więc są "adresowalne"; zwykłego procesu .NET nikt nie rozpozna jako cudzego.
  Sprzątał je dopiero rodzic probe'a (`kill -KILL` tylko na pidach, które pojawiły się po starcie
  potomka).

**Wniosek:** po skrajnym zabiciu kontenery wyleczy następne uruchomienie Aspire, ale sieroty-
procesy `CacheApi` (zajęte porty, otwarte połączenia) zostają, dopóki ktoś ich nie zabije. Jeśli
na runnerze CI ginie cała cgroupa, problemem są **procesy**, nie kontenery. Co *nie* zostało
sprawdzone: czy sierota-`CacheApi` z zajętym stałym portem zablokowałaby następny start
(nasze porty są dynamiczne).

---

### Co dziś zostało na maszynie

Probe sprząta po sobie sam i tylko to, co pojawiło się po starcie potomka (kontenery, sieci,
woluminy, pidy). Po wszystkich przebiegach: `docker ps -a` pokazuje wyłącznie dwa cudze
kontenery sprzed testu, `docker network ls` — cztery sieci sprzed testu, brak procesów `dcp`,
`CacheApi`, `redis`. Woluminów nie przybyło (porównanie migawek w kodzie), jeden cudzy wolumin
anonimowy zniknął między moimi migawkami (nie moją ręką — probe usuwa tylko woluminy powstałe po
starcie potomka; prawdopodobnie inny proces na tej współdzielonej maszynie). Cudzych obrazów
i kontenerów nie ruszano.

### Czego dziś NIE sprawdziliśmy (uczciwie)

- **Dashboard Aspire** — nadal nieobejrzany wizualnie.
- **Windows/macOS i Podman** — tylko Linux + Docker Engine; mechanizm DCP może różnić się
  między platformami.
- **Dokładny mechanizm wykrywania śmierci rodzica przez DCP** (czytanie źródeł, `strace`) —
  wnioskujemy z zachowania i nazw etykiet.
- **Stałe porty** (`WithHostPort`) przy osieroconym `CacheApi`.
- **`WithLifetime(ContainerLifetime.Persistent)`** — kontener "trwały" ma być przeżywać hosta
  *z założenia*; nie mierzyliśmy tego trybu.
- **`SharedType.Keyed`**, `WithDataVolume` + EF Core migracje.
- Tylko jedna wersja każdego komponentu; czasy 12–15 s to ta maszyna, nie stała.

### Następny krok

`ContainerLifetime.Persistent` (kontener, który ma przeżyć hosta — jak go potem odnajduje i
sprząta DCP), `SharedType.Keyed`, `WithDataVolume` + EF Core migracje, dashboard.

---

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md). Wymaga działającego Dockera; cały przebieg trwa
ok. 6 minut.

---

<div align="center">

[← wydanie #14 (wszystkie rubryki)](../README.md) · [spis wydań](../../../README.md)

</div>
