import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { supabase } from '../lib/supabase';
import { useAuth } from '../App';
import { searchFlights, listAlerts, getCurrencyRates, getMe, saveSearch } from '../lib/api';
import AirportAutocomplete from '../components/AirportAutocomplete';
import AirlineAutocomplete from '../components/AirlineAutocomplete';
import UpgradeBanner from '../components/UpgradeBanner';

const CABIN_CLASSES = ['economy', 'premium_economy', 'business', 'first'];
const CURRENCIES = ['USD', 'EUR', 'GBP', 'CAD', 'AUD', 'INR', 'JPY', 'SGD', 'AED'];

export default function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    supabase.auth.getUser().then(({ data: { user: u } }) => {
      if (!u) navigate('/');
    });

    const { data: authListener } = supabase.auth.onAuthStateChange((_event, session) => {
      if (!session?.user) navigate('/');
    });

    return () => {
      authListener?.subscription?.unsubscribe();
    };
  }, [navigate]);

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
  const [displayCurrency, setDisplayCurrency] = useState('USD');
  const [fxRates, setFxRates] = useState(null);

  const [myAlerts, setMyAlerts] = useState([]);
  const [alertsLoading, setAlertsLoading] = useState(false);
  const [alertsError, setAlertsError] = useState('');
  const [meData, setMeData] = useState(null);
  const [saveSearchMsg, setSaveSearchMsg] = useState('');

  useEffect(() => {
    if (user?.email) {
      setAlertsLoading(true);
      listAlerts()
        .then((data) => setMyAlerts(Array.isArray(data) ? data : data.alerts ?? []))
        .catch((err) => setAlertsError(err.message || 'Failed to load alerts'))
        .finally(() => setAlertsLoading(false));
      getMe().then(setMeData).catch(() => {});
    }
  }, [user?.email]);

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

      const data = await searchFlights(payload);

      const offers = Array.isArray(data) ? data : (data.offers ?? data.results ?? []);
      setResults([...offers].sort((a, b) => (a.price ?? 0) - (b.price ?? 0)));
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

  const handleSaveSearch = async () => {
    setSaveSearchMsg('');
    const name = `${form.from_iata.toUpperCase()} → ${form.to_iata.toUpperCase()} ${form.departure_date}`.trim();
    try {
      await saveSearch(name || 'My search', {
        from_iata: form.from_iata.toUpperCase(),
        to_iata: form.to_iata.toUpperCase(),
        departure_date: form.departure_date,
        return_date: form.return_date,
        passengers: form.passengers,
        cabin_class: form.cabin_class,
      });
      setSaveSearchMsg('Saved!');
      setTimeout(() => setSaveSearchMsg(''), 3000);
    } catch (err) {
      setSaveSearchMsg(err.message || 'Failed');
    }
  };

  // Fetch FX rates once on mount (backend caches Frankfurter rates for 1 hour)
  useEffect(() => {
    getCurrencyRates('USD')
      .then((data) => setFxRates({ USD: 1, ...data.rates }))
      .catch(() => setFxRates(null));
  }, []);

  const convertPrice = (price, offerCurrency) => {
    if (!fxRates || price == null) return Number(price);
    const from = (offerCurrency || 'USD').toUpperCase();
    const to = displayCurrency;
    if (from === to) return Number(price);
    const usdAmount = fxRates[from] ? Number(price) / fxRates[from] : Number(price);
    return fxRates[to] ? usdAmount * fxRates[to] : usdAmount;
  };

  return (
    <div style={styles.page}>
      <div style={styles.content}>
        {meData && (
          <UpgradeBanner usage={meData.usage} limits={meData.limits} plan={meData.plan} />
        )}
        {/* Flight Search */}
        <section style={styles.section}>
          <h2 style={styles.sectionTitle}>Search Flights</h2>
          <form onSubmit={handleSearch} style={styles.form}>
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

          {/* Results */}
          {loading && <p style={styles.empty}>Searching for flights...</p>}
          {searched && !loading && results.length === 0 && !error && (
            <p style={styles.empty}>No flights found. Try different dates or airports.</p>
          )}
          {results.length > 0 && (
            <div style={styles.results}>
              <div style={styles.resultsHeader}>
                <h3 style={styles.resultsHeading}>{results.length} flights found</h3>
                <div style={styles.currencyRow}>
                  <button onClick={handleSaveSearch} style={styles.saveSearchBtn}>💾 Save Search</button>
                  {saveSearchMsg && <span style={styles.saveSearchMsg}>{saveSearchMsg}</span>}
                  <label style={styles.currencyLabel}>Display in:</label>
                  <select
                    value={displayCurrency}
                    onChange={(e) => setDisplayCurrency(e.target.value)}
                    style={styles.currencySelect}
                  >
                    {CURRENCIES.map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                </div>
              </div>
              {results.map((offer, idx) => (
                <div key={offer.id ?? idx} style={styles.card}>
                  <div style={styles.route}>
                    <span style={styles.iata}>{offer.from_iata}</span>
                    <span style={styles.arrow}> → </span>
                    <span style={styles.iata}>{offer.to_iata}</span>
                  </div>
                  {(offer.source || offer.provider) && (
                    <div style={styles.meta}>Provider: {offer.source || offer.provider}</div>
                  )}
                  <div style={styles.price}>
                    {displayCurrency} {convertPrice(offer.price, offer.currency).toFixed(2)}
                    {fxRates && (offer.currency || 'USD').toUpperCase() !== displayCurrency && (
                      <span style={styles.originalPrice}>
                        {' '}(orig. {offer.currency || 'USD'} {Number(offer.price).toFixed(2)})
                      </span>
                    )}
                  </div>
                  <button onClick={() => handleCreateAlert(offer)} style={styles.createAlertBtn}>
                    Create alert
                  </button>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* My Alerts Summary */}
        <section style={styles.section}>
          <div style={styles.alertsHeader}>
            <h2 style={styles.sectionTitle}>My Alerts</h2>
            <Link to="/alerts" style={styles.manageLink}>Manage alerts →</Link>
          </div>
          {alertsLoading ? (
            <p style={styles.empty}>Loading alerts...</p>
          ) : alertsError ? (
            <p style={styles.error}>{alertsError}</p>
          ) : myAlerts.length === 0 ? (
            <p style={styles.empty}>No alerts yet. <Link to="/alerts" style={styles.inlineLink}>Create one</Link>.</p>
          ) : (
            <div style={styles.alertList}>
              {myAlerts.slice(0, 5).map((alert) => (
                <div key={alert.id} style={styles.alertCard}>
                  <span style={styles.iata}>{alert.from_iata}</span>
                  <span style={styles.arrow}> → </span>
                  <span style={styles.iata}>{alert.to_iata}</span>
                  <span style={styles.alertMeta}>
                    &nbsp;· Max: {alert.currency || 'USD'} {Number(alert.max_price).toFixed(2)}
                    {alert.departure_date && ` · Dep: ${alert.departure_date}`}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

const styles = {
  page: { minHeight: '100vh', background: '#f3f4f6' },
  content: { maxWidth: '800px', margin: '2rem auto', padding: '0 1rem' },
  section: {
    background: '#fff',
    borderRadius: '8px',
    padding: '1.5rem',
    boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
    marginBottom: '2rem',
  },
  sectionTitle: { fontSize: '1.25rem', fontWeight: '700', color: '#1d4ed8', marginBottom: '1.25rem', marginTop: 0 },
  alertsHeader: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem' },
  manageLink: { fontSize: '0.9rem', color: '#1d4ed8', textDecoration: 'none', fontWeight: '600' },
  inlineLink: { color: '#1d4ed8', textDecoration: 'none', fontWeight: '600' },
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
  createAlertBtn: {
    alignSelf: 'flex-start',
    marginTop: '0.5rem',
    padding: '0.375rem 0.875rem',
    background: '#eff6ff',
    color: '#1d4ed8',
    border: '1px solid #bfdbfe',
    borderRadius: '6px',
    cursor: 'pointer',
    fontWeight: '600',
    fontSize: '0.875rem',
  },
  saveSearchBtn: { padding: '0.375rem 0.875rem', background: '#f0fdf4', color: '#16a34a', border: '1px solid #bbf7d0', borderRadius: '6px', cursor: 'pointer', fontWeight: '600', fontSize: '0.875rem' },
  saveSearchMsg: { fontSize: '0.85rem', color: '#16a34a' },
  error: { color: '#dc2626', fontSize: '0.875rem', margin: 0 },
  empty: { textAlign: 'center', color: '#6b7280', marginTop: '1.5rem' },
  results: { marginTop: '1.5rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' },
  resultsHeader: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' },
  resultsHeading: { fontSize: '1rem', fontWeight: '700', color: '#374151', marginBottom: 0 },
  currencyRow: { display: 'flex', alignItems: 'center', gap: '0.5rem' },
  currencyLabel: { fontSize: '0.875rem', fontWeight: '600', color: '#374151' },
  currencySelect: { padding: '0.25rem 0.5rem', border: '1px solid #d1d5db', borderRadius: '4px', fontSize: '0.875rem', background: '#fff', cursor: 'pointer' },
  originalPrice: { fontSize: '0.75rem', color: '#9ca3af', fontWeight: '400' },
  card: {
    border: '1px solid #e5e7eb',
    borderRadius: '6px',
    padding: '1rem',
    display: 'flex',
    flexDirection: 'column',
    gap: '0.25rem',
  },
  route: { fontSize: '1.125rem', fontWeight: '700' },
  iata: { color: '#1d4ed8', fontWeight: '700' },
  arrow: { color: '#6b7280' },
  meta: { fontSize: '0.875rem', color: '#6b7280' },
  price: { fontSize: '1.25rem', fontWeight: '700', color: '#16a34a' },
  alertList: { display: 'flex', flexDirection: 'column', gap: '0.5rem' },
  alertCard: {
    padding: '0.625rem 0.875rem',
    border: '1px solid #e5e7eb',
    borderRadius: '6px',
    fontSize: '0.9rem',
    color: '#374151',
  },
  alertMeta: { color: '#6b7280', fontSize: '0.875rem' },
};
