import { createClient } from '@supabase/supabase-js';
import { getApiBaseUrl } from './runtimeConfig';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseKey = import.meta.env.VITE_SUPABASE_ANON_KEY;
const supabase = createClient(supabaseUrl, supabaseKey);

export interface FlightOffer {
  id: string;
  provider: string;
  price: number;
  currency: string;
  airline: string;
  airline_name: string;
  from_iata: string;
  to_iata: string;
  departure: string;
  arrival: string;
  stops: number;
  duration_minutes: number | null;
  cabin_class: string;
  booking_link: string | null;
}

export interface SearchRequest {
  from_iata: string;
  to_iata: string;
  departure_date: string;
  return_date?: string;
  passengers: number;
  cabin_class: string;
  airline?: string;
  segments?: FlightSegment[];
  adults?: number;
  children?: number;
  infants?: number;
  min_baggage_kg?: number;
  max_baggage_kg?: number;
}

export interface FlightSegment {
  from_iata: string;
  to_iata: string;
  departure_date: string;
  airline?: string;
}

export interface SearchResponse {
  results: FlightOffer[];
  count: number;
  route: string;
  providers: string[];
}

export interface Airport {
  iata: string;
  icao?: string;
  name: string;
  city: string;
  country: string;
  latitude?: number;
  longitude?: number;
}

export interface Airline {
  id: string;
  name: string;
  alias?: string;
  iata: string;
  icao?: string;
  callsign?: string;
  country: string;
  active: boolean;
}

export async function searchAirportsLive(query: string): Promise<Airport[]> {
  if (!query || query.length < 1) return [];

  try {
    const apiBase = getApiBaseUrl();
    const response = await fetch(
      `${apiBase}/metadata/airports?q=${encodeURIComponent(query)}&commercial_only=true&grouped=false&limit=20`,
      { signal: AbortSignal.timeout(5000) }
    );

    if (!response.ok) {
      console.warn(`[API] Airport search failed: ${response.status}`);
      throw new Error('Airport search failed');
    }

    const data = await response.json();

    if (data.airports && Array.isArray(data.airports)) {
      return data.airports.map((apt: any) => ({
        iata: apt.iata,
        icao: apt.icao,
        name: apt.name,
        city: apt.city,
        country: apt.country,
        latitude: apt.latitude,
        longitude: apt.longitude
      }));
    }

    return [];
  } catch (error) {
    console.error('[API] Airport search error:', error);
    throw error;
  }
}

export async function searchAirlinesLive(query: string): Promise<Airline[]> {
  if (!query || query.length < 1) return [];

  try {
    const apiBase = getApiBaseUrl();
    const response = await fetch(
      `${apiBase}/metadata/airlines?q=${encodeURIComponent(query)}&limit=20`,
      { signal: AbortSignal.timeout(5000) }
    );

    if (!response.ok) {
      console.warn(`[API] Airline search failed: ${response.status}`);
      throw new Error('Airline search failed');
    }

    const data = await response.json();

    if (data.airlines && Array.isArray(data.airlines)) {
      return data.airlines.map((airline: any) => ({
        id: airline.id,
        name: airline.name,
        alias: airline.alias,
        iata: airline.iata,
        icao: airline.icao,
        callsign: airline.callsign,
        country: airline.country,
        active: airline.active
      }));
    }

    return [];
  } catch (error) {
    console.error('[API] Airline search error:', error);
    throw error;
  }
}

export async function convertCurrencyLive(
  amount: number,
  from: string,
  to: string
): Promise<number> {
  const fromUpper = from.toUpperCase();
  const toUpper = to.toUpperCase();

  if (fromUpper === toUpper) return amount;

  try {
    const apiBase = getApiBaseUrl();
    const apiUrl = `${apiBase}/currency/convert?amount=${amount}&from=${fromUpper}&to=${toUpper}`;

    const response = await fetch(apiUrl, {
      signal: AbortSignal.timeout(5000),
      headers: { 'Accept': 'application/json' }
    });

    if (!response.ok) {
      console.error(`Currency conversion failed: ${response.status}`);
      throw new Error(`SERVER: Currency conversion service returned ${response.status}`);
    }

    const data = await response.json();

    if (data.converted_amount !== undefined) {
      return data.converted_amount;
    }

    throw new Error('SERVER: Invalid response format from currency service');
  } catch (error) {
    console.error('Currency conversion error:', error);

    if (error instanceof Error) {
      if (error.message.includes('SERVER:')) {
        throw error;
      }
      if (error.name === 'AbortError' || error.message.includes('fetch')) {
        throw new Error('NETWORK: Unable to reach currency conversion service');
      }
    }

    throw new Error('NETWORK: Currency conversion failed');
  }
}

