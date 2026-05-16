"""Tests for Phase 3 aerodynamic wind-component additions in weather_service.py."""
import math
import unittest
from unittest.mock import MagicMock, patch

from weather_service import (
    _calculate_true_course,
    calculate_wind_component,
    get_aerodynamic_performance,
    get_winds_aloft,
    iata_to_icao,
    iata_to_airport_info,
    _TAS_KT,
)


class TestIataToIcao(unittest.TestCase):
    """Unit tests for iata_to_icao()."""

    def test_known_airport_returns_icao(self):
        # LHR → EGLL is a well-known mapping in airportsdata
        icao = iata_to_icao("LHR")
        self.assertEqual(icao, "EGLL")

    def test_case_insensitive(self):
        self.assertEqual(iata_to_icao("lhr"), iata_to_icao("LHR"))

    def test_unknown_code_returns_iata_fallback(self):
        # An unlikely made-up code should fall back to itself
        result = iata_to_icao("ZZZ")
        self.assertEqual(result, "ZZZ")

    def test_returns_uppercase(self):
        result = iata_to_icao("jfk")
        self.assertTrue(result.isupper(), f"Expected uppercase, got {result}")

    def test_airportsdata_failure_returns_iata(self):
        with patch("weather_service._get_airportsdata", return_value={}):
            result = iata_to_icao("LHR")
        self.assertEqual(result, "LHR")


class TestIataToAirportInfo(unittest.TestCase):
    """Unit tests for iata_to_airport_info()."""

    def test_known_airport_has_name_city_country(self):
        info = iata_to_airport_info("LHR")
        self.assertIn("name", info)
        self.assertIn("city", info)
        self.assertIn("country", info)
        self.assertIn("Heathrow", info["name"])
        self.assertEqual(info["city"], "London")
        self.assertEqual(info["country"], "GB")

    def test_unknown_code_returns_defaults(self):
        info = iata_to_airport_info("ZZZ")
        self.assertEqual(info["name"], "ZZZ")
        self.assertEqual(info["city"], "Unknown City")
        self.assertEqual(info["country"], "Unknown")

    def test_airportsdata_failure_returns_defaults(self):
        with patch("weather_service._get_airportsdata", return_value={}):
            info = iata_to_airport_info("JFK")
        self.assertEqual(info["name"], "JFK")
        self.assertEqual(info["city"], "Unknown City")
        self.assertEqual(info["country"], "Unknown")

    def test_case_insensitive(self):
        info_upper = iata_to_airport_info("JFK")
        info_lower = iata_to_airport_info("jfk")
        self.assertEqual(info_upper["name"], info_lower["name"])

    def test_airportsdata_only_entry_uses_airportsdata_elevation(self):
        """When airportsdata has an entry but internal metadata does not,
        elevation should come from airportsdata so the function succeeds."""
        from weather_service import get_departure_performance
        fake_ad = {
            "LHR": {"icao": "EGLL", "elevation": 83.0, "name": "London Heathrow Airport",
                    "city": "London", "country": "GB"}
        }
        fake_metar = {
            "temperature_c": 15.0,
            "altimeter_in_hg": 29.92,
            "icao": "EGLL",
            "raw_text": "",
        }
        # Internal metadata returns nothing for LHR
        with patch("weather_service._get_airportsdata", return_value=fake_ad), \
             patch("weather_service._get_airports_by_iata", return_value={}), \
             patch("weather_service.get_metar_data", return_value=fake_metar):
            result = get_departure_performance("LHR")

        self.assertIsNotNone(result, "Should succeed when elevation comes from airportsdata")
        self.assertEqual(result["icao"], "EGLL")
        self.assertIn("density_altitude_ft", result)


