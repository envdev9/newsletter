namespace TunitDemo;

// To jest cała "ceremonia" potrzebna do napisania testu w TUnit: zwykła klasa C#,
// zwykła metoda oznaczona atrybutem [Test]. Żadnej bazowej klasy do dziedziczenia,
// żadnego konstruktora z DI, żadnego [TestClass]/[TestFixture] na górze klasy.
public class CalculatorTests
{
    [Test]
    public async Task Add_TwoLiczby_ZwracaSume()
    {
        var calculator = new Calculator();

        var result = calculator.Add(2, 3);

        // Nowa składnia asercji TUnit: await Assert.That(wartosc).IsEqualTo(oczekiwana).
        // "await" jest tu naprawdę potrzebny - asercja jest asynchroniczna.
        await Assert.That(result).IsEqualTo(5);
    }

    [Test]
    public async Task Divide_PrzezZero_RzucaWyjatek()
    {
        var calculator = new Calculator();

        // Lambda przekazana do Assert.That - TUnit sam ją wywoła i złapie wyjątek.
        var dzialanie = () => calculator.Divide(10, 0);

        await Assert.That(dzialanie).Throws<DivideByZeroException>();
    }

    [Test]
    public async Task IsEven_DlaLiczbyNieparzystej_ZwracaFalse()
    {
        var calculator = new Calculator();

        var wynik = calculator.IsEven(7);

        // Asercje na typach prostych - tu bool - też mają czytelne API.
        await Assert.That(wynik).IsFalse();
    }
}
