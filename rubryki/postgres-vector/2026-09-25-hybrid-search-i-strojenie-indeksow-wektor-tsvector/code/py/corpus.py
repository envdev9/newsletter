"""Dane demo. UCZCIWIE: KB_DOCS to ręcznie napisane zdania; korpus benchmarkowy to zdania
składane z szablonów (6 tematów x podmiot x czasownik x dopełnienie x dopisek).
Wektory NIE są deterministyczne z palca - liczy je prawdziwy model (embed_load.py).
Sztuczny jest tylko TEKST korpusu benchmarkowego (nikt go nie czyta - mierzymy indeksy)."""
import random

KB_DOCS = [
    "Błąd 40001 (serialization_failure) oznacza konflikt transakcji na poziomie SERIALIZABLE; aplikacja powinna powtórzyć całą transakcję.",
    "Indeks HNSW buduje wielowarstwowy graf sąsiedztwa i pozwala szybko znaleźć przybliżonych najbliższych sąsiadów w milionach wierszy.",
    "Parametr hnsw.ef_search określa, ilu kandydatów przegląda zapytanie; większa wartość daje lepszy recall kosztem czasu.",
    "IVFFlat dzieli wektory na klastry metodą k-means, a parametr probes wybiera, ile klastrów przeszukać.",
    "Indeks GIN na kolumnie tsvector przyspiesza wyszukiwanie pełnotekstowe operatorem @@.",
    "VACUUM FULL blokuje tabelę wyłącznie i przepisuje ją na nowo; zwykły VACUUM tylko oznacza miejsce do ponownego użycia.",
    "Pakiet Pgvector.EntityFrameworkCore dodaje do EF Core typ Vector i metody do liczenia odległości.",
    "Kubernetes restartuje kontener, gdy sonda liveness zawiedzie kilka razy z rzędu.",
    "Pierogi ruskie robi się z ziemniaków i twarogu; ciasto powinno być cienkie i elastyczne.",
    "Zupa pomidorowa najlepiej smakuje z makaronem i odrobiną śmietany.",
    "Kot domowy potrafi spać nawet szesnaście godzin na dobę.",
    "Psy rasy border collie potrzebują dużo ruchu i zadań umysłowych.",
    "Angular signals zastępują część zastosowań RxJS w prostym stanie komponentu.",
    "Mecz zakończył się rzutami karnymi po dogrywce; bramkarz obronił dwa strzały.",
    "Reciprocal Rank Fusion łączy kilka list rankingowych, sumując 1/(k+pozycja) dla każdego dokumentu.",
    "Zapytanie działa wolno, bo planner wybrał Seq Scan zamiast indeksu; sprawdź EXPLAIN ANALYZE i aktualność statystyk.",
    "Aby zmniejszyć zużycie pamięci przez indeks wektorowy, można zmniejszyć wymiar embeddingu lub użyć typu halfvec.",
    "Replikacja logiczna w PostgreSQL publikuje zmiany tabel do subskrybentów bez kopiowania całego klastra.",
    "Connection pooling w Npgsql ogranicza liczbę połączeń otwieranych do serwera; domyślny rozmiar puli to 100.",
    "Docker Compose uruchamia wiele kontenerów opisanych w jednym pliku YAML.",
    "Wyszukiwanie semantyczne znajduje teksty o podobnym znaczeniu, nawet gdy nie mają wspólnych słów.",
    "Na wolnym łączu sieciowym warto włączyć kompresję odpowiedzi HTTP (gzip lub brotli).",
    "Partycjonowanie tabel po dacie ułatwia usuwanie starych danych i przyspiesza skanowanie zakresów.",
    "Recall to odsetek prawdziwych najbliższych sąsiadów, które zwrócił indeks przybliżony.",
]

