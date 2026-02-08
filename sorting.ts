export type SortOption = 'price' | 'duration' | 'airline_rating' | 'value_score' | 'departure' | 'arrival';

export interface SortableField {
  id: SortOption;
  label: string;
  getValue: (flight: any) => number | string;
}

export const SORT_OPTIONS: SortableField[] = [
  {
    id: 'price',
    label: 'Price (Low to High)',
    getValue: (flight) => flight.price || flight.pricing?.final_price || 0
  },
  {
    id: 'duration',
    label: 'Duration (Shortest First)',
    getValue: (flight) => flight.duration_minutes || 0
  },
  {
    id: 'airline_rating',
    label: 'Airline Rating (Best First)',
    getValue: (flight) => -(flight.airline_rating || 75)
  },
  {
    id: 'value_score',
    label: 'Value Score (Best First)',
    getValue: (flight) => -(flight.valueScore || flight.ai_satisfaction_score || 0)
  },
  {
    id: 'departure',
    label: 'Departure Time (Early to Late)',
    getValue: (flight) => flight.departure || ''
  },
  {
    id: 'arrival',
    label: 'Arrival Time (Early to Late)',
    getValue: (flight) => flight.arrival || ''
  }
];

export function sortFlights(flights: any[], sortBy: SortOption): any[] {
  const sortOption = SORT_OPTIONS.find(opt => opt.id === sortBy);
  if (!sortOption) return flights;

  return [...flights].sort((a, b) => {
    const aValue = sortOption.getValue(a);
    const bValue = sortOption.getValue(b);

    if (typeof aValue === 'number' && typeof bValue === 'number') {
      return aValue - bValue;
    }

    return String(aValue).localeCompare(String(bValue));
  });
}
