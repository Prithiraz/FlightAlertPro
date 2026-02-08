import asyncio
import logging
from typing import List, Dict, Any
from duffel_service import duffel_service
from rapidapi_adapters import aerodatabox_adapter, airscraper_adapter, flightapi_adapter

logger = logging.getLogger(__name__)

class MergeService:
    async def search_all_providers(self, from_iata: str, to_iata: str, departure_date: str,
                                  return_date: str = None, passengers: int = 1) -> List[Dict[str, Any]]:

        tasks = [
            asyncio.to_thread(duffel_service.search_flights, from_iata, to_iata, departure_date, return_date, passengers),
            asyncio.to_thread(aerodatabox_adapter.search_flights, from_iata, to_iata, departure_date),
            asyncio.to_thread(airscraper_adapter.search_flights, from_iata, to_iata, departure_date, return_date, passengers),
            asyncio.to_thread(flightapi_adapter.search_flights, from_iata, to_iata, departure_date)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_offers = []
        for result in results:
            if isinstance(result, list):
                all_offers.extend(result)
            elif isinstance(result, Exception):
                logger.error(f"Provider error: {str(result)}")

        deduped = self._dedupe_offers(all_offers)
        sorted_offers = sorted(deduped, key=lambda x: x.get('price', float('inf')))

        return sorted_offers[:100]

    def _dedupe_offers(self, offers: List[Dict]) -> List[Dict]:
        seen = set()
        unique_offers = []

        for offer in offers:
            airline = offer.get('airline', '')
            depart_time = offer.get('departure', '')[:16]
            price_rounded = round(offer.get('price', 0) / 10) * 10

            key = f"{airline}:{depart_time}:{price_rounded}"

            if key not in seen:
                seen.add(key)
                unique_offers.append(offer)

        logger.info(f"Deduped {len(offers)} offers to {len(unique_offers)}")
        return unique_offers

merge_service = MergeService()
