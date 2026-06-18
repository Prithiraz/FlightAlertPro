import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { apiFetch } from '../lib/api';

export default function DriverApp() {
  const { id: ledgerId } = useParams();
  const [status, setStatus] = useState('en_route'); // en_route | in_position | passenger_met
  const [arrivedAt, setArrivedAt] = useState(null);
  const [metAt, setMetAt] = useState(null);
  const [loading, setLoading] = useState(false);
  const [flightInfo, setFlightInfo] = useState(null);

  // Fetch current assignment from operational_ledger
  useEffect(() => {
    if (!ledgerId) return;
    apiFetch(`/api/dispatch/assignment/${ledgerId}`)
      .then((data) => setFlightInfo(data))
      .catch(() => {});
  }, [ledgerId]);

  const handleInPosition = async () => {
    setLoading(true);
    try {
      const data = await apiFetch('/api/dispatch/log_driver_arrival', {
        method: 'POST',
        body: JSON.stringify({ ledger_id: ledgerId }),
      });
      setArrivedAt(data.logged_at);
      setStatus('in_position');
    } finally {
      setLoading(false);
    }
  };

  const handlePassengerMet = async () => {
    setLoading(true);
    try {
      const data = await apiFetch('/api/dispatch/log_passenger_met', {
        method: 'POST',
        body: JSON.stringify({ ledger_id: ledgerId }),
      });
      setMetAt(data.logged_at);
      setStatus('passenger_met');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.page}>
      <div style={styles.header}>
        <span style={styles.headerTitle}>AeroLogix Driver</span>
        <span style={styles.statusBadge(status)}>{STATUS_LABELS[status]}</span>
      </div>

      {flightInfo && (
        <div style={styles.flightCard}>
          <div style={styles.flightRow}>
            <span style={styles.label}>Flight</span>
            <span style={styles.value}>{flightInfo.flight_id}</span>
          </div>
          <div style={styles.flightRow}>
            <span style={styles.label}>FBO</span>
            <span style={styles.value}>{flightInfo.target_fbo || '—'}</span>
          </div>
          <div style={styles.flightRow}>
            <span style={styles.label}>Dispatch Window</span>
            <span style={styles.windowValue}>{flightInfo.dispatch_window_str || '—'}</span>
          </div>
        </div>
      )}

      <div style={styles.buttonArea}>
        {status === 'en_route' && (
          <button
            onClick={handleInPosition}
            disabled={loading}
            style={styles.arrivalBtn}
          >
            {loading ? 'Logging…' : 'In Position / Arrived at FBO'}
          </button>
        )}

        {status === 'in_position' && (
          <>
            <div style={styles.arrivedNote}>
              Arrived logged at {arrivedAt ? new Date(arrivedAt).toLocaleTimeString() : '—'}
            </div>
            <button
              onClick={handlePassengerMet}
              disabled={loading}
              style={styles.passengerMetBtn}
            >
              {loading ? 'Logging…' : 'PASSENGER MET'}
            </button>
          </>
        )}

        {status === 'passenger_met' && (
          <div style={styles.completedCard}>
            <div style={styles.completedIcon}>✓</div>
            <div style={styles.completedTitle}>Trip Complete</div>
            <div style={styles.completedSub}>
              Passenger met at {metAt ? new Date(metAt).toLocaleTimeString() : '—'}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

const STATUS_LABELS = {
  en_route: 'En Route',
  in_position: 'In Position',
  passenger_met: 'Complete',
};

const styles = {
  page: {
    minHeight: '100vh', background: '#0f172a', color: '#f1f5f9',
    fontFamily: 'system-ui, sans-serif', padding: '0',
  },
  header: {
    background: '#1e293b', padding: '1rem 1.25rem',
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    borderBottom: '1px solid #334155',
  },
  headerTitle: { fontSize: '1.1rem', fontWeight: '700', color: '#38bdf8' },
  statusBadge: (status) => ({
    padding: '0.25rem 0.75rem', borderRadius: '999px', fontSize: '0.75rem', fontWeight: '700',
    background: status === 'passenger_met' ? '#16a34a' : status === 'in_position' ? '#d97706' : '#3b82f6',
    color: '#fff',
  }),
  flightCard: {
    margin: '1.25rem', background: '#1e293b', borderRadius: '12px',
    padding: '1.25rem', border: '1px solid #334155',
  },
  flightRow: { display: 'flex', justifyContent: 'space-between', padding: '0.4rem 0', borderBottom: '1px solid #334155' },
  label: { color: '#94a3b8', fontSize: '0.85rem' },
  value: { fontWeight: '600', fontSize: '0.95rem' },
  windowValue: { fontWeight: '700', fontSize: '1.1rem', color: '#38bdf8' },
  buttonArea: { padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '1rem' },
  arrivalBtn: {
    width: '100%', padding: '1.25rem', fontSize: '1.1rem', fontWeight: '700',
    background: '#2563eb', color: '#fff', border: 'none', borderRadius: '12px',
    cursor: 'pointer', letterSpacing: '0.02em',
  },
  arrivedNote: { textAlign: 'center', color: '#94a3b8', fontSize: '0.9rem' },
  passengerMetBtn: {
    width: '100%', padding: '2.5rem 1.25rem', fontSize: '1.75rem', fontWeight: '900',
    background: '#16a34a', color: '#fff', border: 'none', borderRadius: '16px',
    cursor: 'pointer', letterSpacing: '0.04em', textTransform: 'uppercase',
    boxShadow: '0 8px 32px rgba(22,163,74,0.4)',
  },
  completedCard: {
    textAlign: 'center', padding: '3rem 1rem',
  },
  completedIcon: { fontSize: '4rem', color: '#16a34a' },
  completedTitle: { fontSize: '1.5rem', fontWeight: '800', marginTop: '0.5rem' },
  completedSub: { color: '#94a3b8', marginTop: '0.5rem' },
};
