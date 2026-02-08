import { searchAirportsLive, type Airport } from './liveApi';

export { type Airport };

export interface CityGroup {
  city: string;
  country: string;
  airports: Airport[];
}

let airportCache = new Map<string, Airport[]>();
const CACHE_DURATION = 3600000;

let fallbackAirportsData: Airport[] | null = null;
let fallbackLoadPromise: Promise<Airport[]> | null = null;

const FALLBACK_URL = 'https://raw.githubusercontent.com/jpatokal/openflights/master/data/airports.dat';

async function loadFallbackAirports(): Promise<Airport[]> {
  if (fallbackAirportsData) return fallbackAirportsData;
  if (fallbackLoadPromise) return fallbackLoadPromise;

  fallbackLoadPromise = (async () => {
    try {
      console.log('[Airports] Loading fallback dataset from OpenFlights...');
      const response = await fetch(FALLBACK_URL);
      if (!response.ok) throw new Error('Failed to fetch fallback data');

      const text = await response.text();
      const lines = text.trim().split('\n');

      const airports: Airport[] = [];
      for (const line of lines) {
        const parts = line.split(',').map(p => p.replace(/^"|"$/g, ''));

        const iata = parts[4];
        const icao = parts[5];

        if (!iata || iata === '\\N') continue;

        airports.push({
          id: parts[0],
          name: parts[1],
          city: parts[2],
          country: parts[3],
          iata: iata,
          icao: icao !== '\\N' ? icao : undefined,
          latitude: parseFloat(parts[6]),
          longitude: parseFloat(parts[7])
        });
      }

      fallbackAirportsData = airports;
      console.log(`[Airports] Loaded ${airports.length} airports from fallback dataset`);
      return airports;
    } catch (error) {
      console.error('[Airports] Failed to load fallback data:', error);
      fallbackLoadPromise = null;
      return [];
    }
  })();

  return fallbackLoadPromise;
}

function searchFallbackAirports(query: string, airports: Airport[]): Airport[] {
  const q = query.toLowerCase();
  const matches: { airport: Airport; score: number }[] = [];

  for (const airport of airports) {
    let score = 0;

    if (airport.iata.toLowerCase() === q) {
      score = 100;
    } else if (airport.iata.toLowerCase().startsWith(q)) {
      score = 90;
    } else if (airport.city.toLowerCase() === q) {
      score = 80;
    } else if (airport.city.toLowerCase().startsWith(q)) {
      score = 70;
    } else if (airport.name.toLowerCase().includes(q)) {
      score = 50;
    } else if (airport.country.toLowerCase().includes(q)) {
      score = 30;
    }

    if (score > 0) {
      matches.push({ airport, score });
    }
  }

  matches.sort((a, b) => b.score - a.score);
  return matches.slice(0, 10).map(m => m.airport);
}

export async function searchAirports(query: string): Promise<Airport[]> {
  if (!query || query.length < 1) return [];

  const cacheKey = query.toLowerCase();
  const cached = airportCache.get(cacheKey);

  if (cached) {
    return cached;
  }

  try {
    const results = await searchAirportsLive(query);

    airportCache.set(cacheKey, results);

    setTimeout(() => airportCache.delete(cacheKey), CACHE_DURATION);

    return results;
  } catch (error) {
    console.warn('[Airports] Backend search failed, using fallback dataset:', error);

    const fallbackData = await loadFallbackAirports();
    if (fallbackData.length === 0) return [];

    const results = searchFallbackAirports(query, fallbackData);

    airportCache.set(cacheKey, results);
    setTimeout(() => airportCache.delete(cacheKey), CACHE_DURATION);

    return results;
  }
}

export async function searchCities(query: string): Promise<CityGroup[]> {
  if (!query || query.length < 1) return [];

  const airports = await searchAirports(query);
  const cityMap = new Map<string, CityGroup>();

  airports.forEach(airport => {
    const cityKey = `${airport.city}|${airport.country}`;

    if (!cityMap.has(cityKey)) {
      cityMap.set(cityKey, {
        city: airport.city,
        country: airport.country,
        airports: []
      });
    }
    cityMap.get(cityKey)!.airports.push(airport);
  });

  return Array.from(cityMap.values())
    .sort((a, b) => {
      const q = query.toLowerCase();
      const aMatch = a.city.toLowerCase().startsWith(q);
      const bMatch = b.city.toLowerCase().startsWith(q);
      if (aMatch && !bMatch) return -1;
      if (!aMatch && bMatch) return 1;
      return 0;
    })
    .slice(0, 10);
}
