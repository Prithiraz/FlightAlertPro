import { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { createAlert, listAlerts, deleteAlert } from '../lib/api';
import { useAuth } from '../App';
import AirportAutocomplete from '../components/AirportAutocomplete';

const CURRENCIES = ['USD', 'EUR', 'GBP', 'CAD', 'AUD', 'INR'];
const CHANNELS = ['email', 'whatsapp', 'telegram'];

const emptyForm = {
  from_iata: '',
  to_iata: '',
  max_price: '',
  currency: 'USD',
  departure_date: '',
  notification_channels: ['email'],
};

export default function Alerts() {
  const { user } = useAuth();
  const location = useLocation();
  const [alerts, setAlerts] = useState([]);
  const [form, setForm] = useState(emptyForm);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [prefillApplied, setPrefillApplied] = useState(false);

  useEffect(() => {
    const prefill = location.state?.prefill;
    if (prefill && !prefillApplied) {
      setForm((prev) => ({
        ...prev,
        from_iata: prefill.from_iata ?? prev.from_iata,
        to_iata: prefill.to_iata ?? prev.to_iata,
        departure_date: prefill.departure_date ?? prev.departure_date,
        currency: prefill.currency ?? prev.currency,
        max_price: prefill.max_price ?? prev.max_price,
      }));
      setSuccess('Prefilled alert details from your search.');
      setPrefillApplied(true);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.state?.prefill]);

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
    setForm((prev) => ({ ...prev, [name]: value }));
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

    try {
      const payload = {
        user_email: user.email,
        from_iata: form.from_iata.toUpperCase(),
        to_iata: form.to_iata.toUpperCase(),
        max_price: Number(form.max_price),
        currency: form.currency,
        notification_channels: form.notification_channels,
      };
      if (form.departure_date) {
        payload.departure_date = form.departure_date;
      }

      await createAlert(payload);
      setSuccess('Alert created successfully!');
      setForm(emptyForm);
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
            <label style={styles.label}>Departure Date (optional)</label>
            <input
              type="date"
              name="departure_date"
              value={form.departure_date}
              onChange={handleChange}
              style={{ ...styles.input, maxWidth: '240px' }}
            />
          </div>

          <div style={styles.field}>
            <label style={styles.label}>Notification Channels</label>
            <div style={styles.channels}>
              {CHANNELS.map((ch) => (
                <label key={ch} style={styles.checkLabel}>
                  <input
                    type="checkbox"
                    checked={form.notification_channels.includes(ch)}
                    onChange={() => toggleChannel(ch)}
                  />
                  {' '}{ch.charAt(0).toUpperCase() + ch.slice(1)}
                </label>
              ))}
            </div>
          </div>

          {error && <p style={styles.error}>{error}</p>}
          {success && <p style={styles.success}>{success}</p>}

          <button type="submit" disabled={creating} style={styles.button}>
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
                  {alert.departure_date && ` · Dep: ${alert.departure_date}`}
                </div>
                <div style={styles.alertMeta}>
                  Channels: {(alert.notification_channels || alert.channels || []).join(', ') || '—'}
                </div>
                {alert.created_at && (
                  <div style={styles.alertMeta}>
                    Created: {new Date(alert.created_at).toLocaleDateString()}
                  </div>
                )}
                <button
                  onClick={() => handleDeactivate(alert.id)}
                  style={styles.deactivateBtn}
                >
                  Deactivate
                </button>
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
};
