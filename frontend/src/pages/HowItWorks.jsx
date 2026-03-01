import { useNavigate } from 'react-router-dom';

const STEPS = [
  {
    number: '01',
    title: 'Search Your Route',
    detail: 'Enter your origin, destination, and preferred travel window. FlightAlertPro instantly queries multiple providers — airlines, OTAs, and aggregators — to show you the best available fares.',
  },
  {
    number: '02',
    title: 'Set a Target Price Alert',
    detail: 'Not happy with today\'s price? Enter the maximum price you\'re willing to pay and hit "Create Alert". We start monitoring your route around the clock, every 15 minutes.',
  },
  {
    number: '03',
    title: 'Get Notified & Book',
    detail: 'The moment the fare drops to or below your target, we send you an instant notification by email (and WhatsApp/Telegram on Pro plans). Click the link to book directly at the deal price before it disappears.',
  },
];

export default function HowItWorks() {
  const navigate = useNavigate();

  return (
    <div style={styles.page}>
      <div style={styles.header}>
        <h1 style={styles.title}>How FlightAlertPro Works</h1>
        <p style={styles.sub}>Three simple steps to never miss a cheap flight again.</p>
      </div>

      <div style={styles.steps}>
        {STEPS.map((step, i) => (
          <div key={i} style={styles.step}>
            <div style={styles.stepNumber}>{step.number}</div>
            <div style={styles.stepContent}>
              <h2 style={styles.stepTitle}>{step.title}</h2>
              <p style={styles.stepDetail}>{step.detail}</p>
            </div>
          </div>
        ))}
      </div>

      <div style={styles.infoSection}>
        <h2 style={styles.infoTitle}>What We Monitor</h2>
        <div style={styles.infoGrid}>
          <div style={styles.infoCard}>
            <span style={styles.infoIcon}>🛫</span>
            <h3 style={styles.infoH3}>Multiple Providers</h3>
            <p style={styles.infoP}>We check fares across Duffel, RapidAPI, and direct airline sources simultaneously.</p>
          </div>
          <div style={styles.infoCard}>
            <span style={styles.infoIcon}>⏱️</span>
            <h3 style={styles.infoH3}>Every 15 Minutes</h3>
            <p style={styles.infoP}>Flight prices change constantly. Our workers poll every 15 minutes so you're always up to date.</p>
          </div>
          <div style={styles.infoCard}>
            <span style={styles.infoIcon}>📊</span>
            <h3 style={styles.infoH3}>Price History</h3>
            <p style={styles.infoP}>Pro and above plans include a price history chart so you can see trends and pick the right time to book.</p>
          </div>
          <div style={styles.infoCard}>
            <span style={styles.infoIcon}>🔔</span>
            <h3 style={styles.infoH3}>Multi-Channel Alerts</h3>
            <p style={styles.infoP}>Get notified via email on all plans. Upgrade to Pro for WhatsApp and Telegram instant push alerts.</p>
          </div>
        </div>
      </div>

      <div style={styles.cta}>
        <h2 style={styles.ctaTitle}>Ready to start saving?</h2>
        <button style={styles.ctaBtn} onClick={() => navigate('/login?signup=1')}>Create a Free Account</button>
        <button style={styles.ctaSecondary} onClick={() => navigate('/pricing')}>View Pricing</button>
      </div>
    </div>
  );
}

const styles = {
  page: { fontFamily: 'system-ui, sans-serif', color: '#111827', paddingBottom: '4rem' },
  header: { textAlign: 'center', padding: '4rem 1rem 2rem', background: 'linear-gradient(135deg, #1d4ed8, #3b82f6)', color: '#fff' },
  title: { fontSize: '2.25rem', fontWeight: '800', margin: '0 0 0.75rem' },
  sub: { color: 'rgba(255,255,255,0.85)', fontSize: '1.1rem', margin: 0 },
  steps: { maxWidth: '800px', margin: '3rem auto 0', padding: '0 1rem', display: 'flex', flexDirection: 'column', gap: '2rem' },
  step: { display: 'flex', gap: '1.5rem', alignItems: 'flex-start' },
  stepNumber: {
    flexShrink: 0,
    width: '3rem', height: '3rem',
    borderRadius: '50%',
    background: '#1d4ed8',
    color: '#fff',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    fontWeight: '800', fontSize: '1rem',
  },
  stepContent: {},
  stepTitle: { fontWeight: '700', fontSize: '1.2rem', color: '#1d4ed8', marginBottom: '0.5rem', marginTop: '0.4rem' },
  stepDetail: { fontSize: '0.95rem', color: '#374151', lineHeight: 1.7, margin: 0 },
  infoSection: { maxWidth: '900px', margin: '4rem auto 0', padding: '0 1rem' },
  infoTitle: { textAlign: 'center', fontSize: '1.5rem', fontWeight: '800', color: '#1d4ed8', marginBottom: '1.5rem' },
  infoGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1.5rem' },
  infoCard: { background: '#f9fafb', borderRadius: '12px', padding: '1.5rem', textAlign: 'center' },
  infoIcon: { fontSize: '2rem' },
  infoH3: { fontWeight: '700', fontSize: '1rem', color: '#1d4ed8', margin: '0.5rem 0' },
  infoP: { fontSize: '0.875rem', color: '#6b7280', lineHeight: 1.6, margin: 0 },
  cta: { textAlign: 'center', padding: '4rem 1rem 0', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1rem' },
  ctaTitle: { fontSize: '1.75rem', fontWeight: '800', color: '#1d4ed8', margin: '0 0 0.5rem' },
  ctaBtn: {
    padding: '0.8rem 2.5rem', background: '#1d4ed8', color: '#fff',
    border: 'none', borderRadius: '8px', fontWeight: '700', fontSize: '1.05rem', cursor: 'pointer',
  },
  ctaSecondary: {
    padding: '0.8rem 2.5rem', background: '#fff', color: '#1d4ed8',
    border: '2px solid #1d4ed8', borderRadius: '8px', fontWeight: '700', fontSize: '1.05rem', cursor: 'pointer',
  },
};
