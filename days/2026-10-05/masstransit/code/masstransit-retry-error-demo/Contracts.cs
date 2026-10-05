using System.Collections.Concurrent;
using MassTransit;

namespace MassTransitRetryErrorDemo;

public static class Log
{
    private static readonly System.Diagnostics.Stopwatch Clock = System.Diagnostics.Stopwatch.StartNew();
    public static void Line(string text) => Console.WriteLine($"[{Clock.ElapsedMilliseconds,6} ms] {text}");
}

// --- Kontrakty wiadomości - zwykłe recordy, jak we wszystkich poprzednich wydaniach. ---
public record FlakyOperation(string Id, int FailUntilAttempt);
public record PermanentFailure(string Id);
public record KnownBadData(string Id);
// Typ, dla którego NIKT na endpointcie "flaky" nie ma konsumenta - używany TYLKO do wywołania
// prawdziwej kolejki `_skipped` (patrz scenariusz "orphan").
public record NobodyConsumesThis(string Id);

public class TransientGlitchException(string message) : Exception(message);
public class OrderRejectedException(string message) : Exception(message);
public class KnownBadDataException(string message) : Exception(message);

// --- Konsument 1: "flaky" - zawodzi PRZEJŚCIOWO (pierwsze N-1 prób), potem się udaje.
//     UseMessageRetry (Interval) łapie wyjątek i wywołuje Consume PONOWNIE - to filtr w pipeline
//     odbioru, NIE round-trip przez broker (dlatego zachowuje się identycznie na in-memory i na
//     RabbitMQ - różnica, którą dziś sprawdzamy, jest po stronie kolejek _error/_skipped, nie
//     mechanizmu samego retry). ---
public class FlakyConsumer : IConsumer<FlakyOperation>
{
    private static readonly ConcurrentDictionary<string, int> Attempts = new();

    public Task Consume(ConsumeContext<FlakyOperation> context)
    {
        var m = context.Message;
        var attempt = Attempts.AddOrUpdate(m.Id, 1, (_, v) => v + 1);

        if (attempt < m.FailUntilAttempt)
        {
            Log.Line($"[Flaky]          próba {attempt}/{m.FailUntilAttempt} dla {m.Id} - wyjątek PRZEJŚCIOWY, retry za chwilę");
            throw new TransientGlitchException($"Przejściowy błąd, próba {attempt}");
        }

        Log.Line($"[Flaky]          próba {attempt}/{m.FailUntilAttempt} dla {m.Id} - SUKCES, retry nie jest już potrzebny");
        return Task.CompletedTask;
    }
}

public class FlakyConsumerDefinition : ConsumerDefinition<FlakyConsumer>
{
    protected override void ConfigureConsumer(
        IReceiveEndpointConfigurator endpointConfigurator,
        IConsumerConfigurator<FlakyConsumer> consumerConfigurator,
        IRegistrationContext context)
    {
        // 3 próby odstępu 300 ms - wystarczy, żeby FailUntilAttempt=3 (2 porażki + 1 sukces) się udało.
        endpointConfigurator.UseMessageRetry(r => r.Interval(3, TimeSpan.FromMilliseconds(300)));
    }
}

// --- Konsument 2: "always failing" - błąd TRWAŁY, nigdy się nie uda. Po wyczerpaniu retry (2 próby
//     ponowienia = 3 próby łącznie) MassTransit: (a) publikuje Fault<PermanentFailure>, (b) PRZENOSI
//     oryginalną wiadomość do kolejki `<endpoint>_error` na BROKERZE - to jest kolejka realna,
//     trwała, i PRZEŻYWA zamknięcie tego procesu (sprawdzamy to w trybie `inspect` po `run fail`). ---
public class AlwaysFailingConsumer : IConsumer<PermanentFailure>
{
    private static int _attemptCount;

    public Task Consume(ConsumeContext<PermanentFailure> context)
    {
        var n = Interlocked.Increment(ref _attemptCount);
        Log.Line($"[AlwaysFailing]  próba {n} dla {context.Message.Id} - błąd TRWAŁY, nigdy się nie uda");
        throw new OrderRejectedException($"Zamówienie {context.Message.Id} trwale odrzucone");
    }
}

public class AlwaysFailingConsumerDefinition : ConsumerDefinition<AlwaysFailingConsumer>
{
    protected override void ConfigureConsumer(
        IReceiveEndpointConfigurator endpointConfigurator,
        IConsumerConfigurator<AlwaysFailingConsumer> consumerConfigurator,
        IRegistrationContext context)
    {
        // 2 ponowienia (3 próby łącznie), potem MassTransit uznaje wiadomość za ostatecznie faulted.
        endpointConfigurator.UseMessageRetry(r => r.Interval(2, TimeSpan.FromMilliseconds(200)));
    }
}

// --- Konsument 3: "skippable" - wyjątek znany i oznaczony jako NIEWARTY retry (Ignore<T>).
//     UWAGA, realny wynik zweryfikowany poniżej (sprostowanie względem pierwszego przypuszczenia
//     przy pisaniu tego kodu): Ignore<T> NIE wysyła wiadomości do `_skipped`. `_skipped` to zupełnie
//     inny mechanizm (patrz NobodyConsumesThis/"orphan" niżej) - Ignore<T> tylko WYŁĄCZA retry dla
//     tego wyjątku i NATYCHMIAST (bez czekania na kolejne próby) ląduje w `_error`, tak samo jak
//     błąd trwały z konsumenta 2. Różnica: 1 próba, nie 3. ---
public class SkippableConsumer : IConsumer<KnownBadData>
{
    public Task Consume(ConsumeContext<KnownBadData> context)
    {
        Log.Line($"[Skippable]      {context.Message.Id} - dane znane jako złe, retry nie ma sensu");
        throw new KnownBadDataException($"Dane {context.Message.Id} są znane jako złe");
    }
}

public class SkippableConsumerDefinition : ConsumerDefinition<SkippableConsumer>
{
    protected override void ConfigureConsumer(
        IReceiveEndpointConfigurator endpointConfigurator,
        IConsumerConfigurator<SkippableConsumer> consumerConfigurator,
        IRegistrationContext context)
    {
        endpointConfigurator.UseMessageRetry(r =>
        {
            r.Interval(2, TimeSpan.FromMilliseconds(200));  // ten limit NIE zadziała dla KnownBadDataException
            r.Ignore<KnownBadDataException>();               // ...bo Ignore<T> pomija retry całkowicie
        });
    }
}
