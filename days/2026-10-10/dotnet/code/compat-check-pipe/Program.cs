using System.IO.Pipelines;
using System.Text.Json;

// Ten kod NIE kompiluje sie na net9.0: JsonSerializer nie ma przeciazen przyjmujacych PipeReader.
var pipe = new Pipe();
var wynik = await JsonSerializer.DeserializeAsync<int[]>(pipe.Reader);
await foreach (var x in JsonSerializer.DeserializeAsyncEnumerable<int>(pipe.Reader))
    Console.WriteLine(x);
Console.WriteLine(wynik);
