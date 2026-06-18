import { useState } from 'react';
import { apiFetch } from '../lib/api';

const AIRCRAFT_CATEGORIES = ['narrow_body', 'wide_body', 'regional', 'private'];

export default function DispatcherView() {
  const [form, setForm] = useState({
    flight_id: '',
    target_fbo: '',
    aircraft_category: 'narrow_body',
    altitude_ft: '',
    ground_speed_kt: '',
    scheduled_arrival: '',
    driver_transit_mean_min: 15,
  });
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showEngineering, setShowEngineering] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm(prev => ({ ...prev, [name]: value }));
  };

  const handleCalculate = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const data = await apiFetch('/api/dispatch/calculate', {
        method: 'POST',
        body: JSON.stringify({
          telemetry: {
            altitude_ft: Number(form.altitude_ft),
            ground_speed_kt: Number(form.ground_speed_kt),
            scheduled_arrival: form.scheduled_arrival || undefined,
          },
          fbo_data: { airport_category: 'medium_hub' },
          aircraft_category: form.aircraft_category,
          driver_transit_mean_min: Number(form.driver_transit_mean_min),
        }),
      });
      setResult(data);
    } catch (err) {
      setError(err.message || 'Calculation failed');
    } finally {
      setLoading(false);
    }
  };

  const dw = result?.dispatch_window;
  const pr = result?.passenger_ready;

  // Determine if arrival uncertainty is elevated
  const highUncertainty = pr && pr.sigma_minutes > 8;

  return (
    <div style={styles.page}>
      <h2 style={styles.heading}>AeroLogix Dispatch Console</h2>

      <form onSubmit={handleCalculate} style={styles.form}>
        <div style={styles.row}>
          <Field label="Flight ID">
            <input name="flight_id" value={form.flight_id} onChange={handleChange}
              placeholder="e.g. BA0117" style={styles.input} />
          </Field>
          <Field label="Target FBO">
            <input name="target_fbo" value={form.target_fbo} onChange={handleChange}
              placeholder="e.g. Signature LHR" style={styles.input} />
          </Field>
          <Field label="Aircraft Category">
            <select name="aircraft_category" value={form.aircraft_category}
              onChange={handleChange} style={styles.input}>
              {AIRCRAFT_CATEGORIES.map(c => (
                <option key={c} value={c}>{c.replace('_', ' ')}</option>
              ))}
            </select>
          </Field>
        </div>
        <div style={styles.row}>
          <Field label="Current Altitude (ft)">
            <input name="altitude_ft" type="number" value={form.altitude_ft}
              onChange={handleChange} placeholder="25000" style={styles.input} />
          </Field>
          <Field label="Ground Speed (kt)">
            <input name="ground_speed_kt" type="number" value={form.ground_speed_kt}
              onChange={handleChange} placeholder="420" style={styles.input} />
          </Field>
          <Field label="Scheduled Arrival (ISO)">
            <input name="scheduled_arrival" type="datetime-local" value={form.scheduled_arrival}
              onChange={handleChange} style={styles.input} />
          </Field>
          <Field label="Driver Transit (min)">
            <input name="driver_transit_mean_min" type="number" value={form.driver_transit_mean_min}
              onChange={handleChange} style={styles.input} />
          </Field>
        </div>
        {error && <p style={styles.error}>{error}</p>}
        <button type="submit" disabled={loading} style={styles.calcBtn}>
          {loading ? 'Calculating…' : 'Calculate Dispatch Window'}
        </button>
      </form>

      {result && dw && (
        <div style={styles.resultSection}>
          {/* Primary output card */}
          <div style={styles.windowCard}>
            <div style={styles.windowLabel}>Acceptable Dispatch Window</div>
            <div style={styles.windowValue}>{dw.dispatch_window_str}</div>
            <div style={styles.metricsRow}>
              <Metric label="Expected Driver Wait" value={`${dw.expected_driver_wait_min} mins`} />
              <Metric label="Recommendation Confidence"
                value={dw.recommendation_confidence}
                color={CONFIDENCE_COLORS[dw.recommendation_confidence]} />
              <Metric label="Prediction Sigma" value={`±${dw.total_sigma_minutes} min`} />
            </div>
          </div>

          {/* Uncertainty warning — replaces "Approach Instability" */}
          {highUncertainty && (
            <div style={styles.warningBanner}>
              Arrival Uncertainty Increased — sigma {pr.sigma_minutes.toFixed(1)} min.
              Widen driver standby window or monitor telemetry.
            </div>
          )}

          {/* Engineering Details (collapsed by default) */}
          <div style={styles.engineeringSection}>
            <button onClick={() => setShowEngineering(v => !v)} style={styles.engineeringToggle}>
              {showEngineering ? '▲' : '▼'} Engineering Details
            </button>
            {showEngineering && (
              <div style={styles.engineeringGrid}>
                <EngRow label="Predicted Touchdown" value={result.touchdown?.predicted_touchdown_utc} isTime />
                <EngRow label="Touchdown Method" value={result.touchdown?.method} />
                <EngRow label="Touchdown Sigma" value={`${result.touchdown?.sigma_minutes?.toFixed(1)} min`} />
                <EngRow label="Predicted On-Block" value={result.on_block?.predicted_on_block_utc} isTime />
                <EngRow label="Taxi Mean" value={`${result.on_block?.taxi_mean_min} min`} />
                <EngRow label="On-Block Sigma" value={`${result.on_block?.sigma_minutes?.toFixed(1)} min`} />
                <EngRow label="Passenger Ready" value={pr?.predicted_passenger_ready_utc} isTime />
                <EngRow label="Deplane Mean" value={`${pr?.deplane_mean_min} min`} />
                <EngRow label="Passenger Ready Sigma" value={`${pr?.sigma_minutes?.toFixed(1)} min`} />
                <EngRow label="Optimal Dispatch" value={dw?.optimal_dispatch_utc} isTime />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem', flex: 1, minWidth: '160px' }}>
      <label style={{ fontWeight: '600', fontSize: '0.8rem', color: '#6b7280' }}>{label}</label>
      {children}
    </div>
  );
}

function Metric({ label, value, color }) {
  return (
    <div style={{ textAlign: 'center' }}>
      <div style={{ fontSize: '0.75rem', color: '#9ca3af', marginBottom: '0.2rem' }}>{label}</div>
      <div style={{ fontWeight: '700', fontSize: '1rem', color: color || '#1d4ed8' }}>{value}</div>
    </div>
  );
}

function EngRow({ label, value, isTime }) {
  const display = isTime && value ? new Date(value).toLocaleTimeString() : (value ?? '—');
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.35rem 0',
      borderBottom: '1px solid #f3f4f6', fontSize: '0.85rem' }}>
      <span style={{ color: '#6b7280' }}>{label}</span>
      <span style={{ fontWeight: '600' }}>{display}</span>
    </div>
  );
}

