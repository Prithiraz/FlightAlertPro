import { useState, useEffect } from 'react';
import { useAuth } from '../App';
import { getProfile, updateProfile } from '../lib/api';

export default function Settings() {
  const { user } = useAuth();
  const [lifecycleEmails, setLifecycleEmails] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    getProfile()
      .then((profile) => {
        if (profile.lifecycle_emails_opt_in !== undefined) {
          setLifecycleEmails(profile.lifecycle_emails_opt_in !== false);
        }
      })
      .catch(() => {});
  }, []);

  const handleToggle = async (e) => {
    const val = e.target.checked;
    setLifecycleEmails(val);
    setSaving(true);
    setSaved(false);
    try {
      await updateProfile({ lifecycle_emails_opt_in: val });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {
      // revert on error
      setLifecycleEmails(!val);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={styles.page}>
      <h2 style={styles.heading}>Settings</h2>
      <div style={styles.card}>
        <h3 style={styles.subHeading}>Account</h3>
        <p style={styles.label}>Email</p>
        <p style={styles.value}>{user?.email ?? '—'}</p>
      </div>

      <div style={styles.card}>
        <h3 style={styles.subHeading}>Email Preferences</h3>
        <label style={styles.checkboxRow}>
          <input
            type="checkbox"
            checked={lifecycleEmails}
            onChange={handleToggle}
            disabled={saving}
            style={styles.checkbox}
          />
          <span style={styles.checkboxLabel}>
            Email me tips, product updates, and re-engagement nudges
          </span>
        </label>
        {saved && <p style={styles.savedMsg}>✓ Saved</p>}
        <p style={styles.note}>
          You will always receive transactional emails (price alerts, account security). This setting only controls marketing and lifecycle emails.
        </p>
      </div>
    </div>
  );
}

const styles = {
  page: { maxWidth: '600px', margin: '2rem auto', padding: '0 1rem' },
  heading: { fontSize: '1.75rem', marginBottom: '1.5rem', color: '#1d4ed8' },
  card: {
    background: '#fff',
    borderRadius: '8px',
    padding: '1.5rem',
    boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
    marginBottom: '1.25rem',
  },
  subHeading: { fontSize: '1.125rem', fontWeight: '700', marginBottom: '1rem', color: '#374151' },
  label: { fontSize: '0.875rem', fontWeight: '600', color: '#374151', margin: '0 0 0.25rem' },
  value: { fontSize: '1rem', color: '#111827', margin: '0 0 1rem' },
  checkboxRow: { display: 'flex', alignItems: 'flex-start', gap: '0.625rem', cursor: 'pointer', marginBottom: '0.75rem' },
  checkbox: { marginTop: '0.15rem', flexShrink: 0, width: '1rem', height: '1rem', cursor: 'pointer' },
  checkboxLabel: { fontSize: '0.9rem', color: '#111827', lineHeight: 1.5 },
  savedMsg: { fontSize: '0.8rem', color: '#16a34a', margin: '0 0 0.5rem', fontWeight: '600' },
  note: { fontSize: '0.8rem', color: '#9ca3af', margin: 0, lineHeight: 1.5 },
};
