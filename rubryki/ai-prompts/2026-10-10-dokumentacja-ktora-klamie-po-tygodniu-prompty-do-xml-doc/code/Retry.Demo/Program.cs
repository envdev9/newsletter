// Wykonuje przykłady, które README i ADR podają jako fakty. Kod wyjścia != 0, gdy któryś się rozjedzie.
using Retry;

var failures = 0;
void Check(string name, bool ok)
{
    Console.WriteLine($"{(ok ? "OK  " : "FAIL")} {name}");
    if (!ok) failures++;
}

var b = TimeSpan.FromMilliseconds(100);
Check("Delay(1, 100ms) == 100ms", Backoff.Delay(1, b) == TimeSpan.FromMilliseconds(100));
Check("Delay(3, 100ms) == 400ms", Backoff.Delay(3, b) == TimeSpan.FromMilliseconds(400));
Check("Delay(6, 10s) obciete do MaxDelay (30s)", Backoff.Delay(6, TimeSpan.FromSeconds(10)) == Backoff.MaxDelay);
Check("MaxAttempts == 6", Backoff.MaxAttempts == 6);
Check("MaxDelay == 30s", Backoff.MaxDelay == TimeSpan.FromSeconds(30));

Check("IsTransient(500)", Backoff.IsTransient(500));
Check("IsTransient(503)", Backoff.IsTransient(503));
Check("IsTransient(599)", Backoff.IsTransient(599));
Check("IsTransient(429)", Backoff.IsTransient(429));
Check("!IsTransient(404)", !Backoff.IsTransient(404));
Check("!IsTransient(600)", !Backoff.IsTransient(600));

var threw = false;
try { Backoff.Delay(0, b); } catch (ArgumentOutOfRangeException) { threw = true; }
Check("Delay(0, ...) -> ArgumentOutOfRangeException", threw);

var slept = new List<TimeSpan>();
Task NoSleep(TimeSpan d, CancellationToken _) { slept.Add(d); return Task.CompletedTask; }

var calls = 0;
var result = await Backoff.RunAsync(n => { calls++; return n < 3 ? throw new InvalidOperationException() : Task.FromResult(n); }, b, NoSleep);
Check("RunAsync: sukces w 3. probie, 2 oczekiwania (100ms, 200ms)",
    result == 3 && calls == 3 && slept.Count == 2 && slept[0] == TimeSpan.FromMilliseconds(100) && slept[1] == TimeSpan.FromMilliseconds(200));

slept.Clear();
RetryExhaustedException? exhausted = null;
try { await Backoff.RunAsync<int>(_ => throw new InvalidOperationException("x"), b, NoSleep); }
catch (RetryExhaustedException ex) { exhausted = ex; }
Check("RunAsync: po 6 probach RetryExhaustedException(Attempts=6), 5 oczekiwan",
    exhausted is { Attempts: 6 } && slept.Count == 5);

threw = false;
try { await Backoff.RunAsync<int>(null!, b); } catch (ArgumentNullException) { threw = true; }
Check("RunAsync(null) -> ArgumentNullException", threw);

Console.WriteLine(failures == 0 ? "WSZYSTKO OK" : $"BLEDY: {failures}");
return failures == 0 ? 0 : 1;
