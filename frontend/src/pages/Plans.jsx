import { useState } from 'react';
import { useAuth } from '../App';
import { createCheckoutSession } from '../lib/api';

const PLANS = [
  {
    id: 'free',
    name: 'Free',
    price: '$0',
    period: 'forever',
    color: '#6b7280',
    features: [
      '5 active price alerts',
      'Email notifications only',
      'Basic flight search',
      '15-minute price refresh',
      'Standard support',
    ],
    cta: 'Current Plan',
    disabled: true,
  },
  {
    id: 'pro',
    name: 'Pro',
    price: '$9',
    period: '/month',
    color: '#1d4ed8',
    badge: 'Most Popular',
    features: [
      '50 active price alerts',
      'Email + WhatsApp + Telegram alerts',
      'Flexible date search (±7 days)',
      '5-minute price refresh',
      'Price history charts (30 days)',
      'AI price predictions',
      'Priority support',
    ],
    cta: 'Upgrade to Pro',
    disabled: false,
  },
  {
    id: 'elite',
    name: 'Elite',
    price: '$29',
    period: '/month',
    color: '#7c3aed',
    badge: 'Best Value',
    features: [
      'Unlimited active price alerts',
      'All notification channels',
      'Flexible date search (±14 days)',
      '1-minute price refresh',
      'Price history charts (90 days)',
      'Advanced AI travel recommendations',
      'Destination explorer (Explore feature)',
      'Group booking coordination',
      'Export alerts & history',
      'Dedicated support',
    ],
    cta: 'Upgrade to Elite',
    disabled: false,
  },
  {
    id: 'business',
    name: 'Business',
    price: '$99',
    period: '/month',
    color: '#b45309',
    features: [
      'Everything in Elite',
      'Up to 10 team members',
      'Corporate travel approvals workflow',
      'Expense report exports (CSV/PDF)',
      'White-label API access',
      'Custom alert rules & automations',
      'SLA-backed uptime guarantee',
      'Dedicated account manager',
    ],
    cta: 'Contact Sales',
    disabled: false,
    contactSales: true,
  },
];

