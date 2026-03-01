import { useState, useEffect } from 'react';
import { apiFetch } from '../lib/api';

export default function Analytics() {
  const [isAdmin, setIsAdmin] = useState(null);
  const [series, setSeries] = useState([]);
  const [days, setDays] = useState(7);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch('/api/admin/me')
      .then((d) => {
        if (d.is_admin) {
          setIsAdmin(true);
        } else {
          setIsAdmin(false);
          setLoading(false);
        }
      })
      .catch(() => {
        setIsAdmin(false);
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    if (!isAdmin) return;
    setLoading(true);
    apiFetch(`/api/admin/analytics?days=${days}`)
      .then((d) => setSeries(d.series || []))
      .catch(() => setSeries([]))
      .finally(() => setLoading(false));
  }, [isAdmin, days]);

  if (loading) return <div style={styles.page}><p style={styles.center}>Loading analytics…</p></div>;
  if (!isAdmin) return <div style={styles.page}><p style={{ ...styles.center, color: '#dc2626' }}>Access denied – admin only.</p></div>;

  const maxSearches = Math.max(...series.map((r) => r.searches), 1);
  const maxNotifs = Math.max(...series.map((r) => r.notifications_sent), 1);
  const maxAlerts = Math.max(...series.map((r) => r.alerts_created), 1);

  return (
    <div style={styles.page}>
      <div style={styles.content}>
        <div style={styles.titleRow}>
          <h1 style={styles.h1}>📊 Analytics</h1>
          <div style={styles.daysRow}>
            <span style={styles.daysLabel}>Last:</span>
            {[7, 14, 30].map((d) => (
              <button
                key={d}
                onClick={() => setDays(d)}
                style={{ ...styles.daysBtn, ...(days === d ? styles.daysBtnActive : {}) }}
              >
                {d}d
              </button>
            ))}
          </div>
        </div>

        <section style={styles.section}>
          <h2 style={styles.h2}>Daily Usage – Last {days} Days</h2>
          {series.length === 0 ? (
            <p style={styles.empty}>No data available for this period.</p>
          ) : (
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>Date</th>
                  <th style={styles.th}>Searches</th>
                  <th style={styles.th}>Notifications Sent</th>
                  <th style={styles.th}>Alerts Created</th>
                </tr>
              </thead>
              <tbody>
                {[...series].reverse().map((row) => (
                  <tr key={row.date}>
                    <td style={styles.td}>{row.date}</td>
                    <td style={styles.td}>
                      <span style={styles.count}>{row.searches}</span>
                      <span style={{ ...styles.bar, width: `${(row.searches / maxSearches) * 120}px`, background: '#3b82f6' }} />
                    </td>
                    <td style={styles.td}>
                      <span style={styles.count}>{row.notifications_sent}</span>
                      <span style={{ ...styles.bar, width: `${(row.notifications_sent / maxNotifs) * 120}px`, background: '#16a34a' }} />
                    </td>
                    <td style={styles.td}>
                      <span style={styles.count}>{row.alerts_created}</span>
                      <span style={{ ...styles.bar, width: `${(row.alerts_created / maxAlerts) * 120}px`, background: '#f59e0b' }} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </div>
    </div>
  );
}

const styles = {
  page: { minHeight: '100vh', background: '#f3f4f6' },
  content: { maxWidth: '900px', margin: '2rem auto', padding: '0 1rem' },
  center: { textAlign: 'center', marginTop: '4rem', fontSize: '1.1rem' },
  titleRow: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.5rem' },
  h1: { fontSize: '1.75rem', fontWeight: '800', color: '#1d4ed8', margin: 0 },
  h2: { fontSize: '1.15rem', fontWeight: '700', color: '#1d4ed8', marginBottom: '1rem', marginTop: 0 },
  daysRow: { display: 'flex', alignItems: 'center', gap: '0.5rem' },
  daysLabel: { fontSize: '0.875rem', color: '#6b7280', fontWeight: '600' },
  daysBtn: { padding: '0.25rem 0.75rem', border: '1px solid #d1d5db', borderRadius: '4px', background: '#fff', cursor: 'pointer', fontSize: '0.875rem', color: '#374151' },
  daysBtnActive: { background: '#1d4ed8', color: '#fff', borderColor: '#1d4ed8' },
  section: {
    background: '#fff',
    borderRadius: '8px',
    padding: '1.5rem',
    boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
    marginBottom: '1.5rem',
  },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' },
  th: { textAlign: 'left', padding: '0.5rem 0.75rem', background: '#f9fafb', borderBottom: '2px solid #e5e7eb', fontWeight: '700', color: '#374151' },
  td: { padding: '0.5rem 0.75rem', borderBottom: '1px solid #f3f4f6', color: '#374151', verticalAlign: 'middle' },
  count: { display: 'inline-block', minWidth: '2.5rem', fontWeight: '700' },
  bar: { display: 'inline-block', height: '10px', borderRadius: '3px', marginLeft: '0.5rem', verticalAlign: 'middle', minWidth: '2px' },
  empty: { color: '#9ca3af', fontSize: '0.875rem', textAlign: 'center', padding: '2rem 0' },
};
