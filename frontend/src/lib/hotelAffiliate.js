/**
 * Constructs a dynamic hotel affiliate URL for a given destination and check-in date.
 * Reads VITE_HOTEL_AFFILIATE_BASE_URL and VITE_HOTEL_AFFILIATE_ID from the environment.
 */
export function buildHotelUrl(destination, checkinDate) {
  const base =
    import.meta.env?.VITE_HOTEL_AFFILIATE_BASE_URL ||
    'https://www.booking.com/searchresults.html';
  const affiliateId = import.meta.env?.VITE_HOTEL_AFFILIATE_ID || '';
  const params = new URLSearchParams({ ss: destination });
  if (checkinDate) params.set('checkin', checkinDate);
  if (affiliateId) params.set('aid', affiliateId);
  return `${base}?${params.toString()}`;
}
