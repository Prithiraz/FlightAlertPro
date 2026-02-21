import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { supabase } from '../lib/supabase';
import { useAuth } from '../App';
import { apiFetch } from '../lib/api';

const CABIN_CLASSES = ['economy', 'premium_economy', 'business', 'first'];

export default function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [form, setForm] = useState({
    from_iata: '',
    to_iata: '',
    departure_date: '',
    return_date: '',
    passengers: 1,
    cabin_class: 'economy',
  });
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [searched, setSearched] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleSearch = async (e) => {
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

      const data = await apiFetch('/api/search', {
        method: 'POST',
        body: JSON.stringify(payload),
      });

      const offers = Array.isArray(data) ? data : data.results ?? [];
      setResults([...offers].sort((a, b) => (a.price ?? 0) - (b.price ?? 0)));
    } catch (err) {
      setError(err.message || 'Search failed');
    } finally {
      setLoading(false);
      setSearched(true);
    }
  };

  const handleLogout = async () => {
    await supabase.auth.signOut();
    navigate('/');
  };

  return (
    <div style={styles.page}>
      {/* Header */}
      <header style={styles.header}>
        <div style={styles.logo}>✈️ FlightAlertPro</div>
        <div style={styles.headerRight}>
          <span style={styles.userEmail}>{user?.email}</span>
          <button onClick={handleLogout} style={styles.logoutBtn}>Logout</button>
        </div>
      </header>

      <div style={styles.content}>
        {/* Flight Search */}
        <section style={styles.section}>
          <h2 style={styles.sectionTitle}>Search Flights</h2>
          <form onSubmit={handleSearch} style={styles.form}>
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

            {error && <p style={styles.error}>{error}</p>}

            <button type="submit" disabled={loading} style={styles.button}>
              {loading ? 'Searching...' : 'Search Flights'}
            </button>
          </form>

          {/* Results */}
          {loading && <p style={styles.empty}>Searching for flights...</p>}
          {searched && !loading && results.length === 0 && !error && (
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
                  {offer.provider && (
                    <div style={styles.meta}>Provider: {offer.provider}</div>
                  )}
                  <div style={styles.price}>
                    {offer.currency || 'USD'} {Number(offer.price).toFixed(2)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* My Alerts Placeholder */}
        <section style={styles.section}>
          <h2 style={styles.sectionTitle}>My Alerts</h2>
          <p style={styles.placeholder}>Price alerts coming soon. Stay tuned!</p>
        </section>
      </div>
    </div>
  );
}

const styles = {
  page: { minHeight: '100vh', background: '#f3f4f6' },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '1rem 2rem',
    background: '#1d4ed8',
    color: '#fff',
  },
  logo: { fontWeight: 'bold', fontSize: '1.25rem' },
  headerRight: { display: 'flex', alignItems: 'center', gap: '1rem' },
  userEmail: { fontSize: '0.875rem', opacity: 0.85 },
  logoutBtn: {
    background: 'transparent',
    border: '1px solid #fff',
    color: '#fff',
    padding: '0.375rem 0.75rem',
    borderRadius: '4px',
    cursor: 'pointer',
    fontWeight: '500',
  },
  content: { maxWidth: '800px', margin: '2rem auto', padding: '0 1rem' },
  section: {
    background: '#fff',
    borderRadius: '8px',
    padding: '1.5rem',
    boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
    marginBottom: '2rem',
  },
  sectionTitle: { fontSize: '1.25rem', fontWeight: '700', color: '#1d4ed8', marginBottom: '1.25rem', marginTop: 0 },
  form: { display: 'flex', flexDirection: 'column', gap: '0.75rem' },
  row: { display: 'flex', gap: '1rem', flexWrap: 'wrap' },
  field: { flex: '1', minWidth: '160px', display: 'flex', flexDirection: 'column', gap: '0.25rem' },
  label: { fontWeight: '600', fontSize: '0.875rem', color: '#374151' },
  input: { padding: '0.5rem 0.75rem', border: '1px solid #d1d5db', borderRadius: '6px', fontSize: '1rem' },
  button: {
    alignSelf: 'flex-start',
    marginTop: '0.25rem',
    padding: '0.625rem 1.75rem',
    background: '#1d4ed8',
    color: '#fff',
    border: 'none',
    borderRadius: '6px',
    fontSize: '1rem',
    fontWeight: '600',
    cursor: 'pointer',
  },
  error: { color: '#dc2626', fontSize: '0.875rem', margin: 0 },
  empty: { textAlign: 'center', color: '#6b7280', marginTop: '1.5rem' },
  results: { marginTop: '1.5rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' },
  resultsHeading: { fontSize: '1rem', fontWeight: '700', color: '#374151', marginBottom: '0.5rem' },
  card: {
    border: '1px solid #e5e7eb',
    borderRadius: '6px',
    padding: '1rem',
    display: 'flex',
    flexDirection: 'column',
    gap: '0.25rem',
  },
  route: { fontSize: '1.125rem', fontWeight: '700' },
  iata: { color: '#1d4ed8' },
  arrow: { color: '#6b7280' },
  meta: { fontSize: '0.875rem', color: '#6b7280' },
  price: { fontSize: '1.25rem', fontWeight: '700', color: '#16a34a' },
  placeholder: { color: '#9ca3af', fontStyle: 'italic' },
};
