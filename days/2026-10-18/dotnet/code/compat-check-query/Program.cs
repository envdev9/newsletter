var ok = HttpMethod.Post;                    // istnieje od zawsze - kompiluje sie
var req = new HttpRequestMessage(HttpMethod.Query, "http://127.0.0.1/"); // .NET 10+ - na net9.0 blad
Console.WriteLine(ok + " " + req.Method);
