import { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { searchFlights, flexibleSearch, getPriceHistory } from '../lib/api';

const CABIN_CLASSES = ['economy', 'premium_economy', 'business', 'first'];
const SORT_OPTIONS = [
  { value: 'price', label: 'Price (cheapest first)' },
  { value: 'duration', label: 'Duration (fastest first)' },
  { value: 'stops', label: 'Stops (direct first)' },
  { value: 'departure', label: 'Departure time' },
  { value: 'arrival', label: 'Arrival time' },
];

export default function Search() {
  const location = useLocation();
  const navigate = useNavigate();

  const prefill = location.state?.prefill || {};

  const [form, setForm] = useState({
    from_iata: prefill.from_iata || '',
    to_iata: prefill.to_iata || '',
    departure_date: '',
    return_date: '',
    passengers: 1,
    cabin_class: 'economy',
  });

  // Flexible date state
  const [flexMode, setFlexMode] = useState(false);
  const [flexDays, setFlexDays] = useState(3);

  // Sort / filter state
  const [sortBy, setSortBy] = useState('price');
  const [maxStops, setMaxStops] = useState('');
  const [maxPrice, setMaxPrice] = useState('');

  const [results, setResults] = useState([]);
  const [flexCalendar, setFlexCalendar] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [searched, setSearched] = useState(false);

  const [priceHistory, setPriceHistory] = useState(null);

  // Apply prefill from Explore page
  useEffect(() => {
    if (prefill.from_iata || prefill.to_iata) {
      setForm((prev) => ({
        ...prev,
        from_iata: prefill.from_iata || prev.from_iata,
        to_iata: prefill.to_iata || prev.to_iata,
      }));
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const fetchPriceHistory = async (fromIata, toIata) => {
    try {
      const hist = await getPriceHistory({ from_iata: fromIata, to_iata: toIata });
      setPriceHistory(hist);
    } catch {
      // non-critical
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setResults([]);
    setFlexCalendar(null);
    setSearched(false);
    setPriceHistory(null);

    const fromU = form.from_iata.toUpperCase();
    const toU = form.to_iata.toUpperCase();

    try {
      if (flexMode) {
        const data = await flexibleSearch({
          from_iata: fromU,
          to_iata: toU,
          departure_date: form.departure_date,
          flex_days: flexDays,
          passengers: Number(form.passengers),
          cabin_class: form.cabin_class,
        });
        setFlexCalendar(data);
      } else {
        const payload = {
          segments: [{ from_iata: fromU, to_iata: toU, departure_date: form.departure_date }],
          passengers: { adults: Number(form.passengers) },
          cabin_class: form.cabin_class,
          currency: 'USD',
          sort_by: sortBy,
        };
        if (form.return_date) {
          payload.segments.push({ from_iata: toU, to_iata: fromU, departure_date: form.return_date });
        }
        if (maxStops !== '') payload.max_stops = Number(maxStops);
        if (maxPrice !== '') payload.max_price = Number(maxPrice);

        const data = await searchFlights(payload);
        const offers = Array.isArray(data) ? data : (data.offers ?? data.results ?? []);
        setResults(offers);
      }

      fetchPriceHistory(fromU, toU);
    } catch (err) {
      setError(err.message || 'Search failed');
    } finally {
      setLoading(false);
      setSearched(true);
    }
  };

  const handleCreateAlert = (offer) => {
    navigate('/alerts', {
      state: {
        prefill: {
          from_iata: offer.from_iata ?? form.from_iata.toUpperCase(),
          to_iata: offer.to_iata ?? form.to_iata.toUpperCase(),
          departure_date: form.departure_date,
          currency: offer.currency ?? 'USD',
          max_price: offer.price ? String(Math.ceil(offer.price)) : '',
        },
      },
    });
  };

  const handleSearchFlexDate = (date) => {
    setForm((prev) => ({ ...prev, departure_date: date }));
    setFlexMode(false);
    setFlexCalendar(null);
    setSearched(false);
  };

  return (
    <div style={styles.page}>
      <h2 style={styles.heading}>Search Flights</h2>

      <div style={styles.formCard}>
        <form onSubmit={handleSubmit} style={styles.form}>
          {/* Route row */}
          <div style={styles.row}>
            <div style={styles.field}>
              <label style={styles.label}>From (IATA)</label>
              <input
                name="from_iata"
                value={form.from_iata}
                onChange={handleChange}
                maxLength={3}
                placeholder="LAX"
                required
                style={styles.input}
              />
            </div>
            <div style={styles.field}>
              <label style={styles.label}>To (IATA)</label>
              <input
                name="to_iata"
                value={form.to_iata}
                onChange={handleChange}
                maxLength={3}
                placeholder="JFK"
                required
                style={styles.input}
              />
            </div>
          </div>

          {/* Date row */}
          <div style={styles.row}>
            <div style={styles.field}>
              <label style={styles.label}>Departure Date</label>
              <input
                type="date"
                name="departure_date"
                value={form.departure_date}
                onChange={handleChange}
                required
                style={styles.input}
              />
            </div>
            {!flexMode && (
              <div style={styles.field}>
                <label style={styles.label}>Return Date (optional)</label>
                <input
                  type="date"
                  name="return_date"
                  value={form.return_date}
                  onChange={handleChange}
                  style={styles.input}
                />
              </div>
            )}
          </div>

          {/* Flexible dates toggle */}
          <div style={styles.row}>
            <label style={styles.checkLabel}>
              <input
                type="checkbox"
                checked={flexMode}
                onChange={(e) => setFlexMode(e.target.checked)}
              />
              {' '}Flexible dates — show fare calendar
            </label>
            {flexMode && (
              <select
                value={flexDays}
                onChange={(e) => setFlexDays(Number(e.target.value))}
                style={{ ...styles.input, maxWidth: '180px' }}
              >
                {[1, 2, 3, 5, 7].map((d) => (
                  <option key={d} value={d}>±{d} day{d > 1 ? 's' : ''}</option>
                ))}
              </select>
            )}
          </div>

          {/* Passengers & cabin */}
          <div style={styles.row}>
            <div style={styles.field}>
              <label style={styles.label}>Passengers</label>
              <input
                type="number"
                name="passengers"
                value={form.passengers}
                onChange={handleChange}
                min={1}
                max={9}
                required
                style={styles.input}
              />
            </div>
            <div style={styles.field}>
              <label style={styles.label}>Cabin Class</label>
              <select name="cabin_class" value={form.cabin_class} onChange={handleChange} style={styles.input}>
                {CABIN_CLASSES.map((c) => (
                  <option key={c} value={c}>
                    {c.replace('_', ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Sort & filter row (only in standard mode) */}
          {!flexMode && (
            <details style={styles.filterDetails}>
              <summary style={styles.filterSummary}>Filters &amp; Sort ▸</summary>
              <div style={{ ...styles.row, marginTop: '0.75rem' }}>
                <div style={styles.field}>
                  <label style={styles.label}>Sort by</label>
                  <select value={sortBy} onChange={(e) => setSortBy(e.target.value)} style={styles.input}>
                    {SORT_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value}>{o.label}</option>
                    ))}
                  </select>
                </div>
                <div style={styles.field}>
                  <label style={styles.label}>Max stops</label>
                  <select value={maxStops} onChange={(e) => setMaxStops(e.target.value)} style={styles.input}>
                    <option value="">Any</option>
                    <option value="0">Direct only</option>
                    <option value="1">Up to 1 stop</option>
                    <option value="2">Up to 2 stops</option>
                  </select>
                </div>
                <div style={styles.field}>
                  <label style={styles.label}>Max price (USD)</label>
                  <input
                    type="number"
                    value={maxPrice}
                    onChange={(e) => setMaxPrice(e.target.value)}
                    min={1}
                    placeholder="No limit"
                    style={styles.input}
                  />
                </div>
              </div>
            </details>
          )}

          {error && <p style={styles.error}>{error}</p>}

          <button type="submit" disabled={loading} style={styles.button}>
            {loading ? 'Searching…' : flexMode ? '📅 Show Fare Calendar' : '🔍 Search Flights'}
          </button>
        </form>
      </div>

      {/* Price history trend badge */}
      {priceHistory && priceHistory.trend && (
        <div style={styles.trendBadge}>
          {priceHistory.trend === 'falling' && '📉 Prices are dropping on this route — good time to buy!'}
          {priceHistory.trend === 'rising' && '📈 Prices are rising — consider booking soon.'}
          {priceHistory.trend === 'stable' && '📊 Prices are stable on this route.'}
          {priceHistory.avg_price && (
            <span style={styles.trendSub}>
              {' '}(30-day avg: ${priceHistory.avg_price})
            </span>
          )}
        </div>
      )}

      {/* Flexible fare calendar */}
      {flexCalendar && (
        <div style={styles.calendarSection}>
          <h3 style={styles.calendarTitle}>
            Fare Calendar — {flexCalendar.from_iata} → {flexCalendar.to_iata}
          </h3>
          {flexCalendar.cheapest_date && (
            <p style={styles.calendarBest}>
              🏆 Cheapest day: <strong>{flexCalendar.cheapest_date}</strong> at{' '}
              <strong>${flexCalendar.cheapest_price?.toFixed(2)}</strong>
            </p>
          )}
          <div style={styles.calendarGrid}>
            {flexCalendar.calendar.map((day) => (
              <button
                key={day.date}
                onClick={() => day.min_price !== null && handleSearchFlexDate(day.date)}
                style={{
                  ...styles.calDay,
                  background: day.is_cheapest ? '#dcfce7' : day.min_price !== null ? '#eff6ff' : '#f9fafb',
                  border: day.is_cheapest ? '2px solid #16a34a' : '1px solid #e5e7eb',
                  cursor: day.min_price !== null ? 'pointer' : 'default',
                }}
              >
                <div style={styles.calDate}>{day.date.slice(5)}</div>
                {day.min_price != null ? (
                  <div style={{ ...styles.calPrice, color: day.is_cheapest ? '#16a34a' : '#1d4ed8' }}>
                    ${day.min_price.toFixed(0)}
                  </div>
                ) : (
                  <div style={styles.calNoPrice}>—</div>
                )}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Standard results */}
      {searched && !flexMode && results.length === 0 && !error && !loading && (
        <p style={styles.empty}>No flights found. Try different dates or airports.</p>
      )}

      {results.length > 0 && (
        <div style={styles.results}>
          <h3 style={styles.resultsHeading}>{results.length} flights found</h3>
          {results.map((offer, idx) => (
            <div key={offer.id ?? idx} style={styles.card}>
              <div style={styles.route}>
                <span style={styles.iata}>{offer.from_iata}</span>
                <span style={styles.arrow}> → </span>
                <span style={styles.iata}>{offer.to_iata}</span>
              </div>
              <div style={styles.meta}>
                {offer.airline_name || offer.airline || '—'}
                &nbsp;|&nbsp;{offer.stops ?? 0} stop(s)
                &nbsp;|&nbsp;{offer.cabin_class || form.cabin_class}
                {offer.duration_minutes && <> &nbsp;|&nbsp;{Math.floor(offer.duration_minutes / 60)}h {offer.duration_minutes % 60}m</>}
              </div>
              {offer.departure_time && (
                <div style={styles.meta}>
                  Dep: {new Date(offer.departure_time).toLocaleString()}
                  {offer.arrival_time && ` · Arr: ${new Date(offer.arrival_time).toLocaleString()}`}
                </div>
              )}
              <div style={styles.price}>
                {offer.currency || 'USD'} {Number(offer.price).toFixed(2)}
              </div>
              <div style={styles.cardActions}>
                {offer.booking_url ? (
                  <a href={offer.booking_url} target="_blank" rel="noopener noreferrer" style={styles.bookLink}>
                    Book Now
                  </a>
                ) : (
                  <span style={styles.noBook}>Contact airline</span>
                )}
                <button onClick={() => handleCreateAlert(offer)} style={styles.createAlertBtn}>
                  🔔 Create alert
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const styles = {
  page: { maxWidth: '860px', margin: '2rem auto', padding: '0 1rem' },
  heading: { fontSize: '1.75rem', marginBottom: '1.5rem', color: '#1d4ed8' },
  formCard: { background: '#fff', borderRadius: '10px', boxShadow: '0 2px 8px rgba(0,0,0,0.08)', marginBottom: '1.5rem' },
  form: { padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' },
  row: { display: 'flex', gap: '1rem', flexWrap: 'wrap', alignItems: 'flex-end' },
  field: { flex: '1', minWidth: '160px', display: 'flex', flexDirection: 'column', gap: '0.25rem' },
  label: { fontWeight: '600', fontSize: '0.875rem', color: '#374151' },
  input: { padding: '0.5rem 0.75rem', border: '1px solid #d1d5db', borderRadius: '6px', fontSize: '1rem' },
  checkLabel: { display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.9rem', color: '#374151', cursor: 'pointer', fontWeight: '600' },
  filterDetails: { marginTop: '0.25rem' },
  filterSummary: { cursor: 'pointer', fontWeight: '600', fontSize: '0.875rem', color: '#1d4ed8', userSelect: 'none' },
  button: { alignSelf: 'flex-start', marginTop: '0.25rem', padding: '0.75rem 2rem', background: '#1d4ed8', color: '#fff', border: 'none', borderRadius: '6px', fontSize: '1rem', fontWeight: '700', cursor: 'pointer' },
  error: { color: '#dc2626', fontSize: '0.875rem' },
  trendBadge: { background: '#fefce8', border: '1px solid #fde68a', borderRadius: '8px', padding: '0.75rem 1rem', marginBottom: '1.25rem', fontSize: '0.9rem', color: '#78350f', fontWeight: '600' },
  trendSub: { fontWeight: '400', color: '#92400e' },
  calendarSection: { background: '#fff', borderRadius: '10px', padding: '1.5rem', boxShadow: '0 2px 8px rgba(0,0,0,0.08)', marginBottom: '2rem' },
  calendarTitle: { fontSize: '1.125rem', fontWeight: '700', color: '#374151', marginBottom: '0.75rem' },
  calendarBest: { fontSize: '0.9rem', color: '#16a34a', marginBottom: '1rem' },
  calendarGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(90px, 1fr))', gap: '0.75rem' },
  calDay: { borderRadius: '8px', padding: '0.625rem 0.5rem', textAlign: 'center', transition: 'transform 0.1s', display: 'flex', flexDirection: 'column', gap: '0.25rem' },
  calDate: { fontSize: '0.8rem', fontWeight: '600', color: '#374151' },
  calPrice: { fontSize: '1rem', fontWeight: '700' },
  calNoPrice: { fontSize: '0.9rem', color: '#9ca3af' },
  empty: { textAlign: 'center', color: '#6b7280', marginTop: '2rem' },
  results: { display: 'flex', flexDirection: 'column', gap: '1rem' },
  resultsHeading: { fontSize: '1.25rem', marginBottom: '0.5rem', color: '#374151' },
  card: { background: '#fff', borderRadius: '8px', padding: '1.25rem', boxShadow: '0 2px 8px rgba(0,0,0,0.08)', display: 'flex', flexDirection: 'column', gap: '0.375rem' },
  route: { fontSize: '1.25rem', fontWeight: '700' },
  iata: { color: '#1d4ed8' },
  arrow: { color: '#6b7280' },
  meta: { fontSize: '0.875rem', color: '#6b7280' },
  price: { fontSize: '1.5rem', fontWeight: '700', color: '#16a34a', marginTop: '0.25rem' },
  cardActions: { display: 'flex', gap: '0.75rem', marginTop: '0.5rem', flexWrap: 'wrap' },
  bookLink: { background: '#1d4ed8', color: '#fff', padding: '0.5rem 1rem', borderRadius: '6px', textDecoration: 'none', fontWeight: '600', fontSize: '0.875rem' },
  noBook: { fontSize: '0.875rem', color: '#9ca3af', alignSelf: 'center' },
  createAlertBtn: { padding: '0.5rem 1rem', background: '#eff6ff', color: '#1d4ed8', border: '1px solid #bfdbfe', borderRadius: '6px', cursor: 'pointer', fontWeight: '600', fontSize: '0.875rem' },
};
