using System.Net.Http.Headers;

namespace TunitWebApi.Tests;

/// <summary>
/// Buduje HttpRequestMessage z opcjonalnym tokenem Bearer -- CELOWO zamiast ustawiania
/// fixture.Client.DefaultRequestHeaders.Authorization. Fixture jest wspoldzielony
/// (SharedType.PerClass) miedzy wszystkimi testami jednej klasy, a TUnit domyslnie
/// odpala testy RUNNOLEGLE (wydanie #2) -- mutowanie wspolnego DefaultRequestHeaders z
/// wielu testow naraz byloby wyscigiem (jeden test moglby wyslac zadanie z tokenem
/// podmienionym przez inny, rownolegle dzialajacy test). Osobny HttpRequestMessage per
/// wywolanie eliminuje ten problem bez potrzeby [NotInParallel].
/// </summary>
public static class TestRequests
{
    public static HttpRequestMessage Get(string url, string? bearerToken = null)
    {
        var request = new HttpRequestMessage(HttpMethod.Get, url);
        if (bearerToken is not null)
        {
            request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", bearerToken);
        }

        return request;
    }
}
