"""
Tests de la lógica de puntos (la parte más crítica del bot).
Corré con: python -m unittest
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.standings import compute_standings, points_system_default


class TestComputeStandings(unittest.TestCase):
    def _league(self, results, points_system=None, fl_point=1, fl_requires_points=True):
        return {
            "drivers": [
                {"id": "d1", "name": "Piloto Uno"},
                {"id": "d2", "name": "Piloto Dos"},
                {"id": "d3", "name": "Piloto Tres"},
            ],
            "results": results,
            "pointsSystem": points_system or points_system_default(),
            "fastestLapPoint": fl_point,
            "fastestLapRequiresPoints": fl_requires_points,
        }

    def test_puntos_basicos_por_posicion(self):
        league = self._league({
            "race1": [
                {"driverId": "d1", "position": 1, "dnf": False},
                {"driverId": "d2", "position": 2, "dnf": False},
            ]
        })
        totals = {s["name"]: s["total"] for s in compute_standings(league)}
        self.assertEqual(totals["Piloto Uno"], 25)
        self.assertEqual(totals["Piloto Dos"], 18)
        self.assertEqual(totals["Piloto Tres"], 0)

    def test_dnf_no_suma_puntos(self):
        league = self._league({"race1": [{"driverId": "d1", "position": None, "dnf": True}]})
        totals = {s["name"]: s["total"] for s in compute_standings(league)}
        self.assertEqual(totals["Piloto Uno"], 0)

    def test_vuelta_rapida_requiere_puntos(self):
        # d3 termina fuera de zona de puntos (P11) con vuelta rápida.
        # Con fastestLapRequiresPoints=True no debería sumar el punto extra.
        league = self._league({
            "race1": [
                {"driverId": "d1", "position": 1, "dnf": False},
                {"driverId": "d3", "position": 11, "dnf": False, "fastestLap": True},
            ]
        })
        totals = {s["name"]: s["total"] for s in compute_standings(league)}
        self.assertEqual(totals["Piloto Tres"], 0)

    def test_vuelta_rapida_sin_requerir_puntos(self):
        league = self._league({
            "race1": [
                {"driverId": "d1", "position": 1, "dnf": False},
                {"driverId": "d3", "position": 11, "dnf": False, "fastestLap": True},
            ]
        }, fl_requires_points=False)
        totals = {s["name"]: s["total"] for s in compute_standings(league)}
        self.assertEqual(totals["Piloto Tres"], 1)

    def test_orden_por_puntos_y_luego_victorias(self):
        league = self._league({
            "race1": [
                {"driverId": "d2", "position": 1, "dnf": False},
                {"driverId": "d1", "position": 2, "dnf": False},
            ]
        })
        self.assertEqual(compute_standings(league)[0]["name"], "Piloto Dos")


if __name__ == "__main__":
    unittest.main()
