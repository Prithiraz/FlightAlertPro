export default function TelemetryPanel({ telemetry, loading, error }) {
  if (loading) return <div style={styles.message}>Awaiting uplink…</div>;
  if (error) return <div style={{ ...styles.message, color: '#ff6b8a' }}>{error}</div>;
  if (!telemetry.length) return <div style={styles.message}>No aircraft currently tracked.</div>;

  return (
    <div style={styles.panel}>
      <div style={styles.header}>LIVE FLIGHT TELEMETRY</div>
      <div style={styles.gridHead}>
        <span>Flight</span>
        <span>TAS</span>
        <span>Wind</span>
        <span>Density Alt</span>
        <span>CO2 Burn</span>
        <span>Logistics ETA</span>
      </div>
      {telemetry.map((flight) => (
        <div key={flight.hex_id} style={styles.row}>
          <div>
            <div style={styles.flightCode}>{flight.flight_number || flight.hex_id}</div>
            <div style={styles.subText}>
              HDG {flight.heading_deg?.toFixed?.(0) ?? '--'}° · GS {flight.ground_speed_kt?.toFixed?.(1) ?? '--'} kts
            </div>
          </div>
          <span>{flight.tas_kt?.toFixed?.(1) ?? '--'} kts</span>
          <span style={{ color: (flight.wind_component_kt ?? 0) >= 0 ? '#40fbb5' : '#ff6b8a' }}>
            {(flight.wind_component_kt ?? 0) >= 0 ? '+' : ''}{flight.wind_component_kt?.toFixed?.(1) ?? '--'} kts
          </span>
          <span>{flight.density_altitude_ft?.toLocaleString?.() ?? '--'} ft</span>
          <span>{flight.co2_burn_rate_kg_min?.toFixed?.(2) ?? '--'} kg/min</span>
          <span style={styles.etaBadge}>{flight.logistics_eta_min ?? '--'} min</span>
        </div>
      ))}
    </div>
  );
}

const styles = {
  panel: {
    border: '1px solid #1f3958',
    borderRadius: 12,
    background: 'rgba(7, 13, 27, 0.85)',
    padding: '1rem',
    display: 'flex',
    flexDirection: 'column',
    gap: '0.6rem',
  },
  header: {
    color: '#5eeaff',
    fontWeight: 700,
    letterSpacing: '0.08em',
    fontSize: '0.9rem',
  },
  gridHead: {
    display: 'grid',
    gridTemplateColumns: '1.6fr repeat(5, 1fr)',
    color: '#7ea5d6',
    fontSize: '0.75rem',
    textTransform: 'uppercase',
  },
  row: {
    display: 'grid',
    gridTemplateColumns: '1.6fr repeat(5, 1fr)',
    alignItems: 'center',
    gap: '0.5rem',
    color: '#d9ebff',
    borderTop: '1px solid #132743',
    paddingTop: '0.55rem',
    fontSize: '0.85rem',
  },
  flightCode: { fontWeight: 700 },
  subText: { color: '#88a5c6', fontSize: '0.74rem' },
  etaBadge: {
    justifySelf: 'start',
    background: '#152d47',
    border: '1px solid #2e5b8c',
    borderRadius: 999,
    padding: '0.2rem 0.6rem',
    color: '#75ffcf',
    fontWeight: 700,
  },
  message: {
    border: '1px solid #1f3958',
    borderRadius: 12,
    background: 'rgba(7, 13, 27, 0.85)',
    color: '#9bb6d6',
    padding: '1rem',
    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
  },
};