const CONFIDENCE_COLORS = { High: '#16a34a', Moderate: '#d97706', Low: '#dc2626' };

const styles = {
  page: { maxWidth: '900px', margin: '2rem auto', padding: '0 1rem', fontFamily: 'system-ui, sans-serif' },
  heading: { fontSize: '1.6rem', fontWeight: '800', color: '#1d4ed8', marginBottom: '1.5rem' },
  form: { background: '#fff', padding: '1.5rem', borderRadius: '10px',
    boxShadow: '0 2px 12px rgba(0,0,0,0.08)', marginBottom: '1.5rem' },
  row: { display: 'flex', gap: '1rem', flexWrap: 'wrap', marginBottom: '1rem' },
  input: { padding: '0.5rem 0.75rem', border: '1px solid #d1d5db', borderRadius: '6px',
    fontSize: '0.95rem', width: '100%' },
  error: { color: '#dc2626', fontSize: '0.875rem' },
  calcBtn: { padding: '0.75rem 2rem', background: '#1d4ed8', color: '#fff', border: 'none',
    borderRadius: '8px', fontSize: '1rem', fontWeight: '700', cursor: 'pointer' },
  resultSection: { display: 'flex', flexDirection: 'column', gap: '1rem' },
  windowCard: { background: '#eff6ff', border: '2px solid #3b82f6', borderRadius: '12px',
    padding: '1.75rem', textAlign: 'center' },
  windowLabel: { fontSize: '0.85rem', fontWeight: '700', color: '#3b82f6',
    textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '0.5rem' },
  windowValue: { fontSize: '2.5rem', fontWeight: '900', color: '#1d4ed8', marginBottom: '1.25rem' },
  metricsRow: { display: 'flex', justifyContent: 'space-around', flexWrap: 'wrap', gap: '1rem' },
  warningBanner: { background: '#fef3c7', border: '1px solid #f59e0b', borderRadius: '8px',
    padding: '0.875rem 1.25rem', color: '#92400e', fontWeight: '600', fontSize: '0.9rem' },
  engineeringSection: { background: '#fff', borderRadius: '10px',
    boxShadow: '0 1px 6px rgba(0,0,0,0.06)', overflow: 'hidden' },
  engineeringToggle: { width: '100%', padding: '0.875rem 1.25rem', background: '#f9fafb',
    border: 'none', borderBottom: '1px solid #e5e7eb', textAlign: 'left',
    fontWeight: '700', fontSize: '0.9rem', cursor: 'pointer', color: '#374151' },
  engineeringGrid: { padding: '0.75rem 1.25rem' },
};
