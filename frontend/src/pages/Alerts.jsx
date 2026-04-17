import { useState, useEffect } from 'react';
import { useLocation, Link } from 'react-router-dom';
import { createAlert, listAlerts, deleteAlert, getPreferences } from '../lib/api';
import { useAuth } from '../App';
import AirportAutocomplete from '../components/AirportAutocomplete';
import AirlineAutocomplete from '../components/AirlineAutocomplete';
import {
  canUseFlexibleDates as tierCanUseFlexibleDates,
  canUseClientFields,
  canUseEU261,
  ALERT_LIMITS,
} from '../utils/tierLimits';

const CURRENCIES = ['USD', 'EUR', 'GBP', 'CAD', 'AUD', 'INR'];
const CHANNELS = ['email', 'telegram'];

const emptyForm = {
  from_iata: '',
  to_iata: '',
  trip_type: 'one_way',
  max_price: '',
  currency: 'USD',
  departure_date: '',
  return_date: '',
  departure_start_date: '',
  departure_end_date: '',
  notification_channels: ['email'],
  airline: '',
  client_name: '',
  client_email: '',
};

export default function Alerts() {
  const { user, subscriptionTier } = useAuth();
  const location = useLocation();
  const [alerts, setAlerts] = useState([]);
  const [form, setForm] = useState(emptyForm);
  const [flexibleDates, setFlexibleDates] = useState(false);
  const [toast, setToast] = useState('');
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [prefillApplied, setPrefillApplied] = useState(false);

  const ALERT_LIMITS_LOCAL = ALERT_LIMITS;
  const tier = subscriptionTier || 'free';
  const alertLimit = ALERT_LIMITS_LOCAL[tier] ?? 1;
  const atLimit = alerts.length >= alertLimit;
  const isPaidTier = tier !== 'free';
  const isPro = isPaidTier;
  // Flexible Dates is an Elite/Business feature
  const canUseFlexibleDates = tierCanUseFlexibleDates(tier);
  // Client fields are a Business feature
  const showClientFields = canUseClientFields(tier);
  // EU261 Auto-Claim is an Elite/Business feature
  const showEU261 = canUseEU261(tier);

  const showToast = (msg) => {
    setToast(msg);
    setTimeout(() => setToast(''), 4000);
  };

  useEffect(() => {
    const prefill = location.state?.prefill;
    if (prefill && !prefillApplied) {
      setForm((prev) => ({
        ...prev,
        from_iata: prefill.from_iata ?? prev.from_iata,
        to_iata: prefill.to_iata ?? prev.to_iata,
        departure_date: prefill.departure_date ?? prev.departure_date,
        return_date: prefill.return_date ?? prev.return_date,
        trip_type: prefill.trip_type ?? (prefill.return_date ? 'round_trip' : prev.trip_type),
        currency: prefill.currency ?? prev.currency,
        max_price: prefill.max_price ?? prev.max_price,
      }));
      setSuccess('Prefilled alert details from your search.');
      setPrefillApplied(true);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.state?.prefill]);

  // Auto-populate from user preferences (only when no search prefill is present)
  useEffect(() => {
    if (!user?.email || location.state?.prefill) return;
    getPreferences(user.email)
      .then((prefs) => {
        setForm((prev) => ({
          ...prev,
          from_iata: prefs.home_airport || prev.from_iata,
          currency: prefs.currency || prev.currency,
        }));
      })
      .catch((err) => {
        console.error('Failed to load preferences:', err);
      });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.email]);

  useEffect(() => {
    if (user?.email) {
      fetchAlerts();
    }
  }, [user?.email]);

  const fetchAlerts = async () => {
    setLoading(true);
    try {
      const data = await listAlerts(user.email);
      setAlerts(Array.isArray(data) ? data : data.alerts ?? []);
    } catch (err) {
      setError(err.message || 'Failed to load alerts');
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => {
      if (name === 'trip_type' && value === 'one_way') {
        return { ...prev, trip_type: value, return_date: '' };
      }
      return { ...prev, [name]: value };
    });
  };

  const toggleChannel = (channel) => {
    setForm((prev) => ({
      ...prev,
      notification_channels: prev.notification_channels.includes(channel)
        ? prev.notification_channels.filter((c) => c !== channel)
        : [...prev.notification_channels, channel],
    }));
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    setCreating(true);
    setError('');
    setSuccess('');

    if (!form.from_iata || !form.to_iata) {
      setError('Please select an origin and destination airport.');
      setCreating(false);
      return;
    }
    if (form.trip_type === 'round_trip' && !form.return_date) {
      setError('Please select a return date for round-trip alerts.');
      setCreating(false);
      return;
    }

    try {
      const payload = {
        user_email: user.email,
        from_iata: form.from_iata.toUpperCase(),
        to_iata: form.to_iata.toUpperCase(),
        max_price: Number(form.max_price),
        currency: form.currency,
        notification_channels: form.notification_channels,
        trip_type: form.trip_type,
      };

      if (flexibleDates && canUseFlexibleDates) {
        if (form.departure_start_date) payload.departure_start_date = form.departure_start_date;
        if (form.departure_end_date)   payload.departure_end_date   = form.departure_end_date;
        // Also set departure_date to start for backward compat
        if (form.departure_start_date) payload.departure_date = form.departure_start_date;
      } else if (form.departure_date) {
        payload.departure_date = form.departure_date;
      }
      if (form.trip_type === 'round_trip' && form.return_date) {
        payload.return_date = form.return_date;
      }

      // Business-tier client fields
      if (showClientFields) {
        if (form.client_name)  payload.client_name  = form.client_name;
        if (form.client_email) payload.client_email = form.client_email;
      }

      await createAlert(payload);
      setSuccess('Alert created successfully!');
      setForm(emptyForm);
      setFlexibleDates(false);
      await fetchAlerts();
    } catch (err) {
      setError(err.message || 'Failed to create alert');
    } finally {
      setCreating(false);
    }
  };

  const handleDeactivate = async (alertId) => {
    setError('');
    setSuccess('');
    try {
      await deleteAlert(alertId, user.email);
      setSuccess('Alert removed.');
      setAlerts((prev) => prev.filter((a) => a.id !== alertId));
    } catch (err) {
      setError(err.message || 'Failed to remove alert');
    }
  };

  return (
    <div style={styles.page}>
      {toast && (
        <div style={styles.toast}>
          🔒 {toast}
        </div>
      )}
      <h2 style={styles.heading}>Price Alerts</h2>

      {/* Create Alert Form */}
      <div style={styles.formSection}>
        <h3 style={styles.subHeading}>Create New Alert</h3>
        <form onSubmit={handleCreate} style={styles.form}>
          <div style={styles.row}>
            <div style={styles.field}>
              <label style={styles.label}>From</label>
              <AirportAutocomplete
                placeholder="City or airport"
                value={form.from_iata}
                onChange={(iata) => setForm((prev) => ({ ...prev, from_iata: iata }))}
              />
            </div>
            <div style={styles.field}>
              <label style={styles.label}>To</label>
              <AirportAutocomplete
                placeholder="City or airport"
                value={form.to_iata}
                onChange={(iata) => setForm((prev) => ({ ...prev, to_iata: iata }))}
              />
            </div>
          </div>

          <div style={styles.row}>
            <div style={styles.field}>
              <label style={styles.label}>Trip Type</label>
              <select
                name="trip_type"
                value={form.trip_type}
                onChange={handleChange}
                style={styles.input}
              >
                <option value="one_way">One-Way</option>
                <option value="round_trip">Round-Trip</option>
              </select>
            </div>
            <div style={styles.field}>
              <label style={styles.label}>Max Price</label>
              <input
                type="number"
                name="max_price"
                value={form.max_price}
                onChange={handleChange}
                min={1}
                step="0.01"
                placeholder="500"
                required
                style={styles.input}
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
                {CURRENCIES.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
          </div>

          <div style={styles.field}>
            {/* Flexible Dates toggle */}
            <div style={styles.toggleRow}>
              <button
                type="button"
                onClick={() => {
                  if (!canUseFlexibleDates) {
                    showToast('Flexible Dates is an Elite feature. Upgrade to unlock.');
                  } else {
                    setFlexibleDates((v) => !v);
                  }
                }}
                style={{
                  ...styles.toggleBtn,
                  ...(flexibleDates && canUseFlexibleDates ? styles.toggleBtnActive : {}),
                  ...(canUseFlexibleDates ? {} : styles.toggleBtnLocked),
                }}
                title={canUseFlexibleDates ? '' : 'Upgrade to Elite to use Flexible Dates'}
              >
                {flexibleDates && canUseFlexibleDates ? '📅 Flexible Dates (On)' : '📅 Flexible Dates'}
                {!canUseFlexibleDates && <span style={styles.eliteBadge}>Elite</span>}
              </button>
              <button
                type="button"
                onClick={() => setFlexibleDates(false)}
                style={{
                  ...styles.toggleBtn,
                  ...(!flexibleDates ? styles.toggleBtnActive : {}),
                }}
              >
                Exact Date
              </button>
            </div>

            {flexibleDates && canUseFlexibleDates ? (
              <div style={styles.row}>
                <div style={styles.field}>
                  <label style={styles.label}>Earliest Departure</label>
                  <input
                    type="date"
                    name="departure_start_date"
                    value={form.departure_start_date}
                    onChange={handleChange}
                    style={{ ...styles.input, maxWidth: '200px' }}
                  />
                </div>
                <div style={styles.field}>
                  <label style={styles.label}>Latest Departure</label>
                  <input
                    type="date"
                    name="departure_end_date"
                    value={form.departure_end_date}
                    onChange={handleChange}
                    style={{ ...styles.input, maxWidth: '200px' }}
                  />
                </div>
              </div>
            ) : (
              <div>
                <label style={styles.label}>Departure Date (optional)</label>
                <input
                  type="date"
                  name="departure_date"
                  value={form.departure_date}
                  onChange={handleChange}
                  style={{ ...styles.input, maxWidth: '240px' }}
                />
              </div>
            )}
            {form.trip_type === 'round_trip' && (
              <div style={{ marginTop: '0.75rem' }}>
                <label style={styles.label}>Return Date</label>
                <input
                  type="date"
                  name="return_date"
                  value={form.return_date}
                  onChange={handleChange}
                  style={{ ...styles.input, maxWidth: '240px' }}
                />
              </div>
            )}
          </div>

          <div style={styles.field}>
            <label style={styles.label}>Airline (optional)</label>
            <AirlineAutocomplete
              value={form.airline}
              onChange={(iata) => setForm((prev) => ({ ...prev, airline: iata }))}
            />
          </div>

          {/* Business-tier client fields */}
          {showClientFields && (
            <div style={styles.clientSection}>
              <div style={styles.clientBadge}>🏢 Business – Client Fields</div>
              <div style={styles.row}>
                <div style={styles.field}>
                  <label style={styles.label}>Client Name (optional)</label>
                  <input
                    type="text"
                    name="client_name"
                    value={form.client_name}
                    onChange={handleChange}
                    placeholder="e.g. Acme Corp"
                    style={styles.input}
                  />
                </div>
                <div style={styles.field}>
                  <label style={styles.label}>Client Email (optional)</label>
                  <input
                    type="email"
                    name="client_email"
                    value={form.client_email}
                    onChange={handleChange}
                    placeholder="client@example.com"
                    style={styles.input}
                  />
                </div>
              </div>
            </div>
          )}

          <div style={styles.field}>
            <label style={styles.label}>Notification Channels</label>
            <div style={styles.channels}>
              {CHANNELS.map((ch) => {
                const isTelegramLocked = ch === 'telegram' && !isPro;
                return (
                  <label
                    key={ch}
                    style={{
                      ...styles.checkLabel,
                      ...(isTelegramLocked ? styles.checkLabelDisabled : {}),
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={form.notification_channels.includes(ch)}
                      onChange={() => !isTelegramLocked && toggleChannel(ch)}
                      disabled={isTelegramLocked}
                    />
                    {' '}{ch.charAt(0).toUpperCase() + ch.slice(1)}
                    {isTelegramLocked && (
                      <span style={styles.proBadge}>Pro Only</span>
                    )}
                  </label>
                );
              })}
            </div>
          </div>

          {atLimit && (
            <div style={styles.paywallBox}>
              <p style={styles.paywallText}>
                {tier === 'free'
                  ? '⚠️ You have reached your free limit of 1 alert. Upgrade to monitor additional routes.'
                  : tier === 'pro'
                  ? `⚠️ You have reached your Pro limit of ${ALERT_LIMITS_LOCAL.pro} alerts. Upgrade to Elite for up to 20 alerts.`
                  : `⚠️ You have reached your Elite limit of ${ALERT_LIMITS_LOCAL.elite} alerts. Upgrade to Business for unlimited alerts.`}
              </p>
              <Link to="/pricing" style={styles.paywallLink}>View Plans →</Link>
            </div>
          )}

          {error && <p style={styles.error}>{error}</p>}
          {success && <p style={styles.success}>{success}</p>}

          <button type="submit" disabled={creating || atLimit} style={{
            ...styles.button,
            ...(atLimit ? styles.buttonDisabled : {}),
          }}>
            {creating ? 'Creating...' : 'Create Alert'}
          </button>
        </form>
      </div>

      {/* Existing Alerts */}
      <div>
        <h3 style={styles.subHeading}>Your Alerts</h3>

        {loading ? (
          <p style={styles.empty}>Loading alerts...</p>
        ) : alerts.length === 0 ? (
          <p style={styles.empty}>No alerts yet. Create one above.</p>
        ) : (
          <div style={styles.alertList}>
            {alerts.map((alert) => (
              <div key={alert.id} style={styles.alertCard}>
                <div style={styles.alertRoute}>
                  <span style={styles.iata}>{alert.from_iata}</span>
                  <span style={styles.arrow}> → </span>
                  <span style={styles.iata}>{alert.to_iata}</span>
                </div>
                <div style={styles.alertMeta}>
                  Max: {alert.currency || 'USD'} {Number(alert.max_price).toFixed(2)}
                  {alert.departure_start_date && alert.departure_end_date && alert.departure_start_date !== alert.departure_end_date
                    ? ` · Dates: ${alert.departure_start_date} → ${alert.departure_end_date}`
                    : (alert.departure_date || alert.departure_start_date)
                      && ` · Dep: ${alert.departure_date || alert.departure_start_date}`}
                  {alert.return_date && ` · Return: ${alert.return_date}`}
                </div>
                <div style={styles.alertMeta}>
                  Channels: {(alert.notification_channels || alert.channels || []).join(', ') || '—'}
                </div>
                {alert.created_at && (
                  <div style={styles.alertMeta}>
                    Created: {new Date(alert.created_at).toLocaleDateString()}
                  </div>
                )}
                {alert.client_name && (
                  <div style={styles.alertMeta}>
                    Client: {alert.client_name}
                    {alert.client_email && ` (${alert.client_email})`}
                  </div>
                )}
                <div style={styles.alertActions}>
                  {showEU261 && alert.is_purchased && (
                    <a
                      href={`mailto:?subject=EU261 Claim – ${alert.from_iata}-${alert.to_iata}&body=Please%20check%20your%20FlightAlertPro%20dashboard%20for%20your%20pre-filled%20EU261%20claim.`}
                      style={styles.eu261Btn}
                      title="EU261 Auto-Claim – check your email for the pre-filled claim letter"
                    >
                      ⚖️ EU261 Claim
                    </a>
                  )}
                  <button
                    onClick={() => handleDeactivate(alert.id)}
                    style={styles.deactivateBtn}
                  >
                    Deactivate
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

const styles = {
  page: { maxWidth: '800px', margin: '2rem auto', padding: '0 1rem' },
  heading: { fontSize: '1.75rem', marginBottom: '1.5rem', color: '#1d4ed8' },
  formSection: { background: '#fff', padding: '1.5rem', borderRadius: '8px', boxShadow: '0 2px 8px rgba(0,0,0,0.08)', marginBottom: '2rem' },
  subHeading: { fontSize: '1.125rem', fontWeight: '700', marginBottom: '1rem', color: '#374151' },
  form: { display: 'flex', flexDirection: 'column', gap: '0.75rem' },
  row: { display: 'flex', gap: '1rem', flexWrap: 'wrap' },
  field: { flex: '1', minWidth: '160px', display: 'flex', flexDirection: 'column', gap: '0.25rem' },
  label: { fontWeight: '600', fontSize: '0.875rem', color: '#374151' },
  input: { padding: '0.5rem 0.75rem', border: '1px solid #d1d5db', borderRadius: '6px', fontSize: '1rem' },
  channels: { display: 'flex', gap: '1rem', flexWrap: 'wrap', marginTop: '0.25rem' },
  checkLabel: { display: 'flex', alignItems: 'center', gap: '0.25rem', cursor: 'pointer', fontSize: '0.95rem' },
  button: { alignSelf: 'flex-start', marginTop: '0.25rem', padding: '0.625rem 1.5rem', background: '#1d4ed8', color: '#fff', border: 'none', borderRadius: '6px', fontSize: '1rem', fontWeight: '600', cursor: 'pointer' },
  buttonDisabled: { background: '#9ca3af', cursor: 'not-allowed' },
  error: { color: '#dc2626', fontSize: '0.875rem', margin: 0 },
  success: { color: '#16a34a', fontSize: '0.875rem', margin: 0 },
  empty: { color: '#6b7280', textAlign: 'center', padding: '2rem 0' },
  alertList: { display: 'flex', flexDirection: 'column', gap: '1rem' },
  alertCard: { background: '#fff', borderRadius: '8px', padding: '1.25rem', boxShadow: '0 2px 8px rgba(0,0,0,0.08)', display: 'flex', flexDirection: 'column', gap: '0.375rem' },
  alertRoute: { fontSize: '1.2rem', fontWeight: '700' },
  iata: { color: '#1d4ed8' },
  arrow: { color: '#6b7280' },
  alertMeta: { fontSize: '0.875rem', color: '#6b7280' },
  deactivateBtn: { alignSelf: 'flex-start', marginTop: '0.5rem', padding: '0.375rem 0.875rem', background: '#fee2e2', color: '#dc2626', border: '1px solid #fca5a5', borderRadius: '6px', cursor: 'pointer', fontWeight: '600', fontSize: '0.875rem' },
  checkLabelDisabled: { opacity: 0.5, cursor: 'not-allowed' },
  proBadge: { marginLeft: '0.375rem', background: '#ede9fe', color: '#7c3aed', fontSize: '0.7rem', fontWeight: '700', padding: '0.1rem 0.4rem', borderRadius: '4px', textTransform: 'uppercase', letterSpacing: '0.04em' },
  paywallBox: { background: '#fff7ed', border: '1px solid #fed7aa', borderRadius: '8px', padding: '1rem 1.25rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' },
  paywallText: { color: '#92400e', fontWeight: '600', fontSize: '0.925rem', margin: 0 },
  paywallLink: { color: '#1d4ed8', fontWeight: '700', fontSize: '0.925rem', textDecoration: 'none' },
  // Flexible dates toggle
  toggleRow: { display: 'flex', gap: '0.5rem', marginBottom: '0.5rem', flexWrap: 'wrap' },
  toggleBtn: { padding: '0.375rem 0.875rem', border: '1px solid #d1d5db', borderRadius: '6px', background: '#f9fafb', color: '#374151', cursor: 'pointer', fontSize: '0.875rem', fontWeight: '500', display: 'flex', alignItems: 'center', gap: '0.35rem' },
  toggleBtnActive: { background: '#dbeafe', borderColor: '#3b82f6', color: '#1d4ed8', fontWeight: '700' },
  toggleBtnLocked: { opacity: 0.7, cursor: 'pointer' },
  eliteBadge: { marginLeft: '0.375rem', background: '#fef3c7', color: '#92400e', fontSize: '0.68rem', fontWeight: '700', padding: '0.1rem 0.4rem', borderRadius: '4px', textTransform: 'uppercase', letterSpacing: '0.04em' },
  // Toast notification
  toast: { position: 'fixed', top: '1.25rem', left: '50%', transform: 'translateX(-50%)', background: '#1e293b', color: '#fff', padding: '0.75rem 1.5rem', borderRadius: '8px', fontSize: '0.95rem', fontWeight: '600', zIndex: 9999, boxShadow: '0 4px 12px rgba(0,0,0,0.25)', whiteSpace: 'nowrap' },
  // Business-tier client fields section
  clientSection: { background: '#f0fdf4', border: '1px solid #86efac', borderRadius: '8px', padding: '1rem 1.25rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' },
  clientBadge: { display: 'inline-block', background: '#16a34a', color: '#fff', fontSize: '0.75rem', fontWeight: '700', padding: '0.2rem 0.6rem', borderRadius: '4px', letterSpacing: '0.04em', alignSelf: 'flex-start' },
  // Alert card action row
  alertActions: { display: 'flex', gap: '0.5rem', alignItems: 'center', marginTop: '0.5rem', flexWrap: 'wrap' },
  eu261Btn: { padding: '0.375rem 0.875rem', background: '#eff6ff', color: '#1d4ed8', border: '1px solid #bfdbfe', borderRadius: '6px', cursor: 'pointer', fontWeight: '600', fontSize: '0.875rem', textDecoration: 'none', display: 'inline-flex', alignItems: 'center' },
};
