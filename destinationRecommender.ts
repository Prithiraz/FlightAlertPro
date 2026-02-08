export type Continent = 'Europe' | 'Asia' | 'North America' | 'South America' | 'Africa' | 'Oceania';

export interface Destination {
  city: string;
  country: string;
  continent: Continent;
  iata: string;
  avgPrice: number;
  weather: string;
  season: string;
  popularity: number;
  attractions: string[];
}

export const DESTINATIONS: Destination[] = [
  { city: 'Paris', country: 'France', continent: 'Europe', iata: 'CDG', avgPrice: 450, weather: 'Mild', season: 'Spring/Fall', popularity: 95, attractions: ['Eiffel Tower', 'Louvre', 'Notre-Dame'] },
  { city: 'London', country: 'UK', continent: 'Europe', iata: 'LHR', avgPrice: 420, weather: 'Cool', season: 'Summer', popularity: 92, attractions: ['Big Ben', 'British Museum', 'Tower Bridge'] },
  { city: 'Barcelona', country: 'Spain', continent: 'Europe', iata: 'BCN', avgPrice: 380, weather: 'Warm', season: 'Summer', popularity: 88, attractions: ['Sagrada Familia', 'Park Güell', 'Gothic Quarter'] },
  { city: 'Rome', country: 'Italy', continent: 'Europe', iata: 'FCO', avgPrice: 410, weather: 'Mediterranean', season: 'Spring', popularity: 90, attractions: ['Colosseum', 'Vatican', 'Trevi Fountain'] },
  { city: 'Tokyo', country: 'Japan', continent: 'Asia', iata: 'NRT', avgPrice: 650, weather: 'Temperate', season: 'Spring/Fall', popularity: 93, attractions: ['Shibuya', 'Mt. Fuji', 'Temples'] },
  { city: 'Bangkok', country: 'Thailand', continent: 'Asia', iata: 'BKK', avgPrice: 520, weather: 'Tropical', season: 'Winter', popularity: 85, attractions: ['Grand Palace', 'Temples', 'Markets'] },
  { city: 'Dubai', country: 'UAE', continent: 'Asia', iata: 'DXB', avgPrice: 480, weather: 'Hot', season: 'Winter', popularity: 87, attractions: ['Burj Khalifa', 'Desert Safari', 'Malls'] },
  { city: 'Singapore', country: 'Singapore', continent: 'Asia', iata: 'SIN', avgPrice: 580, weather: 'Tropical', season: 'Year-round', popularity: 86, attractions: ['Marina Bay', 'Gardens', 'Hawker Centers'] },
  { city: 'New York', country: 'USA', continent: 'North America', iata: 'JFK', avgPrice: 320, weather: 'Variable', season: 'Spring/Fall', popularity: 94, attractions: ['Statue of Liberty', 'Central Park', 'Times Square'] },
  { city: 'Los Angeles', country: 'USA', continent: 'North America', iata: 'LAX', avgPrice: 280, weather: 'Sunny', season: 'Year-round', popularity: 89, attractions: ['Hollywood', 'Beaches', 'Theme Parks'] },
  { city: 'Cancun', country: 'Mexico', continent: 'North America', iata: 'CUN', avgPrice: 350, weather: 'Tropical', season: 'Winter', popularity: 82, attractions: ['Beaches', 'Mayan Ruins', 'Cenotes'] },
  { city: 'Sydney', country: 'Australia', continent: 'Oceania', iata: 'SYD', avgPrice: 820, weather: 'Temperate', season: 'Summer', popularity: 88, attractions: ['Opera House', 'Harbour Bridge', 'Beaches'] },
  { city: 'Cape Town', country: 'South Africa', continent: 'Africa', iata: 'CPT', avgPrice: 680, weather: 'Mediterranean', season: 'Summer', popularity: 80, attractions: ['Table Mountain', 'Beaches', 'Wine Country'] },
  { city: 'Buenos Aires', country: 'Argentina', continent: 'South America', iata: 'EZE', avgPrice: 590, weather: 'Temperate', season: 'Spring/Fall', popularity: 78, attractions: ['Tango', 'La Boca', 'Recoleta'] },
];

export function recommendDestinations(budget: number, continent?: Continent, maxResults: number = 5): Destination[] {
  let filtered = DESTINATIONS;

  if (continent) {
    filtered = filtered.filter(d => d.continent === continent);
  }

  filtered = filtered.filter(d => d.avgPrice <= budget * 1.15);

  return filtered
    .sort((a, b) => {
      const aPriceFit = Math.abs(a.avgPrice - budget);
      const bPriceFit = Math.abs(b.avgPrice - budget);
      const priceScore = aPriceFit - bPriceFit;
      const popularityScore = (b.popularity - a.popularity) * 10;
      return priceScore + popularityScore;
    })
    .slice(0, maxResults);
}

export function getCurrentSeason(): string {
  const month = new Date().getMonth() + 1;
  if (month >= 3 && month <= 5) return 'Spring';
  if (month >= 6 && month <= 8) return 'Summer';
  if (month >= 9 && month <= 11) return 'Fall';
  return 'Winter';
}
