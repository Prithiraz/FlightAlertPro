import { searchAirlinesLive } from './liveApi';

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

let airlineCache = new Map<string, Airline[]>();
const CACHE_DURATION = 3600000;

let fallbackAirlinesData: Airline[] | null = null;
let fallbackLoadPromise: Promise<Airline[]> | null = null;

const FALLBACK_URL = 'https://raw.githubusercontent.com/jpatokal/openflights/master/data/airlines.dat';

async function loadFallbackAirlines(): Promise<Airline[]> {
  if (fallbackAirlinesData) return fallbackAirlinesData;
  if (fallbackLoadPromise) return fallbackLoadPromise;

  fallbackLoadPromise = (async () => {
    try {
      console.log('[Airlines] Loading fallback dataset from OpenFlights...');
      const response = await fetch(FALLBACK_URL);
      if (!response.ok) throw new Error('Failed to fetch fallback data');

      const text = await response.text();
      const lines = text.trim().split('\n');

      const airlines: Airline[] = [];
      for (const line of lines) {
        const parts = line.split(',').map(p => p.replace(/^"|"$/g, ''));

        const iata = parts[3];
        const icao = parts[4];

        if (!iata || iata === '\\N' || iata === '-') continue;

        airlines.push({
          id: parts[0],
          name: parts[1],
          alias: parts[2] !== '\\N' ? parts[2] : undefined,
          iata: iata,
          icao: icao !== '\\N' ? icao : undefined,
          callsign: parts[5] !== '\\N' ? parts[5] : undefined,
          country: parts[6],
          active: parts[7] === 'Y'
        });
      }

      fallbackAirlinesData = airlines.filter(a => a.active);
      console.log(`[Airlines] Loaded ${fallbackAirlinesData.length} airlines from fallback dataset`);
      return fallbackAirlinesData;
    } catch (error) {
      console.error('[Airlines] Failed to load fallback data:', error);
      fallbackLoadPromise = null;
      return [];
    }
  })();

  return fallbackLoadPromise;
}

function searchFallbackAirlines(query: string, airlines: Airline[]): Airline[] {
  const q = query.toLowerCase();
  const matches: { airline: Airline; score: number }[] = [];

  for (const airline of airlines) {
    let score = 0;

    if (airline.iata.toLowerCase() === q) {
      score = 100;
    } else if (airline.iata.toLowerCase().startsWith(q)) {
      score = 90;
    } else if (airline.icao?.toLowerCase() === q) {
      score = 85;
    } else if (airline.name.toLowerCase() === q) {
      score = 80;
    } else if (airline.name.toLowerCase().startsWith(q)) {
      score = 70;
    } else if (airline.name.toLowerCase().includes(q)) {
      score = 50;
    } else if (airline.country.toLowerCase().includes(q)) {
      score = 30;
    }

    if (score > 0) {
      matches.push({ airline, score });
    }
  }

  matches.sort((a, b) => b.score - a.score);
  return matches.slice(0, 10).map(m => m.airline);
}

export async function searchAirlines(query: string): Promise<Airline[]> {
  if (!query || query.length < 1) {
    const cached = airlineCache.get('all');
    if (cached) return cached.slice(0, 20);
    return [];
  }

  const cacheKey = query.toLowerCase();
  const cached = airlineCache.get(cacheKey);

  if (cached) {
    return cached;
  }

  try {
    const results = await searchAirlinesLive(query);

    const airlines: Airline[] = results.map(a => ({
      id: a.id,
      name: a.name,
      alias: a.alias,
      iata: a.iata,
      icao: a.icao,
      callsign: a.callsign,
      country: a.country,
      active: a.active
    }));

    airlineCache.set(cacheKey, airlines);

    setTimeout(() => airlineCache.delete(cacheKey), CACHE_DURATION);

    return airlines;
  } catch (error) {
    console.warn('[Airlines] Backend search failed, using fallback dataset:', error);

    const fallbackData = await loadFallbackAirlines();
    if (fallbackData.length === 0) return [];

    const results = searchFallbackAirlines(query, fallbackData);

    airlineCache.set(cacheKey, results);
    setTimeout(() => airlineCache.delete(cacheKey), CACHE_DURATION);

    return results;
  }
}

export function getAirlineByIata(airlines: Airline[], iata: string): Airline | undefined {
  return airlines.find(a => a.iata.toLowerCase() === iata.toLowerCase());
}