export default function Plans() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(null);
  const [error, setError] = useState('');

  const handleUpgrade = async (plan) => {
    if (!user?.email) {
      setError('Please log in to upgrade your plan.');
      return;
    }
    if (plan.contactSales) {
      window.location.href = 'mailto:sales@flightalertpro.com?subject=Business Plan Enquiry';
      return;
    }
    setLoading(plan.id);
    setError('');
    try {
      const origin = window.location.origin;
      const session = await createCheckoutSession({
        userEmail: user.email,
        plan: plan.id,
        successUrl: `${origin}/settings?upgrade=success`,
        cancelUrl: `${origin}/plans`,
      });
      if (session?.url) {
        window.location.href = session.url;
      } else {
        setError('Failed to start checkout. Please try again.');
      }
    } catch (err) {
      setError(err.message || 'Checkout failed. Please try again.');
    } finally {
      setLoading(null);
    }
  };

  return (
    <div style={styles.page}>
      <div style={styles.hero}>
        <h1 style={styles.heroTitle}>Choose your plan</h1>
        <p style={styles.heroSub}>
          From casual travellers to corporate teams — FlightAlertPro has a plan that fits.
          Unlock smarter alerts, flexible search, and AI-powered travel insights.
        </p>
      </div>

      {error && <p style={styles.globalError}>{error}</p>}

      <div style={styles.grid}>
        {PLANS.map((plan) => (
          <div
            key={plan.id}
            style={{
              ...styles.card,
              borderColor: plan.badge ? plan.color : '#e5e7eb',
              borderWidth: plan.badge ? 2 : 1,
            }}
          >
            {plan.badge && (
              <div style={{ ...styles.badge, background: plan.color }}>{plan.badge}</div>
            )}
            <h2 style={{ ...styles.planName, color: plan.color }}>{plan.name}</h2>
            <div style={styles.priceRow}>
              <span style={styles.price}>{plan.price}</span>
              <span style={styles.period}>{plan.period}</span>
            </div>
            <ul style={styles.featureList}>
              {plan.features.map((f) => (
                <li key={f} style={styles.featureItem}>
                  <span style={styles.check}>✓</span> {f}
                </li>
              ))}
            </ul>
            <button
              onClick={() => handleUpgrade(plan)}
              disabled={plan.disabled || loading === plan.id}
              style={{
                ...styles.cta,
                background: plan.disabled ? '#e5e7eb' : plan.color,
                color: plan.disabled ? '#6b7280' : '#fff',
                cursor: plan.disabled ? 'default' : 'pointer',
              }}
            >
              {loading === plan.id ? 'Redirecting…' : plan.cta}
            </button>
          </div>
        ))}
      </div>

      <div style={styles.faqSection}>
        <h2 style={styles.faqTitle}>Frequently asked questions</h2>
        <div style={styles.faqGrid}>
          {FAQ.map((item) => (
            <div key={item.q} style={styles.faqItem}>
              <h3 style={styles.faqQ}>{item.q}</h3>
              <p style={styles.faqA}>{item.a}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

const FAQ = [
  {
    q: 'Can I cancel anytime?',
    a: 'Yes. Cancel your subscription at any time from the Settings page. You keep Pro/Elite benefits until the end of your billing period.',
  },
  {
    q: 'How does the referral programme work?',
    a: 'Share your unique referral link from Settings. When a friend signs up and upgrades to a paid plan, you earn a $10 account credit and they get $5 off.',
  },
  {
    q: 'What happens to my alerts on the Free plan?',
    a: 'You can have up to 5 active alerts. If you downgrade from a paid plan, alerts above the limit are automatically paused.',
  },
  {
    q: 'Is there a free trial for paid plans?',
    a: 'Pro and Elite plans come with a 7-day free trial. No credit card required to start.',
  },
  {
    q: 'What payment methods are accepted?',
    a: 'We accept all major credit/debit cards (Visa, Mastercard, Amex) via Stripe. Bank transfers available for Business plans.',
  },
  {
    q: 'How do AI price predictions work?',
    a: 'We analyse historical prices for each route, seasonal patterns, and demand signals to predict whether current fares are likely to rise or fall.',
  },
];

const styles = {
  page: { minHeight: '100vh', background: '#f9fafb', paddingBottom: '4rem' },
  hero: { textAlign: 'center', padding: '3rem 1rem 2rem', maxWidth: '700px', margin: '0 auto' },
  heroTitle: { fontSize: '2.5rem', fontWeight: '800', color: '#111827', marginBottom: '1rem' },
  heroSub: { fontSize: '1.125rem', color: '#4b5563', lineHeight: 1.6 },
  globalError: { color: '#dc2626', textAlign: 'center', marginBottom: '1rem', fontSize: '0.9rem' },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
    gap: '1.5rem',
    maxWidth: '1200px',
    margin: '0 auto',
    padding: '0 1rem',
  },
  card: {
    background: '#fff',
    borderRadius: '12px',
    border: '1px solid #e5e7eb',
    padding: '2rem',
    display: 'flex',
    flexDirection: 'column',
    gap: '0.75rem',
    position: 'relative',
    boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
  },
  badge: {
    position: 'absolute',
    top: '-0.75rem',
    left: '50%',
    transform: 'translateX(-50%)',
    color: '#fff',
    fontSize: '0.75rem',
    fontWeight: '700',
    padding: '0.25rem 0.875rem',
    borderRadius: '9999px',
    whiteSpace: 'nowrap',
  },
  planName: { fontSize: '1.5rem', fontWeight: '800', margin: 0 },
  priceRow: { display: 'flex', alignItems: 'baseline', gap: '0.25rem' },
  price: { fontSize: '2.5rem', fontWeight: '800', color: '#111827' },
  period: { fontSize: '1rem', color: '#6b7280' },
  featureList: { listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '0.5rem', flexGrow: 1 },
  featureItem: { fontSize: '0.9rem', color: '#374151', display: 'flex', gap: '0.5rem' },
  check: { color: '#16a34a', fontWeight: '700', flexShrink: 0 },
  cta: {
    marginTop: '1rem',
    padding: '0.75rem',
    border: 'none',
    borderRadius: '8px',
    fontSize: '1rem',
    fontWeight: '700',
    transition: 'opacity 0.15s',
  },
  faqSection: { maxWidth: '900px', margin: '4rem auto 0', padding: '0 1rem' },
  faqTitle: { fontSize: '1.75rem', fontWeight: '800', color: '#111827', textAlign: 'center', marginBottom: '2rem' },
  faqGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))',
    gap: '1.5rem',
  },
  faqItem: { background: '#fff', borderRadius: '8px', padding: '1.25rem', boxShadow: '0 1px 4px rgba(0,0,0,0.07)' },
  faqQ: { fontSize: '1rem', fontWeight: '700', color: '#111827', margin: '0 0 0.5rem' },
  faqA: { fontSize: '0.9rem', color: '#4b5563', margin: 0, lineHeight: 1.6 },
};
