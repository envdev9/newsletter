using System.Buffers;
using System.Diagnostics;
using System.IO.Pipelines;
using System.Text;
using System.Text.Json;

// Tryb pomiaru pamieci (osobny proces, zeby PeakWorkingSet64 nie mieszal przebiegow):
//   dotnet run -c Release -- stream    albo    dotnet run -c Release -- list
if (args.Length == 1 && args[0] is "stream" or "list")
{
    await PomiarPamieci(args[0]);
    return;
}

// Pomocnik: wpisuje do Pipe kolejne kawalki (symulacja pakietow z sieci), kazdy z Flush.
static async Task Wpisz(PipeWriter w, string[] kawalki, bool zamknij = true, int opoznienieMs = 0)
{
    foreach (var k in kawalki)
    {
        await w.WriteAsync(Encoding.UTF8.GetBytes(k));   // WriteAsync = write + flush
        if (opoznienieMs > 0) await Task.Delay(opoznienieMs);
    }
    if (zamknij) await w.CompleteAsync();
}

// ---------------------------------------------------------------- 1
Console.WriteLine("--- 1. DeserializeAsync<T>(PipeReader): obiekt skladany z kawalkow ---");
{
    var pipe = new Pipe();
    string[] kawalki = ["{\"Id\":7,\"Naz", "wa\":\"Gdan", "sk\",\"Tagi\":[\"a\",", "\"b\"]}"];
    var producent = Wpisz(pipe.Writer, kawalki, opoznienieMs: 20);
    var zam = await JsonSerializer.DeserializeAsync<Zamowienie>(pipe.Reader);
    await producent;
    Console.WriteLine($"wynik: Id={zam!.Id} Nazwa={zam.Nazwa} Tagi=[{string.Join(",", zam.Tagi)}]");
}

// ---------------------------------------------------------------- 2
Console.WriteLine("--- 2. DeserializeAsyncEnumerable<T>(PipeReader): top-level tablica, element po elemencie ---");
{
    var pipe = new Pipe();
    string[] kawalki = ["[{\"Id\":1,\"Nazwa\":\"a\",\"Tagi\":[]},{\"Id\":", "2,\"Nazwa\":\"b\",\"Tagi\":[]}", ",{\"Id\":3,\"Nazwa\":\"c\",\"Tagi\":[]}]"];
    var producent = Wpisz(pipe.Writer, kawalki, opoznienieMs: 50);
    var sw = Stopwatch.StartNew();
    await foreach (var z in JsonSerializer.DeserializeAsyncEnumerable<Zamowienie>(pipe.Reader))
        Console.WriteLine($"  po ~{(sw.ElapsedMilliseconds / 50) * 50,3} ms: Id={z!.Id} ({z.Nazwa})");
    await producent;
}

// ---------------------------------------------------------------- 3
Console.WriteLine("--- 3. Haczyk: DeserializeAsync czeka na koniec strumienia, nie na koniec obiektu ---");
{
    var pipe = new Pipe();
    var zadanie = JsonSerializer.DeserializeAsync<Zamowienie>(pipe.Reader).AsTask();
    await Wpisz(pipe.Writer, ["{\"Id\":1,\"Nazwa\":\"x\",\"Tagi\":[]}"], zamknij: false);   // kompletny obiekt, writer otwarty
    var pierwszy = await Task.WhenAny(zadanie, Task.Delay(500));
    Console.WriteLine($"500 ms po kompletnym obiekcie, writer otwarty: zakonczone = {pierwszy == zadanie}");
    await pipe.Writer.CompleteAsync();
    var z = await zadanie;
    Console.WriteLine($"po Complete() writera: Id={z!.Id}, zadanie.IsCompletedSuccessfully = {zadanie.IsCompletedSuccessfully}");
    var r = await pipe.Reader.ReadAsync();
    Console.WriteLine($"reader po deserializacji: ReadAsync dziala, Buffer.Length={r.Buffer.Length}, IsCompleted={r.IsCompleted}");
    await pipe.Reader.CompleteAsync();   // zamykanie readera zostaje po naszej stronie
}

// ---------------------------------------------------------------- 4
Console.WriteLine("--- 4. Haczyk: dane po obiekcie (drugi dokument) ---");
{
    var pipe = new Pipe();
    await Wpisz(pipe.Writer, ["{\"Id\":1,\"Nazwa\":\"x\",\"Tagi\":[]}{\"Id\":2}"]);
    try
    {
        var z = await JsonSerializer.DeserializeAsync<Zamowienie>(pipe.Reader);
        Console.WriteLine($"nie rzucilo, Id={z!.Id}");
    }
    catch (Exception e) { Console.WriteLine($"RZUCILO {e.GetType().Name}: {Skroc(e.Message)}"); }
}

// ---------------------------------------------------------------- 5
Console.WriteLine("--- 5. Haczyk: urwany strumien ---");
{
    var pipe = new Pipe();
    await Wpisz(pipe.Writer, ["{\"Id\":1,\"Nazwa\":\"x"]);
    try { await JsonSerializer.DeserializeAsync<Zamowienie>(pipe.Reader); }
    catch (Exception e) { Console.WriteLine($"RZUCILO {e.GetType().Name}: {Skroc(e.Message)}"); }
}

Console.WriteLine("--- 6. Pamiec: patrz  dotnet run -c Release -- stream  /  -- list ---");

static string Skroc(string s) => s.Length > 100 ? s[..100] + "..." : s;

// 250 000 elementow po ~230 B = ~58 MB JSON. Producent pisze do Pipe z progami pauzy 1 MB.
static async Task PomiarPamieci(string tryb)
{
    var elem = "{\"Id\":1,\"Nazwa\":\"" + new string('x', 200) + "\",\"Tagi\":[]}";
    const int n = 250_000;
    var pipe = new Pipe(new PipeOptions(pauseWriterThreshold: 1 << 20, resumeWriterThreshold: 1 << 19));
    var producent = Task.Run(async () =>
    {
        var bytes = Encoding.UTF8.GetBytes(elem + ",");
        pipe.Writer.Write("["u8);
        for (int i = 0; i < n - 1; i++)
        {
            pipe.Writer.Write(bytes);
            if (i % 500 == 0) await pipe.Writer.FlushAsync();
        }
        pipe.Writer.Write(Encoding.UTF8.GetBytes(elem + "]"));
        await pipe.Writer.CompleteAsync();
    });

    var sw = Stopwatch.StartNew();
    int licznik = 0;
    if (tryb == "stream")
    {
        await foreach (var z in JsonSerializer.DeserializeAsyncEnumerable<Zamowienie>(pipe.Reader)) licznik++;
    }
    else
    {
        var lista = await JsonSerializer.DeserializeAsync<List<Zamowienie>>(pipe.Reader);
        licznik = lista!.Count;
    }
    await producent;
    var peak = Process.GetCurrentProcess().PeakWorkingSet64 / (1024 * 1024);
    Console.WriteLine($"tryb={tryb}: {licznik} elementow, PeakWorkingSet64 = {peak} MB, {sw.ElapsedMilliseconds} ms");
}

record Zamowienie(int Id, string Nazwa, string[] Tagi);
