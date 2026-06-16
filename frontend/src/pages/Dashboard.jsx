import { useEffect, useMemo, useState } from 'react';
import { useAuth } from '../App';
import { getLiveTelemetry } from '../lib/api';
import FlightOpsCard from '../components/FlightOpsCard';
import SavingsROI from '../components/SavingsROI';

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
    const tracked = telemetry.length;
    if (!tracked) {
      return { tracked: 0, advisories: 0, avgConfidence: '--' };
    }
    const advisories = telemetry.filter(
      (f) => (f.operational_performance_advisory?.status || 'NOMINAL') === 'ADVISORY',
    ).length;
    const avgConfidence = telemetry.reduce((sum, f) => sum + (f.confidence_interval_min || 0), 0) / tracked;
    return {
      tracked,
      advisories,
      avgConfidence: `± ${Math.round(avgConfidence)} min`,
    };
  }, [telemetry]);

  return (
    <div style={styles.page}>
      <div style={styles.shell}>
        <div style={styles.titleBlock}>
          <div style={styles.kicker}>AEROLOGIX · DISPATCH OPERATIONS</div>
          <h1 style={styles.title}>Arrival & Ground-Transport Dispatch</h1>
          <div style={styles.metaLine}>
            Operator: {user?.email || 'unknown'} · Last uplink:{' '}
            {updatedAt ? new Date(updatedAt).toLocaleTimeString() : 'pending'}
          </div>
        </div>

        <div style={styles.statsGrid}>
          <div style={styles.statCard}>
            <span style={styles.statLabel}>Active Flights</span>
            <span style={styles.statValue}>{stats.tracked}</span>
          </div>
          <div style={styles.statCard}>
            <span style={styles.statLabel}>Performance Advisories</span>
            <span style={{ ...styles.statValue, color: stats.advisories ? '#ffd27a' : '#5ff8bf' }}>
              {stats.advisories}
            </span>
          </div>
          <div style={styles.statCard}>
            <span style={styles.statLabel}>Avg Confidence Band</span>
            <span style={styles.statValue}>{stats.avgConfidence}</span>
          </div>
        </div>

        <SavingsROI flightCount={stats.tracked} />

        {loading && <div style={styles.message}>Awaiting uplink…</div>}
        {!loading && error && <div style={{ ...styles.message, color: '#ff8d8d' }}>{error}</div>}
        {!loading && !error && !telemetry.length && (
          <div style={styles.message}>No active flights currently tracked.</div>
        )}

        <div style={styles.cardGrid}>
          {telemetry.map((flight) => (
            <FlightOpsCard key={flight.hex_id || flight.flight_number} flight={flight} />
          ))}
        </div>
      </div>
    </div>
  );
}

const styles = {
  page: {
    position: 'fixed',
    inset: 0,
    overflowY: 'auto',
    textAlign: 'left',
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
  cardGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(330px, 1fr))',
    gap: '0.85rem',
  },
  message: {
    border: '1px solid #1f3958',
    borderRadius: 12,
    background: 'rgba(7, 13, 27, 0.85)',
    color: '#9bb6d6',
    padding: '1rem',
  },
};
