from amadeus_service import AmadeusService


def test_amadeus_normalizes_round_trip_into_slices():
    service = AmadeusService(client_id="id", client_secret="secret")
    sample_offers = [
        {
            "id": "1",
            "price": {"grandTotal": "512.40", "currency": "USD"},
            "itineraries": [
                {
                    "duration": "PT5H45M",
                    "segments": [
                        {
                            "carrierCode": "AA",
                            "number": "100",
                            "departure": {"iataCode": "JFK", "at": "2026-06-01T08:00:00"},
                            "arrival": {"iataCode": "LAX", "at": "2026-06-01T11:45:00"},
                        }
                    ],
                },
                {
                    "duration": "PT5H20M",
                    "segments": [
                        {
                            "carrierCode": "AA",
                            "number": "101",
                            "departure": {"iataCode": "LAX", "at": "2026-06-10T09:00:00"},
                            "arrival": {"iataCode": "JFK", "at": "2026-06-10T17:20:00"},
                        }
                    ],
                },
            ],
            "travelerPricings": [{"fareDetailsBySegment": [{"cabin": "ECONOMY"}]}],
        }
    ]
    dictionaries = {"carriers": {"AA": "American Airlines"}}

    normalized = service._normalize_offers(sample_offers, dictionaries)

    assert len(normalized) == 1
    offer = normalized[0]
    assert offer["provider"] == "amadeus"
    assert offer["price"] == 512.40
    assert len(offer["slices"]) == 2
    assert offer["slices"][0]["origin_iata"] == "JFK"
    assert offer["slices"][0]["destination_iata"] == "LAX"
    assert offer["slices"][1]["origin_iata"] == "LAX"
    assert offer["slices"][1]["destination_iata"] == "JFK"
