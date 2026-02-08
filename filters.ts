export interface FlightFilters {
  maxStops: number;
  maxPrice: number;
  airlines: string[];
  layoverCities: string[];
  departureWindow: ('morning' | 'afternoon' | 'evening')[];
}

export const DEFAULT_FILTERS: FlightFilters = {
  maxStops: 2,
  maxPrice: 10000,
  airlines: [],
  layoverCities: [],
  departureWindow: ['morning', 'afternoon', 'evening']
};

export function getDepartureWindow(departureTime: string): 'morning' | 'afternoon' | 'evening' {
  try {
    const date = new Date(departureTime);
    const hour = date.getHours();

    if (hour < 12) return 'morning';
    if (hour < 18) return 'afternoon';
    return 'evening';
  } catch {
    return 'morning';
  }
}

export function applyFilters(flights: any[], filters: FlightFilters): any[] {
  return flights.filter(flight => {
    if (flight.stops > filters.maxStops) return false;

    const price = flight.price || flight.pricing?.final_price || 0;
    if (price > filters.maxPrice) return false;

    if (filters.airlines.length > 0 && !filters.airlines.includes(flight.airline)) {
      return false;
    }

    const departureWindow = getDepartureWindow(flight.departure);
    if (!filters.departureWindow.includes(departureWindow)) {
      return false;
    }

    return true;
  });
}

export function getUniqueAirlines(flights: any[]): string[] {
  return [...new Set(flights.map(f => f.airline).filter(Boolean))];
}

export function getPriceRange(flights: any[]): { min: number; max: number } {
  const prices = flights.map(f => f.price || f.pricing?.final_price || 0).filter(p => p > 0);
  return {
    min: Math.min(...prices, 0),
    max: Math.max(...prices, 10000)
  };
}
