from unittest.mock import MagicMock

import requests

from serpapi_service import SerpApiService


def _mock_response(payload: dict, status_code: int = 200) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


def test_serpapi_search_uses_lru_cache(monkeypatch):
    service = SerpApiService(api_key="test-key")
    service._search_flights_cached.cache_clear()

    payload = {
        "search_metadata": {"google_flights_url": "https://www.google.com/travel/flights"},
        "best_flights": [
            {
                "price": 200,
                "total_duration": 180,
                "flights": [
                    {
                        "airline": "United",
                        "flight_number": "UA 100",
                        "departure_airport": {"time": "2026-07-01T10:00:00Z"},
                        "arrival_airport": {"time": "2026-07-01T13:00:00Z"},
                    }
                ],
            }
        ],
    }
    response = _mock_response(payload)
    request_mock = MagicMock(return_value=response)
    monkeypatch.setattr(requests, "get", request_mock)

    first = service.search_flights("JFK", "LAX", "2026-07-01", currency="USD")
    second = service.search_flights("JFK", "LAX", "2026-07-01", currency="USD")

    assert len(first) == 1
    assert second == first
    assert request_mock.call_count == 1


def test_serpapi_maps_google_flights_url_to_booking_link(monkeypatch):
    service = SerpApiService(api_key="test-key")
    service._search_flights_cached.cache_clear()
    google_url = "https://www.google.com/travel/flights/search"
    payload = {
        "search_metadata": {"google_flights_url": google_url},
        "other_flights": [
            {
                "price": 123,
                "total_duration": 95,
                "flights": [
                    {
                        "airline": "Delta Air Lines",
                        "flight_number": "DL 12",
                        "departure_airport": {"time": "2026-07-02T08:00:00Z"},
                        "arrival_airport": {"time": "2026-07-02T09:35:00Z"},
                    }
                ],
            }
        ],
    }
    monkeypatch.setattr(requests, "get", MagicMock(return_value=_mock_response(payload)))

    offers = service.search_flights("JFK", "BOS", "2026-07-02", currency="USD")

    assert offers[0]["booking_link"] == google_url
    assert offers[0]["booking_url"] == google_url


def test_serpapi_returns_empty_list_on_http_error(monkeypatch):
    service = SerpApiService(api_key="test-key")
    service._search_flights_cached.cache_clear()
    response = _mock_response({}, status_code=500)
    response.raise_for_status.side_effect = requests.HTTPError("server error", response=response)
    monkeypatch.setattr(requests, "get", MagicMock(return_value=response))

    offers = service.search_flights("JFK", "SFO", "2026-07-03", currency="USD")

    assert offers == []