class TestCalculateTrueCourse(unittest.TestCase):
    """Unit tests for _calculate_true_course()."""

    def test_due_east(self):
        # Two points on the same latitude, second is east → bearing ~90°
        bearing = _calculate_true_course(0.0, 0.0, 0.0, 10.0)
        self.assertAlmostEqual(bearing, 90.0, delta=1.0)

    def test_due_north(self):
        # Two points on the same longitude, second is north → bearing ~0°
        bearing = _calculate_true_course(0.0, 0.0, 10.0, 0.0)
        self.assertAlmostEqual(bearing, 0.0, delta=1.0)

    def test_due_south(self):
        # Second point is south → bearing ~180°
        bearing = _calculate_true_course(10.0, 0.0, 0.0, 0.0)
        self.assertAlmostEqual(bearing, 180.0, delta=1.0)

    def test_due_west(self):
        # Second point is west → bearing ~270°
        bearing = _calculate_true_course(0.0, 10.0, 0.0, 0.0)
        self.assertAlmostEqual(bearing, 270.0, delta=1.0)

    def test_result_in_0_to_360(self):
        bearing = _calculate_true_course(51.5, -0.1, 40.7, -74.0)  # LHR → JFK
        self.assertGreaterEqual(bearing, 0.0)
        self.assertLess(bearing, 360.0)


class TestCalculateWindComponent(unittest.TestCase):
    """Unit tests for calculate_wind_component()."""

    def test_pure_tailwind(self):
        # Wind FROM 270° (westerly), course 090° (eastbound) → pure tailwind
        result = calculate_wind_component(
            wind_dir_deg=270.0,
            wind_speed_kt=50.0,
            true_course_deg=90.0,
        )
        self.assertGreater(result["wind_component_kt"], 0, "Should be tailwind")
        self.assertAlmostEqual(result["wind_component_kt"], 50.0, delta=1.0)
        self.assertEqual(result["wind_type"], "tailwind")
        self.assertAlmostEqual(result["ground_speed_kt"], _TAS_KT + 50.0, delta=1.0)

    def test_pure_headwind(self):
        # Wind FROM 090° (easterly), course 090° (eastbound) → pure headwind
        result = calculate_wind_component(
            wind_dir_deg=90.0,
            wind_speed_kt=50.0,
            true_course_deg=90.0,
        )
        self.assertLess(result["wind_component_kt"], 0, "Should be headwind")
        self.assertAlmostEqual(result["wind_component_kt"], -50.0, delta=1.0)
        self.assertEqual(result["wind_type"], "headwind")
        self.assertAlmostEqual(result["ground_speed_kt"], _TAS_KT - 50.0, delta=1.0)

    def test_crosswind_has_no_component(self):
        # Wind FROM 000° (northerly), course 090° (eastbound) → no forward component
        result = calculate_wind_component(
            wind_dir_deg=0.0,
            wind_speed_kt=50.0,
            true_course_deg=90.0,
        )
        self.assertAlmostEqual(result["wind_component_kt"], 0.0, delta=1.0)

    def test_zero_wind_speed(self):
        result = calculate_wind_component(
            wind_dir_deg=270.0,
            wind_speed_kt=0.0,
            true_course_deg=90.0,
        )
        self.assertEqual(result["wind_component_kt"], 0.0)
        self.assertAlmostEqual(result["ground_speed_kt"], _TAS_KT, delta=1.0)

    def test_returns_all_required_keys(self):
        result = calculate_wind_component(270.0, 30.0, 90.0)
        self.assertIn("wind_component_kt", result)
        self.assertIn("ground_speed_kt", result)
        self.assertIn("wind_type", result)

    def test_ground_speed_never_zero(self):
        # Even with extreme headwind, ground speed should not drop to ≤ 0
        result = calculate_wind_component(
            wind_dir_deg=90.0,
            wind_speed_kt=600.0,  # stronger than TAS
            true_course_deg=90.0,
        )
        self.assertGreater(result["ground_speed_kt"], 0.0)


