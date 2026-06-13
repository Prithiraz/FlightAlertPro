import { useEffect, useMemo, useState } from 'react';
import { useAuth } from '../App';
import { getLiveTelemetry } from '../lib/api';
import TelemetryPanel from '../components/TelemetryPanel';

const POLL_INTERVAL_MS = 8000;

export default function Dashboard() {
  const { user } = useAuth();
  const [telemetry, setTelemetry] = useState([]);
  const [updatedAt, setUpdatedAt] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let alive = true;

    const refresh = async () => {
      try {
        const payload = await getLiveTelemetry();
        if (!alive) return;
        setTelemetry(Array.isArray(payload.aircraft) ? payload.aircraft : []);
        setUpdatedAt(payload.updated_at || null);
        setError('');
      } catch (err) {
        if (!alive) return;
        setError(err.message || 'Telemetry uplink unavailable.');
      } finally {
        if (alive) setLoading(false);
      }
    };

    refresh();
    const interval = setInterval(refresh, POLL_INTERVAL_MS);
    return () => {
      alive = false;
      clearInterval(interval);
    };
  }, []);

  const stats = useMemo(() => {
    if (!telemetry.length) {
      return { tracked: 0, avgEmission: '--', avgWind: '--', eta: '--' };
    }

    const emission = telemetry.reduce((sum, f) => sum + (f.co2_burn_rate_kg_min || 0), 0) / telemetry.length;
    const wind = telemetry.reduce((sum, f) => sum + (f.wind_component_kt || 0), 0) / telemetry.length;
    const eta = telemetry.reduce((sum, f) => sum + (f.logistics_eta_min || 0), 0) / telemetry.length;

    return {
      tracked: telemetry.length,
      avgEmission: `${emission.toFixed(2)} kg/min`,
      avgWind: `${wind >= 0 ? '+' : ''}${wind.toFixed(1)} kts`,
      eta: `${Math.max(1, Math.round(eta))} min`,
    };
  }, [telemetry]);

  return (
    <div style={styles.page}>
      <div style={styles.shell}>
        <div style={styles.titleBlock}>
          <div style={styles.kicker}>AEROLOGIX COMMAND CENTER</div>
          <h1 style={styles.title}>Live Charter Efficiency Ops</h1>
          <div style={styles.metaLine}>
            Operator: {user?.email || 'unknown'} · Last uplink: {updatedAt ? new Date(updatedAt).toLocaleTimeString() : 'pending'}
          </div>
        </div>

        <div style={styles.statsGrid}>
          <div style={styles.statCard}><span style={styles.statLabel}>Tracked Aircraft</span><span style={styles.statValue}>{stats.tracked}</span></div>
          <div style={styles.statCard}><span style={styles.statLabel}>Avg Emission Rate</span><span style={styles.statValue}>{stats.avgEmission}</span></div>
          <div style={styles.statCard}><span style={styles.statLabel}>Net Wind Vector</span><span style={styles.statValue}>{stats.avgWind}</span></div>
          <div style={styles.statCard}><span style={styles.statLabel}>Logistics ETA</span><span style={styles.etaBadge}>{stats.eta}</span></div>
        </div>

        <TelemetryPanel telemetry={telemetry} loading={loading} error={error} />
      </div>
    </div>
  );
}

const styles = {
  page: {
    minHeight: '100vh',
    background: 'radial-gradient(circle at top, #101d36 0%, #04080f 62%)',
    color: '#d9ebff',
    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
  },
  shell: {
    maxWidth: 1180,
    margin: '0 auto',
    padding: '1.4rem 1rem 2rem',
    display: 'flex',
    flexDirection: 'column',
    gap: '1rem',
  },
  titleBlock: {
    border: '1px solid #1f3958',
    borderRadius: 12,
    padding: '1rem',
    background: 'rgba(6, 11, 24, 0.82)',
    boxShadow: '0 0 25px rgba(48, 202, 255, 0.1)',
  },
  kicker: { color: '#56f0ff', letterSpacing: '0.1em', fontSize: '0.75rem' },
  title: { margin: '0.45rem 0', color: '#f5fbff', fontSize: '1.55rem' },
  metaLine: { color: '#82a4cb', fontSize: '0.82rem' },
  statsGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '0.75rem' },
  statCard: {
    border: '1px solid #1f3958',
    borderRadius: 12,
    background: 'rgba(6, 11, 24, 0.82)',
    padding: '0.8rem 1rem',
    display: 'flex',
    flexDirection: 'column',
    gap: '0.25rem',
  },
  statLabel: { color: '#7ea5d6', fontSize: '0.72rem', textTransform: 'uppercase' },
  statValue: { color: '#ecf7ff', fontSize: '1.2rem', fontWeight: 700 },
  etaBadge: {
    alignSelf: 'flex-start',
    padding: '0.25rem 0.7rem',
    borderRadius: 999,
    border: '1px solid #2a946f',
    background: 'rgba(31, 172, 125, 0.14)',
    color: '#5ff8bf',
    fontWeight: 700,
  },
};
