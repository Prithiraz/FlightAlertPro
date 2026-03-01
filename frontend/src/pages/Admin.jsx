import { useState, useEffect } from 'react';
import { apiFetch } from '../lib/api';

async function adminFetch(path) {
  return apiFetch(path);
}

export default function Admin() {
  const [isAdmin, setIsAdmin] = useState(null);
  const [overview, setOverview] = useState(null);
  const [providers, setProviders] = useState([]);
  const [users, setUsers] = useState([]);
  const [usersSort, setUsersSort] = useState('alerts');
  const [selectedUser, setSelectedUser] = useState(null);
  const [userDetails, setUserDetails] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [copyMsg, setCopyMsg] = useState('');

  useEffect(() => {
    adminFetch('/api/admin/me')
      .then((data) => {
        if (data.is_admin) {
          setIsAdmin(true);
          loadAll();
        } else {
          setIsAdmin(false);
          setLoading(false);
        }
      })
      .catch(() => {
        setIsAdmin(false);
        setLoading(false);
      });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function loadAll() {
    Promise.all([
      adminFetch('/api/admin/overview').then(setOverview).catch(() => {}),
      adminFetch('/api/admin/providers').then((d) => setProviders(d.providers || [])).catch(() => {}),
      loadUsers('alerts'),
    ]).finally(() => setLoading(false));
  }

  function loadUsers(sort) {
    return adminFetch(`/api/admin/users?sort=${sort}&limit=50`)
      .then((d) => setUsers(d.users || []))
      .catch(() => {});
  }

  function handleSortChange(sort) {
    setUsersSort(sort);
    loadUsers(sort);
  }

  function handleUserClick(user) {
    setSelectedUser(user);
    setUserDetails(null);
    adminFetch(`/api/admin/user/${user.user_id}/details`)
      .then(setUserDetails)
      .catch(() => setUserDetails({ error: 'Could not load details' }));
  }

  function handleCopyDiagnostics() {
    const payload = { overview, providers, users: users.slice(0, 10) };
    navigator.clipboard.writeText(JSON.stringify(payload, null, 2))
      .then(() => { setCopyMsg('Copied!'); setTimeout(() => setCopyMsg(''), 3000); })
      .catch(() => { setCopyMsg('Copy failed'); setTimeout(() => setCopyMsg(''), 3000); });
  }

  if (loading) return <div style={styles.page}><p style={styles.center}>Loading admin dashboard…</p></div>;
  if (!isAdmin) return <div style={styles.page}><p style={{ ...styles.center, color: '#dc2626' }}>Access denied – admin only.</p></div>;

  return (
    <div style={styles.page}>
      <div style={styles.content}>
        <div style={styles.titleRow}>
          <h1 style={styles.h1}>🛡️ Admin Dashboard</h1>
          <button onClick={handleCopyDiagnostics} style={styles.diagBtn}>📋 Copy diagnostics</button>
          {copyMsg && <span style={styles.copyMsg}>{copyMsg}</span>}
        </div>

        {error && <p style={styles.error}>{error}</p>}

        {/* Overview cards */}
        {overview && (
          <section style={styles.section}>
            <h2 style={styles.h2}>System Overview</h2>
            <div style={styles.cards}>
              <StatCard label="Total Users" value={overview.total_users} />
              <StatCard label="Total Alerts" value={overview.total_alerts} />
              <StatCard label="Active Alerts" value={overview.active_alerts} />
              <StatCard label="Searches (24h)" value={overview.searches_last_24h} />
              <StatCard label="Notifs Sent (24h)" value={overview.notifications_last_24h?.sent ?? 0} />
              <StatCard label="Notifs Failed (24h)" value={overview.notifications_last_24h?.failed ?? 0} color="#dc2626" />
            </div>
            <p style={styles.ts}>Last updated: {overview.timestamp}</p>
          </section>
        )}

        {/* Provider health */}
        {providers.length > 0 && (
          <section style={styles.section}>
            <h2 style={styles.h2}>Provider Health (24h)</h2>
            <table style={styles.table}>
              <thead>
                <tr>
                  {['Provider', 'Enabled', 'Requests', 'Failures', 'Avg Latency', 'Last Error'].map((h) => (
                    <th key={h} style={styles.th}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {providers.map((p) => (
                  <tr key={p.provider}>
                    <td style={styles.td}>{p.provider}</td>
                    <td style={styles.td}>{p.enabled ? '✅' : '🚫'}</td>
                    <td style={styles.td}>{p.requests_24h}</td>
                    <td style={{ ...styles.td, color: p.failures_24h > 0 ? '#dc2626' : '#374151' }}>{p.failures_24h}</td>
                    <td style={styles.td}>{p.avg_latency_ms != null ? `${p.avg_latency_ms} ms` : '—'}</td>
                    <td style={{ ...styles.td, fontSize: '0.75rem', color: '#6b7280' }}>{p.last_error || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}

        {/* Top errors */}
        {overview?.error_summary_last_24h?.length > 0 && (
          <section style={styles.section}>
            <h2 style={styles.h2}>Top Errors (24h)</h2>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>Error Message</th>
                  <th style={styles.th}>Count</th>
                </tr>
              </thead>
              <tbody>
                {overview.error_summary_last_24h.map((e, i) => (
                  <tr key={i}>
                    <td style={{ ...styles.td, fontFamily: 'monospace', fontSize: '0.8rem' }}>{e.message}</td>
                    <td style={{ ...styles.td, color: '#dc2626', fontWeight: '600' }}>{e.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}

        {/* Users table */}
        <section style={styles.section}>
          <div style={styles.usersHeader}>
            <h2 style={styles.h2}>Users</h2>
            <div style={styles.sortRow}>
              <span style={styles.sortLabel}>Sort by:</span>
              {['alerts', 'searches', 'notifications'].map((s) => (
                <button
                  key={s}
                  onClick={() => handleSortChange(s)}
                  style={{ ...styles.sortBtn, ...(usersSort === s ? styles.sortBtnActive : {}) }}
                >
                  {s.charAt(0).toUpperCase() + s.slice(1)}
                </button>
              ))}
            </div>
          </div>
          <table style={styles.table}>
            <thead>
              <tr>
                {['Email', 'Plan', 'Active Alerts', 'Searches (24h)', 'Notifs (24h)', 'Joined'].map((h) => (
                  <th key={h} style={styles.th}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr
                  key={u.user_id}
                  onClick={() => handleUserClick(u)}
                  style={{ ...styles.userRow, ...(selectedUser?.user_id === u.user_id ? styles.userRowSelected : {}) }}
                >
                  <td style={styles.td}>{u.email}</td>
                  <td style={styles.td}>{u.plan || 'free'}</td>
                  <td style={styles.td}>{u.active_alerts}</td>
                  <td style={styles.td}>{u.searches_24h}</td>
                  <td style={styles.td}>{u.notifications_24h}</td>
                  <td style={styles.td}>{u.created_at ? u.created_at.slice(0, 10) : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {users.length === 0 && <p style={styles.empty}>No users found.</p>}
        </section>

        {/* User detail drawer */}
        {selectedUser && (
          <section style={styles.section}>
            <div style={styles.drawerHeader}>
              <h2 style={styles.h2}>User Details: {selectedUser.email}</h2>
              <button onClick={() => { setSelectedUser(null); setUserDetails(null); }} style={styles.closeBtn}>✕ Close</button>
            </div>
            {!userDetails && <p style={styles.empty}>Loading…</p>}
            {userDetails?.error && <p style={styles.error}>{userDetails.error}</p>}
            {userDetails && !userDetails.error && (
              <div>
                <p><strong>Plan:</strong> {userDetails.profile?.plan || 'free'}</p>
                <p><strong>Onboarded:</strong> {String(userDetails.profile?.onboarded)}</p>
                <h3 style={styles.h3}>Recent Alerts</h3>
                {userDetails.recent_alerts.length === 0 ? (
                  <p style={styles.empty}>None</p>
                ) : (
                  <table style={styles.table}>
                    <thead>
                      <tr>
                        {['Route', 'Max Price', 'Active', 'Created'].map((h) => (
                          <th key={h} style={styles.th}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {userDetails.recent_alerts.map((a) => (
                        <tr key={a.id}>
                          <td style={styles.td}>{a.from_iata} → {a.to_iata}</td>
                          <td style={styles.td}>{a.currency} {a.max_price}</td>
                          <td style={styles.td}>{a.active ? '✅' : '—'}</td>
                          <td style={styles.td}>{(a.created_at || '').slice(0, 10)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
                <h3 style={styles.h3}>Recent Notifications</h3>
                {userDetails.recent_notifications.length === 0 ? (
                  <p style={styles.empty}>None</p>
                ) : (
                  <table style={styles.table}>
                    <thead>
                      <tr>
                        {['Channel', 'Status', 'Error', 'Sent At'].map((h) => (
                          <th key={h} style={styles.th}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {userDetails.recent_notifications.map((n) => (
                        <tr key={n.id}>
                          <td style={styles.td}>{n.channel}</td>
                          <td style={{ ...styles.td, color: n.status === 'failed' ? '#dc2626' : '#16a34a' }}>{n.status}</td>
                          <td style={{ ...styles.td, fontSize: '0.75rem', color: '#6b7280' }}>{n.error_message || '—'}</td>
                          <td style={styles.td}>{(n.sent_at || '').slice(0, 16).replace('T', ' ')}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )}
          </section>
        )}
      </div>
    </div>
  );
}

function StatCard({ label, value, color = '#1d4ed8' }) {
  return (
    <div style={styles.card}>
      <div style={{ ...styles.cardValue, color }}>{value ?? '—'}</div>
      <div style={styles.cardLabel}>{label}</div>
    </div>
  );
}

const styles = {
  page: { minHeight: '100vh', background: '#f3f4f6' },
  content: { maxWidth: '1100px', margin: '2rem auto', padding: '0 1rem' },
  center: { textAlign: 'center', marginTop: '4rem', fontSize: '1.1rem' },
  titleRow: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.5rem' },
  h1: { fontSize: '1.75rem', fontWeight: '800', color: '#1d4ed8', margin: 0 },
  h2: { fontSize: '1.15rem', fontWeight: '700', color: '#1d4ed8', margin: '0 0 1rem 0' },
  h3: { fontSize: '1rem', fontWeight: '700', color: '#374151', margin: '1rem 0 0.5rem 0' },
  section: {
    background: '#fff',
    borderRadius: '8px',
    padding: '1.5rem',
    boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
    marginBottom: '1.5rem',
  },
  cards: { display: 'flex', gap: '1rem', flexWrap: 'wrap', marginBottom: '0.75rem' },
  card: {
    flex: '1',
    minWidth: '120px',
    background: '#eff6ff',
    borderRadius: '8px',
    padding: '1rem',
    textAlign: 'center',
    border: '1px solid #bfdbfe',
  },
  cardValue: { fontSize: '1.75rem', fontWeight: '800' },
  cardLabel: { fontSize: '0.8rem', color: '#6b7280', marginTop: '0.25rem' },
  ts: { fontSize: '0.75rem', color: '#9ca3af', marginTop: '0.25rem' },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' },
  th: { textAlign: 'left', padding: '0.5rem 0.75rem', background: '#f9fafb', borderBottom: '2px solid #e5e7eb', fontWeight: '700', color: '#374151', whiteSpace: 'nowrap' },
  td: { padding: '0.5rem 0.75rem', borderBottom: '1px solid #f3f4f6', color: '#374151', verticalAlign: 'top' },
  usersHeader: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' },
  sortRow: { display: 'flex', alignItems: 'center', gap: '0.5rem' },
  sortLabel: { fontSize: '0.875rem', color: '#6b7280', fontWeight: '600' },
  sortBtn: { padding: '0.25rem 0.75rem', border: '1px solid #d1d5db', borderRadius: '4px', background: '#fff', cursor: 'pointer', fontSize: '0.8rem', color: '#374151' },
  sortBtnActive: { background: '#1d4ed8', color: '#fff', borderColor: '#1d4ed8' },
  userRow: { cursor: 'pointer', transition: 'background 0.1s' },
  userRowSelected: { background: '#eff6ff' },
  drawerHeader: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' },
  closeBtn: { padding: '0.25rem 0.75rem', background: '#f3f4f6', border: '1px solid #d1d5db', borderRadius: '4px', cursor: 'pointer', fontSize: '0.875rem' },
  error: { color: '#dc2626', fontSize: '0.875rem' },
  empty: { color: '#9ca3af', fontSize: '0.875rem', textAlign: 'center', padding: '1rem 0' },
  diagBtn: { padding: '0.5rem 1rem', background: '#1d4ed8', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: '600', fontSize: '0.875rem' },
  copyMsg: { fontSize: '0.875rem', color: '#16a34a', fontWeight: '600' },
};
