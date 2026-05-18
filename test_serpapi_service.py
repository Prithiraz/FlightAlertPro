import json
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import requests

import serpapi_service
from serpapi_service import SerpApiService


def _mock_response(payload: dict, status_code: int = 200) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


def test_serpapi_search_uses_file_cache(monkeypatch, tmp_path):
    service = SerpApiService(api_key="test-key", cache_dir=str(tmp_path))
    monkeypatch.setattr(serpapi_service, "GoogleSearch", None)

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
    assert (tmp_path / "cache_flights_JFK_LAX_2026-07-01_USD.json").exists()


def test_serpapi_refreshes_when_file_cache_is_stale(monkeypatch, tmp_path):
    service = SerpApiService(api_key="test-key", cache_dir=str(tmp_path))
    monkeypatch.setattr(serpapi_service, "GoogleSearch", None)
    cache_path = tmp_path / "cache_flights_JFK_BOS_2026-07-02_USD.json"
    stale_payload = {
        "search_metadata": {"google_flights_url": "https://www.google.com/travel/flights/old"},
        "best_flights": [
            {
                "price": 300,
                "total_duration": 120,
                "flights": [
                    {
                        "airline": "Test",
                        "flight_number": "TS 10",
                        "departure_airport": {"time": "2026-07-02T08:00:00Z"},
                        "arrival_airport": {"time": "2026-07-02T10:00:00Z"},
                    }
                ],
            }
        ],
    }
    cache_path.write_text(json.dumps(stale_payload), encoding="utf-8")
    stale_time = datetime.now(timezone.utc) - timedelta(hours=25)
    cache_path.touch()
    os.utime(cache_path, (stale_time.timestamp(), stale_time.timestamp()))

    fresh_url = "https://www.google.com/travel/flights/fresh"
    fresh_payload = {
        "search_metadata": {"google_flights_url": fresh_url},
        "best_flights": [
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
    monkeypatch.setattr(requests, "get", MagicMock(return_value=_mock_response(fresh_payload)))

    offers = service.search_flights("JFK", "BOS", "2026-07-02", currency="USD")

    assert offers[0]["booking_link"] == fresh_url


def test_serpapi_maps_google_flights_url_to_booking_link(monkeypatch, tmp_path):
    service = SerpApiService(api_key="test-key", cache_dir=str(tmp_path))
    monkeypatch.setattr(serpapi_service, "GoogleSearch", None)
    google_url = "https://www.google.com/travel/flights/search"
    payload = {
        "search_metadata": {"google_flights_url": google_url},
        "best_flights": [
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


def test_serpapi_maps_booking_token_to_google_flights_link(monkeypatch, tmp_path):
    service = SerpApiService(api_key="test-key", cache_dir=str(tmp_path))
    monkeypatch.setattr(serpapi_service, "GoogleSearch", None)
    payload = {
        "best_flights": [
            {
                "price": 99,
                "total_duration": 90,
                "booking_token": "TOKEN123",
                "flights": [
                    {
                        "airline": "United",
                        "flight_number": "UA 777",
                        "departure_airport": {"time": "2026-07-04T08:00:00Z"},
                        "arrival_airport": {"time": "2026-07-04T09:30:00Z"},
                    }
                ],
            }
        ]
    }
    monkeypatch.setattr(requests, "get", MagicMock(return_value=_mock_response(payload)))

    offers = service.search_flights("JFK", "SFO", "2026-07-04", currency="USD")

    assert "TOKEN123" in offers[0]["booking_link"]
    assert offers[0]["booking_url"] == offers[0]["booking_link"]


def test_serpapi_returns_empty_list_on_http_error(monkeypatch, tmp_path):
    service = SerpApiService(api_key="test-key", cache_dir=str(tmp_path))
    monkeypatch.setattr(serpapi_service, "GoogleSearch", None)
    response = _mock_response({}, status_code=500)
    response.raise_for_status.side_effect = requests.HTTPError("server error", response=response)
    monkeypatch.setattr(requests, "get", MagicMock(return_value=response))

    offers = service.search_flights("JFK", "SFO", "2026-07-03", currency="USD")

    assert offers == []
