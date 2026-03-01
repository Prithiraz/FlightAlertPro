import { useState, useEffect, useCallback } from 'react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || (() => {
  const url = new URL(window.location.href);
  url.port = '8000';
  return url.origin;
})();

const STATUS_COLORS = {
  operational: '#16a34a',
  degraded: '#d97706',
  outage: '#dc2626',
  disabled: '#9ca3af',
  unknown: '#6b7280',
};

const STATUS_ICONS = {
  operational: '✅',
  degraded: '⚠️',
  outage: '🔴',
  disabled: '—',
  unknown: '❓',
};

const SEVERITY_COLORS = {
  minor: '#d97706',
  major: '#ea580c',
  critical: '#dc2626',
};

function StatusBadge({ status }) {
  const color = STATUS_COLORS[status] || STATUS_COLORS.unknown;
  const icon = STATUS_ICONS[status] || STATUS_ICONS.unknown;
  return (
    <span style={{ color, fontWeight: '600', fontSize: '0.875rem' }}>
      {icon} {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}

export default function Status() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [copyMsg, setCopyMsg] = useState('');

  const fetchStatus = useCallback(() => {
    fetch(`${API_BASE_URL}/api/status`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d) => { setData(d); setError(null); })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 30_000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  function handleCopy() {
    if (!data) return;
    navigator.clipboard.writeText(JSON.stringify(data, null, 2))
      .then(() => { setCopyMsg('Copied!'); setTimeout(() => setCopyMsg(''), 3000); })
      .catch(() => { setCopyMsg('Copy failed'); setTimeout(() => setCopyMsg(''), 3000); });
  }

  const overallColor = data ? (STATUS_COLORS[data.overall_status] || STATUS_COLORS.unknown) : '#6b7280';

  return (
    <div style={styles.page}>
      <div style={styles.content}>
        {/* Header */}
        <div style={styles.header}>
          <h1 style={styles.h1}>✈️ FlightAlertPro — System Status</h1>
          <div style={styles.headerRight}>
            <button onClick={handleCopy} style={styles.copyBtn}>📋 Copy diagnostics</button>
            {copyMsg && <span style={styles.copyMsg}>{copyMsg}</span>}
          </div>
        </div>

        {loading && <p style={styles.center}>Loading status…</p>}
        {error && <p style={{ ...styles.center, color: '#dc2626' }}>Could not load status: {error}</p>}

        {data && (
          <>
            {/* Overall status banner */}
            <div style={{ ...styles.banner, borderColor: overallColor }}>
              <span style={{ fontSize: '1.5rem' }}>{STATUS_ICONS[data.overall_status] || '❓'}</span>
              <div>
                <div style={{ fontWeight: '800', fontSize: '1.25rem', color: overallColor }}>
                  {data.overall_status.charAt(0).toUpperCase() + data.overall_status.slice(1)}
                </div>
                <div style={styles.bannerSub}>
                  Last updated: {new Date(data.last_updated).toLocaleString()}
                  {' · '}Auto-refreshes every 30 seconds
                </div>
              </div>
            </div>

            {/* Components table */}
            <section style={styles.section}>
              <h2 style={styles.h2}>Components</h2>
              <table style={styles.table}>
                <thead>
                  <tr>
                    {['Component', 'Status', 'Detail'].map((h) => (
                      <th key={h} style={styles.th}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(data.components || []).map((c) => (
                    <tr key={c.name}>
                      <td style={styles.td}><strong>{c.name}</strong></td>
                      <td style={styles.td}><StatusBadge status={c.status} /></td>
                      <td style={{ ...styles.td, color: '#6b7280', fontSize: '0.8rem' }}>
                        {c.detail || (c.last_webhook ? `Last webhook: ${new Date(c.last_webhook).toLocaleString()}` : '—')}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>

            {/* Active incidents */}
            <section style={styles.section}>
              <h2 style={styles.h2}>Active Incidents</h2>
              {(data.incidents || []).length === 0 ? (
                <p style={styles.empty}>No active incidents. 🎉</p>
              ) : (
                <table style={styles.table}>
                  <thead>
                    <tr>
                      {['Title', 'Severity', 'Status', 'Started'].map((h) => (
                        <th key={h} style={styles.th}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {(data.incidents || []).map((inc) => (
                      <tr key={inc.id}>
                        <td style={styles.td}>
                          <strong>{inc.title}</strong>
                          {inc.description && (
                            <div style={{ fontSize: '0.75rem', color: '#6b7280', marginTop: '0.25rem' }}>
                              {inc.description}
                            </div>
                          )}
                        </td>
                        <td style={{ ...styles.td, color: SEVERITY_COLORS[inc.severity] || '#374151', fontWeight: '600' }}>
                          {inc.severity}
                        </td>
                        <td style={styles.td}>{inc.status}</td>
                        <td style={{ ...styles.td, fontSize: '0.8rem', color: '#6b7280' }}>
                          {inc.started_at ? new Date(inc.started_at).toLocaleString() : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </section>
          </>
        )}
      </div>
    </div>
  );
}

const styles = {
  page: { minHeight: '100vh', background: '#f3f4f6' },
  content: { maxWidth: '900px', margin: '0 auto', padding: '2rem 1rem' },
  header: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '0.5rem' },
  h1: { fontSize: '1.5rem', fontWeight: '800', color: '#1d4ed8', margin: 0 },
  h2: { fontSize: '1.1rem', fontWeight: '700', color: '#1d4ed8', margin: '0 0 1rem 0' },
  headerRight: { display: 'flex', alignItems: 'center', gap: '0.75rem' },
  copyBtn: { padding: '0.4rem 0.9rem', background: '#1d4ed8', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: '600', fontSize: '0.8rem' },
  copyMsg: { fontSize: '0.875rem', color: '#16a34a', fontWeight: '600' },
  banner: { display: 'flex', alignItems: 'center', gap: '1rem', background: '#fff', borderRadius: '8px', padding: '1.25rem 1.5rem', border: '2px solid', marginBottom: '1.5rem', boxShadow: '0 2px 8px rgba(0,0,0,0.08)' },
  bannerSub: { fontSize: '0.8rem', color: '#6b7280', marginTop: '0.2rem' },
  section: { background: '#fff', borderRadius: '8px', padding: '1.5rem', boxShadow: '0 2px 8px rgba(0,0,0,0.08)', marginBottom: '1.5rem' },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' },
  th: { textAlign: 'left', padding: '0.5rem 0.75rem', background: '#f9fafb', borderBottom: '2px solid #e5e7eb', fontWeight: '700', color: '#374151' },
  td: { padding: '0.5rem 0.75rem', borderBottom: '1px solid #f3f4f6', color: '#374151', verticalAlign: 'top' },
  center: { textAlign: 'center', marginTop: '4rem', fontSize: '1.1rem', color: '#6b7280' },
  empty: { color: '#9ca3af', fontSize: '0.875rem', textAlign: 'center', padding: '1rem 0' },
};
