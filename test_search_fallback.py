import asyncio

import search
from search import FlightSegment, PassengerCount, SearchRequest


def _request() -> SearchRequest:
    return SearchRequest(
        segments=[FlightSegment(from_iata="JFK", to_iata="LAX", departure_date="2026-06-01")],
        passengers=PassengerCount(adults=1),
        cabin_class="economy",
        currency="USD",
    )


def _duffel_raw_offer() -> dict:
    return {
        "id": "off_123",
        "total_amount": "199.99",
        "total_currency": "USD",
        "slices": [
            {
                "segments": [
                    {
                        "origin": {"iata_code": "JFK"},
                        "destination": {"iata_code": "LAX"},
                        "departing_at": "2026-06-01T10:00:00Z",
                        "arriving_at": "2026-06-01T13:00:00Z",
                        "marketing_carrier": {"iata_code": "DL", "name": "Delta Air Lines"},
                    }
                ]
            }
        ],
    }


def _serpapi_offer() -> dict:
    return {
        "id": "serp_123",
        "price": 149.99,
        "currency": "USD",
        "airline": "AA",
        "airline_name": "American Airlines",
        "from_iata": "JFK",
        "to_iata": "LAX",
        "departure": "2026-06-01T09:00:00Z",
        "arrival": "2026-06-01T12:30:00Z",
        "stops": 0,
        "duration_minutes": 210,
        "cabin_class": "economy",
        "booking_link": "https://www.google.com/travel/flights",
    }


def _stub_enrichment_pipeline(monkeypatch):
    monkeypatch.setattr(search, "_inject_points_valuation", lambda offers: offers)

    def fake_density(offers, from_iata):
        for offer in offers:
            offer["density_altitude_ft"] = 1234
        return offers

    def fake_wind(offers, from_iata, to_iata):
        for offer in offers:
            offer["wind_component_kt"] = 8.0
        return offers

    monkeypatch.setattr(search, "_enrich_offers_with_density_altitude", fake_density)
    monkeypatch.setattr(search, "_enrich_offers_with_wind_component", fake_wind)
    monkeypatch.setattr(search, "_enrich_offers_with_airport_info", lambda offers, _from, _to: offers)
    monkeypatch.setattr(search, "_stamp_tier_requirements", lambda offers: offers)


def test_search_flights_combines_serpapi_and_duffel(monkeypatch):
    search.SEARCH_CACHE.clear()
    request = _request()
    _stub_enrichment_pipeline(monkeypatch)

    async def fake_search_duffel(segment, req):
        return [_duffel_raw_offer()]

    async def fake_search_serpapi(segment, req):
        return [_serpapi_offer()]

    monkeypatch.setattr(search, "search_duffel", fake_search_duffel)
    monkeypatch.setattr(search, "search_serpapi", fake_search_serpapi)

    response = asyncio.run(search.search_flights(request))

    assert response["total_offers"] == 2
    assert response["offers"][0]["source"] == "serpapi"
    assert response["offers"][1]["source"] == "duffel"
    assert set(response["sources_queried"]) == {"duffel", "serpapi"}


def test_search_flights_runs_weather_pipeline_when_serpapi_empty(monkeypatch):
    search.SEARCH_CACHE.clear()
    request = _request()
    _stub_enrichment_pipeline(monkeypatch)

    async def fake_search_duffel(segment, req):
        return [_duffel_raw_offer()]

    async def fake_search_serpapi(segment, req):
        return []

    monkeypatch.setattr(search, "search_duffel", fake_search_duffel)
    monkeypatch.setattr(search, "search_serpapi", fake_search_serpapi)

    response = asyncio.run(search.search_flights(request))

    assert response["total_offers"] == 1
    assert response["offers"][0]["source"] == "duffel"
    assert response["offers"][0]["density_altitude_ft"] == 1234
    assert response["offers"][0]["wind_component_kt"] == 8.0
