import { useEffect, useMemo, useState } from 'react';
import { riskAdjustedDispatchTime, readyTimeWindow } from '../lib/riskDispatch';

const SEVERITY_COLORS = {
  HIGH: { fg: '#ff8d8d', bg: 'rgba(255, 91, 91, 0.12)', border: '#5c2730' },
  MODERATE: { fg: '#ffd27a', bg: 'rgba(255, 184, 77, 0.12)', border: '#5c4a27' },
  LOW: { fg: '#7df0c0', bg: 'rgba(31, 172, 125, 0.12)', border: '#27513f' },
};

function formatClock(iso) {
  if (!iso) return '--:--';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '--:--';
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function formatCountdown(ms) {
  const totalSeconds = Math.round(Math.abs(ms) / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}m ${String(seconds).padStart(2, '0')}s`;
}

function DispatchCountdown({ dispatchTime, buffer = 0 }) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  const target = dispatchTime ? new Date(dispatchTime).getTime() : null;
  if (!target || Number.isNaN(target)) {
    return <div style={styles.dispatchPending}>Dispatch time unavailable</div>;
  }

  const delta = target - now;
  const overdue = delta <= 0;
  const label = overdue ? 'DISPATCH NOW' : `Leave in ${formatCountdown(delta)}`;
  const bufferNote = buffer > 0
    ? `incl. ${buffer} min risk buffer`
    : (buffer < 0 ? `${Math.abs(buffer)} min later (driver-cost weighted)` : 'no risk buffer');
  const sub = overdue
    ? `Driver should already be en route (${formatCountdown(delta)} ago)`
    : `Risk-adjusted depart at ${formatClock(dispatchTime)} · ${bufferNote}`;

  return (
    <div style={{ ...styles.dispatch, ...(overdue ? styles.dispatchOverdue : {}) }}>
      <div style={styles.dispatchLabelRow}>
        <span style={styles.dispatchKicker}>RISK-ADJUSTED DISPATCH TIME</span>
        {overdue && <span style={styles.pulseDot} />}
      </div>
      <div style={styles.dispatchValue}>{label}</div>
      <div style={styles.dispatchSub}>{sub}</div>
    </div>
  );
}

function EngineeringRow({ label, value }) {
  return (
    <div style={styles.engRow}>
      <span style={styles.engLabel}>{label}</span>
      <span style={styles.engValue}>{value}</span>
    </div>
  );
}

export default function FlightOpsCard({ flight, waitCost = 1, lateCost = 5 }) {
  const [showEngineering, setShowEngineering] = useState(false);

  const advisory = flight.operational_performance_advisory || {};
  const severity = advisory.severity || 'LOW';
  const palette = SEVERITY_COLORS[severity] || SEVERITY_COLORS.LOW;

  const confidence = flight.confidence_interval_min;
  const tdt = flight.predicted_touchdown_time;
  const obt = flight.predicted_on_block_time;

  // Phase 2: probabilistic ready-time window + risk-adjusted dispatch. Recomputed
  // live from the dispatcher's cost sliders so there's no "exact" ETA claim.
  const window = useMemo(
    () => readyTimeWindow(obt, confidence, 0.8),
    [obt, confidence],
  );
  const risk = useMemo(
    () => riskAdjustedDispatchTime(obt, confidence, waitCost, lateCost, flight.drive_time_min),
    [obt, confidence, waitCost, lateCost, flight.drive_time_min],
  );
  const riskDispatchIso = risk.dispatchTime ? risk.dispatchTime.toISOString() : flight.risk_adjusted_dispatch_time;

  const engineering = useMemo(() => ([
    { label: 'Ground-ref. energy height', value: flight.energy_height_ft != null ? `${flight.energy_height_ft.toLocaleString()} ft` : '--' },
    { label: 'Estimated wind influence', value: flight.wind_component_kt != null ? `${flight.wind_component_kt >= 0 ? '+' : ''}${flight.wind_component_kt.toFixed(1)} kt ${flight.wind_type || ''}`.trim() : '--' },
    { label: 'True airspeed (est.)', value: flight.tas_kt != null ? `${flight.tas_kt.toFixed(1)} kt` : '--' },
    { label: 'Ground speed', value: flight.ground_speed_kt != null ? `${flight.ground_speed_kt.toFixed(1)} kt` : '--' },
    { label: 'Heading', value: flight.heading_deg != null ? `${flight.heading_deg.toFixed(0)}°` : '--' },
    { label: 'Density altitude', value: flight.density_altitude_ft != null ? `${flight.density_altitude_ft.toLocaleString()} ft` : '--' },
    { label: 'Pressure altitude', value: flight.altitude_ft != null ? `${Number(flight.altitude_ft).toLocaleString()} ft` : '--' },
    { label: 'Fuel burn rate', value: flight.co2_burn_rate_kg_min != null ? `${flight.co2_burn_rate_kg_min.toFixed(2)} kg/min` : '--' },
    { label: 'Planning-horizon ETA', value: flight.logistics_eta_min != null ? `${flight.logistics_eta_min} min` : '--' },
    { label: 'Position', value: (flight.lat != null && flight.lon != null) ? `${flight.lat.toFixed(3)}, ${flight.lon.toFixed(3)}` : '--' },
  ]), [flight]);

  return (
    <div style={styles.card}>
      <div style={styles.cardHead}>
        <div>
          <div style={styles.flightNumber}>{flight.flight_number || flight.hex_id || 'UNKNOWN'}</div>
          <div style={styles.flightId}>ICAO24 {flight.hex_id || '--'}</div>
        </div>
        <div style={{ ...styles.advisoryBadge, color: palette.fg, background: palette.bg, borderColor: palette.border }}>
          <span style={styles.advisoryStatus}>{advisory.status || 'NOMINAL'}</span>
          <span style={styles.advisorySeverity}>{severity}</span>
        </div>
      </div>

      <div style={styles.milestoneGrid}>
        <div style={styles.milestone}>
          <span style={styles.milestoneLabel}>Predicted Touchdown (TDT)</span>
          <span style={styles.milestoneValue}>{formatClock(tdt)}</span>
        </div>
        <div style={styles.milestone}>
          <span style={styles.milestoneLabel}>Median On-Block (OBT)</span>
          <span style={styles.milestoneValue}>{formatClock(window.median ? window.median.toISOString() : obt)}</span>
        </div>
        <div style={styles.milestone}>
          <span style={styles.milestoneLabel}>Confidence Range</span>
          <span style={styles.confidenceValue}>{confidence != null ? `± ${confidence} min` : '--'}</span>
        </div>
      </div>

      <div style={styles.windowBand}>
        <span style={styles.windowLabel}>READY-TIME WINDOW (80%)</span>
        <span style={styles.windowValue}>
          {window.start ? `${formatClock(window.start.toISOString())} – ${formatClock(window.end.toISOString())}` : '--'}
        </span>
      </div>

      {advisory.headline && (
        <div style={{ ...styles.advisoryLine, color: palette.fg }}>
          {advisory.headline}
        </div>
      )}

      <DispatchCountdown dispatchTime={riskDispatchIso} buffer={risk.bufferMinutes} />

      <button
        type="button"
        style={styles.engToggle}
        onClick={() => setShowEngineering((v) => !v)}
        aria-expanded={showEngineering}
      >
        <span>Engineering Details</span>
        <span style={styles.engChevron}>{showEngineering ? '▲' : '▼'}</span>
      </button>

      {showEngineering && (
        <div style={styles.engDrawer}>
          {engineering.map((row) => (
            <EngineeringRow key={row.label} label={row.label} value={row.value} />
          ))}
        </div>
      )}
    </div>
  );
}

const styles = {
  card: {
    border: '1px solid #1f3958',
    borderRadius: 14,
    background: 'rgba(7, 13, 27, 0.88)',
    padding: '1rem',
    display: 'flex',
    flexDirection: 'column',
    gap: '0.85rem',
    boxShadow: '0 0 22px rgba(48, 202, 255, 0.06)',
  },
  cardHead: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: '0.5rem',
  },
  flightNumber: { color: '#f5fbff', fontSize: '1.25rem', fontWeight: 700, letterSpacing: '0.02em' },
  flightId: { color: '#7ea5d6', fontSize: '0.72rem', marginTop: '0.15rem' },
  advisoryBadge: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'flex-end',
    border: '1px solid',
    borderRadius: 10,
    padding: '0.3rem 0.55rem',
    minWidth: 84,
  },
  advisoryStatus: { fontSize: '0.62rem', letterSpacing: '0.12em', opacity: 0.85 },
  advisorySeverity: { fontSize: '0.95rem', fontWeight: 800, letterSpacing: '0.04em' },
  milestoneGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(3, 1fr)',
    gap: '0.5rem',
  },
  milestone: {
    border: '1px solid #132743',
    borderRadius: 10,
    padding: '0.55rem 0.6rem',
    display: 'flex',
    flexDirection: 'column',
    gap: '0.25rem',
    background: 'rgba(10, 19, 38, 0.6)',
  },
  milestoneLabel: { color: '#7ea5d6', fontSize: '0.66rem', textTransform: 'uppercase', letterSpacing: '0.04em' },
  milestoneValue: { color: '#ecf7ff', fontSize: '1.18rem', fontWeight: 700 },
  confidenceValue: { color: '#5eeaff', fontSize: '1.18rem', fontWeight: 700 },
  advisoryLine: { fontSize: '0.82rem', fontWeight: 600 },
  windowBand: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: '0.5rem',
    border: '1px dashed #2a4a6e',
    borderRadius: 10,
    padding: '0.45rem 0.7rem',
    background: 'rgba(10, 19, 38, 0.5)',
  },
  windowLabel: { color: '#7ea5d6', fontSize: '0.64rem', letterSpacing: '0.08em' },
  windowValue: { color: '#bfe6ff', fontSize: '0.95rem', fontWeight: 700 },
  dispatch: {
    border: '1px solid #2a946f',
    borderRadius: 12,
    background: 'rgba(31, 172, 125, 0.1)',
    padding: '0.7rem 0.8rem',
    display: 'flex',
    flexDirection: 'column',
    gap: '0.2rem',
  },
  dispatchOverdue: {
    border: '1px solid #b8434f',
    background: 'rgba(255, 91, 91, 0.14)',
  },
  dispatchLabelRow: { display: 'flex', alignItems: 'center', gap: '0.4rem' },
  dispatchKicker: { color: '#9fd9c4', fontSize: '0.64rem', letterSpacing: '0.1em' },
  dispatchValue: { color: '#f3fff9', fontSize: '1.3rem', fontWeight: 800 },
  dispatchSub: { color: '#9bb6d6', fontSize: '0.74rem' },
  dispatchPending: { color: '#9bb6d6', fontSize: '0.8rem', fontStyle: 'italic' },
  pulseDot: {
    width: 9,
    height: 9,
    borderRadius: '50%',
    background: '#ff5b5b',
    boxShadow: '0 0 8px #ff5b5b',
  },
  engToggle: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    width: '100%',
    background: 'rgba(10, 19, 38, 0.7)',
    border: '1px solid #1f3958',
    borderRadius: 10,
    color: '#9fc2ec',
    padding: '0.5rem 0.7rem',
    fontSize: '0.78rem',
    fontWeight: 600,
    cursor: 'pointer',
    fontFamily: 'inherit',
    letterSpacing: '0.04em',
  },
  engChevron: { fontSize: '0.65rem', color: '#5eeaff' },
  engDrawer: {
    border: '1px solid #132743',
    borderRadius: 10,
    background: 'rgba(4, 9, 18, 0.7)',
    padding: '0.4rem 0.7rem',
    display: 'flex',
    flexDirection: 'column',
  },
  engRow: {
    display: 'flex',
    justifyContent: 'space-between',
    gap: '0.5rem',
    padding: '0.4rem 0',
    borderBottom: '1px solid #0e1d33',
    fontSize: '0.8rem',
  },
  engLabel: { color: '#88a5c6' },
  engValue: { color: '#d9ebff', fontWeight: 600, textAlign: 'right' },
};