class TestGetWindsAloft(unittest.TestCase):
    """Tests for get_winds_aloft()."""

    def test_returns_none_when_no_api_key(self):
        with patch("weather_service._get_api_key", return_value=None):
            result = get_winds_aloft("KJFK")
        self.assertIsNone(result)

    def test_returns_none_on_api_error(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        mock_resp.text = "Service unavailable"
        with patch("weather_service._get_api_key", return_value="fake-key"), \
             patch("requests.get", return_value=mock_resp):
            result = get_winds_aloft("KJFK")
        self.assertIsNone(result)

    def test_returns_wind_data_on_success(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [{
                "forecast": [{
                    "wind": {
                        "direction": 270,
                        "speed_kts": 35,
                    }
                }]
            }]
        }
        with patch("weather_service._get_api_key", return_value="fake-key"), \
             patch("requests.get", return_value=mock_resp):
            result = get_winds_aloft("KJFK")

        self.assertIsNotNone(result)
        self.assertEqual(result["wind_direction_deg"], 270.0)
        self.assertEqual(result["wind_speed_kt"], 35.0)
        self.assertEqual(result["altitude_ft"], 30000)
        self.assertEqual(result["icao"], "KJFK")

    def test_converts_cardinal_direction_to_degrees(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [{
                "forecast": [{
                    "wind": {
                        "direction": "WSW",
                        "speed_kts": 35,
                    }
                }]
            }]
        }
        with patch("weather_service._get_api_key", return_value="fake-key"), \
             patch("requests.get", return_value=mock_resp):
            result = get_winds_aloft("KJFK")

        self.assertIsNotNone(result)
        self.assertEqual(result["wind_direction_deg"], 247.5)

    def test_returns_none_when_no_forecast(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": [{"forecast": []}]}
        with patch("weather_service._get_api_key", return_value="fake-key"), \
             patch("requests.get", return_value=mock_resp):
            result = get_winds_aloft("KJFK")
        self.assertIsNone(result)

    def test_icao_uppercased(self):
        """ICAO code should be normalized to uppercase."""
        captured = {}

        def fake_get(url, **kwargs):
            captured["url"] = url
            mock = MagicMock()
            mock.status_code = 200
            mock.json.return_value = {"data": []}
            return mock

        with patch("weather_service._get_api_key", return_value="fake-key"), \
             patch("requests.get", side_effect=fake_get):
            get_winds_aloft("kjfk")

        self.assertIn("KJFK", captured.get("url", ""))


class TestGetAerodynamicPerformance(unittest.TestCase):
    """Integration-level tests for get_aerodynamic_performance()."""

    def _make_airports(self):
        return {
            "JFK": {
                "latitude": 40.6398,
                "longitude": -73.7789,
                "icao": "KJFK",
            },
            "LHR": {
                "latitude": 51.4775,
                "longitude": -0.4614,
                "icao": "EGLL",
            },
        }

    def test_returns_none_when_airport_not_found(self):
        with patch("weather_service._get_airports_by_iata", return_value={}):
            result = get_aerodynamic_performance("JFK", "LHR")
        self.assertIsNone(result)

    def test_returns_none_when_winds_aloft_unavailable(self):
        with patch("weather_service._get_airports_by_iata", return_value=self._make_airports()), \
             patch("weather_service.get_winds_aloft", return_value=None):
            result = get_aerodynamic_performance("JFK", "LHR")
        self.assertIsNone(result)

    def test_returns_full_dict_on_success(self):
        wind_data = {
            "wind_direction_deg": 270.0,
            "wind_speed_kt": 40.0,
            "altitude_ft": 30000,
            "source": "checkwx_taf",
            "icao": "KJFK",
        }
        with patch("weather_service._get_airports_by_iata", return_value=self._make_airports()), \
             patch("weather_service.get_winds_aloft", return_value=wind_data):
            result = get_aerodynamic_performance("JFK", "LHR")

        self.assertIsNotNone(result)
        required_keys = {
            "from_iata", "to_iata", "true_course_deg",
            "wind_direction_deg", "wind_speed_kt", "altitude_ft",
            "tas_kt", "wind_component_kt", "ground_speed_kt", "wind_type",
        }
        for key in required_keys:
            self.assertIn(key, result, f"Missing key: {key}")

    def test_wind_type_is_tailwind_or_headwind(self):
        wind_data = {
            "wind_direction_deg": 270.0,
            "wind_speed_kt": 40.0,
            "altitude_ft": 30000,
            "source": "checkwx_taf",
            "icao": "KJFK",
        }
        with patch("weather_service._get_airports_by_iata", return_value=self._make_airports()), \
             patch("weather_service.get_winds_aloft", return_value=wind_data):
            result = get_aerodynamic_performance("JFK", "LHR")
        self.assertIn(result["wind_type"], ("tailwind", "headwind"))


if __name__ == "__main__":
    unittest.main()
