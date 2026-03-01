import { useState, useEffect } from 'react';
import { useWorkspace } from '../lib/WorkspaceContext';
import {
  getWorkspaceMembers,
  inviteMember,
  updateMemberRole,
  removeMember,
  listApiKeys,
  createApiKey,
  revokeApiKey,
  getWorkspaceUsage,
} from '../lib/api';

const ROLE_OPTIONS = ['admin', 'member', 'viewer'];

export default function Workspace() {
  const { currentWorkspace, workspaces, setCurrentWorkspace } = useWorkspace();

  const [members, setMembers] = useState([]);
  const [apiKeys, setApiKeys] = useState([]);
  const [usage, setUsage] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Invite form
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState('member');
  const [inviteMsg, setInviteMsg] = useState('');
  const [inviting, setInviting] = useState(false);

  // New API key form
  const [newKeyName, setNewKeyName] = useState('');
  const [newKeyResult, setNewKeyResult] = useState(null);
  const [creatingKey, setCreatingKey] = useState(false);
  const [keyMsg, setKeyMsg] = useState('');

  const isAdmin = currentWorkspace && ['owner', 'admin'].includes(currentWorkspace.my_role);
  const isBusiness = currentWorkspace && ['business', 'elite'].includes(currentWorkspace.plan);

  useEffect(() => {
    if (!currentWorkspace) return;
    setLoading(true);
    setError('');
    Promise.all([
      getWorkspaceMembers(currentWorkspace.id).catch(() => ({ members: [] })),
      isBusiness
        ? listApiKeys(currentWorkspace.id).catch(() => ({ api_keys: [] }))
        : Promise.resolve({ api_keys: [] }),
      getWorkspaceUsage(currentWorkspace.id).catch(() => null),
    ])
      .then(([membersData, keysData, usageData]) => {
        setMembers(membersData.members || []);
        setApiKeys(keysData.api_keys || []);
        setUsage(usageData);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentWorkspace?.id]);

  const handleInvite = async (e) => {
    e.preventDefault();
    if (!inviteEmail.trim()) return;
    setInviting(true);
    setInviteMsg('');
    try {
      const res = await inviteMember(currentWorkspace.id, inviteEmail.trim(), inviteRole);
      setInviteMsg(`✓ Invite created. Share this token: ${res.token}`);
      setInviteEmail('');
    } catch (err) {
      setInviteMsg(`Error: ${err.message}`);
    } finally {
      setInviting(false);
    }
  };

  const handleRoleChange = async (memberId, newRole) => {
    try {
      await updateMemberRole(currentWorkspace.id, memberId, newRole);
      setMembers((prev) =>
        prev.map((m) => (m.id === memberId ? { ...m, role: newRole } : m))
      );
    } catch (err) {
      setError(err.message);
    }
  };

  const handleRemoveMember = async (memberId) => {
    if (!window.confirm('Remove this member?')) return;
    try {
      await removeMember(currentWorkspace.id, memberId);
      setMembers((prev) => prev.filter((m) => m.id !== memberId));
    } catch (err) {
      setError(err.message);
    }
  };

  const handleCreateKey = async (e) => {
    e.preventDefault();
    if (!newKeyName.trim()) return;
    setCreatingKey(true);
    setKeyMsg('');
    setNewKeyResult(null);
    try {
      const res = await createApiKey(currentWorkspace.id, newKeyName.trim());
      setNewKeyResult(res);
      setNewKeyName('');
      // Refresh list
      const keysData = await listApiKeys(currentWorkspace.id).catch(() => ({ api_keys: [] }));
      setApiKeys(keysData.api_keys || []);
    } catch (err) {
      setKeyMsg(`Error: ${err.message}`);
    } finally {
      setCreatingKey(false);
    }
  };

  const handleRevokeKey = async (keyId) => {
    if (!window.confirm('Revoke this API key? This cannot be undone.')) return;
    try {
      await revokeApiKey(currentWorkspace.id, keyId);
      setApiKeys((prev) => prev.filter((k) => k.id !== keyId));
    } catch (err) {
      setError(err.message);
    }
  };

  if (!currentWorkspace) {
    return (
      <div style={styles.page}>
        <h2 style={styles.heading}>Workspace</h2>
        <p style={styles.muted}>No workspace selected.</p>
      </div>
    );
  }

  return (
    <div style={styles.page}>
      <div style={styles.titleRow}>
        <h2 style={styles.heading}>Workspace: {currentWorkspace.name}</h2>
        <span style={styles.badge}>{currentWorkspace.plan?.toUpperCase()}</span>
      </div>
      <p style={styles.muted}>Your role: <strong>{currentWorkspace.my_role}</strong></p>

      {workspaces.length > 1 && (
        <div style={styles.card}>
          <h3 style={styles.subHeading}>Switch Workspace</h3>
          <select
            style={styles.select}
            value={currentWorkspace.id}
            onChange={(e) => {
              const ws = workspaces.find((w) => w.id === e.target.value);
              if (ws) setCurrentWorkspace(ws);
            }}
          >
            {workspaces.map((ws) => (
              <option key={ws.id} value={ws.id}>{ws.name} ({ws.plan})</option>
            ))}
          </select>
        </div>
      )}

      {error && <p style={styles.errorMsg}>{error}</p>}
      {loading && <p style={styles.muted}>Loading…</p>}

      {/* Members */}
      <div style={styles.card}>
        <h3 style={styles.subHeading}>Members</h3>
        {members.length === 0 ? (
          <p style={styles.muted}>No members yet.</p>
        ) : (
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.th}>User ID</th>
                <th style={styles.th}>Role</th>
                {isAdmin && <th style={styles.th}>Actions</th>}
              </tr>
            </thead>
            <tbody>
              {members.map((m) => (
                <tr key={m.id}>
                  <td style={styles.td}>{m.user_id}</td>
                  <td style={styles.td}>
                    {isAdmin && m.role !== 'owner' ? (
                      <select
                        style={styles.selectSmall}
                        value={m.role}
                        onChange={(e) => handleRoleChange(m.id, e.target.value)}
                      >
                        {ROLE_OPTIONS.map((r) => (
                          <option key={r} value={r}>{r}</option>
                        ))}
                      </select>
                    ) : (
                      m.role
                    )}
                  </td>
                  {isAdmin && (
                    <td style={styles.td}>
                      {m.role !== 'owner' && (
                        <button
                          style={styles.dangerBtn}
                          onClick={() => handleRemoveMember(m.id)}
                        >
                          Remove
                        </button>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {/* Invite form */}
        {isAdmin && (
          <form onSubmit={handleInvite} style={styles.inviteForm}>
            <h4 style={styles.formTitle}>Invite Member</h4>
            <div style={styles.formRow}>
              <input
                style={styles.input}
                type="email"
                placeholder="Email address"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                required
              />
              <select
                style={styles.selectSmall}
                value={inviteRole}
                onChange={(e) => setInviteRole(e.target.value)}
              >
                {ROLE_OPTIONS.map((r) => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>
              <button type="submit" style={styles.btn} disabled={inviting}>
                {inviting ? 'Sending…' : 'Invite'}
              </button>
            </div>
            {inviteMsg && (
              <p style={{ ...styles.muted, marginTop: '0.5rem', wordBreak: 'break-all' }}>
                {inviteMsg}
              </p>
            )}
          </form>
        )}
      </div>

      {/* API Keys — Business only */}
      {isBusiness && isAdmin && (
        <div style={styles.card}>
          <h3 style={styles.subHeading}>API Keys</h3>
          <p style={styles.muted}>Use API keys to authenticate programmatic access via the <code>X-API-Key</code> header.</p>

          {newKeyResult && (
            <div style={styles.keyAlert}>
              <strong>New API Key (copy now — not shown again):</strong>
              <code style={styles.keyCode}>{newKeyResult.api_key}</code>
            </div>
          )}

          {apiKeys.length === 0 ? (
            <p style={styles.muted}>No active API keys.</p>
          ) : (
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>Name</th>
                  <th style={styles.th}>Prefix</th>
                  <th style={styles.th}>Last Used</th>
                  <th style={styles.th}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {apiKeys.map((k) => (
                  <tr key={k.id}>
                    <td style={styles.td}>{k.name}</td>
                    <td style={styles.td}><code>{k.key_prefix}…</code></td>
                    <td style={styles.td}>{k.last_used_at ? new Date(k.last_used_at).toLocaleDateString() : 'Never'}</td>
                    <td style={styles.td}>
                      <button style={styles.dangerBtn} onClick={() => handleRevokeKey(k.id)}>
                        Revoke
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <form onSubmit={handleCreateKey} style={styles.inviteForm}>
            <h4 style={styles.formTitle}>Create API Key</h4>
            <div style={styles.formRow}>
              <input
                style={styles.input}
                type="text"
                placeholder="Key name (e.g. CI pipeline)"
                value={newKeyName}
                onChange={(e) => setNewKeyName(e.target.value)}
                required
              />
              <button type="submit" style={styles.btn} disabled={creatingKey}>
                {creatingKey ? 'Creating…' : 'Create'}
              </button>
            </div>
            {keyMsg && <p style={styles.errorMsg}>{keyMsg}</p>}
          </form>
        </div>
      )}

      {!isBusiness && (
        <div style={styles.card}>
          <h3 style={styles.subHeading}>API Keys</h3>
          <p style={styles.muted}>
            API keys are available on the <strong>Business</strong> plan.{' '}
            <a href="/billing" style={styles.link}>Upgrade →</a>
          </p>
        </div>
      )}

      {/* Usage */}
      <div style={styles.card}>
        <h3 style={styles.subHeading}>Usage (last 7 days)</h3>
        {usage ? (
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.th}>Event</th>
                <th style={styles.th}>Count</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(usage.usage || {}).map(([key, val]) => (
                <tr key={key}>
                  <td style={styles.td}>{key}</td>
                  <td style={styles.td}>{val}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p style={styles.muted}>No usage data yet.</p>
        )}
      </div>
    </div>
  );
}

const styles = {
  page: { maxWidth: '800px', margin: '2rem auto', padding: '0 1rem' },
  titleRow: { display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.25rem' },
  heading: { fontSize: '1.75rem', color: '#1d4ed8', margin: 0 },
  badge: {
    background: '#b45309', color: '#fff', fontSize: '0.7rem', fontWeight: '700',
    padding: '0.2rem 0.5rem', borderRadius: '4px', textTransform: 'uppercase',
  },
  muted: { fontSize: '0.875rem', color: '#6b7280', margin: '0.25rem 0 0.75rem' },
  errorMsg: { color: '#dc2626', fontSize: '0.875rem', marginBottom: '0.75rem' },
  card: {
    background: '#fff', borderRadius: '8px', padding: '1.5rem',
    boxShadow: '0 2px 8px rgba(0,0,0,0.08)', marginBottom: '1.25rem',
  },
  subHeading: { fontSize: '1.125rem', fontWeight: '700', color: '#374151', marginBottom: '1rem' },
  formTitle: { fontSize: '0.95rem', fontWeight: '600', color: '#374151', margin: '1rem 0 0.5rem' },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' },
  th: { textAlign: 'left', padding: '0.5rem 0.75rem', borderBottom: '2px solid #e5e7eb', color: '#374151', fontWeight: '600' },
  td: { padding: '0.5rem 0.75rem', borderBottom: '1px solid #e5e7eb', color: '#111827', verticalAlign: 'middle' },
  select: { padding: '0.5rem 0.75rem', border: '1px solid #d1d5db', borderRadius: '6px', fontSize: '0.9rem', background: '#fff', width: '100%' },
  selectSmall: { padding: '0.35rem 0.5rem', border: '1px solid #d1d5db', borderRadius: '4px', fontSize: '0.85rem', background: '#fff' },
  btn: { padding: '0.5rem 1rem', background: '#1d4ed8', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: '600', fontSize: '0.875rem', whiteSpace: 'nowrap' },
  dangerBtn: { padding: '0.3rem 0.6rem', background: '#dc2626', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '0.8rem' },
  inviteForm: { marginTop: '1rem' },
  formRow: { display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' },
  input: { flex: 1, minWidth: '180px', padding: '0.5rem 0.75rem', border: '1px solid #d1d5db', borderRadius: '6px', fontSize: '0.9rem' },
  keyAlert: { background: '#fef3c7', border: '1px solid #f59e0b', borderRadius: '6px', padding: '0.75rem 1rem', marginBottom: '1rem' },
  keyCode: { display: 'block', marginTop: '0.5rem', wordBreak: 'break-all', fontSize: '0.85rem', fontFamily: 'monospace', background: '#fff', padding: '0.5rem', borderRadius: '4px' },
  link: { color: '#1d4ed8', textDecoration: 'underline' },
};
