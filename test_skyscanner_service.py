import unittest
from unittest.mock import MagicMock, patch

from skyscanner_service import SkyscannerProvider


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
        self.assertIn("searchFlightsComplete", request_url)


if __name__ == "__main__":
    unittest.main()
