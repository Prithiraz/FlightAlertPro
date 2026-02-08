export type Currency = 'USD' | 'GBP' | 'EUR' | 'CAD' | 'AUD' | 'INR' | 'JPY' | 'SGD' | 'AED';

export const CURRENCY_SYMBOLS: Record<Currency, string> = {
  'USD': '$',
  'GBP': '£',
  'EUR': '€',
  'CAD': 'C$',
  'AUD': 'A$',
  'INR': '₹',
  'JPY': '¥',
  'SGD': 'S$',
  'AED': 'د.إ',
};

export const CURRENCY_NAMES: Record<Currency, string> = {
  'USD': 'US Dollar',
  'GBP': 'British Pound',
  'EUR': 'Euro',
  'CAD': 'Canadian Dollar',
  'AUD': 'Australian Dollar',
  'INR': 'Indian Rupee',
  'JPY': 'Japanese Yen',
  'SGD': 'Singapore Dollar',
  'AED': 'UAE Dirham',
};

let fxRateCache = new Map<string, { rate: number; timestamp: number }>();
const CACHE_DURATION = 3600000;
let fxApiAvailable = true;

export function isFxApiAvailable(): boolean {
  return fxApiAvailable;
}

export async function getFxRate(from: string, to: string): Promise<number> {
  if (from === to) return 1;

  const cacheKey = `${from}-${to}`;
  const cached = fxRateCache.get(cacheKey);

  if (cached && Date.now() - cached.timestamp < CACHE_DURATION) {
    return cached.rate;
  }

  try {
    const url = `https://api.frankfurter.app/latest?amount=1&from=${from}&to=${to}`;
    const response = await fetch(url);

    if (!response.ok) {
      throw new Error(`Frankfurter API error: ${response.status}`);
    }

    const data = await response.json();
    const rate = data.rates[to];

    if (!rate) {
      throw new Error(`No rate found for ${from} -> ${to}`);
    }

    fxRateCache.set(cacheKey, { rate, timestamp: Date.now() });
    console.log(`[Currency] FX rate ${from}->${to} = ${rate}`);
    fxApiAvailable = true;

    return rate;
  } catch (error) {
    console.warn(`[Currency] Failed to fetch FX rate ${from}->${to}:`, error);
    fxApiAvailable = false;
    return 1;
  }
}

export async function convertAmount(amount: number, from: string, to: string): Promise<number> {
  const rate = await getFxRate(from, to);
  return amount * rate;
}

export function formatMoney(amount: number, currency: string): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(amount);
}

export async function convertCurrency(
  amount: number,
  fromCurrency: Currency,
  toCurrency: Currency
): Promise<number> {
  return convertAmount(amount, fromCurrency, toCurrency);
}

export function convertCurrencySync(amount: number, fromCurrency: Currency, toCurrency: Currency): number {
  if (fromCurrency === toCurrency) return amount;

  const cacheKey = `${fromCurrency}-${toCurrency}`;
  const cached = fxRateCache.get(cacheKey);

  if (cached) {
    return amount * cached.rate;
  }

  return amount;
}

export function formatPrice(amount: number, currency: Currency): string {
  return formatMoney(amount, currency);
}
