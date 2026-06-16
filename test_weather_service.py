"""Tests for Phase 3 aerodynamic wind-component additions in weather_service.py."""
import math
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from weather_service import (
    _calculate_true_course,
    _inverse_standard_normal_cdf,
    calculate_adsb_aerodynamics,
    calculate_confidence_interval,
    calculate_dispatch_time,
    calculate_optimal_dispatch,
    calculate_ready_time_window,
    calculate_energy_height,
    calculate_wind_component,
    get_aerodynamic_performance,
    get_operational_performance_advisory,
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

    def test_departure_performance_falls_back_to_isa_when_metar_missing(self):
        from weather_service import get_departure_performance
        fake_ad = {
            "LHR": {"icao": "EGLL", "elevation": 83.0, "name": "London Heathrow Airport"}
        }
        with patch("weather_service._get_airportsdata", return_value=fake_ad), \
             patch("weather_service._get_airports_by_iata", return_value={}), \
             patch("weather_service.get_metar_data", return_value=None):
            result = get_departure_performance("LHR")

        self.assertIsNotNone(result)
        self.assertEqual(result["temperature_c"], 15.0)
        self.assertEqual(result["altimeter_in_hg"], 29.92)
        self.assertIn("density_altitude_ft", result)

    def test_departure_performance_falls_back_to_isa_for_missing_pressure(self):
        from weather_service import get_departure_performance
        fake_ad = {
            "LHR": {"icao": "EGLL", "elevation": 83.0, "name": "London Heathrow Airport"}
        }
        fake_metar = {
            "temperature_c": 21.0,
            "altimeter_in_hg": None,
            "icao": "EGLL",
            "raw_text": "",
        }
        with patch("weather_service._get_airportsdata", return_value=fake_ad), \
             patch("weather_service._get_airports_by_iata", return_value={}), \
             patch("weather_service.get_metar_data", return_value=fake_metar):
            result = get_departure_performance("LHR")

        self.assertIsNotNone(result)
        self.assertEqual(result["temperature_c"], 21.0)
        self.assertEqual(result["altimeter_in_hg"], 29.92)
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


class TestCalculateAdsbAerodynamics(unittest.TestCase):
    """Unit tests for calculate_adsb_aerodynamics()."""

    def test_returns_required_fields(self):
        result = calculate_adsb_aerodynamics(altitude_ft=32000, ground_speed_kt=430, heading_deg=87)
        required_keys = {
            "heading_deg",
            "ground_speed_kt",
            "tas_kt",
            "wind_component_kt",
            "wind_type",
            "density_altitude_ft",
            "co2_burn_rate_kg_min",
            "logistics_eta_min",
        }
        for key in required_keys:
            self.assertIn(key, result)

    def test_rejects_non_numeric_inputs(self):
        with self.assertRaises(ValueError):
            calculate_adsb_aerodynamics(altitude_ft="high", ground_speed_kt=420, heading_deg=90)

    def test_heading_normalized_to_0_360(self):
        result = calculate_adsb_aerodynamics(altitude_ft=5000, ground_speed_kt=220, heading_deg=725)
        self.assertGreaterEqual(result["heading_deg"], 0.0)
        self.assertLess(result["heading_deg"], 360.0)

    def test_includes_operational_milestone_fields(self):
        result = calculate_adsb_aerodynamics(altitude_ft=32000, ground_speed_kt=430, heading_deg=87)
        self.assertIn("energy_height_ft", result)
        self.assertIn("confidence_interval_min", result)
        self.assertIn("operational_performance_advisory", result)
        self.assertGreaterEqual(result["confidence_interval_min"], 1)
        self.assertIn("severity", result["operational_performance_advisory"])


class TestCalculateConfidenceInterval(unittest.TestCase):
    """Unit tests for calculate_confidence_interval()."""

    def test_returns_positive_integer(self):
        result = calculate_confidence_interval(eta_minutes=40)
        self.assertIsInstance(result, int)
        self.assertGreaterEqual(result, 1)

    def test_widens_with_longer_horizon(self):
        short = calculate_confidence_interval(eta_minutes=10)
        long = calculate_confidence_interval(eta_minutes=120)
        self.assertGreater(long, short)

    def test_widens_with_wind_and_staleness(self):
        calm = calculate_confidence_interval(eta_minutes=40, wind_component_kt=0, data_age_seconds=0)
        windy = calculate_confidence_interval(eta_minutes=40, wind_component_kt=120, data_age_seconds=300)
        self.assertGreater(windy, calm)

    def test_floor_is_one_minute(self):
        self.assertEqual(calculate_confidence_interval(eta_minutes=0), 1)


class TestCalculateDispatchTime(unittest.TestCase):
    """Unit tests for calculate_dispatch_time()."""

    def test_dispatch_is_on_block_minus_drive(self):
        touchdown = datetime(2026, 6, 15, 15, 0)
        # on_block = 15:08, dispatch = on_block - 35 = 14:33
        result = calculate_dispatch_time(touchdown, taxi_time=8, drive_time=35)
        self.assertEqual(result, datetime(2026, 6, 15, 14, 33))

    def test_seconds_are_truncated(self):
        touchdown = datetime(2026, 6, 15, 15, 0, 42)
        result = calculate_dispatch_time(touchdown, taxi_time=10, drive_time=10)
        self.assertEqual(result.second, 0)
        self.assertEqual(result.microsecond, 0)

    def test_rejects_non_datetime(self):
        with self.assertRaises(TypeError):
            calculate_dispatch_time("15:00", taxi_time=8, drive_time=35)


class TestOperationalPerformanceAdvisory(unittest.TestCase):
    """Unit tests for get_operational_performance_advisory()."""

    def test_high_severity_above_3500(self):
        advisory = get_operational_performance_advisory(35000, reference_altitude_ft=30000)
        self.assertEqual(advisory["severity"], "HIGH")
        self.assertEqual(advisory["status"], "ADVISORY")

    def test_moderate_severity(self):
        advisory = get_operational_performance_advisory(32500, reference_altitude_ft=30000)
        self.assertEqual(advisory["severity"], "MODERATE")
        self.assertEqual(advisory["status"], "ADVISORY")

    def test_nominal_when_within_limits(self):
        advisory = get_operational_performance_advisory(31000, reference_altitude_ft=30000)
        self.assertEqual(advisory["severity"], "LOW")
        self.assertEqual(advisory["status"], "NOMINAL")


class TestCalculateEnergyHeight(unittest.TestCase):
    """Unit tests for calculate_energy_height()."""

    def test_static_aircraft_equals_altitude(self):
        self.assertEqual(calculate_energy_height(10000, 0), 10000.0)

    def test_speed_increases_energy_height(self):
        self.assertGreater(
            calculate_energy_height(10000, 400),
            calculate_energy_height(10000, 0),
        )


class TestCalculateOptimalDispatch(unittest.TestCase):
    """Financial-risk (newsvendor) dispatch optimisation."""

    def setUp(self):
        self.base = datetime(2026, 6, 15, 17, 0)

    def test_symmetric_costs_aim_at_median(self):
        result = calculate_optimal_dispatch(self.base, 10, 1.0, 1.0)
        self.assertEqual(result["buffer_minutes"], 0)
        self.assertEqual(result["recommended_dispatch_time"], self.base)
        self.assertAlmostEqual(result["critical_fractile"], 0.5, places=3)

    def test_high_late_cost_shifts_earlier(self):
        result = calculate_optimal_dispatch(self.base, 10, 1.0, 10.0)
        self.assertGreater(result["buffer_minutes"], 0)
        self.assertLess(result["recommended_dispatch_time"], self.base)
        self.assertLess(result["z_score"], 0)

    def test_higher_uncertainty_shifts_even_earlier(self):
        low = calculate_optimal_dispatch(self.base, 10, 1.0, 10.0)
        high = calculate_optimal_dispatch(self.base, 30, 1.0, 10.0)
        self.assertGreater(high["buffer_minutes"], low["buffer_minutes"])

    def test_high_wait_cost_shifts_later(self):
        result = calculate_optimal_dispatch(self.base, 10, 10.0, 1.0)
        self.assertGreater(result["recommended_dispatch_time"], self.base)
        self.assertGreater(result["z_score"], 0)

    def test_zero_uncertainty_has_no_buffer(self):
        result = calculate_optimal_dispatch(self.base, 0, 1.0, 10.0)
        self.assertEqual(result["buffer_minutes"], 0)
        self.assertEqual(result["recommended_dispatch_time"], self.base)

    def test_zero_costs_default_to_median(self):
        result = calculate_optimal_dispatch(self.base, 10, 0.0, 0.0)
        self.assertAlmostEqual(result["critical_fractile"], 0.5, places=3)
        self.assertEqual(result["buffer_minutes"], 0)


class TestReadyTimeWindow(unittest.TestCase):
    """Probabilistic ready-time range instead of an exact ETA."""

    def setUp(self):
        self.base = datetime(2026, 6, 15, 17, 0)

    def test_median_equals_expected(self):
        w = calculate_ready_time_window(self.base, 10, 0.80)
        self.assertEqual(w["median_ready_time"], self.base)

    def test_80pct_band_is_symmetric_1_28_sigma(self):
        w = calculate_ready_time_window(self.base, 10, 0.80)
        self.assertEqual(w["half_width_minutes"], 13)  # round(1.2816 * 10)
        self.assertLess(w["confidence_interval_start"], w["median_ready_time"])
        self.assertGreater(w["confidence_interval_end"], w["median_ready_time"])

    def test_wider_confidence_widens_band(self):
        w80 = calculate_ready_time_window(self.base, 10, 0.80)
        w95 = calculate_ready_time_window(self.base, 10, 0.95)
        self.assertGreater(w95["half_width_minutes"], w80["half_width_minutes"])


class TestInverseNormalCdf(unittest.TestCase):
    def test_known_quantiles(self):
        self.assertAlmostEqual(_inverse_standard_normal_cdf(0.5), 0.0, places=4)
        self.assertAlmostEqual(_inverse_standard_normal_cdf(0.9), 1.2816, places=3)
        self.assertAlmostEqual(_inverse_standard_normal_cdf(0.975), 1.9600, places=3)
        self.assertAlmostEqual(
            _inverse_standard_normal_cdf(0.1),
            -_inverse_standard_normal_cdf(0.9),
            places=4,
        )


if __name__ == "__main__":
    unittest.main()
