import { useNavigate } from 'react-router-dom';

const PLANS = [
  {
    key: 'free',
    label: 'Free',
    price: '$0',
    period: 'forever',
    color: '#6b7280',
    features: [
      '3 active price alerts',
      '20 flight searches / day',
      '5 notifications / day',
      'Email notifications',
    ],
    cta: 'Get Started',
    ctaAction: 'signup',
  },
  {
    key: 'pro',
    label: 'Pro',
    price: '$9',
    period: 'per month',
    color: '#1d4ed8',
    highlight: true,
    features: [
      '20 active price alerts',
      '200 flight searches / day',
      '50 notifications / day',
      'Email + WhatsApp alerts',
      'Priority processing',
    ],
    cta: 'Start Pro',
    ctaAction: 'signup',
  },
  {
    key: 'elite',
    label: 'Elite',
    price: '$29',
    period: 'per month',
    color: '#7c3aed',
    features: [
      '50 active price alerts',
      '500 flight searches / day',
      '100 notifications / day',
      'All channels',
      'Price history & trends',
      'Priority processing',
    ],
    cta: 'Start Elite',
    ctaAction: 'signup',
  },
  {
    key: 'business',
    label: 'Business',
    price: '$99',
    period: 'per month',
    color: '#b45309',
    features: [
      '200 active price alerts',
      '2,000 flight searches / day',
      '500 notifications / day',
      'All channels',
      'Price history & trends',
      'Dedicated support',
    ],
    cta: 'Contact Sales',
    ctaAction: 'signup',
  },
];

export default function Pricing() {
  const navigate = useNavigate();

  return (
    <div style={styles.page}>
      <div style={styles.header}>
        <h1 style={styles.title}>Simple, Transparent Pricing</h1>
        <p style={styles.sub}>Start free and upgrade as your travel needs grow. No hidden fees.</p>
      </div>

      <div style={styles.grid}>
        {PLANS.map((plan) => (
          <div
            key={plan.key}
            style={{
              ...styles.card,
              ...(plan.highlight ? styles.cardHighlight : {}),
              borderTop: `4px solid ${plan.color}`,
            }}
          >
            {plan.highlight && <div style={styles.popularBadge}>Most Popular</div>}
            <div style={{ ...styles.planLabel, color: plan.color }}>{plan.label}</div>
            <div style={styles.priceRow}>
              <span style={styles.price}>{plan.price}</span>
              <span style={styles.period}> / {plan.period}</span>
            </div>
            <ul style={styles.features}>
              {plan.features.map((f) => (
                <li key={f} style={styles.featureItem}>✓ {f}</li>
              ))}
            </ul>
            <button
              style={{ ...styles.cta, background: plan.color }}
              onClick={() => navigate('/login?signup=1')}
            >
              {plan.cta}
            </button>
          </div>
        ))}
      </div>

      <p style={styles.note}>
        All plans include a 14-day money-back guarantee. Cancel any time.
      </p>

      <div style={styles.faqSection}>
        <h2 style={styles.faqTitle}>Frequently Asked Questions</h2>
        <div style={styles.faqGrid}>
          <div style={styles.faqItem}>
            <h3 style={styles.faqQ}>Do I need a credit card to sign up?</h3>
            <p style={styles.faqA}>No. The Free plan requires no credit card. You only need to pay when you upgrade.</p>
          </div>
          <div style={styles.faqItem}>
            <h3 style={styles.faqQ}>Can I cancel my subscription?</h3>
            <p style={styles.faqA}>Yes, you can cancel at any time from your billing dashboard. You'll keep access until the end of your billing period.</p>
          </div>
          <div style={styles.faqItem}>
            <h3 style={styles.faqQ}>What counts as an active alert?</h3>
            <p style={styles.faqA}>Any alert you've created and left enabled. You can deactivate alerts you no longer need to free up slots.</p>
          </div>
          <div style={styles.faqItem}>
            <h3 style={styles.faqQ}>Which notification channels are supported?</h3>
            <p style={styles.faqA}>Email on all plans. WhatsApp and Telegram on Pro and above.</p>
          </div>
        </div>
      </div>
    </div>
  );
}

const styles = {
  page: { fontFamily: 'system-ui, sans-serif', color: '#111827', paddingBottom: '4rem' },
  header: { textAlign: 'center', padding: '4rem 1rem 2rem' },
  title: { fontSize: '2.25rem', fontWeight: '800', color: '#1d4ed8', margin: '0 0 0.75rem' },
  sub: { color: '#6b7280', fontSize: '1.1rem', margin: 0 },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
    gap: '1.5rem',
    maxWidth: '1100px',
    margin: '0 auto',
    padding: '0 1rem',
  },
  card: {
    background: '#fff',
    borderRadius: '12px',
    padding: '2rem',
    boxShadow: '0 2px 12px rgba(0,0,0,0.08)',
    display: 'flex',
    flexDirection: 'column',
    position: 'relative',
  },
  cardHighlight: {
    boxShadow: '0 4px 24px rgba(29,78,216,0.18)',
    transform: 'scale(1.03)',
  },
  popularBadge: {
    position: 'absolute',
    top: '-0.75rem',
    left: '50%',
    transform: 'translateX(-50%)',
    background: '#1d4ed8',
    color: '#fff',
    fontSize: '0.75rem',
    fontWeight: '700',
    padding: '0.25rem 0.75rem',
    borderRadius: '999px',
    whiteSpace: 'nowrap',
  },
  planLabel: { fontSize: '1.2rem', fontWeight: '800', marginBottom: '0.5rem' },
  priceRow: { marginBottom: '1.5rem' },
  price: { fontSize: '2.5rem', fontWeight: '800', color: '#111827' },
  period: { fontSize: '0.9rem', color: '#6b7280' },
  features: { listStyle: 'none', padding: 0, margin: '0 0 1.5rem', flex: 1, display: 'flex', flexDirection: 'column', gap: '0.4rem' },
  featureItem: { fontSize: '0.875rem', color: '#374151' },
  cta: {
    display: 'block',
    width: '100%',
    padding: '0.75rem',
    color: '#fff',
    border: 'none',
    borderRadius: '8px',
    fontWeight: '700',
    fontSize: '1rem',
    cursor: 'pointer',
    marginTop: 'auto',
  },
  note: { textAlign: 'center', color: '#6b7280', fontSize: '0.875rem', marginTop: '2rem' },
  faqSection: { maxWidth: '800px', margin: '3rem auto 0', padding: '0 1rem' },
  faqTitle: { textAlign: 'center', fontSize: '1.5rem', fontWeight: '800', color: '#1d4ed8', marginBottom: '1.5rem' },
  faqGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1.5rem' },
  faqItem: { background: '#f9fafb', borderRadius: '8px', padding: '1.25rem' },
  faqQ: { fontWeight: '700', fontSize: '0.95rem', color: '#111827', marginBottom: '0.5rem', marginTop: 0 },
  faqA: { fontSize: '0.875rem', color: '#6b7280', margin: 0, lineHeight: 1.6 },
};
