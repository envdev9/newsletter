using System.IO.Compression;

// Kazda z ponizszych linii powinna dac blad kompilacji na .NET 9.
await ZipFile.CreateFromDirectoryAsync("src", "out.zip");
await ZipFile.ExtractToDirectoryAsync("out.zip", "dst");
await using var archive = await ZipArchive.CreateAsync(new MemoryStream(), ZipArchiveMode.Create, leaveOpen: false, entryNameEncoding: null);
await using var s = await archive.CreateEntry("a.txt").OpenAsync();
// Dla kontrastu: ta linia istnieje od zawsze i NIE daje bledu.
ZipFile.CreateFromDirectory("src", "sync.zip");
