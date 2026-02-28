import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { searchFlights } from '../lib/api';
import AirportAutocomplete from '../components/AirportAutocomplete';
import AirlineAutocomplete from '../components/AirlineAutocomplete';

const CABIN_CLASSES = ['economy', 'premium_economy', 'business', 'first'];

export default function Search() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    from_iata: '',
    to_iata: '',
    departure_date: '',
    return_date: '',
    passengers: 1,
    cabin_class: 'economy',
    airline_filter: '',
  });
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [searched, setSearched] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setResults([]);
    setSearched(false);

    try {
      const payload = {
        from_iata: form.from_iata.toUpperCase(),
        to_iata: form.to_iata.toUpperCase(),
        departure_date: form.departure_date,
        passengers: Number(form.passengers),
        cabin_class: form.cabin_class,
      };
      if (form.return_date) {
        payload.return_date = form.return_date;
      }

      const data = await searchFlights(payload);

      // Support { offers: [...] }, { results: [...] }, or a plain array
      const offers = Array.isArray(data) ? data : (data.offers ?? data.results ?? []);
      const sorted = [...offers].sort((a, b) => (a.price ?? 0) - (b.price ?? 0));
      setResults(sorted);
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

  return (
    <div style={styles.page}>
      <h2 style={styles.heading}>Search Flights</h2>

      <form onSubmit={handleSubmit} style={styles.form}>
        <div style={styles.row}>
          <AirportAutocomplete
            label="From"
            placeholder="City, airport or IATA (e.g. London)"
            value={form.from_iata}
            onChange={(v) => setForm((p) => ({ ...p, from_iata: v }))}
            required
          />
          <AirportAutocomplete
            label="To"
            placeholder="City, airport or IATA (e.g. JFK)"
            value={form.to_iata}
            onChange={(v) => setForm((p) => ({ ...p, to_iata: v }))}
            required
          />
        </div>

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
        </div>

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
            <select
              name="cabin_class"
              value={form.cabin_class}
              onChange={handleChange}
              style={styles.input}
            >
              {CABIN_CLASSES.map((c) => (
                <option key={c} value={c}>
                  {c.replace('_', ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div style={styles.row}>
          <AirlineAutocomplete
            label="Airline Filter (optional)"
            placeholder="e.g. Emirates, EK"
            value={form.airline_filter}
            onChange={(v) => setForm((p) => ({ ...p, airline_filter: v }))}
          />
          <div style={{ flex: 1, minWidth: '160px' }} />
        </div>

        {error && <p style={styles.error}>{error}</p>}

        <button type="submit" disabled={loading} style={styles.button}>
          {loading ? 'Searching...' : 'Search Flights'}
        </button>
      </form>

      {searched && results.length === 0 && !error && (
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
                {offer.airline_name || offer.airline || '—'} &nbsp;|&nbsp;
                {offer.stops ?? 0} stop(s) &nbsp;|&nbsp;
                {offer.cabin_class || form.cabin_class}
              </div>
              {offer.departure && (
                <div style={styles.meta}>
                  Dep: {new Date(offer.departure).toLocaleString()}
                  {offer.arrival && ` · Arr: ${new Date(offer.arrival).toLocaleString()}`}
                </div>
              )}
              <div style={styles.price}>
                {offer.currency || 'USD'} {Number(offer.price).toFixed(2)}
              </div>
              {offer.booking_link ? (
                <a
                  href={offer.booking_link}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={styles.bookLink}
                >
                  Book Now
                </a>
              ) : (
                <span style={styles.noBook}>Contact airline</span>
              )}
              <button onClick={() => handleCreateAlert(offer)} style={styles.createAlertBtn}>
                Create alert
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const styles = {
  page: { maxWidth: '800px', margin: '2rem auto', padding: '0 1rem' },
  heading: { fontSize: '1.75rem', marginBottom: '1.5rem', color: '#1d4ed8' },
  form: { background: '#fff', padding: '1.5rem', borderRadius: '8px', boxShadow: '0 2px 8px rgba(0,0,0,0.08)', marginBottom: '2rem' },
  row: { display: 'flex', gap: '1rem', marginBottom: '1rem', flexWrap: 'wrap' },
  field: { flex: '1', minWidth: '160px', display: 'flex', flexDirection: 'column', gap: '0.25rem' },
  label: { fontWeight: '600', fontSize: '0.875rem', color: '#374151' },
  input: { padding: '0.5rem 0.75rem', border: '1px solid #d1d5db', borderRadius: '6px', fontSize: '1rem' },
  button: { marginTop: '0.5rem', padding: '0.75rem 2rem', background: '#1d4ed8', color: '#fff', border: 'none', borderRadius: '6px', fontSize: '1rem', fontWeight: '600', cursor: 'pointer' },
  error: { color: '#dc2626', fontSize: '0.875rem' },
  empty: { textAlign: 'center', color: '#6b7280', marginTop: '2rem' },
  results: { display: 'flex', flexDirection: 'column', gap: '1rem' },
  resultsHeading: { fontSize: '1.25rem', marginBottom: '0.5rem', color: '#374151' },
  card: { background: '#fff', borderRadius: '8px', padding: '1.25rem', boxShadow: '0 2px 8px rgba(0,0,0,0.08)', display: 'flex', flexDirection: 'column', gap: '0.375rem' },
  route: { fontSize: '1.25rem', fontWeight: '700' },
  iata: { color: '#1d4ed8' },
  arrow: { color: '#6b7280' },
  meta: { fontSize: '0.875rem', color: '#6b7280' },
  price: { fontSize: '1.5rem', fontWeight: '700', color: '#16a34a', marginTop: '0.25rem' },
  bookLink: { alignSelf: 'flex-start', marginTop: '0.5rem', background: '#1d4ed8', color: '#fff', padding: '0.5rem 1rem', borderRadius: '6px', textDecoration: 'none', fontWeight: '600', fontSize: '0.875rem' },
  noBook: { fontSize: '0.875rem', color: '#9ca3af', marginTop: '0.5rem' },
  createAlertBtn: { alignSelf: 'flex-start', marginTop: '0.5rem', padding: '0.375rem 0.875rem', background: '#eff6ff', color: '#1d4ed8', border: '1px solid #bfdbfe', borderRadius: '6px', cursor: 'pointer', fontWeight: '600', fontSize: '0.875rem' },
};