# (nazwa tematu, podmioty, czasowniki, dopełnienia, dopiski)
TOPICS = [
    ("baza",
     ["Administrator bazy", "Nowy indeks", "Replika", "Planner zapytań", "Autovacuum", "Tabela faktów", "Transakcja", "Kopia zapasowa", "Klaster"],
     ["przyspiesza", "blokuje", "przepisuje", "monitoruje", "odtwarza", "porządkuje", "skanuje", "replikuje", "kompresuje"],
     ["dużą tabelę zamówień", "kolumnę z datami", "strony danych", "statystyki kolumn", "dziennik WAL", "widok zmaterializowany", "klucz obcy", "partycję miesięczną", "sekwencję identyfikatorów"],
     ["w nocy", "przy dużym obciążeniu", "bez przestoju", "po awarii dysku", "zgodnie z harmonogramem", "na serwerze produkcyjnym"]),
    ("dotnet",
     ["Kompilator C#", "Middleware ASP.NET", "Kontener DI", "Serwis w tle", "Biblioteka Polly", "Pętla zdarzeń", "Garbage collector", "Testy jednostkowe", "Endpoint minimalnego API"],
     ["waliduje", "rejestruje", "serializuje", "wstrzykuje", "ponawia", "buforuje", "loguje", "mierzy", "zwalnia"],
     ["żądanie HTTP", "obiekt DTO", "zależność scoped", "wyjątek z bazy", "token JWT", "konfigurację z pliku", "strumień JSON", "kolejkę zadań", "pamięć zarządzaną"],
     ["podczas startu aplikacji", "przy każdym wywołaniu", "asynchronicznie", "w potoku żądań", "z limitem czasu", "w środowisku testowym"]),
    ("kuchnia",
     ["Szef kuchni", "Babcia", "Młody kucharz", "Cukiernik", "Restauracja", "Domowy piekarz", "Blogerka kulinarna", "Kelner", "Rodzina"],
     ["smaży", "gotuje", "piecze", "marynuje", "podaje", "doprawia", "kroi", "miesza", "wyrabia"],
     ["schab z cebulą", "zupę jarzynową", "ciasto drożdżowe", "świeże pierogi", "sos czosnkowy", "sałatkę z pomidorów", "domowy chleb", "kotlety mielone", "szarlotkę z cynamonem"],
     ["na niedzielny obiad", "według rodzinnego przepisu", "przed przyjściem gości", "na małym ogniu", "z dodatkiem ziół", "w wigilijny wieczór"]),
    ("sport",
     ["Napastnik", "Trener", "Maratończyk", "Bramkarz", "Drużyna siatkarzy", "Kolarz", "Sędzia", "Tenisistka", "Kapitan reprezentacji"],
     ["strzela", "analizuje", "biegnie", "broni", "wygrywa", "atakuje", "przygotowuje", "reklamuje", "trenuje"],
     ["decydującego gola", "taktykę na finał", "ostatni kilometr trasy", "rzut karny", "trzeci set", "podjazd pod górę", "spalonego w polu karnym", "serwis przeciwniczki", "mecz ligowy"],
     ["w doliczonym czasie", "przy pełnych trybunach", "mimo kontuzji", "w deszczu", "po przerwie", "w derbach miasta"]),
    ("zwierzeta",
     ["Kot domowy", "Border collie", "Stado saren", "Papuga", "Weterynarz", "Chomik", "Koń wyścigowy", "Ptaki wędrowne", "Szczeniak"],
     ["śpi", "goni", "obserwuje", "szczepi", "gryzie", "odlatuje", "zjada", "ćwiczy", "chowa"],
     ["na ciepłej kanapie", "piłkę w ogrodzie", "kolorowe nasiona", "wszystkie psy w schronisku", "kołowrotek w klatce", "przed nadejściem zimy", "świeże siano", "myszkę zabawkę", "kość z lodówki"],
     ["przez cały dzień", "o świcie", "z ciekawością", "co roku wiosną", "razem z opiekunem", "w cieniu drzewa"]),
    ("podroze",
     ["Turysta", "Przewodnik", "Pociąg pośpieszny", "Linia lotnicza", "Hotel nad morzem", "Rodzina z dziećmi", "Pilot wycieczek", "Kierowca autobusu", "Podróżnik"],
     ["zwiedza", "rezerwuje", "opóźnia", "odwołuje", "poleca", "planuje", "pakuje", "przekracza", "fotografuje"],
     ["starówkę w Krakowie", "bilety na weekend", "przesiadkę we Wrocławiu", "lot do Lizbony", "pokój z widokiem", "trasę przez góry", "walizkę na kółkach", "granicę w nocy", "zachód słońca na plaży"],
     ["w sezonie letnim", "z dużym wyprzedzeniem", "mimo strajku", "w długi weekend", "za rozsądną cenę", "bez biura podróży"]),
]


def _all_sentences(seed_key: int):
    out = []
    for name, subj, verbs, objs, tails in TOPICS:
        for s in subj:
            for v in verbs:
                for o in objs:
                    for t in tails:
                        out.append((name, f"{s} {v} {o} {t}."))
    random.Random(seed_key).shuffle(out)
    return out


def bench_corpus(n_docs: int, n_queries: int):
    """Zwraca (dokumenty, zapytania) - rozłączne zdania, ten sam rozkład, seed stały."""
    sents = _all_sentences(2026)
    docs = [s for _, s in sents[:n_docs]]
    queries = [s for _, s in sents[n_docs:n_docs + n_queries]]
    return docs, queries
