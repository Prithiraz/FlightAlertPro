import { useState, useEffect } from 'react';
import { useAuth } from '../App';
import { generateReferralCode, getReferralStats } from '../lib/api';

export default function Settings() {
  const { user } = useAuth();
  const [referral, setReferral] = useState(null);
  const [referralLoading, setReferralLoading] = useState(false);
  const [referralError, setReferralError] = useState('');
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (user?.email) {
      loadReferralStats();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.email]);

  const loadReferralStats = async () => {
    try {
      const data = await getReferralStats(user.email);
      setReferral(data);
    } catch {
      // Non-critical — silently ignore
    }
  };

  const handleGenerateCode = async () => {
    setReferralLoading(true);
    setReferralError('');
    try {
      const data = await generateReferralCode(user.email);
      setReferral((prev) => ({ ...prev, ...data, has_code: true }));
    } catch (err) {
      setReferralError(err.message || 'Failed to generate code');
    } finally {
      setReferralLoading(false);
    }
  };

  const handleCopy = (text) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div style={styles.page}>
      <h2 style={styles.heading}>Settings</h2>

      {/* Account card */}
      <div style={styles.card}>
        <h3 style={styles.subHeading}>Account</h3>
        <p style={styles.label}>Email</p>
        <p style={styles.value}>{user?.email ?? '—'}</p>
        <p style={styles.label}>Current Plan</p>
        <p style={styles.value}>
          Free{' '}
          <a href="/plans" style={styles.upgradeLink}>Upgrade →</a>
        </p>
      </div>

      {/* Referral programme card */}
      <div style={styles.card}>
        <h3 style={styles.subHeading}>🎁 Refer a Friend — Earn $10 Credit</h3>
        <p style={styles.desc}>
          Share your unique referral link. Every friend who upgrades to a paid plan earns you
          a <strong>$10 account credit</strong>. Your friend gets <strong>$5 off</strong> their
          first upgrade.
        </p>

        {referral?.has_code ? (
          <div style={styles.codeBlock}>
            <div style={styles.codeRow}>
              <span style={styles.codeText}>{referral.referral_link}</span>
              <button onClick={() => handleCopy(referral.referral_link)} style={styles.copyBtn}>
                {copied ? '✓ Copied' : 'Copy'}
              </button>
            </div>
            <div style={styles.statsRow}>
              <span style={styles.stat}>👥 {referral.uses ?? 0} referrals</span>
              <span style={styles.stat}>💰 ${(referral.credits_earned_usd ?? 0).toFixed(2)} earned</span>
            </div>
          </div>
        ) : (
          <div>
            {referralError && <p style={styles.error}>{referralError}</p>}
            <button
              onClick={handleGenerateCode}
              disabled={referralLoading}
              style={styles.genBtn}
            >
              {referralLoading ? 'Generating…' : '✨ Get my referral link'}
            </button>
          </div>
        )}
      </div>

      {/* Notifications card */}
      <div style={styles.card}>
        <h3 style={styles.subHeading}>Notifications</h3>
        <p style={styles.desc}>
          Notification channel preferences (WhatsApp, Telegram) are configured when creating
          a price alert. Visit the <a href="/alerts" style={styles.upgradeLink}>Alerts</a> page
          to manage your alerts.
        </p>
      </div>
    </div>
  );
}

const styles = {
  page: { maxWidth: '640px', margin: '2rem auto', padding: '0 1rem', display: 'flex', flexDirection: 'column', gap: '1.5rem' },
  heading: { fontSize: '1.75rem', marginBottom: '0', color: '#1d4ed8' },
  card: { background: '#fff', borderRadius: '8px', padding: '1.5rem', boxShadow: '0 2px 8px rgba(0,0,0,0.08)', display: 'flex', flexDirection: 'column', gap: '0.625rem' },
  subHeading: { fontSize: '1.125rem', fontWeight: '700', marginBottom: '0.25rem', color: '#374151' },
  label: { fontSize: '0.875rem', fontWeight: '600', color: '#374151', margin: 0 },
  value: { fontSize: '1rem', color: '#111827', margin: 0 },
  desc: { fontSize: '0.9rem', color: '#6b7280', lineHeight: 1.5, margin: 0 },
  upgradeLink: { color: '#1d4ed8', fontWeight: '600', textDecoration: 'none' },
  codeBlock: { background: '#f9fafb', borderRadius: '8px', padding: '1rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' },
  codeRow: { display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' },
  codeText: { fontFamily: 'monospace', fontSize: '0.9rem', color: '#111827', wordBreak: 'break-all' },
  copyBtn: { padding: '0.375rem 0.875rem', background: '#1d4ed8', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: '600', fontSize: '0.875rem', whiteSpace: 'nowrap' },
  statsRow: { display: 'flex', gap: '1.5rem' },
  stat: { fontSize: '0.875rem', color: '#374151', fontWeight: '600' },
  genBtn: { padding: '0.625rem 1.5rem', background: '#7c3aed', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: '700', fontSize: '1rem' },
  error: { color: '#dc2626', fontSize: '0.875rem', margin: '0 0 0.5rem' },
};
