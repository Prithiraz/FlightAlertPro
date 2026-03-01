import { useState, useEffect } from 'react';
import { getBillingStatus, createBillingCheckout, getBillingPortal, getMe } from '../lib/api';

const PLAN_DETAILS = {
  free: {
    label: 'Free',
    price: '$0/mo',
    color: '#6b7280',
    features: ['3 active alerts', '20 searches/day', '5 notifications/day'],
  },
  pro: {
    label: 'Pro',
    price: '$9/mo',
    color: '#1d4ed8',
    features: ['20 active alerts', '200 searches/day', '50 notifications/day', 'Priority queue'],
  },
  elite: {
    label: 'Elite',
    price: '$29/mo',
    color: '#7c3aed',
    features: ['50 active alerts', '500 searches/day', '100 notifications/day', 'Priority queue'],
  },
  business: {
    label: 'Business',
    price: '$99/mo',
    color: '#b45309',
    features: ['200 active alerts', '2000 searches/day', '500 notifications/day', 'Priority queue'],
  },
};

export default function Billing() {
  const [me, setMe] = useState(null);
  const [billing, setBilling] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([getMe().catch(() => null), getBillingStatus().catch(() => null)])
      .then(([meData, billingData]) => {
        setMe(meData);
        setBilling(billingData);
      })
      .finally(() => setLoading(false));
  }, []);

  const handleUpgrade = async (plan) => {
    setError('');
    setActionLoading(plan);
    try {
      const session = await createBillingCheckout(plan);
      if (session?.url) {
        window.location.href = session.url;
      } else {
        setError('Could not create checkout session. Is Stripe configured?');
      }
    } catch (err) {
      setError(err.message || 'Checkout failed');
    } finally {
      setActionLoading('');
    }
  };

  const handlePortal = async () => {
    setError('');
    setActionLoading('portal');
    try {
      const result = await getBillingPortal();
      if (result?.url) {
        window.location.href = result.url;
      } else {
        setError('Could not open billing portal. Is Stripe configured?');
      }
    } catch (err) {
      setError(err.message || 'Portal unavailable');
    } finally {
      setActionLoading('');
    }
  };

  const currentPlan = (me?.plan || billing?.plan || 'free').toLowerCase();
  const limits = me?.limits || {};
  const usage = me?.usage || {};

  return (
    <div style={styles.page}>
      <h2 style={styles.heading}>Plan &amp; Billing</h2>

      {loading ? (
        <p style={styles.empty}>Loading billing info…</p>
      ) : (
        <>
          {/* Current plan summary */}
          <div style={styles.card}>
            <h3 style={styles.subHeading}>Current Plan</h3>
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
              <span
                style={{
                  ...styles.badge,
                  background: PLAN_DETAILS[currentPlan]?.color || '#6b7280',
                }}
              >
                {PLAN_DETAILS[currentPlan]?.label || currentPlan}
              </span>
              {billing?.subscription_status && (
                <span style={styles.subStatus}>
                  Status: {billing.subscription_status}
                </span>
              )}
            </div>

            <div style={styles.usageRow}>
              <div style={styles.usageStat}>
                <span style={styles.usageNum}>{usage.alerts_active ?? '—'}</span>
                <span style={styles.usageLabel}>
                  / {limits.max_active_alerts ?? '—'} active alerts
                </span>
              </div>
              <div style={styles.usageStat}>
                <span style={styles.usageNum}>{limits.max_searches_per_day ?? '—'}</span>
                <span style={styles.usageLabel}>searches/day</span>
              </div>
              <div style={styles.usageStat}>
                <span style={styles.usageNum}>{limits.max_notifications_per_day ?? '—'}</span>
                <span style={styles.usageLabel}>notifications/day</span>
              </div>
            </div>

            {currentPlan !== 'free' && (
              <button
                onClick={handlePortal}
                disabled={actionLoading === 'portal'}
                style={styles.portalBtn}
              >
                {actionLoading === 'portal' ? 'Opening…' : 'Manage Subscription →'}
              </button>
            )}
          </div>

          {/* Plan comparison / upgrade */}
          <h3 style={styles.subHeading}>Upgrade</h3>
          <div style={styles.planGrid}>
            {Object.entries(PLAN_DETAILS)
              .filter(([p]) => p !== currentPlan && p !== 'free')
              .map(([plan, details]) => (
                <div key={plan} style={styles.planCard}>
                  <div style={{ ...styles.planHeader, background: details.color }}>
                    <span style={styles.planLabel}>{details.label}</span>
                    <span style={styles.planPrice}>{details.price}</span>
                  </div>
                  <ul style={styles.featureList}>
                    {details.features.map((f) => (
                      <li key={f} style={styles.featureItem}>✓ {f}</li>
                    ))}
                  </ul>
                  <button
                    onClick={() => handleUpgrade(plan)}
                    disabled={!!actionLoading}
                    style={{ ...styles.upgradeBtn, background: details.color }}
                  >
                    {actionLoading === plan ? 'Redirecting…' : `Upgrade to ${details.label}`}
                  </button>
                </div>
              ))}
          </div>

          {error && <p style={styles.error}>{error}</p>}
        </>
      )}
    </div>
  );
}

