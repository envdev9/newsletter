# Kod do wydania #14 — MassTransit: wiadomość bez trasy (`mandatory`, alternate-exchange)

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Poniżej fragment artykułu + jak odpalić kod od zera.

Wymagania: **.NET 10 SDK**, **Docker** (obraz `rabbitmq:4.3-management`, ok. 150 MB).

## Fragment prasówki, którego dotyczy ten kod

> W #13 alert bez pasującego wiązania znikał bez śladu. Dziś dwa sposoby, żeby go nie
> stracić: flaga `mandatory` (nadawca dostaje `MessageReturnedException` z `312 NO_ROUTE`)
> oraz alternate-exchange (broker odkłada wiadomość do kosza, a konsument kosza widzi
> oryginalny klucz routingu). Zmierzone haczyki: licznik `publish_*` przestaje wykrywać
> zgubione wiadomości, `mandatory` nie działa gdy exchange ma AE, a dodanie AE do
> istniejącego exchange'a kończy się `precondition_failed` widocznym tylko w logu brokera.

## Struktura projektu

```
code/
├── .gitignore                            # pomija bin/, obj/
└── masstransit-unrouted-demo/
    ├── MassTransitUnroutedDemo.csproj    # MassTransit 8.5.10 + MassTransit.RabbitMQ 8.5.10
    ├── Contracts.cs                      # Alert, Notice, 3 konsumenci (w tym kosz)
    └── Program.cs                        # tryby: mandatory / run / mandatory-ae / inspect / ae-conflict
```

## Jak uruchomić od zera

### 1. Postaw RabbitMQ

```bash
docker run -d --name mt-unrouted-demo -p 5672:5672 -p 15672:15672 \
  -e RABBITMQ_DEFAULT_USER=newsletter_dev \
  -e RABBITMQ_DEFAULT_PASS=newsletter_dev_local_only \
  rabbitmq:4.3-management
docker exec mt-unrouted-demo rabbitmq-diagnostics -q ping
```

> ⚠️ `newsletter_dev` / `newsletter_dev_local_only` to dane **wyłącznie do demo** na lokalnym
> kontenerze. Nie używaj ich nigdzie indziej.

### 2. Zbuduj i uruchom (w tej kolejności, na świeżym brokerze)

```bash
dotnet build days/2026-10-07/masstransit/code/masstransit-unrouted-demo
dotnet run --no-build --project days/2026-10-07/masstransit/code/masstransit-unrouted-demo -- mandatory
dotnet run --no-build --project days/2026-10-07/masstransit/code/masstransit-unrouted-demo -- run
dotnet run --no-build --project days/2026-10-07/masstransit/code/masstransit-unrouted-demo -- mandatory-ae
# odczekaj ok. 8 s (statystyki REST API mają opóźnienie), potem:
dotnet run --no-build --project days/2026-10-07/masstransit/code/masstransit-unrouted-demo -- inspect
dotnet run --no-build --project days/2026-10-07/masstransit/code/masstransit-unrouted-demo -- ae-conflict
docker logs mt-unrouted-demo --tail 4          # tu widać precondition_failed z ae-conflict
docker exec mt-unrouted-demo rabbitmqctl list_exchanges name type arguments
```

Kolejność ma znaczenie: tryb `mandatory` nie deklaruje exchange'a `Notice`, a `run` deklaruje
go z argumentem AE. Uruchomienie `mandatory`/`run` w odwrotnych konfiguracjach na tym samym
brokerze skończy się konfliktem argumentów (to jest haczyk #3).

### 3. Posprzątaj (tylko własny kontener)

```bash
docker rm -f mt-unrouted-demo
```

## Zweryfikowany output

Pełny output wszystkich trybów jest w [`../ARTICLE.md`](../ARTICLE.md); to prawdziwe uruchomienie
na RabbitMQ `4.3-management`, .NET SDK 10.0.400, `dotnet build`: 0 Warning(s), 0 Error(s). Skrót:

```
mandatory=False  Publish zakonczony BEZ wyjatku
mandatory=True   MessageReturnedException / PublishReturnException: 312 NO_ROUTE
run:             alerts-critical 1, notices-critical 1, unrouted-sink 1
mandatory-ae:    Publish bez wyjatku, wiadomosc w koszu
ae-conflict:     TaskCanceledException (przyczyna precondition_failed tylko w docker logs)
```

Kontener po demie usunięty (`docker ps -a` pokazał potem tylko cudze kontenery).

Niezweryfikowane: narzut `mandatory`, `Send` + `mandatory`, AE przez policy, łańcuch AE,
exchange `headers`, klaster, TLS, `dotnet test` (brak testów w tym wydaniu).
