import unittest
from unittest.mock import patch, MagicMock

from weather_service import (
    calculate_density_altitude,
    assess_takeoff_risk,
    fetch_metar,
    get_density_altitude_data,
)


class TestCalculateDensityAltitude(unittest.TestCase):
    """Unit tests for the standard aerospace density-altitude formula."""

    def test_standard_sea_level_conditions(self):
        """At sea-level ISA conditions DA should equal elevation (0 ft)."""
        # elevation=0, altimeter=29.92 (standard), temp=15°C (ISA)
        da = calculate_density_altitude(
            elevation_ft=0.0,
            altimeter_inhg=29.92,
            temp_c=15.0,
        )
        self.assertAlmostEqual(da, 0.0, delta=1.0)

    def test_high_elevation_high_temp(self):
        """High elevation + hot day should produce a much higher density altitude."""
        # Denver-like: ~5400 ft elevation, alt=29.65 inHg, temp=35°C
        da = calculate_density_altitude(
            elevation_ft=5400.0,
            altimeter_inhg=29.65,
            temp_c=35.0,
        )
        # PA = 5400 + (29.92 - 29.65) * 1000 = 5400 + 270 = 5670
        # ISA = 15 - (2 * 5400 / 1000) = 15 - 10.8 = 4.2
        # DA = 5670 + 120 * (35 - 4.2) = 5670 + 3696 = 9366
        self.assertAlmostEqual(da, 9366.0, delta=1.0)

    def test_low_altimeter_raises_da(self):
        """Lower altimeter reading (low pressure) should raise pressure altitude."""
        da_low = calculate_density_altitude(
            elevation_ft=1000.0,
            altimeter_inhg=28.92,  # 1 inHg below standard
            temp_c=15.0,
        )
        da_std = calculate_density_altitude(
            elevation_ft=1000.0,
            altimeter_inhg=29.92,
            temp_c=15.0,
        )
        # Lower altimeter → higher pressure altitude → higher DA
        self.assertGreater(da_low, da_std)

    def test_cold_temperature_lowers_da(self):
        """Cold temperature should lower density altitude vs standard."""
        da_cold = calculate_density_altitude(
            elevation_ft=2000.0,
            altimeter_inhg=29.92,
            temp_c=-10.0,
        )
        da_isa = calculate_density_altitude(
            elevation_ft=2000.0,
            altimeter_inhg=29.92,
            temp_c=11.0,  # ISA at 2000 ft = 15 - (2*2) = 11
        )
        self.assertLess(da_cold, da_isa)

    def test_formula_components(self):
        """Verify each sub-formula step manually."""
        elevation_ft = 3000.0
        altimeter_inhg = 29.52
        temp_c = 30.0

        pa = elevation_ft + (29.92 - altimeter_inhg) * 1000  # 3000 + 400 = 3400
        isa = 15 - (2 * elevation_ft / 1000)               # 15 - 6 = 9
        expected_da = pa + 120 * (temp_c - isa)             # 3400 + 120*21 = 3400+2520 = 5920

        da = calculate_density_altitude(elevation_ft, altimeter_inhg, temp_c)
        self.assertAlmostEqual(da, expected_da, delta=1.0)


class TestAssessTakeoffRisk(unittest.TestCase):
    """Unit tests for the takeoff performance risk classifier."""

    def test_low_risk(self):
        self.assertEqual(assess_takeoff_risk(1500.0, 0.0), "LOW")
        self.assertEqual(assess_takeoff_risk(0.0, 0.0), "LOW")

    def test_moderate_risk_boundary(self):
        # Exactly 2000 ft above elevation → MODERATE
        self.assertEqual(assess_takeoff_risk(2000.0, 0.0), "MODERATE")
        self.assertEqual(assess_takeoff_risk(3499.0, 0.0), "MODERATE")

    def test_high_risk_boundary(self):
        # Exactly 3500 ft above elevation → HIGH
        self.assertEqual(assess_takeoff_risk(3500.0, 0.0), "HIGH")
        self.assertEqual(assess_takeoff_risk(5000.0, 0.0), "HIGH")

    def test_with_nonzero_elevation(self):
        # elevation = 4000 ft; DA = 6000 ft → delta = 2000 → MODERATE
        self.assertEqual(assess_takeoff_risk(6000.0, 4000.0), "MODERATE")
        # elevation = 4000 ft; DA = 7500 ft → delta = 3500 → HIGH
        self.assertEqual(assess_takeoff_risk(7500.0, 4000.0), "HIGH")
        # elevation = 4000 ft; DA = 5999 ft → delta = 1999 → LOW
        self.assertEqual(assess_takeoff_risk(5999.0, 4000.0), "LOW")


