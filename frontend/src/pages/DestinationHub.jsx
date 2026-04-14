import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useAuth } from '../App';
import { getTripHub } from '../lib/api';

function CountdownTimer({ departureDate }) {
  const [days, setDays] = useState(null);

  useEffect(() => {
    if (!departureDate) return;
    const calc = () => {
      const dep = new Date(departureDate + 'T00:00:00');
      const now = new Date();
      const diff = Math.ceil((dep - now) / (1000 * 60 * 60 * 24));
      setDays(Math.max(0, diff));
    };
    calc();
    const timer = setInterval(calc, 60000);
    return () => clearInterval(timer);
  }, [departureDate]);

  if (days === null) return null;
  if (days === 0) return <span>✈️ Departing today!</span>;
  return <span>⏳ {days} day{days !== 1 ? 's' : ''} to go</span>;
}

export default function DestinationHub() {
  const { alert_id } = useParams();
  const { user } = useAuth();
  const [hub, setHub] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!user?.email || !alert_id) return;
    getTripHub(alert_id, user.email)
      .then((data) => setHub(data))
      .catch((err) => setError(err.message || 'Failed to load Destination Hub'))
      .finally(() => setLoading(false));
  }, [alert_id, user?.email]);

  if (loading) {
    return (
      <div style={styles.page}>
        <div style={styles.loadingWrap}>
          <p style={styles.loadingText}>✈️ Loading your Destination Hub…</p>
        </div>
      </div>
    );
  }

  if (error || !hub) {
    return (
      <div style={styles.page}>
        <div style={styles.errorWrap}>
          <p style={styles.errorText}>{error || 'Hub data unavailable.'}</p>
          <Link to="/dashboard" style={styles.backLink}>← Back to Dashboard</Link>
        </div>
      </div>
    );
  }

  const {
    destination_city,
    destination_country,
    origin_city,
    from_iata,
    to_iata,
    departure_date,
    airline,
    purchase_price,
    passport_nationality,
    intel,
    esim_affiliate_url,
  } = hub;

  const heroImage = `https://source.unsplash.com/1600x400/?${encodeURIComponent(destination_city)},city`;
  const packingTips = Array.isArray(intel?.packing_tips) ? intel.packing_tips : [];

  return (
    <div style={styles.page}>
      {/* Hero Header */}
      <div style={{ ...styles.hero, backgroundImage: `url(${heroImage})` }}>
        <div style={styles.heroOverlay}>
          <h1 style={styles.heroTitle}>🌍 {destination_city}</h1>
          <p style={styles.heroSub}>
            {from_iata} → {to_iata}
            {departure_date && ` · ${departure_date}`}
          </p>
          <p style={styles.heroCountdown}>
            <CountdownTimer departureDate={departure_date} />
          </p>
        </div>
      </div>

      <div style={styles.content}>
        <Link to="/dashboard" style={styles.backLink}>← Back to Dashboard</Link>

        <div style={styles.grid}>
          {/* Card 1: AI Concierge */}
          <div style={styles.card}>
            <h2 style={styles.cardTitle}>🤖 AI Concierge</h2>
            <p style={styles.cardSubtitle}>
              Personalised for a <strong>{passport_nationality}</strong> passport holder travelling to{' '}
              <strong>{destination_country}</strong>.
            </p>

            <div style={styles.intelSection}>
              <h3 style={styles.intelHeading}>📋 Visa Requirements</h3>
              <p style={styles.intelText}>{intel?.visa_requirements || '—'}</p>
            </div>

            <div style={styles.intelSection}>
              <h3 style={styles.intelHeading}>🌤 Weather Expectation</h3>
              <p style={styles.intelText}>{intel?.weather_expectation || '—'}</p>
            </div>

            <div style={styles.intelSection}>
              <h3 style={styles.intelHeading}>🎒 Packing Tips</h3>
              {packingTips.length > 0 ? (
                <ul style={styles.tipList}>
                  {packingTips.map((tip, i) => (
                    <li key={i} style={styles.tipItem}>✓ {tip}</li>
                  ))}
                </ul>
              ) : (
                <p style={styles.intelText}>No packing tips available.</p>
              )}
            </div>
          </div>

          {/* Card 2: eSIM Upsell */}
          <div style={{ ...styles.card, ...styles.esimCard }}>
            <h2 style={styles.cardTitle}>📱 Stay Connected</h2>
            <p style={styles.esimText}>
              Avoid expensive roaming charges in <strong>{destination_city}</strong>.
              Get a local eSIM before you fly.
            </p>
            <a
              href={esim_affiliate_url}
              target="_blank"
              rel="noopener noreferrer"
              style={styles.esimButton}
            >
              Get your {destination_city} eSIM now →
            </a>
            <p style={styles.esimDisclaimer}>Powered by Airalo · Affiliate link</p>
          </div>

          {/* Card 3: Flight Details */}
          <div style={{ ...styles.card, ...styles.flightCard }}>
            <h2 style={styles.cardTitle}>✈️ Flight Details</h2>
            <div style={styles.flightRow}>
              <div style={styles.flightIata}>{from_iata}</div>
              <div style={styles.flightArrow}>→</div>
              <div style={styles.flightIata}>{to_iata}</div>
            </div>
            <div style={styles.flightMeta}>
              {origin_city} → {destination_city}
            </div>
            {departure_date && (
              <div style={styles.flightDetail}>
                <span style={styles.flightLabel}>Departure</span>
                <span>{departure_date}</span>
              </div>
            )}
            {airline && (
              <div style={styles.flightDetail}>
                <span style={styles.flightLabel}>Airline</span>
                <span>{airline}</span>
              </div>
            )}
            {purchase_price && (
              <div style={styles.flightDetail}>
                <span style={styles.flightLabel}>Price Paid</span>
                <span style={{ fontWeight: 700 }}>${Number(purchase_price).toFixed(2)}</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

const styles = {
  page: { minHeight: '100vh', background: '#f3f4f6' },
  loadingWrap: { display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' },
  loadingText: { fontSize: '1.25rem', color: '#6b7280' },
  errorWrap: { maxWidth: '600px', margin: '4rem auto', textAlign: 'center', padding: '0 1rem' },
  errorText: { color: '#dc2626', fontSize: '1rem', marginBottom: '1rem' },
  hero: {
    width: '100%',
    height: '260px',
    backgroundSize: 'cover',
    backgroundPosition: 'center',
    position: 'relative',
  },
  heroOverlay: {
    position: 'absolute',
    inset: 0,
    background: 'linear-gradient(to bottom, rgba(0,0,0,0.35), rgba(0,0,0,0.65))',
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'center',
    alignItems: 'center',
    color: '#fff',
    textAlign: 'center',
    padding: '1rem',
  },
  heroTitle: { fontSize: '2.25rem', fontWeight: 800, margin: '0 0 0.35rem', textShadow: '0 2px 8px rgba(0,0,0,0.4)' },
  heroSub: { fontSize: '1rem', opacity: 0.9, margin: '0 0 0.5rem' },
  heroCountdown: { fontSize: '1.1rem', fontWeight: 600, background: 'rgba(255,255,255,0.15)', padding: '0.3rem 0.9rem', borderRadius: '999px' },
  content: { maxWidth: '1100px', margin: '1.5rem auto', padding: '0 1rem' },
  backLink: { display: 'inline-block', color: '#1d4ed8', fontSize: '0.875rem', marginBottom: '1rem', textDecoration: 'none', fontWeight: 500 },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '1.25rem' },
  card: {
    background: '#fff',
    borderRadius: '12px',
    padding: '1.5rem',
    boxShadow: '0 2px 12px rgba(0,0,0,0.08)',
  },
  cardTitle: { fontSize: '1.1rem', fontWeight: 700, marginBottom: '0.75rem', color: '#111827' },
  cardSubtitle: { fontSize: '0.85rem', color: '#6b7280', marginBottom: '1rem' },
  intelSection: { marginBottom: '1rem' },
  intelHeading: { fontSize: '0.875rem', fontWeight: 700, color: '#374151', marginBottom: '0.25rem' },
  intelText: { fontSize: '0.875rem', color: '#4b5563', lineHeight: 1.6 },
  tipList: { listStyle: 'none', padding: 0, margin: 0 },
  tipItem: { fontSize: '0.875rem', color: '#4b5563', lineHeight: 1.8 },
  esimCard: { background: 'linear-gradient(135deg, #1d4ed8 0%, #3b82f6 100%)', color: '#fff' },
  esimText: { fontSize: '0.9rem', color: 'rgba(255,255,255,0.9)', marginBottom: '1.25rem', lineHeight: 1.6 },
  esimButton: {
    display: 'inline-block',
    background: '#fff',
    color: '#1d4ed8',
    fontWeight: 700,
    fontSize: '0.9rem',
    padding: '0.65rem 1.25rem',
    borderRadius: '8px',
    textDecoration: 'none',
    marginBottom: '1rem',
  },
  esimDisclaimer: { fontSize: '0.75rem', color: 'rgba(255,255,255,0.6)', margin: 0 },
  flightCard: { background: '#f0f9ff', border: '1px solid #bae6fd' },
  flightRow: { display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.25rem' },
  flightIata: { fontSize: '2rem', fontWeight: 800, color: '#0369a1' },
  flightArrow: { fontSize: '1.5rem', color: '#94a3b8' },
  flightMeta: { fontSize: '0.85rem', color: '#64748b', marginBottom: '1rem' },
  flightDetail: { display: 'flex', justifyContent: 'space-between', fontSize: '0.875rem', color: '#374151', padding: '0.4rem 0', borderTop: '1px solid #e0f2fe' },
  flightLabel: { fontWeight: 600 },
};
