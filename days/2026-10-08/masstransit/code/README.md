# Kod do wydania #15 — MassTransit: Courier w czterech krokach (kompensacja)

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md). Poniżej fragment artykułu + jak odpalić kod od zera.

Wymagania: **.NET 10 SDK**. Bez Dockera i brokera (transport in-memory).

## Fragment prasówki, którego dotyczy ten kod

> Routing slip z czterema aktywnościami (`ReserveInventory -> AuthorizePayment -> CreateShipment
> -> NotifyCustomer`). Zmienne slipa (`CompletedWithVariables`) przepływają do kolejnych
> aktywności po nazwie właściwości. Gdy krok 4 rzuca, kompensacja idzie w kolejności 3, 2, 1, a
> `RoutingSlipFaulted` przychodzi po ostatniej. Gdy kompensacja kroku 2 zwraca `context.Failed`,
> łańcuch się zatrzymuje (krok 1 nietknięty), a zamiast `Faulted` przychodzi
> `RoutingSlipCompensationFailed`. `CompensateContext` widzi tylko log, nie argumenty ani zmienne.

## Struktura projektu

```
code/
├── .gitignore                                  # pomija bin/, obj/
└── masstransit-courier-itinerary-demo/
    ├── MassTransitCourierItineraryDemo.csproj  # MassTransit 8.5.10
    ├── Contracts.cs                            # 4 aktywności, konsument zdarzeń slipa
    └── Program.cs                              # scenariusze: ok / fail / fail-comp
```

## Jak uruchomić od zera

```bash
dotnet build days/2026-10-08/masstransit/code/masstransit-courier-itinerary-demo
dotnet run --no-build --project days/2026-10-08/masstransit/code/masstransit-courier-itinerary-demo -- ok
dotnet run --no-build --project days/2026-10-08/masstransit/code/masstransit-courier-itinerary-demo -- fail
dotnet run --no-build --project days/2026-10-08/masstransit/code/masstransit-courier-itinerary-demo -- fail-comp
```

## Zweryfikowany output

Prawdziwe uruchomienie, .NET SDK 10.0.400, `dotnet build`: 0 Warning(s), 0 Error(s). Skrót:

```
ok:        4x ActivityCompleted -> RoutingSlipCompleted; kroki 2-4 widza reservationId=RES-ORD-1
fail:      COMPENSATE CreateShipment, AuthorizePayment, ReserveInventory (w tej kolejnosci) -> RoutingSlipFaulted
fail-comp: COMPENSATE CreateShipment ok, AuthorizePayment ZAWODZI -> RoutingSlipCompensationFailed (ReserveInventory nie skompensowany)
```

Pełny output w [`../ARTICLE.md`](../ARTICLE.md). Czasy (ms) różnią się między uruchomieniami.

Niezweryfikowane: RabbitMQ zamiast in-memory, `ReviseItinerary`, interakcja z `UseMessageRetry`,
warianty `RoutingSlipEvents` poza `All`, restart procesu w trakcie slipa, `dotnet test`.
