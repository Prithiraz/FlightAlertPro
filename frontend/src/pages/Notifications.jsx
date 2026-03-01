import { useState, useEffect } from 'react';
import { getNotificationHistory } from '../lib/api';

const CHANNELS = ['all', 'email', 'whatsapp', 'telegram', 'sms'];
const STATUSES = ['all', 'sent', 'failed'];

export default function Notifications() {
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [filterChannel, setFilterChannel] = useState('all');
  const [filterStatus, setFilterStatus] = useState('all');

  useEffect(() => {
    fetchNotifications();
  }, []);

  const fetchNotifications = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await getNotificationHistory(50);
      setNotifications(data.notifications || []);
    } catch (err) {
      setError(err.message || 'Failed to load notifications');
    } finally {
      setLoading(false);
    }
  };

  const filtered = notifications.filter((n) => {
    if (filterChannel !== 'all' && n.channel !== filterChannel) return false;
    if (filterStatus !== 'all' && n.status !== filterStatus) return false;
    return true;
  });

  const copyDetails = (n) => {
    const text = JSON.stringify(n, null, 2);
    navigator.clipboard.writeText(text).catch(() => {});
  };

  return (
    <div style={styles.page}>
      <div style={styles.container}>
        <h1 style={styles.heading}>Notification Center</h1>
        <p style={styles.subheading}>Your last 50 notification events.</p>

        <div style={styles.filters}>
          <label style={styles.filterLabel}>Channel:</label>
          <select value={filterChannel} onChange={(e) => setFilterChannel(e.target.value)} style={styles.select}>
            {CHANNELS.map((c) => <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>)}
          </select>
          <label style={styles.filterLabel}>Status:</label>
          <select value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)} style={styles.select}>
            {STATUSES.map((s) => <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>)}
          </select>
        </div>

        {loading && <p style={styles.muted}>Loading…</p>}
        {error && <p style={styles.error}>{error}</p>}

        {!loading && filtered.length === 0 && (
          <div style={styles.empty}>
            <p>No notifications yet. Your alerts will show up here once triggered.</p>
          </div>
        )}

        <div style={styles.list}>
          {filtered.map((n) => {
            const payload = n.payload || {};
            const sentAt = n.sent_at || n.created_at || '';
            const isFailed = n.status === 'failed' || n.status === 'error';
            return (
              <div key={n.id} style={{ ...styles.item, ...(isFailed ? styles.itemFailed : {}) }}>
                <div style={styles.itemLeft}>
                  <span style={styles.channel}>{n.channel || '—'}</span>
                  <span style={{ ...styles.badge, ...(isFailed ? styles.badgeFailed : styles.badgeSent) }}>
                    {n.status || 'sent'}
                  </span>
                </div>
                <div style={styles.itemMeta}>
                  {payload.route ? <span>{payload.route}</span> : null}
                  {payload.price ? <span> · {payload.price}</span> : null}
                  {sentAt ? <span style={styles.time}> · {new Date(sentAt).toLocaleString()}</span> : null}
                </div>
                {n.error && <div style={styles.itemError}>Error: {n.error}</div>}
                <button onClick={() => copyDetails(n)} style={styles.copyBtn} title="Copy details">📋</button>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

const styles = {
  page: { minHeight: '100vh', background: '#f9fafb', padding: '2rem' },
  container: { maxWidth: '900px', margin: '0 auto' },
  heading: { fontSize: '1.75rem', fontWeight: '700', color: '#111827', marginBottom: '0.5rem' },
  subheading: { color: '#6b7280', marginBottom: '1.5rem' },
  filters: { display: 'flex', gap: '0.75rem', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap' },
  filterLabel: { fontWeight: '500', fontSize: '0.9rem' },
  select: { padding: '0.4rem 0.75rem', borderRadius: '6px', border: '1px solid #d1d5db', fontSize: '0.9rem' },
  muted: { color: '#6b7280' },
  error: { color: '#dc2626' },
  empty: {
    textAlign: 'center', padding: '3rem', background: '#fff',
    borderRadius: '8px', color: '#6b7280',
  },
  list: { display: 'flex', flexDirection: 'column', gap: '0.75rem' },
  item: {
    background: '#fff', borderRadius: '8px', padding: '1rem 1.25rem',
    boxShadow: '0 1px 4px rgba(0,0,0,0.07)', position: 'relative',
    display: 'flex', flexDirection: 'column', gap: '0.25rem',
  },
  itemFailed: { borderLeft: '3px solid #dc2626' },
  itemLeft: { display: 'flex', gap: '0.5rem', alignItems: 'center' },
  channel: { fontWeight: '600', fontSize: '0.9rem', color: '#1d4ed8' },
  badge: {
    padding: '0.15rem 0.5rem', borderRadius: '12px',
    fontSize: '0.75rem', fontWeight: '600',
  },
  badgeSent: { background: '#dcfce7', color: '#16a34a' },
  badgeFailed: { background: '#fee2e2', color: '#dc2626' },
  itemMeta: { fontSize: '0.875rem', color: '#374151' },
  itemError: { fontSize: '0.8rem', color: '#dc2626' },
  time: { color: '#9ca3af' },
  copyBtn: {
    position: 'absolute', top: '0.75rem', right: '0.75rem',
    background: 'none', border: 'none', cursor: 'pointer', fontSize: '1rem',
  },
};
