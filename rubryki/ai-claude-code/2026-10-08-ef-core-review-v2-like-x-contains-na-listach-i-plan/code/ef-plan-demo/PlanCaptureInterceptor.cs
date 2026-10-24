using System.Data.Common;
using Microsoft.Data.SqlClient;
using Microsoft.EntityFrameworkCore.Diagnostics;

namespace EfPlanDemo;

/// <summary>
/// Interceptor, ktory po wykonaniu zapytania wysylanego przez EF wyciaga z cache planow SQL Server plan TEGO zapytania
/// (sys.dm_exec_query_plan) i zapisuje go do pliku .xml, ktory mozna przepuscic przez scan_plan.py.
/// Dziala tylko, gdy ustawisz <see cref="NextLabel"/> - jedno zapytanie = jeden plik. Plan idzie osobnym polaczeniem.
///
/// Dlaczego nie SET SHOWPLAN_XML ON: sprawdzone - dla `EXEC sp_executesql N'...', N'@p ...', @p = ...` SQL Server zwraca
/// w trybie SHOWPLAN tylko wiersz "EXECUTE PROC" bez planu wewnetrznego zapytania (bez zadnych RelOp), wiec skaner
/// planu nie mialby czego czytac. Plan z cache jest za to planem, ktory silnik naprawde skompilowal dla wartosci
/// parametru z tego wywolania (parameter sniffing). Cena: to plan kompilacyjny (bez ActualRows) i potrzebne
/// uprawnienie VIEW SERVER STATE (sys.dm_exec_*).
/// </summary>
public class PlanCaptureInterceptor : DbCommandInterceptor
{
    private readonly string _connectionString;
    private readonly string _outDir;

    public PlanCaptureInterceptor(string connectionString, string outDir)
    {
        _connectionString = connectionString;
        _outDir = outDir;
    }

    public string? NextLabel { get; set; }
    public List<string> Written { get; } = new();
    public List<string> Skipped { get; } = new();

    public override DbDataReader ReaderExecuted(DbCommand command, CommandExecutedEventData eventData, DbDataReader result)
    {
        var label = NextLabel;
        if (label is null || command is not SqlCommand src)
        {
            return result;
        }
        NextLabel = null; // tylko pierwsze polecenie po ustawieniu etykiety

        using var conn = new SqlConnection(_connectionString);
        conn.Open();
        using var cmd = conn.CreateCommand();
        // t.text dla sp_executesql to "(@p typ)<tekst zapytania>", wiec szukamy tekstu polecenia jako podciagu
        cmd.CommandText = "SELECT TOP 1 CAST(p.query_plan AS nvarchar(max)) FROM sys.dm_exec_query_stats qs " +
                          "CROSS APPLY sys.dm_exec_sql_text(qs.sql_handle) t " +
                          "CROSS APPLY sys.dm_exec_query_plan(qs.plan_handle) p " +
                          "WHERE CHARINDEX(@cmd, t.text) > 0 AND t.text NOT LIKE '%dm_exec%' " +
                          "ORDER BY qs.creation_time DESC";
        cmd.Parameters.Add(new SqlParameter("@cmd", System.Data.SqlDbType.NVarChar, -1) { Value = src.CommandText });
        var xml = cmd.ExecuteScalar() as string;
        if (xml is not null)
        {
            Directory.CreateDirectory(_outDir);
            var path = Path.Combine(_outDir, label + ".xml");
            File.WriteAllText(path, xml);
            Written.Add(path);
        }
        else
        {
            Skipped.Add($"{label}: brak planu w cache (zapytanie nie trafilo do dm_exec_query_stats)");
        }
        return result;
    }
}
