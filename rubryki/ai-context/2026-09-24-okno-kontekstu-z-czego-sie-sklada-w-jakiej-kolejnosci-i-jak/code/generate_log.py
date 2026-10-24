#!/usr/bin/env python3
"""Generuje deterministyczny, syntetyczny log builda CI.

Symuluje typową sytuację z życia: 4000 linii szumu (kroki kompilacji,
pobierania paczek, testów przechodzących OK) i zaledwie kilka linii, które
faktycznie coś mówią (dwa błędy kompilacji, jeden nieudany test). Dokładnie
tak wygląda log, który dostajesz od `dotnet build` / CI w realnym projekcie -
sygnał ukryty w hałasie.

Użycie:
    python3 generate_log.py > build.log
"""

import random

random.seed(42)  # determinizm - ten sam log za każdym uruchomieniem

STEPS = [
    "Restoring NuGet packages for {proj}...",
    "Determining projects to restore...",
    "Compiling {proj} -> bin/Debug/net10.0/{proj}.dll",
    "Running analyzer CA{code} on {proj}...",
    "Test '{proj}.Tests.Should_{behavior}' PASSED (12 ms)",
    "Copying resource files for {proj}...",
    "Resolving assembly references for {proj}...",
]

PROJECTS = ["Newsletter.Api", "Newsletter.Domain", "Newsletter.Infra", "Newsletter.Tests", "Newsletter.Cli"]
BEHAVIORS = ["ReturnOk", "ValidateInput", "MapDto", "PersistEntity", "RaiseEvent", "ParseDate"]

lines = []
for i in range(4000):
    step = random.choice(STEPS)
    lines.append(
        step.format(
            proj=random.choice(PROJECTS),
            code=random.randint(1000, 1999),
            behavior=random.choice(BEHAVIORS),
        )
    )

# Wstrzykujemy realny sygnał w losowe, ale deterministyczne (seed=42) miejsca.
lines.insert(1234, "error CS0246: The type or namespace name 'IEmailSender' could not be found (are you missing a using directive or an assembly reference?) [Newsletter.Infra.csproj]")
lines.insert(2678, "error CS1002: ; expected [Newsletter.Api.csproj]")
lines.insert(3456, "Test 'Newsletter.Tests.Should_RejectInvalidSlug' FAILED: Expected <ArgumentException> but no exception was thrown (8 ms)")

print("\n".join(lines))
