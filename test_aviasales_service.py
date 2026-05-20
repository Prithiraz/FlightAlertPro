import aviasales_service


def test_search_cached_flights_returns_empty_list_on_request_failure(monkeypatch):
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "token")

    def _raise(*args, **kwargs):
        raise aviasales_service.requests.RequestException("network down")

    monkeypatch.setattr(aviasales_service.requests, "get", _raise)

    results = aviasales_service.search_cached_flights("JFK", "LAX", currency="USD")

    assert results == []


def test_search_cached_flights_normalizes_booking_link(monkeypatch):
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "token")

    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "success": True,
                "data": {
                    "LAX": {
                        "price": 123,
                        "airline": "AA",
                        "flight_number": 100,
                        "departure_at": "2026-06-01T10:00:00Z",
                        "return_at": "2026-06-01T13:00:00Z",
                        "link": "/search/JFK0106LAX1",
                    }
                },
            }

    monkeypatch.setattr(aviasales_service.requests, "get", lambda *args, **kwargs: _Response())

    results = aviasales_service.search_cached_flights("JFK", "LAX", currency="USD")

    assert len(results) == 1
    assert results[0]["booking_link"] == "https://aviasales.com/search/JFK0106LAX1"
    assert results[0]["booking_url"] == "https://aviasales.com/search/JFK0106LAX1"
    assert results[0]["flight_number"] == "100"
