import { useNavigate } from 'react-router-dom';
import { useAuth } from '../App';
import { apiFetch } from '../lib/api';

const FEATURES_FREE = [
  '1 Active Alert',
  'Email Notifications',
];

const FEATURES_PRO = [
  'Unlimited Alerts',
  'Telegram Notifications',
  'Instant Background Checking',
  'Priority Support',
];

export default function Pricing() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const handleUpgrade = async () => {
    if (!user?.email) {
      navigate('/');
      return;
    }

    const successUrl = `${window.location.origin}/dashboard?upgraded=true`;
    const cancelUrl = `${window.location.origin}/pricing`;

    try {
      const params = new URLSearchParams({
        user_email: user.email,
        success_url: successUrl,
        cancel_url: cancelUrl,
        plan: 'pro',
      });

      const data = await apiFetch(`/api/payments/checkout?${params.toString()}`, {
        method: 'POST',
      });

      if (data?.url) {
        window.location.href = data.url;
      } else {
        alert('Checkout URL not received. Please try again.');
      }
    } catch (err) {
      alert(err.message || 'Unable to start checkout. Please try again.');
    }
  };

  const isPro = user?.user_metadata?.is_pro || user?.app_metadata?.is_pro;

  return (
    <div style={styles.page}>
      <div style={styles.hero}>
        <h1 style={styles.heroTitle}>Simple, Transparent Pricing</h1>
        <p style={styles.heroSub}>
          Start for free and upgrade when you need more.
        </p>
      </div>

      <div style={styles.cards}>
        {/* Free Tier */}
        <div style={styles.card}>
          <div style={styles.cardHeader}>
            <h2 style={styles.planName}>Free</h2>
            <div style={styles.price}>
              <span style={styles.priceAmount}>$0</span>
              <span style={styles.pricePeriod}>/month</span>
            </div>
          </div>
          <ul style={styles.featureList}>
            {FEATURES_FREE.map((f) => (
              <li key={f} style={styles.featureItem}>
                <span style={styles.checkIcon}>✓</span> {f}
              </li>
            ))}
          </ul>
          <button style={styles.btnOutline} disabled>
            Current Plan
          </button>
        </div>

        {/* Pro Tier */}
        <div style={{ ...styles.card, ...styles.cardPro }}>
          <div style={styles.popularBadge}>Most Popular</div>
          <div style={styles.cardHeader}>
            <h2 style={{ ...styles.planName, color: '#fff' }}>Pro</h2>
            <div style={styles.price}>
              <span style={{ ...styles.priceAmount, color: '#fff' }}>$9</span>
              <span style={{ ...styles.pricePeriod, color: '#bfdbfe' }}>/month</span>
            </div>
          </div>
          <ul style={styles.featureList}>
            {FEATURES_PRO.map((f) => (
              <li key={f} style={{ ...styles.featureItem, color: '#e0f2fe' }}>
                <span style={{ ...styles.checkIcon, color: '#bfdbfe' }}>✓</span> {f}
              </li>
            ))}
          </ul>
          {isPro ? (
            <button style={styles.btnProDisabled} disabled>
              You're on Pro ✓
            </button>
          ) : (
            <button style={styles.btnPro} onClick={handleUpgrade}>
              Upgrade to Pro
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

const styles = {
  page: {
    maxWidth: '900px',
    margin: '2rem auto',
    padding: '0 1rem',
    fontFamily: 'inherit',
  },
  hero: {
    textAlign: 'center',
    marginBottom: '3rem',
  },
  heroTitle: {
    fontSize: '2rem',
    fontWeight: '800',
    color: '#1d4ed8',
    marginBottom: '0.5rem',
  },
  heroSub: {
    fontSize: '1.1rem',
    color: '#6b7280',
  },
  cards: {
    display: 'flex',
    gap: '2rem',
    justifyContent: 'center',
    flexWrap: 'wrap',
  },
  card: {
    background: '#fff',
    borderRadius: '12px',
    boxShadow: '0 4px 16px rgba(0,0,0,0.10)',
    padding: '2rem',
    flex: '1',
    minWidth: '260px',
    maxWidth: '340px',
    display: 'flex',
    flexDirection: 'column',
    gap: '1.25rem',
    position: 'relative',
  },
  cardPro: {
    background: 'linear-gradient(135deg, #1d4ed8 0%, #2563eb 100%)',
    boxShadow: '0 8px 32px rgba(29,78,216,0.35)',
  },
  popularBadge: {
    position: 'absolute',
    top: '-14px',
    left: '50%',
    transform: 'translateX(-50%)',
    background: '#f59e0b',
    color: '#fff',
    fontSize: '0.75rem',
    fontWeight: '700',
    padding: '0.25rem 0.875rem',
    borderRadius: '99px',
    letterSpacing: '0.05em',
    textTransform: 'uppercase',
  },
  cardHeader: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.25rem',
  },
  planName: {
    fontSize: '1.25rem',
    fontWeight: '700',
    color: '#1d4ed8',
    margin: 0,
  },
  price: {
    display: 'flex',
    alignItems: 'baseline',
    gap: '0.25rem',
  },
  priceAmount: {
    fontSize: '2.5rem',
    fontWeight: '800',
    color: '#111827',
  },
  pricePeriod: {
    fontSize: '1rem',
    color: '#6b7280',
  },
  featureList: {
    listStyle: 'none',
    margin: 0,
    padding: 0,
    display: 'flex',
    flexDirection: 'column',
    gap: '0.625rem',
    flex: 1,
  },
  featureItem: {
    fontSize: '0.95rem',
    color: '#374151',
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
  },
  checkIcon: {
    color: '#16a34a',
    fontWeight: '700',
  },
  btnOutline: {
    padding: '0.625rem 1.25rem',
    border: '1px solid #d1d5db',
    borderRadius: '8px',
    background: '#f9fafb',
    color: '#6b7280',
    fontSize: '0.95rem',
    fontWeight: '600',
    cursor: 'not-allowed',
  },
  btnPro: {
    padding: '0.75rem 1.25rem',
    border: 'none',
    borderRadius: '8px',
    background: '#fff',
    color: '#1d4ed8',
    fontSize: '1rem',
    fontWeight: '700',
    cursor: 'pointer',
    boxShadow: '0 2px 8px rgba(0,0,0,0.10)',
    transition: 'opacity 0.15s',
  },
  btnProDisabled: {
    padding: '0.75rem 1.25rem',
    border: 'none',
    borderRadius: '8px',
    background: 'rgba(255,255,255,0.2)',
    color: '#fff',
    fontSize: '1rem',
    fontWeight: '700',
    cursor: 'not-allowed',
  },
};
