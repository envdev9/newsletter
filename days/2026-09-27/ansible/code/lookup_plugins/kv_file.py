"""Wlasny lookup: kv_file - czyta plik klucz=wartosc i zwraca wartosc(i) dla podanych kluczy.

Lookupy wykonuja sie na kontrolerze (nie na hoscie docelowym).
"""
from ansible.errors import AnsibleError
from ansible.plugins.lookup import LookupBase

DOCUMENTATION = r"""
    name: kv_file
    short_description: wartosci z pliku klucz=wartosc
    options:
      _terms:
        description: klucze do odczytania
        required: true
      file:
        description: sciezka do pliku klucz=wartosc
        required: true
"""


class LookupModule(LookupBase):
    def run(self, terms, variables=None, **kwargs):
        self.set_options(var_options=variables, direct=kwargs)
        path = self.get_option("file")
        found = self.find_file_in_search_path(variables, "files", path)
        if not found:
            raise AnsibleError("kv_file: nie znaleziono pliku %s" % path)
        data = {}
        with open(found, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    data[key.strip()] = value.strip()
        result = []
        for term in terms:
            if term not in data:
                raise AnsibleError("kv_file: brak klucza '%s' w %s" % (term, path))
            result.append(data[term])
        return result
