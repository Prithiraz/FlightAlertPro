import { useState, useEffect } from 'react';
import { apiFetch } from '../lib/api';

export default function Analytics() {
  const [isAdmin, setIsAdmin] = useState(null);
  const [series, setSeries] = useState([]);
  const [growth, setGrowth] = useState([]);
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
    Promise.all([
      apiFetch(`/api/admin/analytics?days=${days}`).catch(() => ({ series: [] })),
      apiFetch(`/api/admin/growth?days=${days}`).catch(() => ({ series: [] })),
    ])
      .then(([analyticsData, growthData]) => {
        setSeries(analyticsData.series || []);
        setGrowth(growthData.series || []);
      })
      .finally(() => setLoading(false));
  }, [isAdmin, days]);

  if (loading) return <div style={styles.page}><p style={styles.center}>Loading analytics…</p></div>;
  if (!isAdmin) return <div style={styles.page}><p style={{ ...styles.center, color: '#dc2626' }}>Access denied – admin only.</p></div>;

  const maxSearches = Math.max(...series.map((r) => r.searches), 1);
  const maxNotifs = Math.max(...series.map((r) => r.notifications_sent), 1);
  const maxAlerts = Math.max(...series.map((r) => r.alerts_created), 1);

  // Growth funnel totals across period
  const funnelTotals = growth.reduce((acc, row) => {
    acc.landing_view = (acc.landing_view || 0) + (row.landing_view || 0);
    acc.pricing_view = (acc.pricing_view || 0) + (row.pricing_view || 0);
    acc.signup_start = (acc.signup_start || 0) + (row.signup_start || 0);
    acc.signup_complete = (acc.signup_complete || 0) + (row.signup_complete || 0);
    acc.first_search = (acc.first_search || 0) + (row.first_search || 0);
    acc.first_alert_created = (acc.first_alert_created || 0) + (row.first_alert_created || 0);
    acc.paid_success = (acc.paid_success || 0) + (row.paid_success || 0);
    return acc;
  }, {});

  const funnelSteps = [
    { key: 'landing_view', label: 'Landing Views', color: '#3b82f6' },
    { key: 'pricing_view', label: 'Pricing Views', color: '#6366f1' },
    { key: 'signup_start', label: 'Signup Started', color: '#8b5cf6' },
    { key: 'signup_complete', label: 'Signup Complete', color: '#ec4899' },
    { key: 'first_search', label: 'First Search', color: '#f59e0b' },
    { key: 'first_alert_created', label: 'First Alert', color: '#10b981' },
    { key: 'paid_success', label: 'Paid', color: '#16a34a' },
  ];

  const topFunnelVal = funnelTotals[funnelSteps[0].key] || 1;

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

        {/* Growth Funnel */}
        <section style={styles.section}>
          <h2 style={styles.h2}>🚀 Growth Funnel – Last {days} Days</h2>
          {funnelSteps.every((s) => !funnelTotals[s.key]) ? (
            <p style={styles.empty}>No growth events recorded yet. Events will appear once users visit the marketing pages.</p>
          ) : (
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>Step</th>
                  <th style={styles.th}>Count</th>
                  <th style={styles.th}>Conversion</th>
                  <th style={styles.th}></th>
                </tr>
              </thead>
              <tbody>
                {funnelSteps.map((step) => {
                  const count = funnelTotals[step.key] || 0;
                  const pct = topFunnelVal > 0 ? (count / topFunnelVal) * 100 : 0;
                  return (
                    <tr key={step.key}>
                      <td style={styles.td}>{step.label}</td>
                      <td style={styles.td}><span style={styles.count}>{count}</span></td>
                      <td style={styles.td}>{pct.toFixed(1)}%</td>
                      <td style={styles.td}>
                        <span style={{ ...styles.bar, width: `${(count / Math.max(...Object.values(funnelTotals), 1)) * 140}px`, background: step.color }} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </section>

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
