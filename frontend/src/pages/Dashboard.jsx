import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { supabase } from '../lib/supabase';
import { useAuth } from '../App';
import { searchFlights, listAlerts, createAlert, getLiveFlightPrice } from '../lib/api';
import AirportAutocomplete from '../components/AirportAutocomplete';
import AirlineAutocomplete from '../components/AirlineAutocomplete';

const CABIN_CLASSES = ['economy', 'premium_economy', 'business', 'first'];
const CURRENCIES = ['USD', 'EUR', 'GBP', 'CAD', 'AUD', 'INR'];

export default function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    supabase.auth.getUser().then(({ data: { user: u } }) => {
      if (!u) navigate('/auth');
    });

    const { data: authListener } = supabase.auth.onAuthStateChange((_event, session) => {
      if (!session?.user) navigate('/auth');
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
    currency: 'USD',
    airline: '',
  });
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [searched, setSearched] = useState(false);

  const [myAlerts, setMyAlerts] = useState([]);
  const [alertsLoading, setAlertsLoading] = useState(false);
  const [alertsError, setAlertsError] = useState('');
  const [activeAlerts, setActiveAlerts] = useState([]);
  const [activeAlertsLoading, setActiveAlertsLoading] = useState(false);
  const [activeAlertsError, setActiveAlertsError] = useState('');

  // Purchased flight form state
  const [purchaseForm, setPurchaseForm] = useState({
    from_iata: '',
    to_iata: '',
    departure_date: '',
    airline: '',
    purchase_price: '',
  });
  const [purchaseLoading, setPurchaseLoading] = useState(false);
  const [purchaseError, setPurchaseError] = useState('');
  const [purchaseSuccess, setPurchaseSuccess] = useState('');
  const [showPurchaseForm, setShowPurchaseForm] = useState(false);

  useEffect(() => {
    if (user?.email) {
      setAlertsLoading(true);
      listAlerts(user.email)
        .then((data) => setMyAlerts(Array.isArray(data) ? data : data.alerts ?? []))
        .catch((err) => setAlertsError(err.message || 'Failed to load alerts'))
        .finally(() => setAlertsLoading(false));
    }
  }, [user?.email]);

  const fetchActiveAlerts = async () => {
    setActiveAlertsLoading(true);
    setActiveAlertsError('');
    try {
      const { data: { session } } = await supabase.auth.getSession();
      const userEmail = session?.user?.email;
      if (!userEmail) {
        setActiveAlerts([]);
        return;
      }

      const { data, error: fetchError } = await supabase
        .from('price_alerts')
        .select('id, from_iata, to_iata, departure_date, max_price, currency, active')
        .eq('user_email', userEmail)
        .eq('active', true)
        .order('created_at', { ascending: false });

      if (fetchError) throw fetchError;
      const alerts = data || [];
      const alertsWithLivePrices = [];
      for (const alert of alerts) {
        if (!alert.departure_date) {
          alertsWithLivePrices.push({
            ...alert,
            current_live_price: null,
            current_live_price_currency: alert.currency || 'USD',
          });
          continue;
        }

        try {
          const livePrice = await getLiveFlightPrice(
            alert.from_iata,
            alert.to_iata,
            alert.departure_date
          );
          alertsWithLivePrices.push({
            ...alert,
            current_live_price: Number(livePrice.current_price),
            current_live_price_currency: livePrice.currency || alert.currency || 'USD',
          });
        } catch {
          alertsWithLivePrices.push({
            ...alert,
            current_live_price: null,
            current_live_price_currency: alert.currency || 'USD',
          });
        }
      }

      setActiveAlerts(alertsWithLivePrices);
    } catch (err) {
      setActiveAlertsError(err.message || 'Failed to load active alerts.');
    } finally {
      setActiveAlertsLoading(false);
    }
  };

  useEffect(() => {
    fetchActiveAlerts();
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
        currency: form.currency,
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

  const formatSliceTime = (timeValue) => {
    if (!timeValue) return '--:--';
    const parsed = new Date(timeValue);
    if (Number.isNaN(parsed.getTime())) {
      const fallback = String(timeValue).split('T')[1];
      return fallback ? fallback.slice(0, 5) : '--:--';
    }
    return parsed.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
  };

  const formatStops = (stops) => (stops === 0 ? 'direct' : `${stops ?? 0} stop(s)`);

  const formatCheckedBags = (offer) => {
    const checkedBags = offer?.slices?.[0]?.segments?.[0]?.checked_bags;
    if (checkedBags === undefined || checkedBags === null || checkedBags === '') return 'N/A';
    if (typeof checkedBags === 'number' || typeof checkedBags === 'string') return checkedBags;
    if (typeof checkedBags === 'object') {
      if (checkedBags.quantity !== undefined && checkedBags.quantity !== null) return checkedBags.quantity;
      if (checkedBags.count !== undefined && checkedBags.count !== null) return checkedBags.count;
      if (checkedBags.weight !== undefined && checkedBags.weight !== null) return checkedBags.weight;
    }
    return 'N/A';
  };

  const handlePurchaseFormChange = (e) => {
    const { name, value } = e.target;
    setPurchaseForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleAddPurchasedFlight = async (e) => {
    e.preventDefault();
    setPurchaseLoading(true);
    setPurchaseError('');
    setPurchaseSuccess('');

    if (!purchaseForm.from_iata || !purchaseForm.to_iata) {
      setPurchaseError('Please select an origin and destination airport.');
      setPurchaseLoading(false);
      return;
    }
    if (!purchaseForm.purchase_price || Number(purchaseForm.purchase_price) <= 0) {
      setPurchaseError('Please enter the price you paid.');
      setPurchaseLoading(false);
      return;
    }

    try {
      await createAlert({
        user_email: user.email,
        from_iata: purchaseForm.from_iata.toUpperCase(),
        to_iata: purchaseForm.to_iata.toUpperCase(),
        departure_date: purchaseForm.departure_date || undefined,
        airline: purchaseForm.airline || undefined,
        // max_price is required by the backend; set it to purchase_price so the
        // worker knows which route to query, even though threshold logic is
        // overridden for purchased alerts
        max_price: Number(purchaseForm.purchase_price),
        is_purchased: true,
        purchase_price: Number(purchaseForm.purchase_price),
        notification_channels: ['email'],
      });

      setPurchaseSuccess(`✅ Tracking added! We'll alert you if the price drops $25 or more.`);
      setPurchaseForm({ from_iata: '', to_iata: '', departure_date: '', airline: '', purchase_price: '' });
      setShowPurchaseForm(false);

      // Refresh alerts list
      if (user?.email) {
        const data = await listAlerts(user.email);
        setMyAlerts(Array.isArray(data) ? data : data.alerts ?? []);
      }
    } catch (err) {
      setPurchaseError(err.message || 'Failed to add purchased flight.');
    } finally {
      setPurchaseLoading(false);
    }
  };

  const purchasedAlerts = myAlerts.filter((a) => a.is_purchased);
  const lowestLivePrice = activeAlerts
    .map((a) => Number(a.current_live_price))
    .filter((price) => Number.isFinite(price) && price > 0)
    .reduce((min, price) => (min === null || price < min ? price : min), null);
  const monitoredRoutes = new Set([
    ...activeAlerts.map((a) => `${a.from_iata}-${a.to_iata}`),
    ...purchasedAlerts.map((a) => `${a.from_iata}-${a.to_iata}`),
  ]).size;

  return (
    <div style={styles.page}>
      <div style={styles.content}>
        {/* Flight Search */}
        <section style={styles.section}>
          <h2 style={styles.sectionTitle}>Search Flights</h2>
          <form onSubmit={handleSearch} style={styles.form}>
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
              <div style={styles.field}>
                <label style={styles.label}>Currency</label>
                <select
                  name="currency"
                  value={form.currency}
                  onChange={handleChange}
                  style={styles.input}
                >
                  {CURRENCIES.map((currency) => (
                    <option key={currency} value={currency}>
                      {currency}
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
              {results.map((offer, idx) => {
                const checkedBags = formatCheckedBags(offer);
                const bookingLink = offer.booking_link || offer.booking_url;
                const hasSlices = Array.isArray(offer.slices) && offer.slices.length > 0;
                const priceText = offer.price !== undefined && offer.price !== null ? offer.price : '--';

                return (
                  <div
                    key={offer.id ?? idx}
                    style={{ border: '1px solid #dbe3f0', borderRadius: '12px', padding: '1rem 1.25rem', background: '#fff', boxShadow: '0 4px 14px rgba(15, 23, 42, 0.06)', display: 'flex', justifyContent: 'space-between', alignItems: 'stretch', gap: '1rem', flexWrap: 'wrap' }}
                  >
                    <div style={{ flex: '1 1 420px', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                      {hasSlices ? (
                        offer.slices.map((slice, sliceIndex) => (
                          <div key={`${offer.id ?? idx}-slice-${sliceIndex}`} style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.75rem', borderBottom: sliceIndex === offer.slices.length - 1 ? 'none' : '1px solid #f1f5f9', paddingBottom: sliceIndex === offer.slices.length - 1 ? 0 : '0.65rem' }}>
                            <span style={{ fontWeight: 700, color: '#0f172a' }}>{offer.airline_name || offer.airline_iata || 'Airline'}</span>
                            <span style={{ color: '#334155', fontWeight: 600 }}>{formatSliceTime(slice?.departure_time)} - {formatSliceTime(slice?.arrival_time)}</span>
                            <span style={{ color: '#475569' }}>{slice?.origin_iata || '--'} - {slice?.destination_iata || '--'}</span>
                            <span style={{ color: '#64748b' }}>{formatStops(slice?.stops)}</span>
                            <span style={{ color: '#64748b' }}>{slice?.duration || '—'}</span>
                          </div>
                        ))
                      ) : (
                        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.75rem' }}>
                          <span style={{ fontWeight: 700, color: '#0f172a' }}>{offer.airline_name || offer.airline_iata || 'Airline'}</span>
                          <span style={{ color: '#334155', fontWeight: 600 }}>{formatSliceTime(offer.departure)} - {formatSliceTime(offer.arrival)}</span>
                          <span style={{ color: '#475569' }}>{offer.from_iata || '--'} - {offer.to_iata || '--'}</span>
                          <span style={{ color: '#64748b' }}>{formatStops(offer.stops)}</span>
                          <span style={{ color: '#64748b' }}>{offer.duration || '—'}</span>
                        </div>
                      )}
                    </div>
                    <div style={{ minWidth: '170px', borderLeft: '1px solid #e5e7eb', paddingLeft: '1rem', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'flex-start', gap: '0.6rem' }}>
                      <span style={{ fontSize: '0.85rem', color: '#475569' }}>👜 {checkedBags} checked bags</span>
                      <span style={{ fontSize: '1.6rem', fontWeight: 800, color: '#0f172a', lineHeight: 1 }}>{offer.currency || form.currency || 'USD'} {priceText}</span>
                      {bookingLink && (
                        <a
                          href={bookingLink}
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{ backgroundColor: '#f97316', color: '#fff', padding: '0.5rem 1.1rem', borderRadius: '8px', textDecoration: 'none', fontWeight: 800, fontSize: '0.92rem' }}
                        >
                          Select
                        </a>
                      )}
                      <button onClick={() => handleCreateAlert(offer)} style={{ backgroundColor: '#fff', color: '#1d4ed8', border: '1px solid #bfdbfe', padding: '0.45rem 0.9rem', borderRadius: '6px', fontWeight: 700, cursor: 'pointer', fontSize: '0.82rem' }}>
                        Track price
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {/* Travel Intelligence + My Active Alerts */}
        <section style={styles.section}>
          <div style={styles.alertsHeader}>
            <h2 style={styles.sectionTitle}>Travel Intelligence</h2>
            <Link to="/alerts" style={styles.manageLink}>Manage all alerts →</Link>
          </div>

          <div style={styles.statsGrid}>
            <div style={styles.statCard}>
              <div style={styles.statLabel}>Active Price Alerts</div>
              <div style={styles.statValue}>{activeAlerts.length}</div>
              <div style={styles.statHint}>Real-time alerts tracking live fares</div>
            </div>
            <div style={styles.statCard}>
              <div style={styles.statLabel}>Monitored Routes</div>
              <div style={styles.statValue}>{monitoredRoutes}</div>
              <div style={styles.statHint}>{purchasedAlerts.length} purchased trips in watch mode</div>
            </div>
            <div style={styles.statCard}>
              <div style={styles.statLabel}>Best Live Market Price</div>
              <div style={styles.statValue}>{lowestLivePrice !== null ? `$${lowestLivePrice.toFixed(2)}` : '—'}</div>
              <div style={styles.statHint}>Based on currently active route checks</div>
            </div>
          </div>

          <h3 style={styles.resultsHeading}>My Active Alerts</h3>
          {activeAlertsLoading ? (
            <p style={styles.empty}>Loading active alerts...</p>
          ) : activeAlertsError ? (
            <p style={styles.error}>{activeAlertsError}</p>
          ) : activeAlerts.length === 0 ? (
            <p style={styles.empty}>No active alerts yet.</p>
          ) : (
            <div style={styles.alertList}>
              {activeAlerts.map((alert) => (
                <div key={alert.id} style={styles.alertCard}>
                  <span style={styles.iata}>{alert.from_iata}</span>
                  <span style={styles.arrow}> → </span>
                  <span style={styles.iata}>{alert.to_iata}</span>
                  <span style={styles.alertMeta}>
                    &nbsp;· Target: {alert.currency || 'USD'} {Number(alert.max_price).toFixed(2)}
                    {` · Current Live Price: ${
                      alert.current_live_price != null
                        ? `${alert.current_live_price_currency || alert.currency || 'USD'} ${Number(alert.current_live_price).toFixed(2)}`
                        : 'Unavailable'
                    }`}
                    {alert.departure_date && ` · Dep: ${alert.departure_date}`}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* My Upcoming Trips — Post-Booking Travel Credit Engine */}
        <section style={styles.section}>
          <div style={styles.alertsHeader}>
            <h2 style={styles.sectionTitle}>🧳 My Upcoming Trips (Post-Booking)</h2>
            <button
              onClick={() => { setShowPurchaseForm((v) => !v); setPurchaseError(''); setPurchaseSuccess(''); }}
              style={styles.addTripBtn}
            >
              {showPurchaseForm ? 'Cancel' : '+ Add Purchased Flight'}
            </button>
          </div>

          <p style={styles.tripSubtitle}>
            Already booked? Add your flight below. We'll alert you if the price drops by $25+ so you can claim a travel credit from the airline.
          </p>

          {purchaseSuccess && <p style={styles.success}>{purchaseSuccess}</p>}

          {showPurchaseForm && (
            <form onSubmit={handleAddPurchasedFlight} style={{ ...styles.form, marginBottom: '1.25rem', background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '8px', padding: '1rem' }}>
              <div style={styles.row}>
                <div style={styles.field}>
                  <label style={styles.label}>From</label>
                  <AirportAutocomplete
                    placeholder="LAX – Los Angeles"
                    value={purchaseForm.from_iata}
                    onChange={(iata) => setPurchaseForm((prev) => ({ ...prev, from_iata: iata }))}
                  />
                </div>
                <div style={styles.field}>
                  <label style={styles.label}>To</label>
                  <AirportAutocomplete
                    placeholder="JFK – New York"
                    value={purchaseForm.to_iata}
                    onChange={(iata) => setPurchaseForm((prev) => ({ ...prev, to_iata: iata }))}
                  />
                </div>
              </div>
              <div style={styles.row}>
                <div style={styles.field}>
                  <label style={styles.label}>Departure Date</label>
                  <input
                    type="date"
                    name="departure_date"
                    value={purchaseForm.departure_date}
                    onChange={handlePurchaseFormChange}
                    style={styles.input}
                  />
                </div>
                <div style={styles.field}>
                  <label style={styles.label}>Airline (optional)</label>
                  <AirlineAutocomplete
                    value={purchaseForm.airline}
                    onChange={(iata) => setPurchaseForm((prev) => ({ ...prev, airline: iata }))}
                  />
                </div>
              </div>
              <div style={styles.row}>
                <div style={styles.field}>
                  <label style={styles.label}>What You Paid (USD)</label>
                  <input
                    type="number"
                    name="purchase_price"
                    value={purchaseForm.purchase_price}
                    onChange={handlePurchaseFormChange}
                    placeholder="e.g. 450.00"
                    min="1"
                    step="0.01"
                    required
                    style={styles.input}
                  />
                </div>
              </div>
              {purchaseError && <p style={styles.error}>{purchaseError}</p>}
              <button type="submit" disabled={purchaseLoading} style={styles.button}>
                {purchaseLoading ? 'Adding...' : 'Track This Flight'}
              </button>
            </form>
          )}

          {alertsLoading ? (
            <p style={styles.empty}>Loading trips...</p>
          ) : alertsError ? (
            <p style={styles.error}>{alertsError}</p>
          ) : purchasedAlerts.length === 0 ? (
            <p style={styles.empty}>No purchased flights tracked yet.</p>
          ) : (
            <div style={styles.alertList}>
              {purchasedAlerts.map((alert) => {
                const purchased = Number(alert.purchase_price || alert.max_price);
                const live = alert.last_triggered_price ? Number(alert.last_triggered_price) : null;
                const pct = live !== null && purchased > 0 ? Math.max(0, Math.min(100, (live / purchased) * 100)) : null;
                const savings = live !== null ? purchased - live : null;
                return (
                  <div
                    key={alert.id}
                    style={{ ...styles.tripCard, cursor: 'pointer', position: 'relative' }}
                    onClick={() => navigate(`/hub/${alert.id}`)}
                    title="Open Destination Hub"
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                      <span style={styles.iata}>{alert.from_iata}</span>
                      <span style={styles.arrow}> → </span>
                      <span style={styles.iata}>{alert.to_iata}</span>
                      {alert.airline && <span style={styles.alertMeta}>&nbsp;· {alert.airline}</span>}
                      {alert.departure_date && <span style={styles.alertMeta}>&nbsp;· {alert.departure_date}</span>}
                    </div>
                    <div style={{ display: 'flex', gap: '1.5rem', fontSize: '0.875rem', marginBottom: '0.5rem' }}>
                      <span>🔒 You paid: <strong>${purchased.toFixed(2)}</strong></span>
                      {live !== null ? (
                        <span style={{ color: savings >= 25 ? '#16a34a' : '#6b7280' }}>
                          📊 Market now: <strong>${live.toFixed(2)}</strong>
                          {savings >= 25 && <span style={{ color: '#16a34a', fontWeight: 700 }}>&nbsp;(Save ${savings.toFixed(2)}!)</span>}
                        </span>
                      ) : (
                        <span style={{ color: '#6b7280' }}>📊 Market: checking...</span>
                      )}
                    </div>
                    {pct !== null && (
                      <div style={{ marginTop: '0.25rem' }}>
                        <div style={styles.progressTrack}>
                          <div
                            style={{
                              ...styles.progressBar,
                              width: `${pct}%`,
                              background: pct < 90 ? '#16a34a' : '#ca8a04',
                            }}
                          />
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: '#6b7280', marginTop: '2px' }}>
                          <span>$0</span>
                          <span>Current: ${live.toFixed(2)} ({pct.toFixed(0)}% of purchase)</span>
                          <span>${purchased.toFixed(2)}</span>
                        </div>
                      </div>
                    )}
                    <div style={{ marginTop: '0.75rem', fontSize: '0.8rem', color: '#1d4ed8', fontWeight: 600 }}>
                      🌍 Open Destination Hub →
                    </div>
                  </div>
                );
              })}
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
  error: { color: '#dc2626', fontSize: '0.875rem', margin: 0 },
  empty: { textAlign: 'center', color: '#6b7280', marginTop: '1.5rem' },
  results: { marginTop: '1.5rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' },
  resultsHeading: { fontSize: '1rem', fontWeight: '700', color: '#374151', marginBottom: '0.5rem' },
  statsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
    gap: '0.75rem',
    marginBottom: '1.25rem',
  },
  statCard: {
    border: '1px solid #e2e8f0',
    borderRadius: '10px',
    padding: '0.875rem',
    background: 'linear-gradient(180deg, #ffffff 0%, #f8fafc 100%)',
  },
  statLabel: { fontSize: '0.78rem', fontWeight: '700', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.03em' },
  statValue: { fontSize: '1.5rem', fontWeight: '800', color: '#0f172a', marginTop: '0.35rem' },
  statHint: { fontSize: '0.8rem', color: '#64748b', marginTop: '0.35rem' },
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
  tripCard: {
    padding: '0.875rem',
    border: '1px solid #d1fae5',
    borderRadius: '8px',
    background: '#f0fdf4',
    fontSize: '0.9rem',
    color: '#374151',
  },
  tripSubtitle: { fontSize: '0.875rem', color: '#6b7280', marginTop: 0, marginBottom: '1rem' },
  addTripBtn: {
    padding: '0.4rem 0.9rem',
    background: '#16a34a',
    color: '#fff',
    border: 'none',
    borderRadius: '6px',
    fontSize: '0.875rem',
    fontWeight: '600',
    cursor: 'pointer',
  },
  success: { color: '#16a34a', fontSize: '0.875rem', margin: '0 0 0.75rem 0' },
  progressTrack: { background: '#e5e7eb', borderRadius: '9999px', height: '8px', overflow: 'hidden' },
  progressBar: { height: '8px', borderRadius: '9999px', transition: 'width 0.4s ease' },
  alertMeta: { color: '#6b7280', fontSize: '0.875rem' },
  aiInsight: {
    fontSize: '0.875rem',
    color: '#1d4ed8',
    background: '#eff6ff',
    borderRadius: '6px',
    padding: '0.5rem 0.75rem',
    fontStyle: 'italic',
  },
  aiInsightLocked: {
    fontSize: '0.8rem',
    color: '#9ca3af',
    background: '#f9fafb',
    borderRadius: '6px',
    padding: '0.4rem 0.75rem',
  },
  aiInsightLabel: { fontWeight: '700', fontStyle: 'normal' },
};
