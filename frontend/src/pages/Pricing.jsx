import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../App';
import { supabase } from '../lib/supabase';

const TIERS = [
  {
    id: 'free',
    name: 'Free',
    price: 0,
    color: '#374151',
    background: '#fff',
    cardStyle: {},
    features: [
      '1 Active Alert',
      'Email Notifications',
    ],
    cta: 'Current Plan',
    ctaDisabled: true,
  },
  {
    id: 'pro',
    name: 'Pro',
    price: 9,
    color: '#1d4ed8',
    background: '#eff6ff',
    cardStyle: { borderColor: '#93c5fd' },
    features: [
      '5 Active Alerts',
      'Email & Telegram Notifications',
      'Instant Background Checking',
      'Priority Support',
    ],
    cta: 'Upgrade to Pro',
    badge: null,
  },
  {
    id: 'elite',
    name: 'Elite',
    price: 19,
    color: '#fff',
    background: 'linear-gradient(135deg, #1d4ed8 0%, #2563eb 100%)',
    cardStyle: { boxShadow: '0 8px 32px rgba(29,78,216,0.35)' },
    features: [
      '20 Active Alerts',
      'Email & Telegram Notifications',
      'AI Flight Insights',
      'Instant Background Checking',
      'Priority Support',
    ],
    buttonText: 'Upgrade to Elite',
    cta: 'Upgrade to Elite',
    badge: 'Most Popular',
  },
  {
    id: 'business',
    name: 'Business',
    price: 39,
    color: '#fff',
    background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)',
    cardStyle: { boxShadow: '0 8px 32px rgba(0,0,0,0.35)' },
    features: [
      'Unlimited Alerts',
      'All Notification Channels',
      'AI Flight Insights',
      'Instant Background Checking',
      'Dedicated Support',
      'Team Access',
    ],
    buttonText: 'Upgrade to Business',
    cta: 'Upgrade to Business',
    badge: null,
  },
];

