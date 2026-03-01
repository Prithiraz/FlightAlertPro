import { useNavigate } from 'react-router-dom';

/**
 * UpgradeBanner – shown when the user is at or above 80% of a plan limit.
 *
 * Props:
 *   usage  – { alerts_active, saved_searches_count }
 *   limits – { max_active_alerts }
 *   plan   – current plan string
 */
export default function UpgradeBanner({ usage = {}, limits = {}, plan = 'free' }) {
  const navigate = useNavigate();

  const maxAlerts = limits.max_active_alerts || 3;
  const activeAlerts = usage.alerts_active || 0;
  const alertPct = maxAlerts > 0 ? activeAlerts / maxAlerts : 0;

  const nearLimit = alertPct >= 0.8;
  const atLimit = activeAlerts >= maxAlerts;

  if (plan !== 'free' && !nearLimit) return null;

  const message = atLimit
    ? `You've reached your limit of ${maxAlerts} active alerts on the ${plan} plan.`
    : `You're using ${activeAlerts} of ${maxAlerts} available alerts (${Math.round(alertPct * 100)}%).`;

  return (
    <div style={styles.banner}>
      <span style={styles.icon}>⚡</span>
      <span style={styles.message}>{message} Upgrade for more.</span>
      <button
        onClick={() => navigate('/billing')}
        style={styles.cta}
      >
        Upgrade →
      </button>
    </div>
  );
}

const styles = {
  banner: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.75rem',
    background: '#fefce8',
    border: '1px solid #fde68a',
    borderRadius: '8px',
    padding: '0.75rem 1rem',
    marginBottom: '1.5rem',
    flexWrap: 'wrap',
  },
  icon: { fontSize: '1.1rem' },
  message: { flex: 1, color: '#92400e', fontSize: '0.9rem' },
  cta: {
    padding: '0.4rem 1rem',
    background: '#f59e0b',
    color: '#fff',
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer',
    fontWeight: '600',
    fontSize: '0.875rem',
    whiteSpace: 'nowrap',
  },
};
