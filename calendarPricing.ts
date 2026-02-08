export interface DayPrice {
  date: string;
  price: number;
  isCheapest: boolean;
  dayOfWeek: string;
}

export function generateCalendarPrices(basePrice: number, daysCount: number = 30): DayPrice[] {
  const prices: DayPrice[] = [];
  const today = new Date();

  for (let i = 0; i < daysCount; i++) {
    const date = new Date(today);
    date.setDate(today.getDate() + i);

    const dayOfWeek = date.toLocaleDateString('en-US', { weekday: 'short' });
    const isWeekend = dayOfWeek === 'Sat' || dayOfWeek === 'Sun';
    const weekdayFactor = isWeekend ? 1.15 : 0.95;

    const randomFactor = 0.85 + Math.random() * 0.3;
    const trendFactor = 1 - (i / daysCount) * 0.1;

    const price = Math.round(basePrice * weekdayFactor * randomFactor * trendFactor);

    prices.push({
      date: date.toISOString().split('T')[0],
      price,
      isCheapest: false,
      dayOfWeek
    });
  }

  const minPrice = Math.min(...prices.map(p => p.price));
  prices.forEach(p => {
    p.isCheapest = p.price === minPrice;
  });

  return prices;
}

export function getCheapestDays(prices: DayPrice[], count: number = 3): DayPrice[] {
  return [...prices].sort((a, b) => a.price - b.price).slice(0, count);
}

export function getWeekendPrices(prices: DayPrice[]): DayPrice[] {
  return prices.filter(p => p.dayOfWeek === 'Sat' || p.dayOfWeek === 'Sun');
}

export function getWeekdayPrices(prices: DayPrice[]): DayPrice[] {
  return prices.filter(p => p.dayOfWeek !== 'Sat' && p.dayOfWeek !== 'Sun');
}
