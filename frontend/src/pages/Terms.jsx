import { useNavigate } from 'react-router-dom';

export default function Terms() {
  const navigate = useNavigate();
  return (
    <div style={styles.page}>
      <h1 style={styles.title}>Terms of Service</h1>
      <p style={styles.updated}>Last updated: March 2026</p>

      <section style={styles.section}>
        <h2 style={styles.h2}>1. Acceptance of Terms</h2>
        <p style={styles.p}>By creating an account or using FlightAlertPro ("Service"), you agree to these Terms of Service. If you do not agree, do not use the Service.</p>
      </section>

      <section style={styles.section}>
        <h2 style={styles.h2}>2. Description of Service</h2>
        <p style={styles.p}>FlightAlertPro monitors flight prices on your behalf and notifies you when fares meet your criteria. We are not a travel agency and do not sell flight tickets. All bookings are made directly with the airline or travel provider.</p>
      </section>

      <section style={styles.section}>
        <h2 style={styles.h2}>3. Account Responsibilities</h2>
        <p style={styles.p}>You are responsible for maintaining the security of your account credentials. You must not share your account or use the Service to scrape, resell, or automate queries beyond the rate limits of your plan.</p>
      </section>

      <section style={styles.section}>
        <h2 style={styles.h2}>4. Paid Plans & Billing</h2>
        <p style={styles.p}>Paid subscriptions are billed monthly via Stripe. You may cancel at any time; you will retain access until the end of the billing period. Refunds are offered within 14 days of initial payment on request.</p>
      </section>

      <section style={styles.section}>
        <h2 style={styles.h2}>5. Acceptable Use</h2>
        <p style={styles.p}>You agree not to use the Service for illegal purposes, to harass others, or to interfere with the Service's infrastructure. We reserve the right to suspend accounts that violate these terms.</p>
      </section>

      <section style={styles.section}>
        <h2 style={styles.h2}>6. Disclaimer of Warranties</h2>
        <p style={styles.p}>The Service is provided "as is". We do not guarantee price accuracy, uptime, or that alerts will be delivered within any specific timeframe. Flight prices change rapidly and we are not responsible for missed deals.</p>
      </section>

      <section style={styles.section}>
        <h2 style={styles.h2}>7. Limitation of Liability</h2>
        <p style={styles.p}>To the maximum extent permitted by law, FlightAlertPro's total liability for any claim arising out of the Service shall not exceed the amount you paid in the 12 months preceding the claim.</p>
      </section>

      <section style={styles.section}>
        <h2 style={styles.h2}>8. Changes to Terms</h2>
        <p style={styles.p}>We may update these Terms at any time. Continued use of the Service after changes constitutes acceptance of the updated Terms.</p>
      </section>

      <section style={styles.section}>
        <h2 style={styles.h2}>9. Contact</h2>
        <p style={styles.p}>Legal questions? Email <a href="mailto:legal@flightalertpro.com" style={styles.link}>legal@flightalertpro.com</a>.</p>
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
