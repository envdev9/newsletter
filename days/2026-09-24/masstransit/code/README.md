# Kod do wydania #1 — Messaging .NET z MassTransit (in-memory)

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Poniżej ten sam kod + jak go odpalić.

Wymagania: **.NET 10 SDK** (`dotnet --version` → `10.x`). Jeśli SDK jest w
`~/.dotnet`, dodaj je do PATH: `export PATH="$HOME/.dotnet:$PATH"`.

## Fragment prasówki, którego dotyczy ten kod

> `Message` to zwykły, niemutowalny `record`, który dzielą ze sobą Producer i
> Consumer - żadnej wspólnej klasy bazowej, żadnego "serwisu". `Consumer` to klasa
> implementująca `IConsumer<T>` z jedną metodą `Consume`. `Bus` (`IBus`) to
> magistrala spinająca całość - dziś na transporcie `UsingInMemory`, bez RabbitMQ i
> bez Dockera. `Publish` wysyła event do wszystkich subskrybentów (0, 1 albo więcej),
> `Send` wysyła komendę do jednego, konkretnego adresata - eventy się publikuje,
> komendy się wysyła.
>
> MassTransit `9.x` wymaga skonfigurowania licencji przy starcie busu (nawet
> darmowej) - to wykracza poza zakres "najprostszego możliwego startu", więc ten
> projekt używa ostatniej wersji linii 8.x, `8.5.10` (Apache 2.0, bez wymogu
> licencji).

## Struktura projektu

```
masstransit-inmemory-demo/
├── MassTransitInMemoryDemo.csproj   # PackageReference MassTransit 8.5.10
├── Messages.cs                      # record OrderPlaced + OrderPlacedConsumer
└── Program.cs                       # host, rejestracja MassTransit, Publish
```

## Jak uruchomić od zera

```bash
export PATH="$HOME/.dotnet:$PATH"
cd masstransit-inmemory-demo
dotnet restore
dotnet build
dotnet run
```

## Zweryfikowany output (prawdziwe uruchomienie)

```
info: MassTransit[0]
      Configured endpoint OrderPlaced, Consumer: MassTransitInMemoryDemo.OrderPlacedConsumer
info: Microsoft.Hosting.Lifetime[0]
      Application started. Press Ctrl+C to shut down.
Publikuję: zamówienie d65f6a31-d43f-4951-a567-23636bdb54b7 od Jan Kowalski...
info: MassTransit[0]
      Bus started: loopback://localhost/
info: MassTransitInMemoryDemo.OrderPlacedConsumer[0]
      Odebrano: zamówienie d65f6a31-d43f-4951-a567-23636bdb54b7 od Jan Kowalski na kwotę 149.99 zł
Odebrano: zamówienie d65f6a31-d43f-4951-a567-23636bdb54b7 od Jan Kowalski na kwotę 149.99 zł
info: MassTransit[0]
      Bus stopped: loopback://localhost/
Bus zatrzymany, koniec programu.
```

Program kończy się sam (bez Ctrl+C), kod wyjścia `0` - `Publish` wysyła
`OrderPlaced`, `OrderPlacedConsumer` go odbiera i wypisuje na konsolę, po 500 ms bus
jest zatrzymywany (`host.StopAsync()`) i proces kończy działanie.

Sprawdzone lokalnie na `.NET SDK 10.0.400`, pakiet `MassTransit 8.5.10`, przed
publikacją.

### Uwaga o wersji MassTransit

Najpierw wypróbowano najnowszą stabilną `9.2.2` - kompiluje się, ale start busu
kończy się `MassTransit.ConfigurationException: License must be specified with
SetLicense/SetLicenseLocation...` (MassTransit 9+ wymaga jawnej konfiguracji
licencji, nawet darmowej). Żeby zostać przy "zero Dockera, zero dodatkowej
konfiguracji" na start, projekt używa ostatniej wersji linii 8.x: `8.5.10`.
