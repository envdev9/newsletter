// Na net9.0 ten plik NIE kompiluje sie - oczekiwane bledy w README.
using System.Net.WebSockets;

WebSocket ws = null!;
using var s1 = WebSocketStream.CreateWritableMessageStream(ws, WebSocketMessageType.Text);
using var s2 = WebSocketStream.CreateReadableMessageStream(ws);
using var s3 = WebSocketStream.Create(ws, WebSocketMessageType.Text, ownsWebSocket: false);
