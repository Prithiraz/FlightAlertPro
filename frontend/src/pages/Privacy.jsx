import { useNavigate } from 'react-router-dom';

export default function Privacy() {
  const navigate = useNavigate();
  return (
    <div style={styles.page}>
      <h1 style={styles.title}>Privacy Policy</h1>
      <p style={styles.updated}>Last updated: March 2026</p>

      <section style={styles.section}>
        <h2 style={styles.h2}>1. Information We Collect</h2>
        <p style={styles.p}>We collect information you provide directly when you create an account (email address, password) and information generated through your use of the service (flight searches, alert configurations, notification preferences).</p>
      </section>

      <section style={styles.section}>
        <h2 style={styles.h2}>2. How We Use Your Information</h2>
        <p style={styles.p}>We use your information to provide, operate, and improve FlightAlertPro, including sending flight price alerts and product-related emails. We do not sell your personal data to third parties.</p>
      </section>

      <section style={styles.section}>
        <h2 style={styles.h2}>3. Data Storage & Security</h2>
        <p style={styles.p}>Your data is stored securely using Supabase (PostgreSQL) with row-level security policies. We use HTTPS for all data in transit and access controls to limit internal exposure.</p>
      </section>

      <section style={styles.section}>
        <h2 style={styles.h2}>4. Cookies & Analytics</h2>
        <p style={styles.p}>We use minimal functional cookies required to maintain your login session. We may log anonymised events (page views, feature usage) to improve the product. No third-party advertising cookies are set.</p>
      </section>

      <section style={styles.section}>
        <h2 style={styles.h2}>5. Third-Party Services</h2>
        <p style={styles.p}>We integrate with Stripe (payments), Supabase (database & auth), and optional messaging providers (WhatsApp via YCloud, Telegram). Each provider's own privacy policy applies to data they process on our behalf.</p>
      </section>

      <section style={styles.section}>
        <h2 style={styles.h2}>6. Your Rights</h2>
        <p style={styles.p}>You may request access to, correction of, or deletion of your personal data at any time by emailing us. Account deletion removes all personal data within 30 days.</p>
      </section>

      <section style={styles.section}>
        <h2 style={styles.h2}>7. Contact</h2>
        <p style={styles.p}>Questions? Email us at <a href="mailto:privacy@flightalertpro.com" style={styles.link}>privacy@flightalertpro.com</a>.</p>
      </section>

      <button style={styles.back} onClick={() => navigate(-1)}>← Back</button>
    </div>
  );
}

const styles = {
  page: { maxWidth: '760px', margin: '0 auto', padding: '3rem 1.5rem', fontFamily: 'system-ui, sans-serif', color: '#111827' },
  title: { fontSize: '2rem', fontWeight: '800', color: '#1d4ed8', marginBottom: '0.25rem' },
  updated: { color: '#9ca3af', fontSize: '0.875rem', marginBottom: '2rem' },
  section: { marginBottom: '1.75rem' },
  h2: { fontWeight: '700', fontSize: '1.1rem', color: '#374151', marginBottom: '0.5rem' },
  p: { fontSize: '0.95rem', lineHeight: 1.7, color: '#374151', margin: 0 },
  link: { color: '#1d4ed8' },
  back: { marginTop: '2rem', background: 'none', border: '1px solid #d1d5db', borderRadius: '6px', padding: '0.5rem 1rem', cursor: 'pointer', fontSize: '0.875rem', color: '#374151' },
};
