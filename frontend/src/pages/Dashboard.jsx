import { useEffect, useMemo, useState } from 'react';
import { useAuth } from '../App';
import { getLiveTelemetry } from '../lib/api';
import FlightOpsCard from '../components/FlightOpsCard';

const POLL_INTERVAL_MS = 8000;

export default function Dashboard() {
  const { user } = useAuth();
  const [telemetry, setTelemetry] = useState([]);
  const [updatedAt, setUpdatedAt] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [policy, setPolicy] = useState('BALANCED');

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
    return () => { alive = false; clearInterval(interval); };
  }, []);

  const stats = useMemo(() => {
    const tracked = telemetry.length;
    const advisories = telemetry.filter(f => (f.performance_advisory || 'NOMINAL') !== 'NOMINAL').length;
    return { tracked, advisories };
  }, [telemetry]);

  return (
    <div style={{ position: 'fixed', inset: 0, overflowY: 'auto', background: '#04080f', color: '#d9ebff', fontFamily: 'ui-monospace, SFMono-Regular, monospace' }}>
      <div style={{ maxWidth: 1180, margin: '0 auto', padding: '1.5rem 1rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        
        {/* Header Block */}
        <div style={{ border: '1px solid #1f3958', borderRadius: 12, padding: '1rem 1.5rem', background: '#0a1122', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ color: '#5eeaff', letterSpacing: '2px', fontSize: '0.75rem', fontWeight: 'bold' }}>AEROLOGIX · COMMAND CENTER</div>
            <h1 style={{ margin: '0.2rem 0', color: '#f5fbff', fontSize: '1.4rem' }}>Arrival Logistics</h1>
            <div style={{ color: '#82a4cb', fontSize: '0.8rem' }}>Operator: {user?.email || 'Unknown'}</div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', justifyContent: 'flex-end', marginBottom: '0.5rem' }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: error ? '#ff4d4d' : '#5ff8bf', boxShadow: `0 0 8px ${error ? '#ff4d4d' : '#5ff8bf'}` }}></span>
              <span style={{ color: error ? '#ff4d4d' : '#5ff8bf', fontSize: '0.8rem', fontWeight: 'bold', letterSpacing: '1px' }}>
                {error ? 'NETWORK OFFLINE' : 'LIVE ADS-B FEED'}
              </span>
            </div>
            <div style={{ color: '#82a4cb', fontSize: '0.75rem' }}>Last Uplink: {updatedAt ? new Date(updatedAt).toLocaleTimeString() : 'Pending'}</div>
          </div>
        </div>

        {/* Policy & Stats Controls */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 2fr', gap: '1rem' }}>
          <div style={{ border: '1px solid #1f3958', borderRadius: 8, padding: '1rem', background: '#0a1122' }}>
            <div style={{ color: '#7ea5d6', fontSize: '0.7rem', textTransform: 'uppercase' }}>Active Targets</div>
            <div style={{ color: '#fff', fontSize: '1.5rem', fontWeight: 'bold' }}>{stats.tracked}</div>
          </div>
          <div style={{ border: '1px solid #1f3958', borderRadius: 8, padding: '1rem', background: '#0a1122' }}>
            <div style={{ color: '#7ea5d6', fontSize: '0.7rem', textTransform: 'uppercase' }}>Advisories</div>
            <div style={{ color: stats.advisories > 0 ? '#ffd27a' : '#fff', fontSize: '1.5rem', fontWeight: 'bold' }}>{stats.advisories}</div>
          </div>
          <div style={{ border: '1px solid #2fcaff', borderRadius: 8, padding: '1rem', background: 'rgba(47, 202, 255, 0.05)', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
            <div style={{ color: '#5eeaff', fontSize: '0.7rem', textTransform: 'uppercase', marginBottom: '0.5rem', fontWeight: 'bold' }}>Global Service Policy</div>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              {['EFFICIENCY', 'BALANCED', 'VIP_PROTECTED'].map(p => (
                <button key={p} onClick={() => setPolicy(p)} style={{ flex: 1, padding: '0.5rem', background: policy === p ? '#2fcaff' : '#1f3958', color: policy === p ? '#04080f' : '#82a4cb', border: 'none', borderRadius: 4, fontSize: '0.75rem', fontWeight: 'bold', cursor: 'pointer' }}>
                  {p.replace('_', ' ')}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Flight Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(330px, 1fr))', gap: '1rem', marginTop: '0.5rem' }}>
          {telemetry.map(flight => <FlightOpsCard key={flight.hex_id} flight={flight} policy={policy} />)}
        </div>
      </div>
    </div>
  );
}