export default function Pricing() {
  const { user, subscriptionTier } = useAuth();
  const navigate = useNavigate();
  const [checkoutPlan, setCheckoutPlan] = useState(null);
  const [, setIsLoading] = useState(false);

  const handleCheckout = async (planId) => {
    try {
      console.log("1. Stripe button clicked for plan:", planId);
      setCheckoutPlan(planId);
      setIsLoading(true);

      const userEmail = user?.email;
      if (!userEmail) {
        alert("You must be logged in to upgrade!");
        setCheckoutPlan(null);
        setIsLoading(false);
        return;
      }

      // Pack the exact JSON data the Python backend is expecting
      const payload = {
        user_email: userEmail,
        success_url: `${window.location.origin}/dashboard?upgraded=true`,
        cancel_url: `${window.location.origin}/pricing`,
        plan: planId.toLowerCase()
      };

      console.log("2. Sending JSON payload:", payload);

      const response = await fetch('/api/payments/checkout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Server returned ${response.status}: ${errorText}`);
      }

      const data = await response.json();
      console.log("3. Stripe checkout URL received:", data); 

      if (data && data.checkout_url) {
        window.location.href = data.checkout_url;
      } else {
        throw new Error("Backend did not return a checkout_url.");
      }
    } catch (err) {
      console.error("STRIPE CRASH DETECTED:", err);
      alert(`Checkout failed: ${err.message}. Check browser console for details.`);
      setCheckoutPlan(null);
      setIsLoading(false);
    }
  };

  const currentTier = subscriptionTier || 'free';

  return (
    <div style={styles.page}>
      <div style={styles.hero}>
        <h1 style={styles.heroTitle}>Simple, Transparent Pricing</h1>
        <p style={styles.heroSub}>
          Start for free and upgrade when you need more.
        </p>
      </div>

      <div style={styles.cards}>
        {TIERS.map((tier) => {
          const isGradient = tier.background.startsWith('linear-gradient');
          const isCurrentTier = currentTier === tier.id;
          const isDowngrade = TIERS.findIndex(t => t.id === tier.id) < TIERS.findIndex(t => t.id === currentTier);

          return (
            <div
              key={tier.id}
              style={{
                ...styles.card,
                background: tier.background,
                ...tier.cardStyle,
              }}
            >
              {tier.badge && (
                <div style={styles.popularBadge}>{tier.badge}</div>
              )}
              <div style={styles.cardHeader}>
                <h2 style={{ ...styles.planName, color: isGradient ? '#fff' : tier.color }}>
                  {tier.name}
                </h2>
                <div style={styles.price}>
                  <span style={{ ...styles.priceAmount, color: isGradient ? '#fff' : '#111827' }}>
                    ${tier.price}
                  </span>
                  <span style={{ ...styles.pricePeriod, color: isGradient ? 'rgba(255,255,255,0.7)' : '#6b7280' }}>
                    /month
                  </span>
                </div>
              </div>

              <ul style={styles.featureList}>
                {tier.features.map((f) => (
                  <li key={f} style={{ ...styles.featureItem, color: isGradient ? 'rgba(255,255,255,0.9)' : '#374151' }}>
                    <span style={{ ...styles.checkIcon, color: isGradient ? 'rgba(255,255,255,0.7)' : '#16a34a' }}>✓</span>
                    {' '}{f}
                  </li>
                ))}
              </ul>

              {isCurrentTier ? (
                <button
                  style={{
                    ...styles.btnCurrent,
                    background: isGradient ? 'rgba(255,255,255,0.2)' : '#f3f4f6',
                    color: isGradient ? '#fff' : '#6b7280',
                  }}
                  disabled
                >
                  Current Plan ✓
                </button>
              ) : tier.id === 'free' || isDowngrade ? (
                <button
                  style={{
                    ...styles.btnCurrent,
                    background: '#f3f4f6',
                    color: '#6b7280',
                  }}
                  disabled
                >
                  {tier.id === 'free' ? 'Free Plan' : 'Lower Tier'}
                </button>
              ) : (
                <button
                  style={{
                    ...styles.btnUpgrade,
                    background: isGradient ? '#fff' : tier.color,
                    color: isGradient ? '#111827' : '#fff',
                  }}
                  disabled={checkoutPlan !== null}
                  onClick={() => handleCheckout(tier.id)}
                >
                  {checkoutPlan === tier.id ? 'Starting checkout…' : (tier.buttonText || tier.cta)}
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

const styles = {
  page: {
    maxWidth: '1100px',
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
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(230px, 1fr))',
    gap: '1.5rem',
    alignItems: 'start',
  },
  card: {
    borderRadius: '12px',
    boxShadow: '0 4px 16px rgba(0,0,0,0.10)',
    padding: '2rem 1.5rem',
    display: 'flex',
    flexDirection: 'column',
    gap: '1.25rem',
    position: 'relative',
    border: '1px solid transparent',
  },
  popularBadge: {
    position: 'absolute',
    top: '-14px',
    left: '50%',
    transform: 'translateX(-50%)',
    background: '#f59e0b',
    color: '#fff',
    fontSize: '0.72rem',
    fontWeight: '700',
    padding: '0.25rem 0.875rem',
    borderRadius: '99px',
    letterSpacing: '0.05em',
    textTransform: 'uppercase',
    whiteSpace: 'nowrap',
  },
  cardHeader: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.25rem',
  },
  planName: {
    fontSize: '1.25rem',
    fontWeight: '700',
    margin: 0,
  },
  price: {
    display: 'flex',
    alignItems: 'baseline',
    gap: '0.25rem',
  },
  priceAmount: {
    fontSize: '2.25rem',
    fontWeight: '800',
  },
  pricePeriod: {
    fontSize: '0.95rem',
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
    fontSize: '0.9rem',
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
  },
  checkIcon: {
    fontWeight: '700',
    flexShrink: 0,
  },
  btnUpgrade: {
    padding: '0.75rem 1.25rem',
    border: 'none',
    borderRadius: '8px',
    fontSize: '0.95rem',
    fontWeight: '700',
    cursor: 'pointer',
    boxShadow: '0 2px 8px rgba(0,0,0,0.10)',
    transition: 'opacity 0.15s',
    textAlign: 'center',
  },
  btnCurrent: {
    padding: '0.75rem 1.25rem',
    border: 'none',
    borderRadius: '8px',
    fontSize: '0.95rem',
    fontWeight: '700',
    cursor: 'not-allowed',
    textAlign: 'center',
  },
};
