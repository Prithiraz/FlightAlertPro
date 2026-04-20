import asyncio
from unittest.mock import MagicMock

import search
from search import FlightSegment, PassengerCount, SearchRequest


def test_search_amadeus_skips_when_circuit_open(monkeypatch):
    segment = FlightSegment(from_iata="JFK", to_iata="LAX", departure_date="2026-06-01")
    request = SearchRequest(
        segments=[segment],
        passengers=PassengerCount(adults=1),
        cabin_class="economy",
        currency="USD",
    )

    monkeypatch.setattr(search, "check_circuit_breaker", lambda supplier: False)

    results = asyncio.run(search.search_amadeus(segment, request))
    assert results == []


def test_search_amadeus_maps_return_leg_and_passengers(monkeypatch):
    outbound = FlightSegment(from_iata="JFK", to_iata="LAX", departure_date="2026-06-01")
    inbound = FlightSegment(from_iata="LAX", to_iata="JFK", departure_date="2026-06-10")
    request = SearchRequest(
        segments=[outbound, inbound],
        passengers=PassengerCount(adults=2),
        cabin_class="business",
        currency="EUR",
    )

    fake_service = MagicMock()
    fake_service.enabled = True
    fake_service.search_flights.return_value = [{"id": "offer-1"}]

    monkeypatch.setattr(search, "check_circuit_breaker", lambda supplier: True)
    monkeypatch.setattr(search, "record_success", lambda supplier: None)
    monkeypatch.setattr(search, "record_failure", lambda supplier: None)
    monkeypatch.setattr(search, "amadeus_service", fake_service)

    results = asyncio.run(search.search_amadeus(outbound, request))

    assert results == [{"id": "offer-1"}]
    fake_service.search_flights.assert_called_once_with(
        from_iata="JFK",
        to_iata="LAX",
        departure_date="2026-06-01",
        return_date="2026-06-10",
        passengers=2,
        cabin_class="business",
        currency="EUR",
    )