class TestFetchMetar(unittest.TestCase):
    """Unit tests for METAR API fetching."""

    @patch("weather_service.config")
    def test_returns_none_when_no_api_key(self, mock_config):
        mock_config.CHECKWX_API_KEY = None
        result = fetch_metar("LAX")
        self.assertIsNone(result)

    @patch("weather_service.requests.get")
    @patch("weather_service.config")
    def test_returns_none_on_http_error(self, mock_config, mock_get):
        mock_config.CHECKWX_API_KEY = "test-key"
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_get.return_value = mock_response
        result = fetch_metar("LAX")
        self.assertIsNone(result)

    @patch("weather_service.requests.get")
    @patch("weather_service.config")
    def test_parses_valid_metar_response(self, mock_config, mock_get):
        mock_config.CHECKWX_API_KEY = "test-key"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "temperature": {"celsius": 25},
                    "altimeter": {"inhg": 29.85},
                    "station": {
                        "elevation": {"meters": 300},
                        "geometry": {},
                    },
                }
            ]
        }
        mock_get.return_value = mock_response

        result = fetch_metar("DEN")
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result["temp_c"], 25.0)
        self.assertAlmostEqual(result["altimeter_inhg"], 29.85)
        self.assertAlmostEqual(result["elevation_ft"], round(300 * 3.28084, 0))

    @patch("weather_service.requests.get")
    @patch("weather_service.config")
    def test_returns_none_when_data_empty(self, mock_config, mock_get):
        mock_config.CHECKWX_API_KEY = "test-key"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}
        mock_get.return_value = mock_response

        result = fetch_metar("XYZ")
        self.assertIsNone(result)

    @patch("weather_service.requests.get")
    @patch("weather_service.config")
    def test_returns_none_on_request_exception(self, mock_config, mock_get):
        import requests as req
        mock_config.CHECKWX_API_KEY = "test-key"
        mock_get.side_effect = req.RequestException("timeout")
        result = fetch_metar("LAX")
        self.assertIsNone(result)


class TestGetDensityAltitudeData(unittest.TestCase):
    """Integration-style tests for the public helper."""

    @patch("weather_service.fetch_metar")
    def test_returns_none_tuple_when_metar_unavailable(self, mock_fetch):
        mock_fetch.return_value = None
        da, risk = get_density_altitude_data("LAX")
        self.assertIsNone(da)
        self.assertIsNone(risk)

    @patch("weather_service.fetch_metar")
    def test_computes_correct_da_and_risk(self, mock_fetch):
        # Denver-like scenario: high DA → HIGH risk
        mock_fetch.return_value = {
            "elevation_ft": 5434.0,
            "altimeter_inhg": 29.65,
            "temp_c": 38.0,
        }
        da, risk = get_density_altitude_data("DEN")
        self.assertIsNotNone(da)
        self.assertIsInstance(da, float)
        # DA should be well above elevation (high temp + slight low pressure)
        self.assertGreater(da, 5434.0 + 2000)
        self.assertEqual(risk, "HIGH")

    @patch("weather_service.fetch_metar")
    def test_low_risk_cool_conditions(self, mock_fetch):
        mock_fetch.return_value = {
            "elevation_ft": 0.0,
            "altimeter_inhg": 29.92,
            "temp_c": 5.0,  # Cool, below ISA at sea level (15°C)
        }
        da, risk = get_density_altitude_data("SFO")
        self.assertIsNotNone(da)
        self.assertEqual(risk, "LOW")


if __name__ == "__main__":
    unittest.main()
