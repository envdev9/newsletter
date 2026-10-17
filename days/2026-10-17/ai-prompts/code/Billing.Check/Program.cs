using Billing;

var failures = 0;

void Check(string name, decimal actual, decimal expected)
{
    var ok = actual == expected;
    Console.WriteLine($"{(ok ? "OK  " : "FAIL")} {name}: {actual} (oczekiwano {expected})");
    if (!ok) failures++;
}

Check("Round(2.675)", Money.Round(2.675m), 2.68m);
Check("Round(2.665)", Money.Round(2.665m), 2.67m);
Check("Round(0.125)", Money.Round(0.125m), 0.13m);
Check("Round(-0.125)", Money.Round(-0.125m), -0.13m);
Check("LineTotal(3 x 0.835)", InvoiceCalculator.LineTotal(new InvoiceLine("A", 3, 0.835m)), 2.51m);
Check("Total(2 x 0.125 + 10.00, rabat 10%)",
    InvoiceCalculator.Total(new[] { new InvoiceLine("A", 2, 0.125m), new InvoiceLine("B", 1, 10.00m) }, 10m), 9.22m);

Console.WriteLine(failures == 0 ? "WSZYSTKO OK" : $"BLEDY: {failures}");
return failures == 0 ? 0 : 1;
