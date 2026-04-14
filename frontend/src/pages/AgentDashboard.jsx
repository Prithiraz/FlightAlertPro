import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../App';
import { listAlerts, createAlert, deleteAlert } from '../lib/api';
import AirportAutocomplete from '../components/AirportAutocomplete';

const CURRENCIES = ['USD', 'EUR', 'GBP', 'CAD', 'AUD', 'INR'];

const emptyForm = {
  from_iata: '',
  to_iata: '',
  max_price: '',
  currency: 'USD',
  departure_date: '',
  client_name: '',
  client_email: '',
  notification_channels: ['email'],
};

export default function AgentDashboard() {
  const { user, subscriptionTier } = useAuth();
  const navigate = useNavigate();

  const [alerts, setAlerts] = useState([]);
  const [form, setForm] = useState(emptyForm);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [proposalAlert, setProposalAlert] = useState(null);

  // Guard: only business tier
  useEffect(() => {
    if (subscriptionTier && subscriptionTier !== 'business') {
      navigate('/dashboard', { replace: true });
    }
  }, [subscriptionTier, navigate]);

  useEffect(() => {
    if (user?.email) {
      fetchAlerts();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.email]);

  const fetchAlerts = async () => {
    setLoading(true);
    try {
      const data = await listAlerts(user.email);
      const list = Array.isArray(data) ? data : data.alerts ?? [];
      setAlerts(list);
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
        client_name: form.client_name || undefined,
        client_email: form.client_email || undefined,
      };
      if (form.departure_date) payload.departure_date = form.departure_date;

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

  // Group alerts by client_name (or "Personal" when no client)
  const grouped = alerts.reduce((acc, alert) => {
    const key = alert.client_name || 'Personal';
    if (!acc[key]) acc[key] = [];
    acc[key].push(alert);
    return acc;
  }, {});

  // Build a plain-text flight deal proposal for sharing
  const buildProposal = (alert) => {
    const lines = [
      'FLIGHT DEAL PROPOSAL',
      '════════════════════',
      `Route         : ${alert.from_iata} → ${alert.to_iata}`,
      `Target Price  : ${alert.currency || 'USD'} ${Number(alert.max_price).toFixed(2)}`,
    ];
    if (alert.departure_date) lines.push(`Departure     : ${alert.departure_date}`);
    if (alert.client_name)    lines.push(`Prepared for  : ${alert.client_name}`);
    lines.push('');
    lines.push('This alert was set up by your travel agent via FlightAlertPro.');
    lines.push('You will be notified as soon as a matching deal is found.');
    return lines.join('\n');
  };

  const handleShowProposal = (alert) => {
    setProposalAlert(alert);
  };

  const handleCopyProposal = () => {
    if (!proposalAlert) return;
    navigator.clipboard.writeText(buildProposal(proposalAlert)).then(() => {
      setSuccess('Proposal copied to clipboard!');
    });
  };

  if (subscriptionTier && subscriptionTier !== 'business') {
    return null;
  }

  return (
    <div style={styles.page}>
      <h2 style={styles.heading}>🧳 Travel Agent Portal</h2>
      <p style={styles.sub}>Manage flight alerts for your clients. Grouped by client name below.</p>

      {/* Proposal modal */}
      {proposalAlert && (
        <div style={styles.modalOverlay} onClick={() => setProposalAlert(null)}>
          <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
            <h3 style={styles.modalTitle}>Flight Deal Proposal</h3>
            <pre style={styles.proposalText}>{buildProposal(proposalAlert)}</pre>
            <div style={styles.modalActions}>
              <button onClick={handleCopyProposal} style={styles.btnPrimary}>📋 Copy to Clipboard</button>
              <button onClick={() => setProposalAlert(null)} style={styles.btnSecondary}>Close</button>
            </div>
          </div>
        </div>
      )}

      {/* Create Alert Form */}
      <div style={styles.formSection}>
        <h3 style={styles.subHeading}>Create Alert for Client</h3>
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
              <select name="currency" value={form.currency} onChange={handleChange} style={styles.input}>
                {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
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

          {/* Business-tier client fields */}
          <div style={styles.clientSection}>
            <div style={styles.clientBadge}>🏢 Business Tier – Client Fields</div>
            <div style={styles.row}>
              <div style={styles.field}>
                <label style={styles.label}>Client Name</label>
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
                <label style={styles.label}>Client Email</label>
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

          {error  && <p style={styles.error}>{error}</p>}
          {success && <p style={styles.successMsg}>{success}</p>}

          <button type="submit" disabled={creating} style={styles.btnPrimary}>
            {creating ? 'Creating…' : 'Create Alert'}
          </button>
        </form>
      </div>

      {/* CRM-style alert table grouped by client */}
      <div>
        <h3 style={styles.subHeading}>Client Alerts</h3>

        {loading ? (
          <p style={styles.empty}>Loading alerts…</p>
        ) : alerts.length === 0 ? (
          <p style={styles.empty}>No alerts yet. Create one above.</p>
        ) : (
          Object.entries(grouped).map(([clientName, clientAlerts]) => (
            <div key={clientName} style={styles.clientGroup}>
              <div style={styles.clientGroupHeader}>
                <span style={styles.clientGroupIcon}>👤</span>
                <span style={styles.clientGroupName}>{clientName}</span>
                <span style={styles.clientGroupCount}>{clientAlerts.length} alert{clientAlerts.length !== 1 ? 's' : ''}</span>
              </div>
              <table style={styles.table}>
                <thead>
                  <tr>
                    <th style={styles.th}>Route</th>
                    <th style={styles.th}>Max Price</th>
                    <th style={styles.th}>Departure</th>
                    <th style={styles.th}>Channels</th>
                    <th style={styles.th}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {clientAlerts.map((alert) => (
                    <tr key={alert.id} style={styles.tr}>
                      <td style={styles.td}>
                        <span style={styles.iata}>{alert.from_iata}</span>
                        <span style={styles.arrow}> → </span>
                        <span style={styles.iata}>{alert.to_iata}</span>
                      </td>
                      <td style={styles.td}>
                        {alert.currency || 'USD'} {Number(alert.max_price).toFixed(2)}
                      </td>
                      <td style={styles.td}>{alert.departure_date || '—'}</td>
                      <td style={styles.td}>
                        {(alert.notification_channels || alert.channels || []).join(', ') || '—'}
                      </td>
                      <td style={styles.td}>
                        <button
                          onClick={() => handleShowProposal(alert)}
                          style={styles.btnProposal}
                          title="Generate deal proposal"
                        >
                          📄 Proposal
                        </button>
                        <button
                          onClick={() => handleDeactivate(alert.id)}
                          style={styles.btnDeactivate}
                        >
                          Remove
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

const styles = {
  page: { maxWidth: '960px', margin: '2rem auto', padding: '0 1rem' },
  heading: { fontSize: '1.75rem', marginBottom: '0.5rem', color: '#1d4ed8' },
  sub: { color: '#6b7280', marginBottom: '1.5rem', fontSize: '0.95rem' },
  formSection: {
    background: '#fff', padding: '1.5rem', borderRadius: '8px',
    boxShadow: '0 2px 8px rgba(0,0,0,0.08)', marginBottom: '2rem',
  },
  subHeading: { fontSize: '1.125rem', fontWeight: '700', marginBottom: '1rem', color: '#374151' },
  form: { display: 'flex', flexDirection: 'column', gap: '0.75rem' },
  row: { display: 'flex', gap: '1rem', flexWrap: 'wrap' },
  field: { flex: '1', minWidth: '160px', display: 'flex', flexDirection: 'column', gap: '0.25rem' },
  label: { fontWeight: '600', fontSize: '0.875rem', color: '#374151' },
  input: { padding: '0.5rem 0.75rem', border: '1px solid #d1d5db', borderRadius: '6px', fontSize: '1rem' },
  clientSection: {
    background: '#f0fdf4', border: '1px solid #86efac', borderRadius: '8px',
    padding: '1rem 1.25rem', display: 'flex', flexDirection: 'column', gap: '0.75rem',
  },
  clientBadge: {
    display: 'inline-block', background: '#16a34a', color: '#fff',
    fontSize: '0.75rem', fontWeight: '700', padding: '0.2rem 0.6rem', borderRadius: '4px',
    letterSpacing: '0.04em', alignSelf: 'flex-start',
  },
  error: { color: '#dc2626', fontSize: '0.875rem', margin: 0 },
  successMsg: { color: '#16a34a', fontSize: '0.875rem', margin: 0 },
  empty: { color: '#6b7280', textAlign: 'center', padding: '2rem 0' },
  btnPrimary: {
    alignSelf: 'flex-start', padding: '0.625rem 1.5rem',
    background: '#1d4ed8', color: '#fff', border: 'none',
    borderRadius: '6px', fontSize: '1rem', fontWeight: '600', cursor: 'pointer',
  },
  btnSecondary: {
    padding: '0.625rem 1.25rem', background: '#f3f4f6', color: '#374151',
    border: '1px solid #d1d5db', borderRadius: '6px', fontSize: '0.95rem',
    fontWeight: '600', cursor: 'pointer',
  },
  clientGroup: { marginBottom: '1.5rem' },
  clientGroupHeader: {
    display: 'flex', alignItems: 'center', gap: '0.5rem',
    background: '#eff6ff', borderRadius: '6px 6px 0 0',
    padding: '0.625rem 1rem', borderBottom: '2px solid #bfdbfe',
  },
  clientGroupIcon: { fontSize: '1rem' },
  clientGroupName: { fontWeight: '700', color: '#1d4ed8', fontSize: '1rem' },
  clientGroupCount: { marginLeft: 'auto', fontSize: '0.8rem', color: '#6b7280' },
  table: { width: '100%', borderCollapse: 'collapse', background: '#fff' },
  th: {
    textAlign: 'left', padding: '0.625rem 0.875rem',
    background: '#f9fafb', fontSize: '0.8rem', fontWeight: '700',
    color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.04em',
    borderBottom: '1px solid #e5e7eb',
  },
  tr: { borderBottom: '1px solid #f3f4f6' },
  td: { padding: '0.625rem 0.875rem', fontSize: '0.9rem', color: '#374151', verticalAlign: 'middle' },
  iata: { color: '#1d4ed8', fontWeight: '700' },
  arrow: { color: '#9ca3af' },
  btnProposal: {
    padding: '0.3rem 0.7rem', marginRight: '0.4rem',
    background: '#eff6ff', color: '#1d4ed8',
    border: '1px solid #bfdbfe', borderRadius: '5px',
    fontSize: '0.8rem', fontWeight: '600', cursor: 'pointer',
  },
  btnDeactivate: {
    padding: '0.3rem 0.7rem', background: '#fee2e2', color: '#dc2626',
    border: '1px solid #fca5a5', borderRadius: '5px',
    fontSize: '0.8rem', fontWeight: '600', cursor: 'pointer',
  },
  // Modal
  modalOverlay: {
    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)',
    display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999,
  },
  modal: {
    background: '#fff', borderRadius: '10px', padding: '2rem',
    maxWidth: '560px', width: '90%', boxShadow: '0 8px 32px rgba(0,0,0,0.18)',
  },
  modalTitle: { fontSize: '1.2rem', fontWeight: '700', marginBottom: '1rem', color: '#1d4ed8' },
  proposalText: {
    background: '#f9fafb', border: '1px solid #e5e7eb', borderRadius: '6px',
    padding: '1rem', fontSize: '0.875rem', color: '#374151',
    whiteSpace: 'pre-wrap', fontFamily: 'monospace', marginBottom: '1rem',
    maxHeight: '300px', overflowY: 'auto',
  },
  modalActions: { display: 'flex', gap: '0.75rem' },
};
