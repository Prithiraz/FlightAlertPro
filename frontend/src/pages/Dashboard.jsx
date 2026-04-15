import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { supabase } from '../lib/supabase';
import { useAuth } from '../App';
import { searchFlights, listAlerts, createAlert, getLiveFlightPrice } from '../lib/api';
import AirportAutocomplete from '../components/AirportAutocomplete';
import AirlineAutocomplete from '../components/AirlineAutocomplete';

const CABIN_CLASSES = ['economy', 'premium_economy', 'business', 'first'];

export default function Dashboard() {
  const { user, subscriptionTier } = useAuth();
  const navigate = useNavigate();

  const tier = subscriptionTier || 'free';
  const hasAiInsights = tier === 'elite' || tier === 'business';

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
    airline: '',
  });
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [searched, setSearched] = useState(false);

  const [myAlerts, setMyAlerts] = useState([]);
  const [alertsLoading, setAlertsLoading] = useState(false);
  const [alertsError, setAlertsError] = useState('');
  const [createAlertForm, setCreateAlertForm] = useState({
    from_iata: '',
    to_iata: '',
    departure_date: '',
    max_price: '',
  });
  const [createAlertLoading, setCreateAlertLoading] = useState(false);
  const [createAlertError, setCreateAlertError] = useState('');
  const [createAlertSuccess, setCreateAlertSuccess] = useState('');
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

  const handlePurchaseFormChange = (e) => {
    const { name, value } = e.target;
    setPurchaseForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleCreateAlertFormChange = (e) => {
    const { name, value } = e.target;
    setCreateAlertForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleCreateAlertSubmit = async (e) => {
    e.preventDefault();
    setCreateAlertError('');
    setCreateAlertSuccess('');

    const parsedTargetPrice = parseFloat(createAlertForm.max_price);
    if (!Number.isFinite(parsedTargetPrice) || parsedTargetPrice <= 0) {
      setCreateAlertError('Target price must be a positive number greater than 0.');
      return;
    }

    setCreateAlertLoading(true);

    try {
      const { data: { session } } = await supabase.auth.getSession();
      const userEmail = session?.user?.email;

      if (!userEmail) {
        setCreateAlertError('You must be signed in to create alerts.');
        setCreateAlertLoading(false);
        return;
      }

      const { error: insertError } = await supabase.from('price_alerts').insert({
        user_email: userEmail,
        from_iata: createAlertForm.from_iata.trim().toUpperCase(),
        to_iata: createAlertForm.to_iata.trim().toUpperCase(),
        departure_date: createAlertForm.departure_date || null,
        max_price: parsedTargetPrice,
        currency: 'USD',
      });

      if (insertError) throw insertError;

      setCreateAlertSuccess('Alert created successfully.');
      setCreateAlertForm({
        from_iata: '',
        to_iata: '',
        departure_date: '',
        max_price: '',
      });
      await fetchActiveAlerts();
    } catch (err) {
      setCreateAlertError(err.message || 'Failed to create alert.');
    } finally {
      setCreateAlertLoading(false);
    }
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
                <div
                  key={offer.id ?? idx}
                  style={{
                    ...styles.card,
                    ...(offer.is_error_fare && hasAiInsights
                      ? {
                          boxShadow: '0 0 0 3px #ef4444, 0 0 18px 4px rgba(239,68,68,0.45)',
                          border: '2px solid #f97316',
                        }
                      : {}),
                  }}
                >
                  {offer.is_error_fare && hasAiInsights && (
                    <div style={{
                      display: 'inline-block',
                      background: 'linear-gradient(90deg, #ef4444, #f97316)',
                      color: '#fff',
                      fontSize: '0.75rem',
                      fontWeight: '700',
                      padding: '2px 10px',
                      borderRadius: '9999px',
                      marginBottom: '6px',
                      letterSpacing: '0.03em',
                    }}>
                      🔥 PROBABLE ERROR FARE
                    </div>
                  )}
                  <div style={styles.route}>
                    <span style={styles.iata}>{offer.from_iata}</span>
                    <span style={styles.arrow}> → </span>
                    <span style={styles.iata}>{offer.to_iata}</span>
                  </div>
                  {(offer.source || offer.provider) && (
                    <div style={styles.meta}>Provider: {offer.source || offer.provider}</div>
                  )}
                  <div style={styles.price}>
                    {offer.currency || 'USD'} {Number(offer.price).toFixed(2)}
                  </div>
                  {/* AI Market Advice */}
                  {offer.is_error_fare && (
                    hasAiInsights ? (
                      <div style={{
                        background: '#f0fdf4',
                        border: '1px solid #bbf7d0',
                        borderRadius: '8px',
                        padding: '8px 12px',
                        marginTop: '6px',
                        fontSize: '0.85rem',
                      }}>
                        <div style={{ fontWeight: '600', marginBottom: '4px', color: '#374151' }}>🤖 AI Market Advice</div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          {offer.ai_action === 'BUY NOW' ? (
                            <span style={{ background: '#16a34a', color: '#fff', fontSize: '0.75rem', fontWeight: '700', padding: '2px 8px', borderRadius: '4px' }}>✅ BUY NOW</span>
                          ) : (
                            <span style={{ background: '#ca8a04', color: '#fff', fontSize: '0.75rem', fontWeight: '700', padding: '2px 8px', borderRadius: '4px' }}>⏳ WAIT</span>
                          )}
                          <span style={{ color: '#4b5563' }}>{offer.ai_advice}</span>
                        </div>
                      </div>
                    ) : (
                      <div style={{ position: 'relative', overflow: 'hidden', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '8px 12px', marginTop: '6px', fontSize: '0.85rem' }}>
                        <div style={{ fontWeight: '600', marginBottom: '4px', color: '#374151' }}>🤖 AI Market Advice</div>
                        <div style={{ filter: 'blur(4px)', userSelect: 'none', pointerEvents: 'none', color: '#4b5563' }}>
                          ✅ BUY NOW — This price is significantly below the 14-day average.
                        </div>
                        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(248,250,252,0.75)' }}>
                          <a href="/pricing" style={{ background: '#1d4ed8', color: '#fff', fontSize: '0.75rem', fontWeight: '600', padding: '6px 12px', borderRadius: '6px', textDecoration: 'none' }}>
                            🔒 Upgrade to Elite to see AI Advice
                          </a>
                        </div>
                      </div>
                    )
                  )}
                  {hasAiInsights && offer.ai_insight && (
                    <div style={styles.aiInsight}>
                      <span style={styles.aiInsightLabel}>✨ AI Insight: </span>
                      {offer.ai_insight}
                    </div>
                  )}
                  {!hasAiInsights && !offer.is_error_fare && (
                    <div style={styles.aiInsightLocked}>
                      ✨ AI Insights available on Elite &amp; Business plans.{' '}
                      <a href="/pricing" style={{ color: '#1d4ed8', fontWeight: '600' }}>Upgrade →</a>
                    </div>
                  )}
                  <button onClick={() => handleCreateAlert(offer)} style={styles.createAlertBtn}>
                    Create alert
                  </button>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Create Alert + My Active Alerts */}
        <section style={styles.section}>
          <div style={styles.alertsHeader}>
            <h2 style={styles.sectionTitle}>Create Alert</h2>
            <Link to="/alerts" style={styles.manageLink}>Advanced alert options →</Link>
          </div>

          <form onSubmit={handleCreateAlertSubmit} style={styles.form}>
            <div style={styles.row}>
              <div style={styles.field}>
                <label style={styles.label}>Origin Airport Code</label>
                <input
                  type="text"
                  name="from_iata"
                  value={createAlertForm.from_iata}
                  onChange={handleCreateAlertFormChange}
                  placeholder="LAX"
                  maxLength={3}
                  required
                  style={styles.input}
                />
              </div>
              <div style={styles.field}>
                <label style={styles.label}>Destination Airport Code</label>
                <input
                  type="text"
                  name="to_iata"
                  value={createAlertForm.to_iata}
                  onChange={handleCreateAlertFormChange}
                  placeholder="JFK"
                  maxLength={3}
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
                  value={createAlertForm.departure_date}
                  onChange={handleCreateAlertFormChange}
                  style={styles.input}
                />
              </div>
              <div style={styles.field}>
                <label style={styles.label}>Maximum Price (Alert Threshold)</label>
                <input
                  type="number"
                  name="max_price"
                  value={createAlertForm.max_price}
                  onChange={handleCreateAlertFormChange}
                  min="1"
                  step="0.01"
                  placeholder="e.g. 299.99"
                  required
                  style={styles.input}
                />
              </div>
            </div>

            {createAlertError && <p style={styles.error}>{createAlertError}</p>}
            {createAlertSuccess && <p style={styles.success}>{createAlertSuccess}</p>}

            <button type="submit" disabled={createAlertLoading} style={styles.button}>
              {createAlertLoading ? 'Creating...' : 'Create Alert'}
            </button>
          </form>

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
          ) : myAlerts.filter((a) => a.is_purchased).length === 0 ? (
            <p style={styles.empty}>No purchased flights tracked yet.</p>
          ) : (
            <div style={styles.alertList}>
              {myAlerts.filter((a) => a.is_purchased).map((alert) => {
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
