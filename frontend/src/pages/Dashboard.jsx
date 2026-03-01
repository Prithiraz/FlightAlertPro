import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { supabase } from '../lib/supabase';
import { useAuth } from '../App';
import { usePreferences } from '../lib/PreferencesContext';
import { searchFlights, listAlerts, getMe, saveSearch } from '../lib/api';
import { convert, formatCurrency } from '../lib/currency';
import { formatDate } from '../lib/datetime';
import { t } from '../i18n';
import AirportAutocomplete from '../components/AirportAutocomplete';
import AirlineAutocomplete from '../components/AirlineAutocomplete';
import UpgradeBanner from '../components/UpgradeBanner';

const CABIN_CLASSES = ['economy', 'premium_economy', 'business', 'first'];
const CURRENCIES = ['USD', 'EUR', 'GBP', 'CAD', 'AUD', 'INR', 'JPY', 'SGD', 'AED'];

export default function Dashboard() {
  const { user } = useAuth();
  const { locale, timezone, homeCurrency } = usePreferences();
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
  const [displayCurrency, setDisplayCurrency] = useState(null);
  // converted prices: Map<offerIndex, convertedAmount|null>
  const [convertedPrices, setConvertedPrices] = useState({});

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

  // Sync displayCurrency with user's home currency preference (initialize only)
  useEffect(() => {
    setDisplayCurrency((prev) => prev || homeCurrency);
  }, [homeCurrency]);

  // When results come in, convert prices to displayCurrency using Frankfurter
  useEffect(() => {
    if (!results.length || !displayCurrency) return;
    let cancelled = false;
    setConvertedPrices({});
    results.forEach((offer, idx) => {
      const offerCurrency = (offer.currency || 'USD').toUpperCase();
      if (offerCurrency === displayCurrency) {
        setConvertedPrices((prev) => ({ ...prev, [idx]: Number(offer.price) }));
        return;
      }
      convert(Number(offer.price), offerCurrency, displayCurrency).then((val) => {
        if (!cancelled) setConvertedPrices((prev) => ({ ...prev, [idx]: val }));
      });
    });
    return () => { cancelled = true; };
  }, [results, displayCurrency]);

  return (
    <div style={styles.page}>
      <div style={styles.content}>
        {meData && (
          <UpgradeBanner usage={meData.usage} limits={meData.limits} plan={meData.plan} />
        )}
        {/* Flight Search */}
        <section style={styles.section}>
          <h2 style={styles.sectionTitle}>{t('dashboard.searchFlights')}</h2>
          <form onSubmit={handleSearch} style={styles.form}>
            <div style={styles.row}>
              <AirportAutocomplete
                label={t('common.from')}
                placeholder="City, airport or IATA (e.g. London)"
                value={form.from_iata}
                onChange={(v) => setForm((p) => ({ ...p, from_iata: v }))}
                required
              />
              <AirportAutocomplete
                label={t('common.to')}
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
              {loading ? t('dashboard.searching') : t('dashboard.searchBtn')}
            </button>
          </form>

          {/* Results */}
          {loading && <p style={styles.empty}>{t('dashboard.searching')}</p>}
          {searched && !loading && results.length === 0 && !error && (
            <p style={styles.empty}>{t('dashboard.noResults')}</p>
          )}
          {results.length > 0 && (
            <div style={styles.results}>
              <div style={styles.resultsHeader}>
                <h3 style={styles.resultsHeading}>{t('dashboard.flightsFound', { n: results.length })}</h3>
                <div style={styles.currencyRow}>
                  <button onClick={handleSaveSearch} style={styles.saveSearchBtn}>{t('dashboard.saveSearch')}</button>
                  {saveSearchMsg && <span style={styles.saveSearchMsg}>{saveSearchMsg}</span>}
                  <label style={styles.currencyLabel}>{t('dashboard.displayIn')}</label>
                  <select
                    value={displayCurrency || homeCurrency}
                    onChange={(e) => setDisplayCurrency(e.target.value)}
                    style={styles.currencySelect}
                  >
                    {CURRENCIES.map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                </div>
              </div>
              {results.map((offer, idx) => {
                const converted = convertedPrices[idx];
                const offerCurrency = (offer.currency || 'USD').toUpperCase();
                const activeCurrency = displayCurrency || homeCurrency;
                return (
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
                      {converted != null
                        ? formatCurrency(converted, activeCurrency, locale)
                        : formatCurrency(Number(offer.price), offerCurrency, locale)}
                      {offerCurrency !== activeCurrency && converted != null && (
                        <span style={styles.originalPrice}>
                          {' '}(orig. {formatCurrency(Number(offer.price), offerCurrency, locale)})
                        </span>
                      )}
                    </div>
                    <button onClick={() => handleCreateAlert(offer)} style={styles.createAlertBtn}>
                      {t('dashboard.createAlert')}
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {/* My Alerts Summary */}
        <section style={styles.section}>
          <div style={styles.alertsHeader}>
            <h2 style={styles.sectionTitle}>{t('dashboard.myAlerts')}</h2>
            <Link to="/alerts" style={styles.manageLink}>{t('dashboard.manageAlerts')}</Link>
          </div>
          {alertsLoading ? (
            <p style={styles.empty}>Loading alerts...</p>
          ) : alertsError ? (
            <p style={styles.error}>{alertsError}</p>
          ) : myAlerts.length === 0 ? (
            <p style={styles.empty}>{t('dashboard.noAlerts')} <Link to="/alerts" style={styles.inlineLink}>{t('dashboard.createOne')}</Link>.</p>
          ) : (
            <div style={styles.alertList}>
              {myAlerts.slice(0, 5).map((alert) => (
                <div key={alert.id} style={styles.alertCard}>
                  <span style={styles.iata}>{alert.from_iata}</span>
                  <span style={styles.arrow}> → </span>
                  <span style={styles.iata}>{alert.to_iata}</span>
                  <span style={styles.alertMeta}>
                    &nbsp;· Max: {formatCurrency(Number(alert.max_price), alert.currency || 'USD', locale)}
                    {alert.departure_date && ` · Dep: ${formatDate(alert.departure_date, { locale, timezone })}`}
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
