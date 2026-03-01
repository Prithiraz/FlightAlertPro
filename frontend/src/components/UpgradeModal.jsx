import { useNavigate } from 'react-router-dom';
import { trackEvent } from '../lib/api';

/**
 * UpgradeModal – shown as a modal overlay when a user hits a plan limit or tries a premium feature.
 *
 * Props:
 *   reason   – string key: 'alert_limit' | 'search_limit' | 'premium_feature'
 *   feature  – optional human-readable feature name
 *   onClose  – callback to dismiss the modal
 */
export default function UpgradeModal({ reason = 'alert_limit', feature, onClose }) {
  const navigate = useNavigate();

  const messages = {
    alert_limit: {
      icon: '🔔',
      title: 'Alert Limit Reached',
      body: 'You\'ve used all your available price alerts. Upgrade your plan to monitor more routes.',
    },
    search_limit: {
      icon: '🔍',
      title: 'Search Limit Reached',
      body: 'You\'ve reached your daily search limit. Upgrade to search more flights without restrictions.',
    },
    premium_feature: {
      icon: '⚡',
      title: 'Premium Feature',
      body: `${feature || 'This feature'} is available on Pro and above. Upgrade to unlock it.`,
    },
  };

  const { icon, title, body } = messages[reason] || messages.alert_limit;

  const handleUpgrade = () => {
    trackEvent('upgrade_click', { reason }).catch(() => {});
    onClose?.();
    navigate('/billing');
  };

  return (
    <div style={styles.overlay} onClick={onClose}>
      <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
        <button style={styles.closeBtn} onClick={onClose} aria-label="Close">×</button>
        <div style={styles.icon}>{icon}</div>
        <h2 style={styles.title}>{title}</h2>
        <p style={styles.body}>{body}</p>

        <div style={styles.plans}>
          <div style={styles.planItem}>
            <span style={styles.planName}>Pro</span>
            <span style={styles.planPrice}>$9/mo</span>
            <span style={styles.planHint}>20 alerts</span>
          </div>
          <div style={{ ...styles.planItem, ...styles.planHighlight }}>
            <span style={styles.planName}>Elite</span>
            <span style={styles.planPrice}>$29/mo</span>
            <span style={styles.planHint}>50 alerts</span>
          </div>
          <div style={styles.planItem}>
            <span style={styles.planName}>Business</span>
            <span style={styles.planPrice}>$99/mo</span>
            <span style={styles.planHint}>200 alerts</span>
          </div>
        </div>

        <button style={styles.upgradeCta} onClick={handleUpgrade}>
          See Upgrade Options →
        </button>
        <button style={styles.dismissBtn} onClick={onClose}>
          Maybe later
        </button>
      </div>
    </div>
  );
}

const styles = {
  overlay: {
    position: 'fixed', inset: 0,
    background: 'rgba(0,0,0,0.55)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    zIndex: 1000,
    padding: '1rem',
  },
  modal: {
    background: '#fff',
    borderRadius: '16px',
    padding: '2rem',
    maxWidth: '440px',
    width: '100%',
    textAlign: 'center',
    position: 'relative',
    boxShadow: '0 8px 32px rgba(0,0,0,0.18)',
  },
  closeBtn: {
    position: 'absolute', top: '0.75rem', right: '1rem',
    background: 'none', border: 'none', fontSize: '1.5rem',
    cursor: 'pointer', color: '#9ca3af', lineHeight: 1,
  },
  icon: { fontSize: '2.5rem', marginBottom: '0.5rem' },
  title: { fontSize: '1.4rem', fontWeight: '800', color: '#1d4ed8', margin: '0 0 0.5rem' },
  body: { fontSize: '0.95rem', color: '#6b7280', lineHeight: 1.6, margin: '0 0 1.5rem' },
  plans: { display: 'flex', gap: '0.75rem', justifyContent: 'center', marginBottom: '1.5rem', flexWrap: 'wrap' },
  planItem: {
    display: 'flex', flexDirection: 'column', alignItems: 'center',
    background: '#f9fafb', border: '1px solid #e5e7eb',
    borderRadius: '10px', padding: '0.75rem 1rem', minWidth: '100px',
  },
  planHighlight: { background: '#1d4ed8', color: '#fff', border: 'none' },
  planName: { fontWeight: '800', fontSize: '0.95rem' },
  planPrice: { fontSize: '1.1rem', fontWeight: '700', margin: '0.15rem 0' },
  planHint: { fontSize: '0.75rem', opacity: 0.75 },
  upgradeCta: {
    display: 'block', width: '100%',
    padding: '0.8rem', background: '#1d4ed8', color: '#fff',
    border: 'none', borderRadius: '8px', fontWeight: '700', fontSize: '1rem',
    cursor: 'pointer', marginBottom: '0.75rem',
  },
  dismissBtn: {
    background: 'none', border: 'none', color: '#9ca3af',
    cursor: 'pointer', fontSize: '0.875rem',
  },
};
