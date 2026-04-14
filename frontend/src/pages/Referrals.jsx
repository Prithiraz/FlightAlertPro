import { useState, useEffect } from 'react';
import { useAuth } from '../App';
import { getReferralInfo } from '../lib/api';

const SOCIAL_PROMPT =
  "I use this AI to track error fares and save hundreds on flights. Use my link to get 30 days of Elite access for free: ";

export default function Referrals() {
  const { user } = useAuth();
  const [referralCode, setReferralCode] = useState('');
  const [referredCount, setReferredCount] = useState(0);
  const [eliteUntil, setEliteUntil] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);
  const [socialCopied, setSocialCopied] = useState(false);

  useEffect(() => {
    if (!user?.email) return;
    getReferralInfo(user.email)
      .then((data) => {
        setReferralCode(data.referral_code || '');
        setReferredCount(data.referred_count ?? 0);
        setEliteUntil(data.elite_until ? new Date(data.elite_until) : null);
      })
      .catch((err) => setError(err.message || 'Failed to load referral info'))
      .finally(() => setLoading(false));
  }, [user?.email]);

  const referralLink = referralCode
    ? `${window.location.origin}/?ref=${referralCode}`
    : '';

  const socialText = referralLink ? `${SOCIAL_PROMPT}${referralLink}` : '';

  const handleCopyLink = async () => {
    if (!referralLink) return;
    try {
      await navigator.clipboard.writeText(referralLink);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch {
      /* fallback: select a textarea */
    }
  };

  const handleCopySocial = async () => {
    if (!socialText) return;
    try {
      await navigator.clipboard.writeText(socialText);
      setSocialCopied(true);
      setTimeout(() => setSocialCopied(false), 2500);
    } catch {
      /* noop */
    }
  };

  const eliteActive = eliteUntil && eliteUntil > new Date();

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <h1 style={styles.heading}>🎁 Refer &amp; Earn Free Elite</h1>
        <p style={styles.subheading}>
          Share your unique link. When a friend signs up, you both win&nbsp;—&nbsp;you get
          <strong> 30 days of Elite access</strong> unlocked automatically.
        </p>

        {loading && <p style={styles.muted}>Loading your referral info…</p>}
        {error && <p style={styles.errorText}>{error}</p>}

        {!loading && !error && (
          <>
            {/* ── Referral Link ── */}
            <section style={styles.section}>
              <label style={styles.label}>Your Unique Referral Link</label>
              <div style={styles.linkRow}>
                <input
                  readOnly
                  value={referralLink}
                  style={styles.linkInput}
                  onClick={(e) => e.target.select()}
                />
                <button onClick={handleCopyLink} style={styles.copyBtn}>
                  {copied ? '✅ Copied!' : '📋 Copy Link'}
                </button>
              </div>
            </section>

            {/* ── Stats Tracker ── */}
            <section style={styles.section}>
              <div style={styles.statsRow}>
                <div style={styles.statBox}>
                  <span style={styles.statNumber}>{referredCount}</span>
                  <span style={styles.statLabel}>Friends Referred</span>
                </div>
                <div style={{ ...styles.statBox, background: eliteActive ? '#d1fae5' : '#f3f4f6' }}>
                  <span style={{ ...styles.statNumber, color: eliteActive ? '#065f46' : '#6b7280' }}>
                    {eliteActive
                      ? eliteUntil.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
                      : '—'}
                  </span>
                  <span style={styles.statLabel}>
                    {eliteActive ? '🌟 Elite Access Until' : 'Elite Access Unlocked Until'}
                  </span>
                </div>
              </div>
            </section>

            {/* ── Social Share ── */}
            <section style={styles.section}>
              <label style={styles.label}>Share on Social Media</label>
              <div style={styles.socialBox}>
                <p style={styles.socialText}>{socialText}</p>
                <button onClick={handleCopySocial} style={styles.socialBtn}>
                  {socialCopied ? '✅ Copied!' : '📣 Copy Message'}
                </button>
              </div>
            </section>

            {/* ── How it works ── */}
            <section style={styles.howItWorks}>
              <h2 style={styles.howTitle}>How it works</h2>
              <ol style={styles.steps}>
                <li>Copy your unique referral link above.</li>
                <li>Share it with friends who love cheap flights.</li>
                <li>When they sign up, you automatically receive <strong>30 days of Elite access</strong>.</li>
                <li>No limits — each successful referral stacks another 30 days.</li>
              </ol>
            </section>
          </>
        )}
      </div>
    </div>
  );
}

const styles = {
  page: {
    minHeight: '100vh',
    background: '#f0f4ff',
    display: 'flex',
    justifyContent: 'center',
    padding: '2rem 1rem',
  },
  card: {
    background: '#ffffff',
    borderRadius: '12px',
    boxShadow: '0 4px 24px rgba(0,0,0,0.08)',
    padding: '2.5rem',
    maxWidth: '640px',
    width: '100%',
    alignSelf: 'flex-start',
  },
  heading: {
    fontSize: '1.75rem',
    fontWeight: '700',
    color: '#1d4ed8',
    marginBottom: '0.5rem',
  },
  subheading: {
    color: '#374151',
    marginBottom: '2rem',
    lineHeight: '1.6',
  },
  section: {
    marginBottom: '2rem',
  },
  label: {
    display: 'block',
    fontWeight: '600',
    marginBottom: '0.5rem',
    color: '#111827',
  },
  linkRow: {
    display: 'flex',
    gap: '0.5rem',
  },
  linkInput: {
    flex: 1,
    padding: '0.625rem 0.875rem',
    border: '1.5px solid #93c5fd',
    borderRadius: '6px',
    fontSize: '0.9rem',
    color: '#1d4ed8',
    background: '#eff6ff',
    outline: 'none',
  },
  copyBtn: {
    padding: '0.625rem 1.25rem',
    background: '#1d4ed8',
    color: '#fff',
    border: 'none',
    borderRadius: '6px',
    fontWeight: '600',
    cursor: 'pointer',
    whiteSpace: 'nowrap',
  },
  statsRow: {
    display: 'flex',
    gap: '1rem',
  },
  statBox: {
    flex: 1,
    background: '#f9fafb',
    borderRadius: '8px',
    padding: '1.25rem',
    textAlign: 'center',
    border: '1px solid #e5e7eb',
  },
  statNumber: {
    display: 'block',
    fontSize: '1.75rem',
    fontWeight: '700',
    color: '#1d4ed8',
    marginBottom: '0.25rem',
  },
  statLabel: {
    fontSize: '0.8rem',
    color: '#6b7280',
    fontWeight: '500',
  },
  socialBox: {
    background: '#fafafa',
    border: '1.5px solid #e5e7eb',
    borderRadius: '8px',
    padding: '1rem',
  },
  socialText: {
    color: '#374151',
    marginBottom: '0.75rem',
    lineHeight: '1.6',
    wordBreak: 'break-all',
  },
  socialBtn: {
    padding: '0.5rem 1rem',
    background: '#10b981',
    color: '#fff',
    border: 'none',
    borderRadius: '6px',
    fontWeight: '600',
    cursor: 'pointer',
  },
  howItWorks: {
    background: '#eff6ff',
    borderRadius: '8px',
    padding: '1.25rem 1.5rem',
  },
  howTitle: {
    fontSize: '1rem',
    fontWeight: '700',
    color: '#1d4ed8',
    marginBottom: '0.75rem',
  },
  steps: {
    paddingLeft: '1.25rem',
    color: '#374151',
    lineHeight: '1.8',
  },
  muted: {
    color: '#6b7280',
  },
  errorText: {
    color: '#dc2626',
  },
};
