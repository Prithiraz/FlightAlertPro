import { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { getDriverTrip, logDriverEvent } from '../lib/api';

const STEPS = [
  {
    event: 'arrived_at_fbo',
    label: 'I Have Arrived at FBO',
    done: 'Arrived at FBO',
    column: 'arrived_at_fbo_at',
  },
  {
    event: 'passenger_exited',
    label: 'Passenger Has Exited Terminal',
    done: 'Passenger exited terminal',
    column: 'passenger_exited_at',
  },
  {
    event: 'passenger_collected',
    label: 'Passenger Collected / Departed',
    done: 'Passenger collected',
    column: 'passenger_collected_at',
  },
];

function formatClock(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

export default function DriverView() {
  const { flightId } = useParams();
  const [trip, setTrip] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getDriverTrip(flightId);
      setTrip(data);
    } catch (e) {
      setError(e.message || 'Unable to load trip');
    } finally {
      setLoading(false);
    }
  }, [flightId]);

  useEffect(() => {
    load();
  }, [load]);

  const ledger = trip?.ledger || {};
  const nextEvent = trip?.next_event ?? 'arrived_at_fbo';
  const completed = nextEvent === null;

  const handleClick = async (eventType) => {
    setSubmitting(eventType);
    setError(null);
    try {
      const res = await logDriverEvent(flightId, eventType);
      setTrip((prev) => ({
        ...(prev || {}),
        ledger: res.ledger,
        next_event: res.next_event,
      }));
    } catch (e) {
      setError(e.message || 'Could not record event');
    } finally {
      setSubmitting(null);
    }
  };

  const waitMinutes = ledger?.driver_wait_minutes;

  return (
    <div style={styles.page}>
      <div style={styles.shell}>
        <div style={styles.kicker}>AEROLOGIX · DRIVER</div>

        {loading && <div style={styles.muted}>Loading trip…</div>}

        {!loading && error && !trip && (
          <div style={styles.errorBox}>{error}</div>
        )}

        {!loading && trip && (
          <>
            <div style={styles.passengerCard}>
              <div style={styles.passengerLabel}>TARGET PASSENGER</div>
              <div style={styles.passengerName}>
                {trip.passenger_name || 'Passenger'}
              </div>
              <div style={styles.flightRow}>
                <span style={styles.flightTag}>
                  {trip.flight_number || flightId}
                </span>
                {trip.fbo && <span style={styles.fbo}>{trip.fbo}</span>}
              </div>
              {trip.predicted_on_block_time && (
                <div style={styles.obt}>
                  Predicted On-Block · {formatClock(trip.predicted_on_block_time)}
                </div>
              )}
            </div>

            {error && <div style={styles.errorBox}>{error}</div>}

            <div style={styles.steps}>
              {STEPS.map((step, idx) => {
                const ts = ledger?.[step.column];
                const isDone = Boolean(ts);
                const isActive = step.event === nextEvent;
                const isSubmitting = submitting === step.event;
                const disabled = !isActive || isSubmitting;
                return (
                  <button
                    key={step.event}
                    type="button"
                    onClick={() => handleClick(step.event)}
                    disabled={disabled}
                    style={{
                      ...styles.stepBtn,
                      ...(isDone ? styles.stepDone : {}),
                      ...(isActive ? styles.stepActive : {}),
                      ...(disabled && !isDone ? styles.stepLocked : {}),
                    }}
                  >
                    <span style={styles.stepIndex}>
                      {isDone ? '✓' : idx + 1}
                    </span>
                    <span style={styles.stepText}>
                      <span style={styles.stepLabel}>
                        {isSubmitting ? 'Saving…' : isDone ? step.done : step.label}
                      </span>
                      {isDone && (
                        <span style={styles.stepTime}>{formatClock(ts)}</span>
                      )}
                    </span>
                  </button>
                );
              })}
            </div>

            {completed && (
              <div style={styles.summary}>
                <div style={styles.summaryTitle}>Trip complete</div>
                {waitMinutes != null ? (
                  <div style={styles.summaryWait}>
                    Driver wait vs predicted OBT:{' '}
                    <strong
                      style={{
                        color: waitMinutes > 0 ? '#ffd27a' : '#7df0c0',
                      }}
                    >
                      {waitMinutes > 0 ? '+' : ''}
                      {waitMinutes} min
                    </strong>
                  </div>
                ) : (
                  <div style={styles.muted}>Wait time recorded.</div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

const styles = {
  page: {
    position: 'fixed',
    inset: 0,
    background: 'radial-gradient(circle at 50% 0%, #0c1830 0%, #060b16 60%)',
    color: '#eaf3ff',
    fontFamily: 'system-ui, -apple-system, Segoe UI, Roboto, sans-serif',
    overflowY: 'auto',
    display: 'flex',
    justifyContent: 'center',
  },
  shell: {
    width: '100%',
    maxWidth: 460,
    padding: '1.5rem 1.1rem 2.5rem',
    display: 'flex',
    flexDirection: 'column',
    gap: '1.1rem',
  },
  kicker: {
    color: '#5eeaff',
    fontSize: '0.72rem',
    letterSpacing: '0.18em',
    fontWeight: 700,
    textAlign: 'center',
  },
  muted: { color: '#9bb6d6', fontSize: '0.9rem', textAlign: 'center' },
  errorBox: {
    border: '1px solid #b8434f',
    background: 'rgba(255, 91, 91, 0.14)',
    color: '#ffb4b4',
    borderRadius: 10,
    padding: '0.7rem 0.8rem',
    fontSize: '0.85rem',
  },
  passengerCard: {
    border: '1px solid #1f3958',
    borderRadius: 16,
    background: 'rgba(8, 15, 30, 0.9)',
    padding: '1.2rem 1.1rem',
    display: 'flex',
    flexDirection: 'column',
    gap: '0.45rem',
  },
  passengerLabel: {
    color: '#7ea5d6',
    fontSize: '0.66rem',
    letterSpacing: '0.12em',
  },
  passengerName: { fontSize: '1.7rem', fontWeight: 800, lineHeight: 1.1 },
  flightRow: { display: 'flex', alignItems: 'center', gap: '0.6rem', marginTop: '0.2rem' },
  flightTag: {
    background: 'rgba(94, 234, 255, 0.12)',
    border: '1px solid #21506b',
    color: '#9fe9ff',
    borderRadius: 8,
    padding: '0.2rem 0.55rem',
    fontSize: '0.85rem',
    fontWeight: 700,
    letterSpacing: '0.03em',
  },
  fbo: { color: '#9bb6d6', fontSize: '0.85rem' },
  obt: { color: '#8fb0d6', fontSize: '0.8rem', marginTop: '0.2rem' },
  steps: { display: 'flex', flexDirection: 'column', gap: '0.8rem' },
  stepBtn: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.9rem',
    width: '100%',
    minHeight: 78,
    padding: '0 1.1rem',
    borderRadius: 16,
    border: '1px solid #1f3958',
    background: 'rgba(10, 19, 38, 0.7)',
    color: '#eaf3ff',
    fontFamily: 'inherit',
    fontSize: '1.1rem',
    fontWeight: 700,
    textAlign: 'left',
    cursor: 'pointer',
    transition: 'transform 0.05s ease',
  },
  stepActive: {
    border: '1px solid #2fcaff',
    background: 'linear-gradient(180deg, rgba(47, 202, 255, 0.18), rgba(47, 202, 255, 0.06))',
    boxShadow: '0 0 26px rgba(47, 202, 255, 0.18)',
  },
  stepDone: {
    border: '1px solid #2a946f',
    background: 'rgba(31, 172, 125, 0.12)',
    cursor: 'default',
  },
  stepLocked: { opacity: 0.45, cursor: 'not-allowed' },
  stepIndex: {
    flexShrink: 0,
    width: 34,
    height: 34,
    borderRadius: '50%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: 'rgba(255,255,255,0.08)',
    fontSize: '1rem',
    fontWeight: 800,
  },
  stepText: { display: 'flex', flexDirection: 'column', gap: '0.15rem' },
  stepLabel: { lineHeight: 1.2 },
  stepTime: { fontSize: '0.78rem', fontWeight: 600, color: '#9fd9c4' },
  summary: {
    border: '1px solid #2a946f',
    borderRadius: 16,
    background: 'rgba(31, 172, 125, 0.1)',
    padding: '1.1rem',
    textAlign: 'center',
    display: 'flex',
    flexDirection: 'column',
    gap: '0.35rem',
  },
  summaryTitle: { fontSize: '1.1rem', fontWeight: 800, color: '#bff7e2' },
  summaryWait: { fontSize: '0.95rem', color: '#d9ebff' },
};
