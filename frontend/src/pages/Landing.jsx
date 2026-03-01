import { useNavigate } from 'react-router-dom';

const STEPS = [
  { icon: '🔍', title: 'Search Flights', desc: 'Enter your route and travel dates to see live fares from multiple providers.' },
  { icon: '🔔', title: 'Set an Alert', desc: 'Choose a target price. We monitor 24/7 and notify you the moment fares drop.' },
  { icon: '✈️', title: 'Book & Save', desc: 'Click your alert to book directly with the airline or travel agent at the low price.' },
];

const SOCIAL_PROOF = [
  { quote: 'Saved $340 on a round trip to Tokyo!', author: 'Alex M.' },
  { quote: 'Set the alert and forgot about it. Got an email when fares dropped 40%.', author: 'Priya S.' },
  { quote: 'The best flight price tracker I\'ve used.', author: 'James K.' },
];

export default function Landing() {
  const navigate = useNavigate();

  return (
    <div style={styles.page}>
      {/* Hero */}
      <section style={styles.hero}>
        <div style={styles.heroInner}>
          <h1 style={styles.heroTitle}>Never Overpay for a Flight Again</h1>
          <p style={styles.heroSub}>
            Set a target price. We watch fares 24/7 across all major providers and alert you the moment your route drops to budget.
          </p>
          <div style={styles.heroActions}>
            <button style={styles.ctaPrimary} onClick={() => navigate('/login?signup=1')}>Get Started Free</button>
            <button style={styles.ctaSecondary} onClick={() => navigate('/how-it-works')}>See How It Works</button>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section style={styles.section}>
        <h2 style={styles.sectionTitle}>How It Works</h2>
        <div style={styles.stepsGrid}>
          {STEPS.map((s, i) => (
            <div key={i} style={styles.stepCard}>
              <div style={styles.stepIcon}>{s.icon}</div>
              <h3 style={styles.stepTitle}>{s.title}</h3>
              <p style={styles.stepDesc}>{s.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Social proof */}
      <section style={{ ...styles.section, background: '#f0f7ff' }}>
        <h2 style={styles.sectionTitle}>Loved by Travellers</h2>
        <div style={styles.proofGrid}>
          {SOCIAL_PROOF.map((p, i) => (
            <div key={i} style={styles.proofCard}>
              <p style={styles.proofQuote}>"{p.quote}"</p>
              <p style={styles.proofAuthor}>— {p.author}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Pricing teaser */}
      <section style={styles.section}>
        <h2 style={styles.sectionTitle}>Simple, Transparent Pricing</h2>
        <p style={styles.sectionSub}>Start free. Upgrade any time. No credit card needed.</p>
        <div style={styles.pricingTeaser}>
          <div style={styles.teaserCard}>
            <span style={styles.teaserPlan}>Free</span>
            <span style={styles.teaserPrice}>$0/mo</span>
            <span style={styles.teaserHint}>3 active alerts</span>
          </div>
          <div style={{ ...styles.teaserCard, ...styles.teaserHighlight }}>
            <span style={styles.teaserPlan}>Pro</span>
            <span style={styles.teaserPrice}>$9/mo</span>
            <span style={styles.teaserHint}>20 active alerts</span>
          </div>
          <div style={styles.teaserCard}>
            <span style={styles.teaserPlan}>Elite</span>
            <span style={styles.teaserPrice}>$29/mo</span>
            <span style={styles.teaserHint}>50 active alerts</span>
          </div>
        </div>
        <div style={styles.teaserActions}>
          <button style={styles.ctaPrimary} onClick={() => navigate('/pricing')}>See Full Pricing</button>
          <button style={styles.ctaSecondary} onClick={() => navigate('/login?signup=1')}>Start Free</button>
        </div>
      </section>

      {/* Footer links */}
      <footer style={styles.footer}>
        <p style={styles.footerCopy}>© {new Date().getFullYear()} FlightAlertPro. All rights reserved.</p>
        <div style={styles.footerLinks}>
          <button style={styles.footerLink} onClick={() => navigate('/privacy')}>Privacy Policy</button>
          <button style={styles.footerLink} onClick={() => navigate('/terms')}>Terms of Service</button>
          <button style={styles.footerLink} onClick={() => navigate('/how-it-works')}>How It Works</button>
        </div>
      </footer>
    </div>
  );
}

const styles = {
  page: { fontFamily: 'system-ui, sans-serif', color: '#111827' },
  hero: {
    background: 'linear-gradient(135deg, #1d4ed8 0%, #3b82f6 100%)',
    color: '#fff',
    padding: '5rem 1rem',
  },
  heroInner: { maxWidth: '700px', margin: '0 auto', textAlign: 'center' },
  heroTitle: { fontSize: '2.5rem', fontWeight: '800', margin: '0 0 1rem', lineHeight: 1.2 },
  heroSub: { fontSize: '1.125rem', opacity: 0.9, marginBottom: '2rem', lineHeight: 1.6 },
  heroActions: { display: 'flex', gap: '1rem', justifyContent: 'center', flexWrap: 'wrap' },
  ctaPrimary: {
    padding: '0.8rem 2rem',
    background: '#fff',
    color: '#1d4ed8',
    border: 'none',
    borderRadius: '8px',
    fontWeight: '700',
    fontSize: '1rem',
    cursor: 'pointer',
  },
  ctaSecondary: {
    padding: '0.8rem 2rem',
    background: 'transparent',
    color: '#fff',
    border: '2px solid rgba(255,255,255,0.7)',
    borderRadius: '8px',
    fontWeight: '700',
    fontSize: '1rem',
    cursor: 'pointer',
  },
  section: { padding: '4rem 1rem', maxWidth: '100%' },
  sectionTitle: { textAlign: 'center', fontSize: '1.75rem', fontWeight: '800', marginBottom: '0.5rem', color: '#1d4ed8' },
  sectionSub: { textAlign: 'center', color: '#6b7280', marginBottom: '2rem' },
  stepsGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1.5rem', maxWidth: '900px', margin: '2rem auto 0' },
  stepCard: { background: '#fff', borderRadius: '12px', padding: '2rem', boxShadow: '0 2px 12px rgba(0,0,0,0.07)', textAlign: 'center' },
  stepIcon: { fontSize: '2.5rem', marginBottom: '0.75rem' },
  stepTitle: { fontWeight: '700', fontSize: '1.1rem', marginBottom: '0.5rem', color: '#1d4ed8' },
  stepDesc: { fontSize: '0.9rem', color: '#6b7280', lineHeight: 1.6 },
  proofGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1.5rem', maxWidth: '900px', margin: '2rem auto 0' },
  proofCard: { background: '#fff', borderRadius: '12px', padding: '1.5rem', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' },
  proofQuote: { fontSize: '0.95rem', color: '#374151', fontStyle: 'italic', marginBottom: '0.75rem', lineHeight: 1.6 },
  proofAuthor: { fontSize: '0.875rem', fontWeight: '700', color: '#1d4ed8', margin: 0 },
  pricingTeaser: { display: 'flex', gap: '1rem', justifyContent: 'center', flexWrap: 'wrap', maxWidth: '700px', margin: '2rem auto 1.5rem' },
  teaserCard: {
    display: 'flex', flexDirection: 'column', alignItems: 'center',
    background: '#f9fafb', border: '1px solid #e5e7eb', borderRadius: '12px',
    padding: '1.5rem 2rem', minWidth: '160px', gap: '0.25rem',
  },
  teaserHighlight: { background: '#1d4ed8', color: '#fff', border: 'none' },
  teaserPlan: { fontWeight: '800', fontSize: '1.1rem' },
  teaserPrice: { fontSize: '1.5rem', fontWeight: '700' },
  teaserHint: { fontSize: '0.8rem', opacity: 0.75 },
  teaserActions: { display: 'flex', gap: '1rem', justifyContent: 'center', flexWrap: 'wrap', marginTop: '0.5rem' },
  footer: { background: '#1f2937', color: '#9ca3af', padding: '2rem 1rem', textAlign: 'center' },
  footerCopy: { margin: '0 0 0.75rem' },
  footerLinks: { display: 'flex', gap: '1.5rem', justifyContent: 'center', flexWrap: 'wrap' },
  footerLink: { background: 'none', border: 'none', color: '#9ca3af', cursor: 'pointer', fontSize: '0.875rem', textDecoration: 'underline' },
};