export async function searchFlightsViaRapidAPI(request: SearchRequest): Promise<SearchResponse> {
  try {
    const apiBase = getApiBaseUrl();
    const response = await fetch(`${apiBase}/search`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(request),
      signal: AbortSignal.timeout(30000)
    });

    if (!response.ok) {
      throw new Error(`Flight search failed: ${response.status}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Flight search error:', error);
    throw new Error('Flight search temporarily unavailable. Please try again.');
  }
}

export async function createPriceAlert(alertData: {
  user_email: string;
  from_iata: string;
  to_iata: string;
  max_price: number;
  departure_date?: string;
  channels: string[];
  phone?: string;
}): Promise<{ success: boolean; alert_id?: string; error?: string }> {
  try {
    const { data, error } = await supabase
      .from('price_alerts')
      .insert([{
        user_email: alertData.user_email,
        from_iata: alertData.from_iata,
        to_iata: alertData.to_iata,
        max_price: alertData.max_price,
        departure_date: alertData.departure_date,
        channels: alertData.channels,
        phone: alertData.phone,
        active: true,
        created_at: new Date().toISOString()
      }])
      .select()
      .single();

    if (error) {
      console.error('Supabase alert creation error:', error);
      return { success: false, error: error.message };
    }

    return { success: true, alert_id: data.id };
  } catch (error) {
    console.error('Alert creation error:', error);
    return { success: false, error: 'Failed to create alert' };
  }
}

export async function createStripeCheckout(priceId: string): Promise<{ sessionId?: string; url?: string; error?: string }> {
  try {
    const apiBase = getApiBaseUrl();
    const response = await fetch(`${apiBase}/payments/create-checkout`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ price_id: priceId }),
      signal: AbortSignal.timeout(10000)
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || 'Checkout creation failed');
    }

    const data = await response.json();
    return { sessionId: data.session_id, url: data.url };
  } catch (error) {
    console.error('Stripe checkout error:', error);
    return { error: error instanceof Error ? error.message : 'Payment system temporarily unavailable' };
  }
}

export interface PriceAlert {
  id: string;
  user_email: string;
  from_iata: string;
  to_iata: string;
  max_price: number;
  departure_date?: string;
  active: boolean;
  channels: string[];
  phone?: string;
  currency?: string;
  created_at: string;
  triggered_at?: string;
}

export async function getPriceAlerts(userEmail: string): Promise<PriceAlert[]> {
  try {
    const { data, error } = await supabase
      .from('price_alerts')
      .select('*')
      .eq('user_email', userEmail)
      .order('created_at', { ascending: false });

    if (error) {
      console.error('Failed to fetch alerts:', error);
      throw new Error('DB: Unable to fetch alerts');
    }

    return data || [];
  } catch (error) {
    console.error('Get alerts error:', error);
    if (error instanceof Error && error.message.includes('DB:')) {
      throw error;
    }
    throw new Error('NETWORK: Failed to connect to database');
  }
}

export async function togglePriceAlertActive(
  alertId: string,
  active: boolean
): Promise<{ success: boolean; error?: string }> {
  try {
    const { error } = await supabase
      .from('price_alerts')
      .update({ active })
      .eq('id', alertId);

    if (error) {
      console.error('Failed to toggle alert:', error);
      return { success: false, error: 'DB: Unable to update alert' };
    }

    return { success: true };
  } catch (error) {
    console.error('Toggle alert error:', error);
    return { success: false, error: 'NETWORK: Failed to connect to database' };
  }
}

export async function deletePriceAlert(alertId: string): Promise<{ success: boolean; error?: string }> {
  try {
    const { error } = await supabase
      .from('price_alerts')
      .delete()
      .eq('id', alertId);

    if (error) {
      console.error('Failed to delete alert:', error);

      if (error.code === 'PGRST301' || error.message.includes('policy')) {
        const { error: updateError } = await supabase
          .from('price_alerts')
          .update({ active: false })
          .eq('id', alertId);

        if (updateError) {
          return { success: false, error: 'DB: Unable to delete or deactivate alert' };
        }
        return { success: true };
      }

      return { success: false, error: 'DB: Unable to delete alert' };
    }

    return { success: true };
  } catch (error) {
    console.error('Delete alert error:', error);
    return { success: false, error: 'NETWORK: Failed to connect to database' };
  }
}

export function getSupabaseAuth() {
  return supabase.auth;
}

export async function checkBackendHealth(): Promise<{ healthy: boolean; error?: string }> {
  try {
    const apiBase = getApiBaseUrl();
    const response = await fetch(`${apiBase}/systemcheck`, {
      signal: AbortSignal.timeout(5000)
    });

    if (!response.ok) {
      return { healthy: false, error: `Backend returned ${response.status}` };
    }

    const data = await response.json();
    console.log('[Backend] Health check:', data);

    return { healthy: true };
  } catch (error) {
    console.error('[Backend] Health check failed:', error);
    return {
      healthy: false,
      error: error instanceof Error ? error.message : 'Backend unreachable'
    };
  }
}