const styles = {
  page: { maxWidth: '900px', margin: '2rem auto', padding: '0 1rem' },
  heading: { fontSize: '1.75rem', marginBottom: '1.5rem', color: '#1d4ed8' },
  card: {
    background: '#fff',
    padding: '1.5rem',
    borderRadius: '8px',
    boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
    marginBottom: '2rem',
  },
  subHeading: { fontSize: '1.125rem', fontWeight: '700', marginBottom: '1rem', color: '#374151' },
  badge: {
    display: 'inline-block',
    color: '#fff',
    fontWeight: '700',
    fontSize: '1rem',
    padding: '0.3rem 0.9rem',
    borderRadius: '999px',
  },
  subStatus: { fontSize: '0.875rem', color: '#6b7280' },
  usageRow: { display: 'flex', gap: '2rem', marginTop: '1rem', flexWrap: 'wrap' },
  usageStat: { display: 'flex', flexDirection: 'column', alignItems: 'center' },
  usageNum: { fontSize: '1.5rem', fontWeight: '700', color: '#1d4ed8' },
  usageLabel: { fontSize: '0.75rem', color: '#6b7280', marginTop: '0.125rem' },
  portalBtn: {
    marginTop: '1.25rem',
    padding: '0.5rem 1.25rem',
    background: '#fff',
    color: '#1d4ed8',
    border: '1px solid #1d4ed8',
    borderRadius: '6px',
    cursor: 'pointer',
    fontWeight: '600',
    fontSize: '0.9rem',
  },
  planGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '1rem', marginBottom: '1.5rem' },
  planCard: {
    background: '#fff',
    borderRadius: '8px',
    boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
    overflow: 'hidden',
    display: 'flex',
    flexDirection: 'column',
  },
  planHeader: {
    padding: '1rem',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  planLabel: { color: '#fff', fontWeight: '700', fontSize: '1.1rem' },
  planPrice: { color: 'rgba(255,255,255,0.9)', fontSize: '0.95rem', fontWeight: '600' },
  featureList: { listStyle: 'none', padding: '1rem', margin: 0, flex: 1, display: 'flex', flexDirection: 'column', gap: '0.375rem' },
  featureItem: { fontSize: '0.875rem', color: '#374151' },
  upgradeBtn: {
    display: 'block',
    width: '100%',
    padding: '0.625rem',
    color: '#fff',
    border: 'none',
    cursor: 'pointer',
    fontWeight: '600',
    fontSize: '0.9rem',
  },
  error: { color: '#dc2626', fontSize: '0.875rem', marginTop: '0.5rem' },
  empty: { color: '#6b7280', textAlign: 'center', padding: '2rem 0' },
};
