import { useState, useEffect, Fragment } from 'react';
import { useNavigate } from 'react-router-dom';
import { searchFlights, getPreferences } from '../lib/api';
import { useAuth } from '../App';
import { buildHotelUrl } from '../lib/hotelAffiliate';
import AirportAutocomplete from '../components/AirportAutocomplete';
import AirlineAutocomplete from '../components/AirlineAutocomplete';
import FlightResultCard from '../components/FlightResultCard';
import FlightCardSkeleton from '../components/FlightCardSkeleton';
import Toast from '../components/Toast';

const SKELETON_COUNT = 4;
const AD_INSERTION_INDEX = 1;

const CABIN_CLASSES = ['economy', 'premium_economy', 'business', 'first'];

function AncillaryAdCard({ destination, checkinDate }) {
  const hotelUrl = buildHotelUrl(destination, checkinDate);
  return (
    <div style={adCardStyles.card}>
      <span style={adCardStyles.emoji}>🏨</span>
      <div style={adCardStyles.body}>
        <p style={adCardStyles.headline}>
          Unlock 15% off hotels in <strong>{destination}</strong> when you book today
        </p>
        <a
          href={hotelUrl}
          target="_blank"
          rel="noopener noreferrer"
          style={adCardStyles.cta}
        >
          View Hotel Deals →
        </a>
      </div>
    </div>
  );
}

const adCardStyles = {
  card: {
    display: 'flex',
    alignItems: 'center',
    gap: '1rem',
    background: 'linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%)',
    border: '1px solid #fcd34d',
    borderRadius: '8px',
    padding: '1rem 1.25rem',
  },
  emoji: { fontSize: '2rem', lineHeight: 1 },
  body: { display: 'flex', flexDirection: 'column', gap: '0.35rem' },
  headline: { margin: 0, fontSize: '0.95rem', color: '#92400e' },
  cta: {
    display: 'inline-block',
    padding: '0.4rem 1rem',
    background: '#f59e0b',
    color: '#fff',
    borderRadius: '6px',
    fontSize: '0.875rem',
    fontWeight: '600',
    textDecoration: 'none',
    width: 'fit-content',
  },
};

export default function Search() {
  const navigate = useNavigate();
  const { user, subscriptionTier } = useAuth();
  const [form, setForm] = useState({
    from_iata: '',
    to_iata: '',
    departure_date: '',
    return_date: '',
    passengers: 1,
    cabin_class: 'economy',
    airline: '',
  });
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [toast, setToast] = useState('');
  const [searched, setSearched] = useState(false);

  // Auto-populate from user preferences on mount
  useEffect(() => {
    if (!user?.email) return;
    getPreferences(user.email)
      .then((prefs) => {
        setForm((prev) => ({
          ...prev,
          from_iata: prefs.home_airport || prev.from_iata,
          cabin_class: prefs.default_cabin || prev.cabin_class,
        }));
      })
      .catch((err) => {
        console.error('Failed to load preferences:', err);
      });
  }, [user?.email]);

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

    if (!form.from_iata || !form.to_iata) {
      setError('Please select an origin and destination airport.');
      setLoading(false);
      return;
    }

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
      const msg = err.message || 'Search failed';
      setError(msg);
      setToast(msg);
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
          <div style={styles.field}>
            <label style={styles.label}>From</label>
            <AirportAutocomplete
              placeholder="LAX – Los Angeles"
              value={form.from_iata}
              onChange={(iata) => setForm((prev) => ({ ...prev, from_iata: iata }))}
            />
          </div>
          <div style={styles.field}>
            <label style={styles.label}>To</label>
            <AirportAutocomplete
              placeholder="JFK – New York"
              value={form.to_iata}
              onChange={(iata) => setForm((prev) => ({ ...prev, to_iata: iata }))}
            />
          </div>
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
          <div style={styles.field}>
            <label style={styles.label}>Airline (optional)</label>
            <AirlineAutocomplete
              value={form.airline}
              onChange={(iata) => setForm((prev) => ({ ...prev, airline: iata }))}
            />
          </div>
        </div>

        {error && <p style={styles.error}>{error}</p>}

        <button type="submit" disabled={loading} style={styles.button}>
          {loading ? 'Searching...' : 'Search Flights'}
        </button>
      </form>

      {/* Skeleton loaders while fetching */}
      {loading && (
        <div style={styles.results}>
          {Array.from({ length: SKELETON_COUNT }).map((_, i) => (
            <FlightCardSkeleton key={`skeleton-${i}`} />
          ))}
        </div>
      )}

      {!loading && searched && results.length === 0 && !error && (
        <p style={styles.empty}>No flights found. Try different dates or airports.</p>
      )}

      {!loading && results.length > 0 && (
        <div style={styles.results}>
          <h3 style={styles.resultsHeading}>{results.length} flights found</h3>
          {results.map((offer, idx) => (
            <Fragment key={offer.id ?? idx}>
              <FlightResultCard
                offer={offer}
                cabinClass={form.cabin_class}
                onCreateAlert={handleCreateAlert}
                subscriptionTier={subscriptionTier}
              />
              {idx === AD_INSERTION_INDEX && (
                <AncillaryAdCard
                  destination={form.to_iata.toUpperCase()}
                  checkinDate={form.departure_date}
                />
              )}
            </Fragment>
          ))}
        </div>
      )}

      <Toast message={toast} onClose={() => setToast('')} />
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
};
