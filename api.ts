import {
  searchFlightsViaRapidAPI,
  createPriceAlert,
  createStripeCheckout,
  type FlightOffer,
  type SearchRequest,
  type SearchResponse,
  type FlightSegment
} from './liveApi';

export { type FlightOffer, type SearchRequest, type SearchResponse, type FlightSegment };

export async function searchFlights(request: SearchRequest): Promise<SearchResponse> {
  if (!request.from_iata || !request.to_iata) {
    throw new Error('Please select departure and arrival airports');
  }

  if (!request.departure_date) {
    throw new Error('Please select a departure date');
  }

  try {
    return await searchFlightsViaRapidAPI(request);
  } catch (error) {
    console.error('Flight search error:', error);
    throw new Error(
      error instanceof Error
        ? error.message
        : 'Unable to search flights at this time. Please try again later.'
    );
  }
}

export async function createAlert(alertData: {
  user_email: string;
  from_iata: string;
  to_iata: string;
  max_price: number;
  departure_date?: string;
  channels: string[];
  phone?: string;
}): Promise<{ success: boolean; alert_id?: string; error?: string }> {
  if (!alertData.user_email || !alertData.from_iata || !alertData.to_iata) {
    return { success: false, error: 'Missing required fields' };
  }

  return await createPriceAlert(alertData);
}

export async function initiateCheckout(priceId: string): Promise<{ sessionId?: string; url?: string; error?: string }> {
  return await createStripeCheckout(priceId);
}
