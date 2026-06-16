import { useEffect, useMemo, useState } from 'react';
import { calculateDispatchWindow, readyTimeWindow } from '../lib/riskDispatch';

const SEVERITY_COLORS = {
  HIGH: { fg: '#ff8d8d', bg: 'rgba(255, 91, 91, 0.12)', border: '#5c2730' },
  MODERATE: { fg: '#ffd27a', bg: 'rgba(255, 184, 77, 0.12)', border: '#5c4a27' },
  LOW: { fg: '#7df0c0', bg: 'rgba(31, 172, 125, 0.12)', border: '#27513f' },
};

// Surface uncertainty band derived from the (compounded) arrival uncertainty.
// We deliberately speak in terms of *arrival uncertainty*, not aerodynamic
// stability — the dispatcher cares about how wide the pickup window is.
function uncertaintyBand(uncertaintyMin) {
  const u = Number(uncertaintyMin) || 0;
  if (u > 14) return { status: 'ELEVATED', severity: 'HIGH', headline: 'Arrival Uncertainty Increased' };
  if (u > 6) return { status: 'WATCH', severity: 'MODERATE', headline: 'Arrival Uncertainty Moderate' };
  return { status: 'STABLE', severity: 'LOW', headline: 'Arrival Window Tight' };
}

const CONFIDENCE_COLORS = {
  High: '#7df0c0',
  Moderate: '#ffd27a',
  Low: '#ff8d8d',
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

function DispatchWindow({ windowStart, windowEnd, expectedWait, confidence }) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  const startMs = windowStart ? new Date(windowStart).getTime() : null;
  const endMs = windowEnd ? new Date(windowEnd).getTime() : null;
  if (!startMs || Number.isNaN(startMs)) {
    return <div style={styles.dispatchPending}>Dispatch window unavailable</div>;
  }

  const beforeWindow = now < startMs;
  const inWindow = endMs != null && now >= startMs && now <= endMs;
  const overdue = endMs != null && now > endMs;

  let countdown;
  if (beforeWindow) countdown = `Window opens in ${formatCountdown(startMs - now)}`;
  else if (inWindow) countdown = `DISPATCH WINDOW OPEN · closes in ${formatCountdown(endMs - now)}`;
  else countdown = `Window closed ${formatCountdown(now - endMs)} ago`;

  const confColor = CONFIDENCE_COLORS[confidence] || '#cfe3ff';

  return (
    <div style={{ ...styles.dispatch, ...(overdue ? styles.dispatchOverdue : (inWindow ? styles.dispatchActive : {})) }}>
      <div style={styles.dispatchLabelRow}>
        <span style={styles.dispatchKicker}>ACCEPTABLE DISPATCH WINDOW</span>
        {(inWindow || overdue) && <span style={styles.pulseDot} />}
      </div>
      <div style={styles.dispatchValue}>
        {formatClock(windowStart)} – {formatClock(windowEnd)}
      </div>
      <div style={styles.dispatchSub}>{countdown}</div>
      <div style={styles.metricRow}>
        <span style={styles.metricChip}>Expected Driver Wait: <strong>{expectedWait} mins</strong></span>
        <span style={{ ...styles.metricChip, color: confColor }}>Recommendation Confidence: <strong>{confidence}</strong></span>
      </div>
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

  const tdt = flight.predicted_touchdown_time;
  const obt = flight.predicted_on_block_time;
  // The passenger-ready distribution (compounded down the modular chain) drives
  // both the surface uncertainty band and the dispatch window.
  const readyIso = flight.predicted_passenger_ready_time || obt;
  const uncertainty = flight.ready_uncertainty_minutes != null
    ? flight.ready_uncertainty_minutes
    : flight.confidence_interval_min;

  const band = uncertaintyBand(uncertainty);
  const palette = SEVERITY_COLORS[band.severity] || SEVERITY_COLORS.LOW;

  // Probabilistic ready-time window + acceptable dispatch window. Recomputed
  // live from the dispatcher's cost sliders so there's no "exact" ETA claim.
  const window = useMemo(
    () => readyTimeWindow(readyIso, uncertainty, 0.8),
    [readyIso, uncertainty],
  );
  const dispatchWindow = useMemo(
    () => calculateDispatchWindow(readyIso, uncertainty, waitCost, lateCost, flight.drive_time_min),
    [readyIso, uncertainty, waitCost, lateCost, flight.drive_time_min],
  );
  const windowStartIso = dispatchWindow.start ? dispatchWindow.start.toISOString() : flight.dispatch_window_start;
  const windowEndIso = dispatchWindow.end ? dispatchWindow.end.toISOString() : flight.dispatch_window_end;

  const engineering = useMemo(() => {
    const adv = flight.operational_performance_advisory || {};
    return [
    { label: 'Operational performance advisory', value: adv.headline ? `${adv.headline} (${adv.severity || 'LOW'})` : '--' },
    { label: 'Stability / approach margin', value: adv.detail || 'Nominal' },
    { label: 'Density altitude', value: flight.density_altitude_ft != null ? `${flight.density_altitude_ft.toLocaleString()} ft` : '--' },
    { label: 'Ground-ref. energy height', value: flight.energy_height_ft != null ? `${flight.energy_height_ft.toLocaleString()} ft` : '--' },
    { label: 'Estimated wind influence', value: flight.wind_component_kt != null ? `${flight.wind_component_kt >= 0 ? '+' : ''}${flight.wind_component_kt.toFixed(1)} kt ${flight.wind_type || ''}`.trim() : '--' },
    { label: 'True airspeed (est.)', value: flight.tas_kt != null ? `${flight.tas_kt.toFixed(1)} kt` : '--' },
    { label: 'Ground speed', value: flight.ground_speed_kt != null ? `${flight.ground_speed_kt.toFixed(1)} kt` : '--' },
    { label: 'Heading', value: flight.heading_deg != null ? `${flight.heading_deg.toFixed(0)}°` : '--' },
    { label: 'Pressure altitude', value: flight.altitude_ft != null ? `${Number(flight.altitude_ft).toLocaleString()} ft` : '--' },
    { label: 'Fuel burn rate', value: flight.co2_burn_rate_kg_min != null ? `${flight.co2_burn_rate_kg_min.toFixed(2)} kg/min` : '--' },
    { label: 'Planning-horizon ETA', value: flight.logistics_eta_min != null ? `${flight.logistics_eta_min} min` : '--' },
    { label: 'Position', value: (flight.lat != null && flight.lon != null) ? `${flight.lat.toFixed(3)}, ${flight.lon.toFixed(3)}` : '--' },
    ];
  }, [flight]);

  return (
    <div style={styles.card}>
      <div style={styles.cardHead}>
        <div>
          <div style={styles.flightNumber}>{flight.flight_number || flight.hex_id || 'UNKNOWN'}</div>
          <div style={styles.flightId}>ICAO24 {flight.hex_id || '--'}</div>
        </div>
        <div style={{ ...styles.advisoryBadge, color: palette.fg, background: palette.bg, borderColor: palette.border }}>
          <span style={styles.advisoryStatus}>{band.status}</span>
          <span style={styles.advisorySeverity}>{band.severity}</span>
        </div>
      </div>

      <div style={styles.milestoneGrid}>
        <div style={styles.milestone}>
          <span style={styles.milestoneLabel}>Predicted Touchdown (TDT)</span>
          <span style={styles.milestoneValue}>{formatClock(tdt)}</span>
        </div>
        <div style={styles.milestone}>
          <span style={styles.milestoneLabel}>Median On-Block (OBT)</span>
          <span style={styles.milestoneValue}>{formatClock(obt)}</span>
        </div>
        <div style={styles.milestone}>
          <span style={styles.milestoneLabel}>Confidence Range</span>
          <span style={styles.confidenceValue}>{uncertainty != null ? `± ${uncertainty} min` : '--'}</span>
        </div>
      </div>

      <div style={styles.windowBand}>
        <span style={styles.windowLabel}>PASSENGER-READY WINDOW (80%)</span>
        <span style={styles.windowValue}>
          {window.start ? `${formatClock(window.start.toISOString())} – ${formatClock(window.end.toISOString())}` : '--'}
        </span>
      </div>

      {band.severity !== 'LOW' && (
        <div style={{ ...styles.advisoryLine, color: palette.fg }}>
          ⚠ {band.headline}
        </div>
      )}

      <DispatchWindow
        windowStart={windowStartIso}
        windowEnd={windowEndIso}
        expectedWait={dispatchWindow.expectedDriverWaitMinutes}
        confidence={dispatchWindow.confidence}
      />

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
  dispatchActive: {
    border: '1px solid #30caff',
    background: 'rgba(48, 202, 255, 0.14)',
  },
  dispatchLabelRow: { display: 'flex', alignItems: 'center', gap: '0.4rem' },
  dispatchKicker: { color: '#9fd9c4', fontSize: '0.64rem', letterSpacing: '0.1em' },
  dispatchValue: { color: '#f3fff9', fontSize: '1.3rem', fontWeight: 800 },
  dispatchSub: { color: '#9bb6d6', fontSize: '0.74rem' },
  dispatchPending: { color: '#9bb6d6', fontSize: '0.8rem', fontStyle: 'italic' },
  metricRow: { display: 'flex', flexWrap: 'wrap', gap: '0.4rem', marginTop: '0.45rem' },
  metricChip: {
    color: '#cfe3ff',
    fontSize: '0.72rem',
    border: '1px solid #1f3958',
    borderRadius: 8,
    padding: '0.25rem 0.5rem',
    background: 'rgba(10, 19, 38, 0.6)',
  },
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
