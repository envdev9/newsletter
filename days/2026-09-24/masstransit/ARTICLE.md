<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #1 — 24 września 2026

![MassTransit](https://img.shields.io/badge/MassTransit-FF6600?style=for-the-badge)

## Messaging w .NET z MassTransit: pierwszy Producer i Consumer bez Dockera

</div>

---

> _"Nie potrzebujesz RabbitMQ, żeby zrozumieć messaging. Potrzebujesz jednej klasy,
> jednego rekordu i piętnastu minut."_

Dziś zaczynamy nowy, comiesięczny wątek: **messaging w .NET z MassTransit**. Zero
Dockera, zero RabbitMQ - transport **in-memory**, żeby skupić się wyłącznie na
pojęciach, nie na infrastrukturze. Kod w [`code/`](code/) realnie się uruchamia i
publikuje komunikat, który konsument faktycznie odbiera - output niżej jest
skopiowany z prawdziwego uruchomienia, nie zmyślony.

---

## Problem, który MassTransit rozwiązuje

Wyobraź sobie typowy scenariusz: serwis A przyjmuje zamówienie i musi o tym
poinformować serwis B (wysyłka), serwis C (fakturowanie) i serwis D (powiadomienia
e-mail). Najprostsze podejście - serwis A woła bezpośrednio B, C i D przez HTTP -
działa, dopóki nie zapytasz: co jeśli D akurat nie odpowiada? Co jeśli chcesz dodać
serwis E za pół roku, bez dotykania A? Co jeśli B ma przetworzyć zamówienie dopiero
za 5 minut, bo akurat jest przeciążony?

To jest dokładnie problem, który rozwiązuje **messaging asynchroniczny**: zamiast A
wołać B/C/D bezpośrednio, A wysyła **komunikat** na wspólną "magistralę" (bus), a
B/C/D **subskrybują** to, co je interesuje. A nie wie, ilu jest odbiorców, ani czy są
akurat online. Dochodzi nowy odbiorca (E)? Dopisuje subskrypcję, A nic nie zmienia.

**MassTransit** to biblioteka .NET, która daje wspólne, ujednolicone API do tego typu
komunikacji - niezależnie od tego, czy pod spodem faktycznie stoi RabbitMQ, Azure
Service Bus, Amazon SQS, czy (jak dziś) zwykła kolejka w pamięci procesu. Uczysz się
API raz, transport dopinasz później.

---

## Cztery pojęcia, od których wszystko się zaczyna

### 1. Message (komunikat) - zwykły kontrakt danych

W MassTransit komunikat to **nie klasa ze specjalną bazą, nie DTO z adnotacjami** -
to zwykły typ .NET, najlepiej niemutowalny. Idealnie nadaje się do tego `record`:

```csharp
public record OrderPlaced(Guid OrderId, string CustomerName, decimal Amount);
```

To jedyna rzecz, którą **dzielą** ze sobą producent i konsument. Nie muszą znać
swojej implementacji nawzajem - muszą się tylko zgodzić co do kształtu `OrderPlaced`.
Ważny techniczny detal: typ komunikatu **musi mieć namespace** (MassTransit buduje z
niego nazwę kolejki/adresu) - gołego rekordu w globalnej przestrzeni nazw (np. prosto
w top-level `Program.cs`) nie da się użyć jako komunikatu.

### 2. Consumer - kto i jak reaguje

Consumer to klasa implementująca `IConsumer<T>` - jeden wymagany member, metoda
`Consume`:

```csharp
public class OrderPlacedConsumer : IConsumer<OrderPlaced>
{
    public Task Consume(ConsumeContext<OrderPlaced> context)
    {
        var msg = context.Message;
        Console.WriteLine($"Odebrano: zamówienie {msg.OrderId} od {msg.CustomerName}");
        return Task.CompletedTask;
    }
}
```

`ConsumeContext<T>` to "koperta" wokół Twojego komunikatu - oprócz samej treści
(`context.Message`) daje dostęp m.in. do nagłówków, informacji o nadawcy i - co
przyda się w kolejnych wydaniach tego wątku - możliwości odpowiedzi (`RespondAsync`)
czy ponownej publikacji.

### 3. Bus - magistrala, przez którą wszystko przechodzi

Bus (`IBus`) to obiekt reprezentujący całą infrastrukturę messagingu - połączenie z
transportem, zarejestrowanych konsumentów, kolejki. W typowej aplikacji .NET
rejestrujesz MassTransit raz, w kontenerze DI, i dostajesz `IBus` przez wstrzykiwanie
zależności:

```csharp
builder.Services.AddMassTransit(x =>
{
    x.AddConsumer<OrderPlacedConsumer>();

    x.UsingInMemory((context, cfg) =>
    {
        cfg.ConfigureEndpoints(context);
    });
});
```

`UsingInMemory` to dziś nasz transport - kolejka żyjąca wyłącznie w pamięci tego
jednego procesu, znika, gdy proces się kończy. Świetna do nauki i testów
jednostkowych/integracyjnych; w produkcji sięgniesz po `UsingRabbitMq` albo inny
prawdziwy transport (kolejne wydania tego wątku). `ConfigureEndpoints(context)`
automatycznie tworzy kolejkę dla każdego zarejestrowanego konsumenta - nie trzeba
ręcznie mapować typu komunikatu na nazwę kolejki.

### 4. `Publish` vs `Send` - różnica, którą trzeba zrozumieć od razu

To najczęstsze pierwsze pytanie i warto je rozstrzygnąć zanim napiszesz jakikolwiek
kod produkcyjny:

| | `Publish` | `Send` |
|---|---|---|
| Model | **Publish/Subscribe** (jeden-do-wielu) | **Point-to-point** (jeden-do-jednego) |
| Kto odbiera | Wszyscy subskrybenci danego typu komunikatu, ilu by ich nie było (0, 1, 5) | Dokładnie jeden, konkretny adresat pod znanym adresem |
| Semantyka | "Stało się coś" (event) - `OrderPlaced`, `PaymentReceived` | "Zrób coś" (command) - `ShipOrder`, `ChargeCard` |
| Nadawca wie o odbiorcy? | Nie - nadawca nie ma pojęcia, kto (i czy ktokolwiek) słucha | Tak - wysyła pod konkretny, znany adres/kolejkę |

W skrócie: **eventy się `Publish`-uje, komendy się `Send`-a**. `OrderPlaced` to
event ("zamówienie zostało złożone", fakt dokonany) - stąd w kodzie niżej używamy
`bus.Publish(order)`. Gdybyśmy chcieli **zlecić** konkretnej usłudze wysyłkowej
konkretne zadanie ("wyślij tę przesyłkę"), użylibyśmy `Send` do jej dedykowanej
kolejki. Pomylenie tych dwóch to najczęstszy błąd projektowy początkujących - `Send`
komendy do wielu odbiorców nie ma sensu (kto ją właściwie wykona?), a `Publish`
polecenia rozmywa odpowiedzialność (nikt nie wie, kto miał je obsłużyć).

---

## Kod: Producer + Consumer na transporcie in-memory

Pełny, samodzielny projekt konsolowy: [`code/masstransit-inmemory-demo/`](code/masstransit-inmemory-demo/).
Trzy pliki:

- `Messages.cs` - kontrakt `OrderPlaced` + `OrderPlacedConsumer`, oba w jawnym
  namespace `MassTransitInMemoryDemo` (wymóg opisany wyżej).
- `Program.cs` - buduje generic host, rejestruje MassTransit z transportem
  in-memory, publikuje jeden `OrderPlaced`, czeka chwilę, zatrzymuje bus i kończy
  proces.
- `MassTransitInMemoryDemo.csproj` - pakiet `MassTransit` w wersji **8.5.10**.

### Dlaczego akurat 8.5.10, nie najnowsza wersja

Najnowsza stabilna linia MassTransit to dziś `9.x`. Sprawdziłem to lokalnie: `9.2.2`
kompiluje się bez problemu, ale **odmawia startu busu** z wyjątkiem
`MassTransit.ConfigurationException: License must be specified with
SetLicense/SetLicenseLocation...`. MassTransit od wersji 9 wymaga skonfigurowania
licencji (darmowej dla małych zastosowań, ale trzeba ją jawnie ustawić) - to wykracza
poza zakres dzisiejszego "najprostszego możliwego startu". `8.5.10` to ostatnia
wersja z linii 8.x (Apache 2.0, bez wymogu licencji) i to jej używa kod w tym
wydaniu. Temat licencjonowania w MassTransit 9+ to dobry kandydat na osobne, przyszłe
wydanie tego wątku.

```csharp
// Program.cs (fragment - pełny plik w code/)
var builder = Host.CreateApplicationBuilder(args);

builder.Services.AddMassTransit(x =>
{
    x.AddConsumer<OrderPlacedConsumer>();

    x.UsingInMemory((context, cfg) =>
    {
        cfg.ConfigureEndpoints(context);
    });
});

using IHost host = builder.Build();
await host.StartAsync();

var bus = host.Services.GetRequiredService<IBus>();

var order = new OrderPlaced(Guid.NewGuid(), "Jan Kowalski", 149.99m);
await bus.Publish(order);

await Task.Delay(500);   // czas dla konsumenta na przetworzenie
await host.StopAsync();  // program kończy się sam, nie wisi w nieskończoność
```

### Zweryfikowany output (prawdziwe uruchomienie, nie zmyślony)

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

Proces kończy się sam z kodem wyjścia `0` (`echo $?` po uruchomieniu potwierdza to
lokalnie) - żadnego ręcznego Ctrl+C.

---

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md) - dokładne komendy od zera.

---

<div align="center">

[← wróć do wydania #1 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
