using System.Collections.Concurrent;
using MassTransit;

namespace MassTransitTopicRouting;

// Wiadomość routowana po kluczu "<region>.<rodzaj>", np. "eu.temp" -> exchange typu TOPIC.
public record SensorReading(string Region, string Kind, double Value);

// Wiadomość routowana po kluczu = poziom ważności -> exchange typu DIRECT.
public record Alert(string Severity, string Text);

// Wspólny licznik: kto co dostał (do podsumowania na końcu scenariusza).
public static class Tally
{
    public static readonly ConcurrentDictionary<string, ConcurrentBag<string>> Received = new();

    public static void Add(string consumer, string what)
    {
        Received.GetOrAdd(consumer, _ => new ConcurrentBag<string>()).Add(what);
        Console.WriteLine($"  [{consumer,-15}] dostał {what}");
    }
}

// Wiązanie "eu.#" - wszystko z regionu eu (# = zero lub więcej słów).
public class EuConsumer : IConsumer<SensorReading>
{
    public Task Consume(ConsumeContext<SensorReading> c)
    {
        Tally.Add("eu-all", $"{c.Message.Region}.{c.Message.Kind}={c.Message.Value}");
        return Task.CompletedTask;
    }
}

// Wiązanie "*.temp" - temperatura z dowolnego regionu (* = dokładnie jedno słowo).
public class TempConsumer : IConsumer<SensorReading>
{
    public Task Consume(ConsumeContext<SensorReading> c)
    {
        Tally.Add("temp-anywhere", $"{c.Message.Region}.{c.Message.Kind}={c.Message.Value}");
        return Task.CompletedTask;
    }
}

// Wiązanie "#" - audyt, dostaje wszystko.
public class AuditConsumer : IConsumer<SensorReading>
{
    public Task Consume(ConsumeContext<SensorReading> c)
    {
        Tally.Add("audit", $"{c.Message.Region}.{c.Message.Kind}={c.Message.Value}");
        return Task.CompletedTask;
    }
}

// Konsument "naiwny": zostawiony na domyślnej topologii konsumpcji (ConfigureEndpoints),
// czyli bez własnego klucza wiązania. Eksperyment: czy cokolwiek dostanie z exchange'a topic?
public class NaiveConsumer : IConsumer<SensorReading>
{
    public Task Consume(ConsumeContext<SensorReading> c)
    {
        Tally.Add("naive-default", $"{c.Message.Region}.{c.Message.Kind}={c.Message.Value}");
        return Task.CompletedTask;
    }
}

// Direct: kolejka związana tylko z kluczem "critical".
public class CriticalAlertConsumer : IConsumer<Alert>
{
    public Task Consume(ConsumeContext<Alert> c)
    {
        Tally.Add("alerts-critical", $"{c.Message.Severity}: {c.Message.Text}");
        return Task.CompletedTask;
    }
}
