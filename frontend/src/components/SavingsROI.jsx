import { useState } from 'react';

const DEFAULT_WAIT_PREVENTED_MIN = 25;
const DEFAULT_HOURLY_RATE = 65;

export default function SavingsROI({ flightCount = 0 }) {
  const [waitPerFlight, setWaitPerFlight] = useState(DEFAULT_WAIT_PREVENTED_MIN);
  const [hourlyRate, setHourlyRate] = useState(DEFAULT_HOURLY_RATE);

  const flights = Math.max(0, flightCount);
  const totalWaitPreventedMin = waitPerFlight * Math.max(1, flights);
  const savings = (totalWaitPreventedMin / 60) * hourlyRate;

  return (
    <div style={styles.panel}>
      <div style={styles.header}>SAVINGS ROI</div>
      <div style={styles.subhead}>
        Driver wait time prevented by precision dispatch, valued at the driver hourly rate.
      </div>

      <div style={styles.inputs}>
        <label style={styles.field}>
          <span style={styles.fieldLabel}>Wait prevented / flight (min)</span>
          <input
            type="number"
            min="0"
            value={waitPerFlight}
            onChange={(e) => setWaitPerFlight(Math.max(0, Number(e.target.value) || 0))}
            style={styles.input}
          />
        </label>
        <label style={styles.field}>
          <span style={styles.fieldLabel}>Driver hourly rate ($)</span>
          <input
            type="number"
            min="0"
            value={hourlyRate}
            onChange={(e) => setHourlyRate(Math.max(0, Number(e.target.value) || 0))}
            style={styles.input}
          />
        </label>
      </div>

      <div style={styles.formula}>
        ({totalWaitPreventedMin.toLocaleString()} min prevented across {Math.max(1, flights)} flight{flights === 1 ? '' : 's'})
        {' × '}${hourlyRate}/hr
      </div>

      <div style={styles.resultBlock}>
        <span style={styles.resultLabel}>Estimated Savings</span>
        <span style={styles.resultValue}>
          ${savings.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </span>
      </div>
    </div>
  );
}

const styles = {
  panel: {
    border: '1px solid #1f3958',
    borderRadius: 14,
    background: 'rgba(7, 13, 27, 0.88)',
    padding: '1rem',
    display: 'flex',
    flexDirection: 'column',
    gap: '0.6rem',
  },
  header: { color: '#5eeaff', fontWeight: 700, letterSpacing: '0.08em', fontSize: '0.9rem' },
  subhead: { color: '#82a4cb', fontSize: '0.78rem' },
  inputs: { display: 'flex', gap: '0.6rem', flexWrap: 'wrap' },
  field: { display: 'flex', flexDirection: 'column', gap: '0.25rem', flex: '1 1 160px' },
  fieldLabel: { color: '#7ea5d6', fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.03em' },
  input: {
    background: 'rgba(4, 9, 18, 0.8)',
    border: '1px solid #1f3958',
    borderRadius: 8,
    color: '#ecf7ff',
    padding: '0.5rem 0.6rem',
    fontSize: '0.95rem',
    fontFamily: 'inherit',
  },
  formula: { color: '#88a5c6', fontSize: '0.76rem' },
  resultBlock: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    border: '1px solid #2a946f',
    background: 'rgba(31, 172, 125, 0.12)',
    borderRadius: 12,
    padding: '0.7rem 0.9rem',
  },
  resultLabel: { color: '#9fd9c4', fontSize: '0.74rem', letterSpacing: '0.06em', textTransform: 'uppercase' },
  resultValue: { color: '#5ff8bf', fontSize: '1.6rem', fontWeight: 800 },
};
