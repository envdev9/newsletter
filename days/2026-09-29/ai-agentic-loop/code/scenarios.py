"""Scenariusze testowe dla skill_router_sim.py.

Kazdy scenariusz to jedno zadanie uzytkownika + notatka, co ma zademonstrowac.
Uzywane przez run_tests.py. Zebrane w jednym miejscu, zeby ARTICLE.md i testy
odwolywaly sie do tych samych tekstow (zero rozjazdu miedzy tym co jest w
artykule a tym co faktycznie policzono).
"""

SCENARIOS = [
    {
        "id": "A-literal-match",
        "task": (
            "Test dotnet test failuje po tym jak zmienilem model domeny i dodalem "
            "migracje EF Core zmieniajaca typ kolumny Amount z int na decimal."
        ),
        "note": (
            "Zadanie dotyka dwoch tematow naraz (test + migracja) i uzywa slow "
            "wprost z opisow - oba dobre, konkretne skille powinny zapalic sie."
        ),
    },
    {
        "id": "B-paraphrase",
        "task": (
            "Cos sie psuje w pipeline dokladnie tam gdzie sprawdzamy poprawnosc "
            "kodu, mimo ze nikt nic nie zmienial od wczoraj."
        ),
        "note": (
            "Ten sam problem co A (podejrzenie flaky/regresji w testach), ale "
            "opisany bez ani jednego slowa z v1-narrow ('test', 'dotnet', 'build'). "
            "Widac czy zadziala tylko wersja z opisem zaprojektowanym pod parafrazy (v2)."
        ),
    },
    {
        "id": "C-migration-clear",
        "task": (
            "Migracja dodaje DROP COLUMN na tabeli Orders, kolumna Legacy - czy "
            "taka migracja jest bezpieczna do wgrania na produkcji?"
        ),
        "note": "Jednoznaczna domena migracji EF Core - powinien wygrac jeden skill, wyraznie.",
    },
    {
        "id": "D-unrelated",
        "task": "Jak skonfigurowac Serilog zeby wysylal logi do Seq z poziomu ASP.NET Core?",
        "note": (
            "Zadanie nie dotyczy zadnego z zainstalowanych skilli. Test na to, ze "
            "domyslny stan to 'nic sie nie laduje', nie 'zaladuj cokolwiek najbardziej podobne'."
        ),
    },
    {
        "id": "E-inflection-limit",
        "task": (
            "Chcemy dropnac kolumne Legacy z tabeli Orders w nowej migracji, czy "
            "to bezpieczne na produkcji?"
        ),
        "note": (
            "Ten sam temat co C, inna odmiana slow (kolumne/kolumny, migracji/migracje, "
            "bezpieczne/bezpieczna, dropnac/DROP). Pokazuje limit heurystyki bez stemmingu: "
            "prawidlowy skill dostaje sygnal, ale za slaby, zeby przekroczyc prog."
        ),
    },
]
