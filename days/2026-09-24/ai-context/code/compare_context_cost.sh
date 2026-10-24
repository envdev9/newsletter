#!/usr/bin/env bash
# Demonstracja: ile kontekstu zjada wrzucenie CAŁEGO logu modelowi do ręki,
# w porównaniu z przefiltrowaniem go najpierw narzędziami tekstowymi.
#
# Scenariusz jest celowo realistyczny: log builda CI, 4000+ linii szumu,
# 3 linie faktycznego sygnału (2 błędy kompilacji, 1 nieudany test) ukryte
# w środku pliku.
set -euo pipefail
cd "$(dirname "$0")"

echo "== Generowanie syntetycznego logu builda =="
python3 generate_log.py > build.log
echo "Wygenerowano: $(wc -l < build.log) linii, $(wc -c < build.log) bajtów -> build.log"

echo
echo "=================================================================="
echo "1) cat całego pliku - tak jakby ktoś wrzucił cały log do kontekstu"
echo "=================================================================="
cat build.log | python3 token_budget.py

echo
echo "=================================================================="
echo "2) head -n 50 - pierwsze 50 linii pliku"
echo "=================================================================="
head -n 50 build.log | python3 token_budget.py
echo "--- czy w pierwszych 50 liniach jest jakikolwiek sygnał błędu? ---"
head -n 50 build.log | grep -E "error |FAILED" || echo "(brak - sygnał jest głębiej w pliku, head go nie widzi)"

echo
echo "=================================================================="
echo "3) grep -E 'error |FAILED' - tylko linie z faktycznym sygnałem"
echo "=================================================================="
grep -E "error |FAILED" build.log | python3 token_budget.py
echo "--- treść, którą faktycznie widzi model ---"
grep -E "error |FAILED" build.log

echo
echo "=================================================================="
echo "Podsumowanie: o ile mniej znaków trafia do kontekstu z grep niż z cat"
echo "=================================================================="
cat_chars=$(wc -c < build.log)
grep_chars=$(grep -E "error |FAILED" build.log | wc -c)
python3 -c "
cat_chars = $cat_chars
grep_chars = $grep_chars
ratio = cat_chars / grep_chars
print(f'cat:  {cat_chars} znaków')
print(f'grep: {grep_chars} znaków')
print(f'grep zużywa {ratio:.0f}x mniej kontekstu niż cat całego pliku')
"
