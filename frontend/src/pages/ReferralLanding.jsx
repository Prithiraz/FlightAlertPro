import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { apiFetch } from '../lib/api';

export default function ReferralLanding() {
  const { code } = useParams();
  const navigate = useNavigate();
  const [tracked, setTracked] = useState(false);

  useEffect(() => {
    if (!code) return;

    // Store referral code in localStorage for later claim at signup
    localStorage.setItem('referral_code', code);

    // Track visit event (fire-and-forget)
    apiFetch('/api/referral/track', {
      method: 'POST',
      body: JSON.stringify({ code, event_type: 'visit' }),
    }).catch(() => {/* ignore */});

    setTracked(true);
  }, [code]);

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <div style={styles.emoji}>✈️</div>
        <h1 style={styles.title}>You've been invited to FlightAlertPro!</h1>
        <p style={styles.sub}>
          Your friend thinks you'll love saving money on flights. Set a price target — we'll alert you the moment fares drop.
        </p>

        <div style={styles.perks}>
          <div style={styles.perk}>🔔 Price alerts 24/7</div>
          <div style={styles.perk}>✅ Free to get started</div>
          <div style={styles.perk}>💸 No credit card required</div>
        </div>

        <button
          style={styles.cta}
          onClick={() => navigate('/login?signup=1')}
          disabled={!tracked && !!code}
        >
          Create Free Account →
        </button>

        {code && (
          <p style={styles.refNote}>Referral code <strong>{code}</strong> will be applied automatically.</p>
        )}
      </div>
    </div>
  );
}

const styles = {
  page: {
    minHeight: '100vh',
    background: 'linear-gradient(135deg, #1d4ed8 0%, #3b82f6 100%)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    padding: '2rem 1rem',
    fontFamily: 'system-ui, sans-serif',
  },
  card: {
    background: '#fff',
    borderRadius: '16px',
    padding: '2.5rem',
    maxWidth: '480px',
    width: '100%',
    textAlign: 'center',
    boxShadow: '0 8px 32px rgba(0,0,0,0.15)',
  },
  emoji: { fontSize: '3rem', marginBottom: '0.75rem' },
  title: { fontSize: '1.6rem', fontWeight: '800', color: '#1d4ed8', margin: '0 0 0.75rem' },
  sub: { fontSize: '1rem', color: '#6b7280', lineHeight: 1.6, margin: '0 0 1.5rem' },
  perks: { display: 'flex', flexDirection: 'column', gap: '0.5rem', marginBottom: '2rem', textAlign: 'left' },
  perk: { fontSize: '0.95rem', color: '#374151', padding: '0.375rem 0' },
  cta: {
    display: 'block',
    width: '100%',
    padding: '0.875rem',
    background: '#1d4ed8',
    color: '#fff',
    border: 'none',
    borderRadius: '8px',
    fontWeight: '700',
    fontSize: '1.05rem',
    cursor: 'pointer',
    marginBottom: '1rem',
  },
  refNote: { fontSize: '0.8rem', color: '#9ca3af', margin: 0 },
};
