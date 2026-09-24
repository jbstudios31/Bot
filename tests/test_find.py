"""
Tests de las funciones de búsqueda (find_driver y find_race).

find_driver y find_race son exactamente el tipo de función que se rompe
en silencio con un refactor: si alguien cambia el orden del matching
(exacto → substring), un usuario con nombre similar al de otro empieza
a "pisar" al equivocado y nadie se entera hasta que se carga un
resultado mal. Estos tests cubren esos casos.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.standings import find_driver, find_race


class TestFindDriver(unittest.TestCase):
    def _league(self):
        return {
            "drivers": [
                {"id": "d1", "name": "Gonzalez A"},
                {"id": "d2", "name": "Gonzalez B"},
                {"id": "d3", "name": "Martinez"},
                {"id": "d4", "name": "Pérez"},
            ]
        }

    def test_match_exacto(self):
        league = self._league()
        self.assertEqual(find_driver(league, "Gonzalez A")["id"], "d1")
        self.assertEqual(find_driver(league, "Martinez")["id"], "d3")

    def test_match_exacto_prefiere_sobre_substring(self):
        # Bug que se rompía antes: con solo matching por substring, "Gonzalez A"
        # podía matchear "Gonzalez B" (el primero que apareciera). El test
        # verifica que el match exacto gana sobre el substring.
        league = self._league()
        self.assertEqual(find_driver(league, "Gonzalez A")["id"], "d1")
        self.assertEqual(find_driver(league, "Gonzalez B")["id"], "d2")

    def test_match_parcial_como_fallback(self):
        # Si el nombre no es exacto pero es substring, tiene que matchear
        # algún piloto, no devolver None.
        league = self._league()
        self.assertIsNotNone(find_driver(league, "gonzalez"))
        self.assertIsNotNone(find_driver(league, "MARTINEZ"))  # case-insensitive

    def test_no_match_devuelve_none(self):
        league = self._league()
        self.assertIsNone(find_driver(league, "Nadie"))

    def test_acentos_case_insensitive(self):
        # find_driver hace .lower() en ambos lados, pero no normaliza acentos:
        # "Pérez" (con tilde) y "Perez" (sin tilde) son strings distintos.
        # El test documenta este comportamiento: si en el futuro se quiere
        # matchear sin acentos, hay que agregar normalización acá.
        league = self._league()
        self.assertEqual(find_driver(league, "pérez")["id"], "d4")
        # "PEREZ" sin tilde NO matchea "Pérez" con tilde (es substring distinto).
        self.assertIsNone(find_driver(league, "PEREZ"))

    def test_drivers_como_dict(self):
        # Firebase puede devolver drivers como dict {id: {name: ...}} en vez
        # de lista. find_driver tiene que normalizar eso.
        league = {
            "drivers": {
                "d1": {"id": "d1", "name": "Gonzalez A"},
                "d2": {"id": "d2", "name": "Martinez"},
            }
        }
        self.assertEqual(find_driver(league, "Gonzalez A")["id"], "d1")


class TestFindRace(unittest.TestCase):
    def _races(self):
        return [
            {"id": "r1", "name": "Monaco"},
            {"id": "r2", "name": "Monaco Sprint"},
            {"id": "r3", "name": "Silverstone"},
        ]

    def test_match_exacto_prefiere_sobre_substring(self):
        # Si el usuario escribe "Monaco" exacto, NO debe devolver "Monaco
        # Sprint" (que también contiene "Monaco" como substring).
        races = self._races()
        self.assertEqual(find_race(races, "Monaco")["id"], "r1")

    def test_match_exacto_para_sprint(self):
        races = self._races()
        self.assertEqual(find_race(races, "Monaco Sprint")["id"], "r2")

    def test_match_parcial_como_fallback(self):
        races = self._races()
        # Si escribe solo "sprint" (sin "Monaco"), matchea por substring.
        self.assertEqual(find_race(races, "sprint")["id"], "r2")

    def test_no_match_devuelve_none(self):
        races = self._races()
        self.assertIsNone(find_race(races, "Imola"))


if __name__ == "__main__":
    unittest.main()
