using System.Data.Common;
using Microsoft.EntityFrameworkCore.Diagnostics;
using Npgsql;

namespace PgPlanDemo;

/// <summary>
/// Odpowiednik PlanCaptureInterceptor z #15, ale dla PostgreSQL - i prostszy: Postgres nie potrzebuje DMV ani cache planow,
/// bo potrafi opisac WYKONANIE dowolnego zapytania: EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) &lt;to samo polecenie z tymi samymi
/// parametrami&gt;. Plan jest wiec nie "kompilacyjny", tylko z faktycznego wykonania (ActualRows, Buffers, Rows Removed by Filter).
/// Cena: zapytanie wykonuje sie drugi raz (na osobnym polaczeniu) - interceptor wlaczaj tylko w testach/dev i tylko dla SELECT.
/// Dziala tylko, gdy ustawisz <see cref="NextLabel"/> - jedno zapytanie = jeden plik.
/// </summary>
public class PgPlanCaptureInterceptor : DbCommandInterceptor
{
    private readonly string _connectionString;
    private readonly string _outDir;

    public PgPlanCaptureInterceptor(string connectionString, string outDir)
    {
        _connectionString = connectionString;
        _outDir = outDir;
    }

    public string? NextLabel { get; set; }
    public List<string> Written { get; } = new();

    public override DbDataReader ReaderExecuted(DbCommand command, CommandExecutedEventData eventData, DbDataReader result)
    {
        var label = NextLabel;
        if (label is null || command is not NpgsqlCommand src)
        {
            return result;
        }
        NextLabel = null; // tylko pierwsze polecenie po ustawieniu etykiety

        if (!src.CommandText.TrimStart().StartsWith("SELECT", StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidOperationException("EXPLAIN ANALYZE wykonuje polecenie - interceptor przyjmuje tylko SELECT");
        }

        using var conn = new NpgsqlConnection(_connectionString);
        conn.Open();
        using var cmd = new NpgsqlCommand("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + src.CommandText, conn);
        foreach (NpgsqlParameter p in src.Parameters)
        {
            cmd.Parameters.Add(p.Clone());
        }
        var json = (string)cmd.ExecuteScalar()!;
        Directory.CreateDirectory(_outDir);
        var path = Path.Combine(_outDir, label + ".json");
        File.WriteAllText(path, json);
        Written.Add(path);
        return result;
    }
}
