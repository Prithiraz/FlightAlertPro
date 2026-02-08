export interface AIInsight {
  type: 'trend' | 'savings' | 'timing' | 'alternative' | 'warning';
  title: string;
  message: string;
  confidence: number;
  icon: string;
}

export function generateInsights(
  flights: any[],
  route: string,
  departureDate: string
): AIInsight[] {
  const insights: AIInsight[] = [];

  const avgPrice = flights.reduce((sum, f) => sum + (f.price || 0), 0) / flights.length;
  const cheapestFlight = flights.reduce((min, f) => (f.price < min.price ? f : min), flights[0]);
  const priceDiff = avgPrice - cheapestFlight.price;

  if (priceDiff > avgPrice * 0.2) {
    insights.push({
      type: 'savings',
      title: 'Alternative airports save money',
      message: `Flying to nearby airports could save up to $${Math.round(priceDiff)}`,
      confidence: 78,
      icon: '💰'
    });
  }

  const month = new Date(departureDate).getMonth() + 1;
  const isHighSeason = [6, 7, 8, 12].includes(month);

  if (isHighSeason) {
    insights.push({
      type: 'timing',
      title: 'Peak season pricing',
      message: 'You\'re traveling during high season. Prices typically drop 20-30% in shoulder months',
      confidence: 85,
      icon: '📅'
    });
  } else {
    insights.push({
      type: 'timing',
      title: 'Good timing',
      message: 'You\'re traveling during off-peak season when prices are typically lower',
      confidence: 82,
      icon: '✨'
    });
  }

  const hasMultiStop = flights.some(f => f.stops > 0);
  if (hasMultiStop) {
    const directFlights = flights.filter(f => f.stops === 0);
    const connectingFlights = flights.filter(f => f.stops > 0);

    if (directFlights.length > 0 && connectingFlights.length > 0) {
      const directAvg = directFlights.reduce((sum, f) => sum + f.price, 0) / directFlights.length;
      const connectingAvg = connectingFlights.reduce((sum, f) => sum + f.price, 0) / connectingFlights.length;
      const savings = directAvg - connectingAvg;

      if (savings > 50) {
        insights.push({
          type: 'alternative',
          title: 'Connecting flights save money',
          message: `Flights with 1 stop average $${Math.round(savings)} less than direct flights`,
          confidence: 88,
          icon: '🔄'
        });
      }
    }
  }

  const routeTrends: Record<string, string> = {
    'LAX_NYC': 'This route typically drops 15% in January and September',
    'SFO_LHR': 'Prices usually lowest in February and November',
    'JFK_CDG': 'Best deals found 6-8 weeks before departure',
    'MIA_BCN': 'This route peaks in July-August, drops in October-November',
  };

  const trend = routeTrends[route];
  if (trend) {
    insights.push({
      type: 'trend',
      title: 'Historical price trends',
      message: trend,
      confidence: 75,
      icon: '📊'
    });
  }

  const daysUntilFlight = Math.ceil(
    (new Date(departureDate).getTime() - new Date().getTime()) / (1000 * 60 * 60 * 24)
  );

  if (daysUntilFlight < 14) {
    insights.push({
      type: 'warning',
      title: 'Last-minute booking',
      message: 'Booking within 2 weeks often means higher prices. Consider flexible dates if possible',
      confidence: 90,
      icon: '⚠️'
    });
  } else if (daysUntilFlight > 90) {
    insights.push({
      type: 'timing',
      title: 'Early bird advantage',
      message: 'Booking early gives you more options and potentially better prices',
      confidence: 80,
      icon: '🐦'
    });
  }

  return insights.sort((a, b) => b.confidence - a.confidence).slice(0, 4);
}

export function getInsightsByType(insights: AIInsight[], type: AIInsight['type']): AIInsight[] {
  return insights.filter(i => i.type === type);
}
