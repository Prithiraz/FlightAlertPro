import unittest
from unittest.mock import MagicMock, patch

from skyscanner_service import (
    SkyscannerProvider,
    calculate_haversine_distance,
    estimate_carbon_footprint,
)


class TestSkyscannerProvider(unittest.TestCase):
    def setUp(self):
        self.provider = SkyscannerProvider(api_key="test", api_host="sky-scrapper.p.rapidapi.com")

    def test_normalize_response_reconstructs_relational_payload(self):
        payload = {
            "data": {
                "itineraries": [
                    {
                        "id": "itin-1",
                        "outboundLegId": "leg-out",
                        "inboundLegId": "leg-in",
                        "pricingOptions": [
                            {
                                "price": {"amount": "199.99", "unit": "USD"},
                                "deeplinkUrl": "https://book.example.com/itin-1",
                            }
                        ],
                    }
                ],
                "legs": [
                    {
                        "id": "leg-out",
                        "originPlaceId": "p1",
                        "destinationPlaceId": "p2",
                        "departure": "2026-06-01T08:00:00Z",
                        "arrival": "2026-06-01T10:45:00Z",
                        "durationInMinutes": 165,
                        "stopCount": 0,
                        "carrierIds": ["c1"],
                        "segments": [
                            {
                                "originPlaceId": "p1",
                                "destinationPlaceId": "p2",
                                "departure": "2026-06-01T08:00:00Z",
                                "arrival": "2026-06-01T10:45:00Z",
                                "carrierIds": ["c1"],
                                "checkedBags": 1,
                            }
                        ],
                    },
                    {
                        "id": "leg-in",
                        "originPlaceId": "p2",
                        "destinationPlaceId": "p1",
                        "departure": "2026-06-10T14:00:00Z",
                        "arrival": "2026-06-10T17:30:00Z",
                        "durationInMinutes": 210,
                        "stopCount": 1,
                        "carrierIds": ["c1"],
                        "segments": [
                            {
                                "originPlaceId": "p2",
                                "destinationPlaceId": "p1",
                                "departure": "2026-06-10T14:00:00Z",
                                "arrival": "2026-06-10T17:30:00Z",
                                "carrierIds": ["c1"],
                            }
                        ],
                    },
                ],
                "carriers": [{"id": "c1", "name": "WestJet", "iata": "WS"}],
                "places": [
                    {"id": "p1", "name": "Los Angeles International", "displayCode": "LAX"},
                    {"id": "p2", "name": "John F Kennedy Intl", "displayCode": "JFK"},
                ],
            }
        }

        offers = self.provider._normalize_response(payload, trip_type="round_trip")
        self.assertEqual(len(offers), 1)

        offer = offers[0]
        self.assertEqual(offer["airline_name"], "WestJet")
        self.assertEqual(offer["airline_iata"], "WS")
        self.assertEqual(offer["price"], 199.99)
        self.assertEqual(offer["booking_url"], "https://book.example.com/itin-1")
        self.assertEqual(len(offer["slices"]), 2)
        self.assertEqual(offer["slices"][0]["origin_iata"], "LAX")
        self.assertEqual(offer["slices"][0]["destination_iata"], "JFK")
        self.assertEqual(offer["slices"][1]["origin_iata"], "JFK")
        self.assertEqual(offer["slices"][1]["destination_iata"], "LAX")

    def test_defaults_for_missing_duration_bags_and_deeplink(self):
        payload = {
            "data": {
                "itineraries": [{"id": "itin-2", "legIds": ["leg-out"], "pricingOptions": [{"price": {"amount": "120"}}]}],
                "legs": [
                    {
                        "id": "leg-out",
                        "originPlaceId": "p1",
                        "destinationPlaceId": "p2",
                        "departure": "2026-07-01T08:00:00Z",
                        "arrival": "2026-07-01T09:30:00Z",
                        "carrierIds": ["c1"],
                        "segments": [{"originPlaceId": "p1", "destinationPlaceId": "p2", "carrierIds": ["c1"]}],
                    }
                ],
                "carriers": [{"id": "c1", "name": "Airline A", "iataCode": "AA"}],
                "places": [
                    {"id": "p1", "displayCode": "YYZ"},
                    {"id": "p2", "displayCode": "YVR"},
                ],
            }
        }
        offers = self.provider._normalize_response(payload, trip_type="one_way")
        self.assertEqual(len(offers), 1)
        offer = offers[0]
        self.assertEqual(offer["booking_url"], "https://www.skyscanner.com")
        self.assertEqual(offer["slices"][0]["duration_minutes"], 90)
        self.assertEqual(offer["slices"][0]["segments"][0]["checked_bags"], 0)

    def test_builds_base_url_from_configured_host(self):
        provider = SkyscannerProvider(api_key="test", api_host="skyscanner-flights-travel-api.p.rapidapi.com")
        self.assertEqual(provider.base_url, "https://skyscanner-flights-travel-api.p.rapidapi.com")
        self.assertEqual(provider._headers()["X-RapidAPI-Host"], "skyscanner-flights-travel-api.p.rapidapi.com")
        self.assertEqual(provider.AIRPORT_SEARCH_ENDPOINT, "/flights/searchAirport")
        self.assertEqual(provider.FLIGHT_SEARCH_ENDPOINT, "/flights/searchFlights")

    def test_airport_identifiers_reads_first_place_item(self):
        client = MagicMock()
        response = MagicMock()
        response.json.return_value = {
            "places": [{"skyId": "LAXA", "entityId": "27536211"}]
        }
        client.get.return_value = response

        sky_id, entity_id = self.provider._airport_identifiers(client, "LAX")

        self.assertEqual(sky_id, "LAXA")
        self.assertEqual(entity_id, "27536211")

    def test_airport_identifiers_uses_first_place_item(self):
        client = MagicMock()
        response = MagicMock()
        response.json.return_value = {
            "places": [
                {"skyId": "JFKA", "entityId": "95565058"},
                {"skyId": "JFKB", "entityId": "95565059"},
            ]
        }
        client.get.return_value = response

        sky_id, entity_id = self.provider._airport_identifiers(client, "JFK")

        self.assertEqual(sky_id, "JFKA")
        self.assertEqual(entity_id, "95565058")

    @patch("skyscanner_service.logger.error")
    def test_airport_identifiers_logs_raw_response_text_on_lookup_failure(self, mock_error):
        client = MagicMock()
        response = MagicMock()
        response.json.return_value = {"places": []}
        response.text = '{"places":[]}'
        client.get.return_value = response

        sky_id, entity_id = self.provider._airport_identifiers(client, "ABC")

        self.assertIsNone(sky_id)
        self.assertIsNone(entity_id)
        mock_error.assert_called_once_with(
            "Skyscanner airport lookup failed for %s. Raw response: %s",
            "ABC",
            '{"places":[]}',
        )

    @patch("skyscanner_service.httpx.Client")
    def test_search_uses_configured_host_for_request_routing(self, client_cls):
        provider = SkyscannerProvider(api_key="test", api_host="https://skyscanner-flights-travel-api.p.rapidapi.com/")

        mock_client = MagicMock()
        client_cls.return_value.__enter__.return_value = mock_client
        provider._airport_identifiers = MagicMock(side_effect=[("LAX-sky", "95565050"), ("JFK-sky", "95565058")])
        provider._normalize_response = MagicMock(return_value=[{"id": "offer-1"}])

        mock_response = MagicMock()
        mock_response.json.return_value = {"data": {"itineraries": []}}
        mock_client.get.return_value = mock_response

        offers = provider.search_flights("LAX", "JFK", "2026-08-01")

        self.assertEqual(offers, [{"id": "offer-1"}])
        request_url = mock_client.get.call_args.args[0]
        self.assertTrue(request_url.startswith("https://skyscanner-flights-travel-api.p.rapidapi.com/"))
        self.assertIn("/flights/searchFlights", request_url)

    @patch("skyscanner_service.httpx.Client")
    def test_search_normalizes_non_list_itineraries_before_response_parsing(self, client_cls):
        provider = SkyscannerProvider(api_key="test", api_host="sky-scrapper.p.rapidapi.com")

        mock_client = MagicMock()
        client_cls.return_value.__enter__.return_value = mock_client
        provider._airport_identifiers = MagicMock(side_effect=[("LAX-sky", "95565050"), ("JFK-sky", "95565058")])
        provider._normalize_response = MagicMock(return_value=[])

        mock_response = MagicMock()
        mock_response.json.return_value = {"data": {"itineraries": "unexpected-shape", "context": {"currency": "USD"}}}
        mock_client.get.return_value = mock_response

        provider.search_flights("LAX", "JFK", "2026-08-01")

        provider._normalize_response.assert_called_once_with(
            {"data": {"itineraries": [], "context": {"currency": "USD"}}},
            trip_type="one_way",
        )

    @patch("skyscanner_service.httpx.Client")
    def test_search_supports_top_level_itineraries_payload(self, client_cls):
        provider = SkyscannerProvider(api_key="test", api_host="sky-scrapper.p.rapidapi.com")

        mock_client = MagicMock()
        client_cls.return_value.__enter__.return_value = mock_client
        provider._airport_identifiers = MagicMock(side_effect=[("LAXA", "27536211"), ("JFKA", "95565058")])
        provider._normalize_response = MagicMock(return_value=[])

        mock_response = MagicMock()
        mock_response.json.return_value = {"itineraries": [], "context": {"currency": "USD"}}
        mock_client.get.return_value = mock_response

        provider.search_flights("LAX", "JFK", "2026-08-01")

        provider._normalize_response.assert_called_once_with(
            {"data": {"itineraries": [], "context": {"currency": "USD"}}},
            trip_type="one_way",
        )

    @patch("skyscanner_service.httpx.Client")
    def test_search_logs_raw_response_when_itineraries_empty(self, client_cls):
        provider = SkyscannerProvider(api_key="test", api_host="sky-scrapper.p.rapidapi.com")

        mock_client = MagicMock()
        client_cls.return_value.__enter__.return_value = mock_client
        provider._airport_identifiers = MagicMock(side_effect=[("LAXA", "27536211"), ("JFKA", "95565058")])
        provider._normalize_response = MagicMock(return_value=[])

        mock_response = MagicMock()
        mock_response.json.return_value = {"data": {"itineraries": [], "context": {"currency": "USD"}}}
        mock_response.text = '{"data":{"itineraries":[],"context":{"currency":"USD"}}}'
        mock_client.get.return_value = mock_response

        with patch("skyscanner_service.logger.debug") as mock_debug, patch("skyscanner_service.logger.error") as mock_error:
            provider.search_flights("LAX", "JFK", "2026-08-01")

        mock_debug.assert_called_once()
        mock_error.assert_called_once_with(
            'Flight search raw response: {"data":{"itineraries":[],"context":{"currency":"USD"}}}'
        )

    # ── Phase 1: Haversine distance ──────────────────────────────────────────

    def test_haversine_distance_lhr_jfk(self):
        # LHR: 51.4706, -0.461941  |  JFK: 40.63980103, -73.77890015
        dist = calculate_haversine_distance(51.4706, -0.461941, 40.63980103, -73.77890015)
        # Great-circle distance is approximately 5,540 km
        self.assertGreater(dist, 5_000)
        self.assertLess(dist, 6_000)

    def test_haversine_distance_same_point_is_zero(self):
        self.assertAlmostEqual(calculate_haversine_distance(0.0, 0.0, 0.0, 0.0), 0.0, places=4)

    def test_efficiency_score_in_offer(self):
        """Offers for known IATA pairs must include a numeric efficiency_score."""
        payload = {
            "data": {
                "itineraries": [
                    {
                        "id": "itin-eff",
                        "outboundLegId": "leg-out",
                        "pricingOptions": [{"price": {"amount": "300", "unit": "USD"}}],
                    }
                ],
                "legs": [
                    {
                        "id": "leg-out",
                        "originPlaceId": "p1",
                        "destinationPlaceId": "p2",
                        "departure": "2026-09-01T08:00:00Z",
                        "arrival": "2026-09-01T16:00:00Z",
                        "durationInMinutes": 480,
                        "stopCount": 0,
                        "carrierIds": ["c1"],
                        "segments": [],
                    }
                ],
                "carriers": [{"id": "c1", "name": "Test Airline", "iata": "TA"}],
                "places": [
                    {"id": "p1", "displayCode": "LAX"},
                    {"id": "p2", "displayCode": "JFK"},
                ],
            }
        }
        offers = self.provider._normalize_response(payload, trip_type="one_way")
        self.assertEqual(len(offers), 1)
        offer = offers[0]
        self.assertIn("efficiency_score", offer)
        self.assertIn("gcd_distance", offer)
        self.assertIn("gcd_km", offer)
        self.assertIn("efficiency_pct", offer)
        self.assertIsInstance(offer["efficiency_score"], float)
        # LAX→JFK coords are known; efficiency = GCD / (GCD + 100).
        gcd = offer["gcd_distance"]
        self.assertIsNotNone(gcd)
        expected = round(gcd / (gcd + 100), 4)
        self.assertAlmostEqual(offer["efficiency_score"], expected, places=4)
        # gcd_km is an alias for gcd_distance
        self.assertEqual(offer["gcd_km"], gcd)
        # efficiency_pct is efficiency_score * 100
        self.assertAlmostEqual(offer["efficiency_pct"], round(expected * 100, 2), places=2)
        # Efficiency must be strictly less than 1 (route overhead > 0)
        self.assertLess(offer["efficiency_score"], 1.0)

    def test_efficiency_score_fallback_for_unknown_iata(self):
        """Offers with unknown IATA codes fall back to the 1.1x-multiplier baseline."""
        payload = {
            "data": {
                "itineraries": [
                    {
                        "id": "itin-unk",
                        "outboundLegId": "leg-out",
                        "pricingOptions": [{"price": {"amount": "150", "unit": "USD"}}],
                    }
                ],
                "legs": [
                    {
                        "id": "leg-out",
                        "originPlaceId": "p1",
                        "destinationPlaceId": "p2",
                        "departure": "2026-09-01T08:00:00Z",
                        "arrival": "2026-09-01T10:00:00Z",
                        "durationInMinutes": 120,
                        "stopCount": 0,
                        "carrierIds": ["c1"],
                        "segments": [],
                    }
                ],
                "carriers": [{"id": "c1", "name": "Mystery Air", "iata": "MA"}],
                "places": [
                    {"id": "p1", "displayCode": "ZZZ"},
                    {"id": "p2", "displayCode": "XXX"},
                ],
            }
        }
        offers = self.provider._normalize_response(payload, trip_type="one_way")
        self.assertEqual(len(offers), 1)
        offer = offers[0]
        self.assertAlmostEqual(offer["efficiency_score"], round(1 / 1.1, 4), places=4)
        self.assertIsNone(offer["gcd_distance"])
        self.assertIsNone(offer["co2_emissions_kg"])
        # Alias fields must also be present
        self.assertIsNone(offer["gcd_km"])
        self.assertIsNone(offer["co2_kg"])
        self.assertAlmostEqual(offer["efficiency_pct"], round(round(1 / 1.1, 4) * 100, 2), places=2)

    # ── Carbon Footprint Engine ───────────────────────────────────────────────

    def test_carbon_footprint_short_haul(self):
        """Short-haul route (< 3700 km) uses 0.15 kg/km × 1.9 RF."""
        # 1000 km short-haul: 1000 × 0.15 × 1.9 = 285.0 kg
        result = estimate_carbon_footprint(1000.0)
        self.assertAlmostEqual(result, 285.0, places=4)

    def test_carbon_footprint_long_haul(self):
        """Long-haul route (≥ 3700 km) uses 0.11 kg/km × 1.9 RF."""
        # 10000 km long-haul: 10000 × 0.11 × 1.9 = 2090.0 kg
        result = estimate_carbon_footprint(10_000.0)
        self.assertAlmostEqual(result, 2090.0, places=4)

    def test_carbon_footprint_boundary_short_haul(self):
        """Route exactly at 3,699 km is short-haul."""
        result = estimate_carbon_footprint(3699.0)
        self.assertAlmostEqual(result, 3699.0 * 0.15 * 1.9, places=4)

    def test_carbon_footprint_boundary_long_haul(self):
        """Route at exactly 3,700 km is long-haul."""
        result = estimate_carbon_footprint(3700.0)
        self.assertAlmostEqual(result, 3700.0 * 0.11 * 1.9, places=4)

    def test_co2_in_offer_known_iata(self):
        """Offers for known IATA pairs must include a non-None co2_emissions_kg."""
        payload = {
            "data": {
                "itineraries": [
                    {
                        "id": "itin-co2",
                        "outboundLegId": "leg-out",
                        "pricingOptions": [{"price": {"amount": "250", "unit": "USD"}}],
                    }
                ],
                "legs": [
                    {
                        "id": "leg-out",
                        "originPlaceId": "p1",
                        "destinationPlaceId": "p2",
                        "departure": "2026-09-01T08:00:00Z",
                        "arrival": "2026-09-01T16:00:00Z",
                        "durationInMinutes": 480,
                        "stopCount": 0,
                        "carrierIds": ["c1"],
                        "segments": [],
                    }
                ],
                "carriers": [{"id": "c1", "name": "Test Airline", "iata": "TA"}],
                "places": [
                    {"id": "p1", "displayCode": "LAX"},
                    {"id": "p2", "displayCode": "JFK"},
                ],
            }
        }
        offers = self.provider._normalize_response(payload, trip_type="one_way")
        self.assertEqual(len(offers), 1)
        offer = offers[0]
        self.assertIn("co2_emissions_kg", offer)
        self.assertIn("co2_kg", offer)
        self.assertIsNotNone(offer["co2_emissions_kg"])
        self.assertIsInstance(offer["co2_emissions_kg"], float)
        # LAX→JFK is ~3975 km (long-haul): 3975 × 0.11 × 1.9
        gcd = offer["gcd_distance"]
        expected_co2 = round(estimate_carbon_footprint(gcd), 2)
        self.assertAlmostEqual(offer["co2_emissions_kg"], expected_co2, places=2)
        # co2_kg is an alias for co2_emissions_kg
        self.assertEqual(offer["co2_kg"], offer["co2_emissions_kg"])

    # ── UTC standardisation ───────────────────────────────────────────────────

    def test_to_utc_iso_converts_offset_to_utc(self):
        result = SkyscannerProvider._to_utc_iso("2026-06-01T10:00:00+02:00")
        self.assertEqual(result, "2026-06-01T08:00:00+00:00")

    def test_to_utc_iso_passes_through_utc_unchanged(self):
        result = SkyscannerProvider._to_utc_iso("2026-06-01T08:00:00+00:00")
        self.assertEqual(result, "2026-06-01T08:00:00+00:00")

    def test_to_utc_iso_naive_datetime_treated_as_utc(self):
        result = SkyscannerProvider._to_utc_iso("2026-06-01T08:00:00")
        self.assertEqual(result, "2026-06-01T08:00:00+00:00")

    def test_to_utc_iso_z_suffix_converted(self):
        result = SkyscannerProvider._to_utc_iso("2026-06-01T08:00:00Z")
        self.assertEqual(result, "2026-06-01T08:00:00+00:00")

    def test_build_slice_stores_utc_times(self):
        """departure_time and arrival_time in built slices must be UTC ISO strings."""
        payload = {
            "data": {
                "itineraries": [
                    {
                        "id": "itin-utc",
                        "outboundLegId": "leg-out",
                        "pricingOptions": [{"price": {"amount": "200", "unit": "USD"}}],
                    }
                ],
                "legs": [
                    {
                        "id": "leg-out",
                        "originPlaceId": "p1",
                        "destinationPlaceId": "p2",
                        # +05:30 offset → UTC 02:30
                        "departure": "2026-09-01T08:00:00+05:30",
                        "arrival": "2026-09-01T12:00:00+05:30",
                        "durationInMinutes": 240,
                        "stopCount": 0,
                        "carrierIds": ["c1"],
                        "segments": [],
                    }
                ],
                "carriers": [{"id": "c1", "name": "Test Air", "iata": "TA"}],
                "places": [
                    {"id": "p1", "displayCode": "BOM"},
                    {"id": "p2", "displayCode": "DEL"},
                ],
            }
        }
        offers = self.provider._normalize_response(payload, trip_type="one_way")
        self.assertEqual(len(offers), 1)
        dep = offers[0]["slices"][0]["departure_time"]
        arr = offers[0]["slices"][0]["arrival_time"]
        self.assertEqual(dep, "2026-09-01T02:30:00+00:00")
        self.assertEqual(arr, "2026-09-01T06:30:00+00:00")

    # ── Round-trip stitching & itinerary validation ───────────────────────────

    def test_is_valid_itinerary_accepts_correct_pairing(self):
        outbound = {"arrival_time": "2026-06-01T10:00:00+00:00"}
        inbound = {"departure_time": "2026-06-10T08:00:00+00:00"}
        self.assertTrue(SkyscannerProvider.is_valid_itinerary(outbound, inbound))

    def test_is_valid_itinerary_rejects_impossible_pairing(self):
        outbound = {"arrival_time": "2026-06-10T15:00:00+00:00"}
        inbound = {"departure_time": "2026-06-10T08:00:00+00:00"}
        self.assertFalse(SkyscannerProvider.is_valid_itinerary(outbound, inbound))

    def test_is_valid_itinerary_allows_same_time(self):
        outbound = {"arrival_time": "2026-06-01T10:00:00+00:00"}
        inbound = {"departure_time": "2026-06-01T10:00:00+00:00"}
        self.assertTrue(SkyscannerProvider.is_valid_itinerary(outbound, inbound))

    def test_is_valid_itinerary_missing_times_are_accepted(self):
        self.assertTrue(SkyscannerProvider.is_valid_itinerary({}, {}))

    def test_invalid_round_trip_itinerary_is_discarded(self):
        """Itineraries where outbound arrives after inbound departs must be dropped."""
        payload = {
            "data": {
                "itineraries": [
                    {
                        "id": "itin-bad",
                        "outboundLegId": "leg-out",
                        "inboundLegId": "leg-in",
                        "pricingOptions": [{"price": {"amount": "500", "unit": "USD"}}],
                    }
                ],
                "legs": [
                    {
                        "id": "leg-out",
                        "originPlaceId": "p1",
                        "destinationPlaceId": "p2",
                        "departure": "2026-06-10T06:00:00Z",
                        "arrival": "2026-06-10T20:00:00Z",  # arrives after inbound departs
                        "durationInMinutes": 840,
                        "stopCount": 0,
                        "carrierIds": ["c1"],
                        "segments": [],
                    },
                    {
                        "id": "leg-in",
                        "originPlaceId": "p2",
                        "destinationPlaceId": "p1",
                        "departure": "2026-06-10T08:00:00Z",  # departs before outbound arrives
                        "arrival": "2026-06-10T18:00:00Z",
                        "durationInMinutes": 600,
                        "stopCount": 0,
                        "carrierIds": ["c1"],
                        "segments": [],
                    },
                ],
                "carriers": [{"id": "c1", "name": "Test Air", "iata": "TA"}],
                "places": [
                    {"id": "p1", "displayCode": "LAX"},
                    {"id": "p2", "displayCode": "JFK"},
                ],
            }
        }
        offers = self.provider._normalize_response(payload, trip_type="round_trip")
        self.assertEqual(len(offers), 0)

    def test_valid_round_trip_itinerary_is_kept(self):
        """Valid round-trip pairings produce an itinerary with two slices."""
        payload = {
            "data": {
                "itineraries": [
                    {
                        "id": "itin-ok",
                        "outboundLegId": "leg-out",
                        "inboundLegId": "leg-in",
                        "pricingOptions": [{"price": {"amount": "600", "unit": "USD"}}],
                    }
                ],
                "legs": [
                    {
                        "id": "leg-out",
                        "originPlaceId": "p1",
                        "destinationPlaceId": "p2",
                        "departure": "2026-06-01T08:00:00Z",
                        "arrival": "2026-06-01T16:00:00Z",
                        "durationInMinutes": 480,
                        "stopCount": 0,
                        "carrierIds": ["c1"],
                        "segments": [],
                    },
                    {
                        "id": "leg-in",
                        "originPlaceId": "p2",
                        "destinationPlaceId": "p1",
                        "departure": "2026-06-10T10:00:00Z",
                        "arrival": "2026-06-10T18:00:00Z",
                        "durationInMinutes": 480,
                        "stopCount": 0,
                        "carrierIds": ["c1"],
                        "segments": [],
                    },
                ],
                "carriers": [{"id": "c1", "name": "Test Air", "iata": "TA"}],
                "places": [
                    {"id": "p1", "displayCode": "LAX"},
                    {"id": "p2", "displayCode": "JFK"},
                ],
            }
        }
        offers = self.provider._normalize_response(payload, trip_type="round_trip")
        self.assertEqual(len(offers), 1)
        self.assertEqual(len(offers[0]["slices"]), 2)
        self.assertEqual(offers[0]["slices"][0]["origin_iata"], "LAX")
        self.assertEqual(offers[0]["slices"][1]["origin_iata"], "JFK")

    # ── Data Contract: gcd_km / co2_kg / efficiency_pct ──────────────────────

    def test_data_contract_fields_present_known_iata(self):
        """Every offer for a known IATA pair must expose gcd_km, co2_kg, efficiency_pct."""
        payload = {
            "data": {
                "itineraries": [
                    {
                        "id": "itin-dc",
                        "outboundLegId": "leg-out",
                        "pricingOptions": [{"price": {"amount": "350", "unit": "USD"}}],
                    }
                ],
                "legs": [
                    {
                        "id": "leg-out",
                        "originPlaceId": "p1",
                        "destinationPlaceId": "p2",
                        "departure": "2026-10-01T09:00:00Z",
                        "arrival": "2026-10-01T14:00:00Z",
                        "durationInMinutes": 300,
                        "stopCount": 0,
                        "carrierIds": ["c1"],
                        "segments": [],
                    }
                ],
                "carriers": [{"id": "c1", "name": "Test Carrier", "iata": "TC"}],
                "places": [
                    {"id": "p1", "displayCode": "LAX"},
                    {"id": "p2", "displayCode": "JFK"},
                ],
            }
        }
        offers = self.provider._normalize_response(payload, trip_type="one_way")
        self.assertEqual(len(offers), 1)
        offer = offers[0]

        # gcd_km must be present and equal to gcd_distance
        self.assertIn("gcd_km", offer)
        self.assertIsNotNone(offer["gcd_km"])
        self.assertEqual(offer["gcd_km"], offer["gcd_distance"])

        # co2_kg must be present and equal to co2_emissions_kg
        self.assertIn("co2_kg", offer)
        self.assertIsNotNone(offer["co2_kg"])
        self.assertEqual(offer["co2_kg"], offer["co2_emissions_kg"])

        # efficiency_pct must be present and equal to efficiency_score × 100
        self.assertIn("efficiency_pct", offer)
        self.assertIsInstance(offer["efficiency_pct"], float)
        self.assertAlmostEqual(
            offer["efficiency_pct"], round(offer["efficiency_score"] * 100, 2), places=4
        )

    def test_data_contract_fields_present_unknown_iata(self):
        """Every offer, even with unknown IATA codes, exposes gcd_km, co2_kg, efficiency_pct."""
        payload = {
            "data": {
                "itineraries": [
                    {
                        "id": "itin-dc-unk",
                        "outboundLegId": "leg-out",
                        "pricingOptions": [{"price": {"amount": "100", "unit": "USD"}}],
                    }
                ],
                "legs": [
                    {
                        "id": "leg-out",
                        "originPlaceId": "p1",
                        "destinationPlaceId": "p2",
                        "departure": "2026-10-01T09:00:00Z",
                        "arrival": "2026-10-01T11:00:00Z",
                        "durationInMinutes": 120,
                        "stopCount": 0,
                        "carrierIds": ["c1"],
                        "segments": [],
                    }
                ],
                "carriers": [{"id": "c1", "name": "Ghost Air", "iata": "GA"}],
                "places": [
                    {"id": "p1", "displayCode": "ZZZ"},
                    {"id": "p2", "displayCode": "XXX"},
                ],
            }
        }
        offers = self.provider._normalize_response(payload, trip_type="one_way")
        self.assertEqual(len(offers), 1)
        offer = offers[0]

        # gcd_km and co2_kg are None for unknown airports
        self.assertIn("gcd_km", offer)
        self.assertIsNone(offer["gcd_km"])
        self.assertIn("co2_kg", offer)
        self.assertIsNone(offer["co2_kg"])

        # efficiency_pct is the fallback value × 100
        self.assertIn("efficiency_pct", offer)
        self.assertAlmostEqual(
            offer["efficiency_pct"], round(offer["efficiency_score"] * 100, 2), places=4
        )
