// Demonstracja "siatki bezpieczeństwa" z promptu refaktoryzacyjnego (refactor_good.txt):
// test charakteryzujący porównuje STARĄ implementację z NOWĄ na siatce wejść.
// Zero pakietów - zwykła aplikacja konsolowa; exit 0 = zachowanie identyczne, 1 = różnice.
//
// Użycie:  dotnet run            -> refaktoryzacja poprawna (oczekiwane: 0 różnic)
//          dotnet run -- mutant  -> refaktoryzacja "z błędem" (zaokrąglanie po każdym kroku)

var mode = args.Length > 0 && args[0] == "mutant" ? Impl.Mutant : Impl.Refactored;

decimal[] unitPrices = [0m, 0.01m, 9.99m, 19.995m, 100m, 1234.56m];
int[] quantities = [0, 1, 9, 10, 49, 50, 100];
bool[] loyalFlags = [false, true];
string?[] coupons = [null, "SAVE10", "save10", "OLD10"];
DateOnly[] days = [new(2026, 12, 31), new(2027, 1, 1)];

int total = 0, diffs = 0;
foreach (var p in unitPrices)
foreach (var q in quantities)
foreach (var loyal in loyalFlags)
foreach (var c in coupons)
foreach (var d in days)
{
    total++;
    var before = OldPricing.CalculateTotal(p, q, loyal, c, d);
    var after = mode == Impl.Refactored
        ? NewPricing.CalculateTotal(p, q, loyal, c, d)
        : MutantPricing.CalculateTotal(p, q, loyal, c, d);
    if (before != after)
    {
        diffs++;
        if (diffs <= 5)
            Console.WriteLine($"ROZNICA: cena={p} ilosc={q} lojalny={loyal} kupon={c ?? "-"} dzien={d} stary={before} nowy={after}");
    }
}

Console.WriteLine($"tryb={mode} przypadkow={total} roznic={diffs}");
return diffs == 0 ? 0 : 1;

enum Impl { Refactored, Mutant }

// ---- STARY kod: jeden blok warunków ----
static class OldPricing
{
    public static decimal CalculateTotal(decimal unitPrice, int qty, bool loyal, string? coupon, DateOnly today)
    {
        decimal total = unitPrice * qty;
        if (coupon == "SAVE10" && today <= new DateOnly(2026, 12, 31))
        {
            total = total * 0.90m;
        }
        if (qty >= 50)
        {
            total = total * 0.92m;
        }
        else if (qty >= 10)
        {
            total = total * 0.95m;
        }
        if (loyal)
        {
            total = total * 0.97m;
        }
        return Math.Round(total, 2, MidpointRounding.AwayFromZero);
    }
}

// ---- NOWY kod: ta sama kolejność, osobne małe metody ----
static class NewPricing
{
    public static decimal CalculateTotal(decimal unitPrice, int qty, bool loyal, string? coupon, DateOnly today)
    {
        decimal total = unitPrice * qty;
        total = ApplyCoupon(total, coupon, today);
        total = ApplyVolume(total, qty);
        total = ApplyLoyalty(total, loyal);
        return Math.Round(total, 2, MidpointRounding.AwayFromZero);
    }

    static decimal ApplyCoupon(decimal total, string? coupon, DateOnly today) =>
        coupon == "SAVE10" && today <= new DateOnly(2026, 12, 31) ? total * 0.90m : total;

    static decimal ApplyVolume(decimal total, int qty) => qty switch
    {
        >= 50 => total * 0.92m,
        >= 10 => total * 0.95m,
        _ => total,
    };

    static decimal ApplyLoyalty(decimal total, bool loyal) => loyal ? total * 0.97m : total;
}

// ---- "Refaktoryzacja z błędem": zaokrągla po każdym kroku (typowy subtelny błąd) ----
static class MutantPricing
{
    static decimal R(decimal v) => Math.Round(v, 2, MidpointRounding.AwayFromZero);

    public static decimal CalculateTotal(decimal unitPrice, int qty, bool loyal, string? coupon, DateOnly today)
    {
        decimal total = unitPrice * qty;
        if (coupon == "SAVE10" && today <= new DateOnly(2026, 12, 31)) total = R(total * 0.90m);
        if (qty >= 50) total = R(total * 0.92m);
        else if (qty >= 10) total = R(total * 0.95m);
        if (loyal) total = R(total * 0.97m);
        return R(total);
    }
}
