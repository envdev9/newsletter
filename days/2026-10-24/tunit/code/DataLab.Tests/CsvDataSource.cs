using System.Globalization;
using TUnit.Core;

namespace DataLab.Tests;

/// <summary>
/// Własne źródło danych: wiersze z pliku CSV leżącego obok binarki.
/// Każdy wiersz = osobny test. Metoda GenerateDataSources woła się przy odkrywaniu testów.
/// </summary>
[AttributeUsage(AttributeTargets.Method)]
public sealed class CsvCasesAttribute(string file) : DataSourceGeneratorAttribute<decimal, string, decimal>
{
    public static int GenerateCalls;

    protected override IEnumerable<Func<(decimal, string, decimal)>> GenerateDataSources(DataGeneratorMetadata metadata)
    {
        Interlocked.Increment(ref GenerateCalls);
        var path = Path.Combine(AppContext.BaseDirectory, file);
        foreach (var line in File.ReadLines(path).Skip(1).Where(l => !string.IsNullOrWhiteSpace(l)))
        {
            var p = line.Split(',');
            var row = (
                decimal.Parse(p[0], CultureInfo.InvariantCulture),
                p[1],
                decimal.Parse(p[2], CultureInfo.InvariantCulture));
            yield return () => row;
        }
    }
}
