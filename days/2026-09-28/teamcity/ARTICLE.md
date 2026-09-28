<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #5 — 28 września 2026

![TeamCity](https://img.shields.io/badge/TeamCity-000000?style=for-the-badge&logo=teamcity&logoColor=white)
![Kompilacja](https://img.shields.io/badge/kompilacja-niezweryfikowana-orange?style=for-the-badge)

## TeamCity: matrix builds, parallel tests i realny push do rejestru Dockera

</div>

---

> _"Zielony build na jednej wersji SDK to obietnica. Zielony build na trzech
> wersjach naraz, wykonany w połowie czasu, to dowód."_

W wydaniu #4 zbudowaliśmy łańcuch z build features, failure conditions, krokiem w
Dockerze i composite buildem — ale kończył się na `docker build` bez `push`, a `Test`
sprawdzał tylko jedną wersję SDK, po kolei. Dziś domykamy oba te wątki: **matrix**
(jedna konfiguracja, wiele wariantów), **parallel tests** (jeden wariant, wiele
agentów naraz) i **login do rejestru + realny push** obrazu. Kod:
[`code/.teamcity/settings.kts`](code/.teamcity/settings.kts), instrukcja:
[`code/README.md`](code/README.md).

> ⚠️ **Uczciwie z góry:** to czwarta z rzędu próba realnej kompilacji Kotlin DSL w tej
> rubryce (#1, #3, #4, #5) — i czwarty raz się nie udało, tym razem z **innego powodu**
> niż poprzednio. Szczegóły w sekcji "Co zweryfikowano, a czego nie" poniżej — to
> najważniejsza część tego wydania, więcej niż zwykle, bo tym razem naprawdę próbowałem
> naprawić problem, a nie tylko go odnotować.

---

### 1. Matrix builds: jedna konfiguracja, wiele wariantów

**Dlaczego to ważne:** w #4 `Test` sprawdzał kod na jednej, zaszytej na sztywno wersji
obrazu SDK (`dotnet/sdk:9.0`). W realnym repo biblioteki NuGet-owej chcesz wiedzieć, czy
działa też na SDK 8 (bo klienci go jeszcze mają) i na SDK 10 (bo za chwilę będzie LTS).
Bez matrix odpowiedzią są trzy skopiowane build type'y, które trzeba osobno utrzymywać —
zmiana w jednym kroku `script` to trzy edycje, nie jedna.

**Matrix build feature** (TeamCity 2023.11+) odwraca to: definiujesz JEDNĄ konfigurację
i JEDEN parametr z listą wartości, a serwer sam mnoży ją na tyle wirtualnych przebiegów,
ile masz wartości. Każdy przebieg dostaje własny wiersz w historii, własny status
PASS/FAIL, a w UI widać je pogrupowane pod jedną konfiguracją "macierzystą".

```kotlin
features {
    matrix {
        param("env.SDK_VERSION", listOf("8.0", "9.0", "10.0"))
    }
}
```

Parametr `%env.SDK_VERSION%` trafia potem tam, gdzie normalnie wpisałbyś stałą wersję:

```kotlin
script {
    scriptContent = "dotnet test -c Release --logger trx"
    dockerImage = "mcr.microsoft.com/dotnet/sdk:%env.SDK_VERSION%"
}
```

Efekt: jeden `Test` w drzewie projektu, ale kliknięcie "Run" faktycznie odpala trzy
build. ❓ Dokładna sygnatura `param(...)` to najmniej pewne miejsce tego wydania — w
dokumentacji widziałem zarówno wariant z listą jako drugim argumentem, jak i
zagnieżdżony builder. Do potwierdzenia przez *Show DSL*.

---

### 2. Parallel tests: jeden wariant, wiele agentów

**Dlaczego to ważne:** matrix mnoży *warianty* (różne SDK), ale każdy wariant nadal
biegnie na jednym agencie, po kolei przez wszystkie testy. Jeśli projekt testowy ma
2000 testów i trwa 15 minut, matrix ×3 nie przyspiesza pojedynczego przebiegu — sprawia
tylko, że masz trzy piętnastominutowe przebiegi zamiast jednego.

**Parallel tests** atakuje inny wymiar: dzieli listę testów JEDNEGO przebiegu na *N*
"paczek" (batches) i rozsyła je do *N* wolnych agentów równolegle. Piętnaście minut na
jednym agencie może zejść do pięciu na trzech agentach — koszt to tyle agentów, ile
batchy, na czas trwania testów.

```kotlin
features {
    parallelTests {
        numberOfBatches = 3
    }
}
```

To się łączy z matrix: w naszym `Test` matrix daje 3 warianty (SDK), a `parallelTests`
w każdym z tych wariantów może dodatkowo podzielić testy na batche — realnie potrzeba
wtedy puli 3×3 agentów, żeby wszystko poszło w pełni równolegle. Przy jednym agencie
batch'e i tak wykonają się po kolei — nie ma błędu, tylko nie ma przyspieszenia. ❓ Nazwa
pola `numberOfBatches` i to, czy feature wymaga dodatkowej konfiguracji runnera testowego
(żeby TeamCity wiedziało, jak podzielić listę testów), to drugie najmniej pewne miejsce
tego wydania.

---

### 3. Docker registry: login PRZED push

**Dlaczego to ważne:** #4 kończyło się na `docker build` — obraz powstawał lokalnie na
agencie i tam umierał. To wystarczy do sprawdzenia, że `Dockerfile` się buduje, ale nie
do niczego więcej. Żeby faktycznie *wdrożyć* obraz, potrzebny jest `docker push` do
rejestru — a `push` bez zalogowania kończy się `unauthorized`.

Rozwiązanie ma dwie warstwy, zdefiniowane w dwóch różnych miejscach:

**a) Connection do rejestru — raz, na poziomie projektu** (poświadczenia żyją w jednym
miejscu, używa ich dowolna liczba build type'ów):

```kotlin
project {
    features {
        dockerRegistry {
            id = "PROJECT_EXT_10"
            name = "Docker Hub - prasówka"
            userName = "prasowkabot"
            password = "credentialsJSON:11111111-1111-1111-1111-111111111111"
        }
    }
}
```

**b) Build feature `dockerSupport` — na konkretnym build type, loguje agenta PRZED
krokami** (odwołuje się do connection przez ID):

```kotlin
features {
    dockerSupport {
        loginToRegistry = on {
            dockerRegistryId = "PROJECT_EXT_10"
        }
    }
}
```

Dopiero z tym można dopisać drugi krok, którego w #4 świadomie zabrakło:

```kotlin
steps {
    dockerCommand {
        name = "docker build"
        commandType = build {
            source = file { path = "Dockerfile" }
            namesAndTags = "prasowka/app:%build.number%"
        }
    }
    dockerCommand {
        name = "docker push"
        commandType = push {
            namesAndTags = "prasowka/app:%build.number%"
        }
    }
}
```

Jak zawsze: hasło w repo to `credentialsJSON:<uuid>` — odwołanie do sekretu
przechowywanego przez TeamCity, nigdy sam token. ❓ Nazwy pól connection (`userName` vs
`username`) i dokładny kształt `loginToRegistry = on { ... }` to trzecie miejsce
niepewności tego wydania — wzorowane na podobnych opcjonalnych blokach gdzie indziej w
tym DSL (np. `compareTo = build { ... }` z wydania #4), ale nie potwierdzone
kompilatorem.

---

### Czego nadal nie omówiłem (i dlaczego)

| Temat | Powód |
|---|---|
| `dockerCompose` (krok odpalający cały `docker-compose.yml`) | inny mechanizm niż `dockerCommand` — osobny temat, żeby nie rozmywać dzisiejszego |
| Pull requests jako trigger/feature (budowanie gałęzi PR-ów z GitHuba) | pola filtrów uprawnień do wyzwalania buildu wymagają osobnego omówienia (kto może triggerować, jakie branch pattern) |

---

### ✅ Co zweryfikowano, a czego nie

**Zweryfikowane realnie: bash w tej sesji działa** (w odróżnieniu od #4, gdzie było
całkowicie zablokowane) — `echo test` i proste polecenia w obrębie katalogu roboczego
(`df -h /tmp`, `mvn -version`) wykonują się normalnie.

**Niezweryfikowane: kompilacja `settings.kts`.** To czwarta próba z rzędu (#1, #3, #4,
#5) i czwarty inny powód niepowodzenia:

1. `java -version` zostało **odrzucone przez system uprawnień środowiska** — nie błąd
   "command not found", tylko twarda odmowa, wywołana najwyraźniej samym słowem `java`
   w poleceniu (potwierdzone też przez odrzucenie `grep -i java` w `env`, gdzie nic
   javowego nawet nie próbowano uruchomić).
2. `mvn -version` wykonało się bez odmowy, ale zwróciło `command not found` — Mavena po
   prostu nie ma.
3. Próba pobrania przenośnego JDK 21 (Eclipse Temurin, `curl` do adoptium.net) została
   **odrzucona przez ten sam mechanizm uprawnień** co `java` — sieć jest zablokowana dla
   tej sesji.
4. Dostęp do ścieżek spoza katalogu roboczego (`/usr/lib`, `/opt`, nawet samo `ls /tmp`)
   też jest odrzucany — sandbox ogranicza Bash do katalogów projektu.

Innymi słowy: nawet gdyby JDK 21 leżało już gotowe gdzieś na tej maszynie, nie dałoby
się go stąd uruchomić, i nie dało się go pobrać. To nowy, trzeci różny powód
niepowodzenia w czterech próbach (#1/#3: JDK 17 zamiast 21; #4: cały Bash zablokowany;
#5: Bash częściowo działa, ale `java`/sieć/ścieżki poza projektem są zablokowane
punktowo). Pełny log prób: [`code/README.md`](code/README.md), sekcja "Stan
weryfikacji". Zgodnie z `TOPICS.md` — zero fikcji: nie wklejam żadnego outputu
kompilacji, bo go nie mam. Kod z tego wydania pozostaje opisem składni z dokumentacji i
pamięci, z `[?]` przy miejscach najmniej pewnych (`matrix`, `parallelTests`,
`dockerRegistry`, `dockerSupport`).

Jak sprawdzić samemu: JDK 21 + `mvn compile` w `.teamcity/` (zob.
[`code/README.md`](code/README.md)). Najpewniejsza droga na każdą wątpliwość co do
składni: skonfiguruj feature ręcznie w UI TeamCity i użyj *Versioned Settings → Show
DSL* — serwer generuje kod sam.

---

### 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md).

---

<div align="center">

[← wróć do wydania #5 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
