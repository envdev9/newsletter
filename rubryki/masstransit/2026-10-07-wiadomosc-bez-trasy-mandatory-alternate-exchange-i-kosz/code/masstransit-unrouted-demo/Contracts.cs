using System.Collections.Concurrent;
using MassTransit;
using MassTransit.RabbitMqTransport;

namespace MassTransitUnrouted;

// Dwa typy z identyczną topologią direct, różnią się TYLKO tym, że Notice ma alternate-exchange.
public record Alert(string Severity, string Text);
public record Notice(string Severity, string Text);

public static class Tally
{
    public static readonly ConcurrentDictionary<string, ConcurrentBag<string>> Received = new();

    public static void Add(string who, string what) =>
        Received.GetOrAdd(who, _ => new ConcurrentBag<string>()).Add(what);
}

public class CriticalAlertConsumer : IConsumer<Alert>
{
    public Task Consume(ConsumeContext<Alert> context)
    {
        Tally.Add("alerts-critical", context.Message.Text);
        Console.WriteLine($"  [alerts-critical ] Alert  {context.Message.Severity}: {context.Message.Text}");
        return Task.CompletedTask;
    }
}

public class CriticalNoticeConsumer : IConsumer<Notice>
{
    public Task Consume(ConsumeContext<Notice> context)
    {
        Tally.Add("notices-critical", context.Message.Text);
        Console.WriteLine($"  [notices-critical] Notice {context.Message.Severity}: {context.Message.Text}");
        return Task.CompletedTask;
    }
}

// Konsument "kosza" podpiętego pod alternate-exchange. Czyta klucz routingu z RabbitMqBasicConsumeContext
// - to jest odpowiedź na pytanie z #13 "czy konsument widzi klucz routingu".
public class UnroutedNoticeConsumer : IConsumer<Notice>
{
    public Task Consume(ConsumeContext<Notice> context)
    {
        var key = context.TryGetPayload<RabbitMqBasicConsumeContext>(out var rmq) ? rmq.RoutingKey : "(brak payloadu)";
        Tally.Add("unrouted-sink", context.Message.Text);
        Console.WriteLine($"  [unrouted-sink   ] Notice {context.Message.Severity}: {context.Message.Text}  | oryginalny klucz routingu = '{key}'");
        return Task.CompletedTask;
    }
}
