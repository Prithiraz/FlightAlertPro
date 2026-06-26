import React from 'react';

export default function FlightOpsCard({ flight }) {
  // 1. Honesty Check: Detect if the backend tagged this as mock data
  const isSimulated = flight.flight_number?.includes('[SIMULATED]');
  const cleanFlightNumber = flight.flight_number?.replace('[SIMULATED]', '').trim() || flight.hex_id;
  
  // 2. Math Calculations based on the new Physics Engine
  const eta = flight.logistics_eta_min ? Math.round(flight.logistics_eta_min) : 30;
  const variance = flight.confidence_interval_min || 5;
  const minWindow = eta - variance;
  const maxWindow = eta + variance;

  return (
    <div style={{ border: '1px solid #1f3958', borderRadius: '12px', padding: '1.2rem', background: 'rgba(6, 11, 24, 0.82)', display: 'flex', flexDirection: 'column', gap: '0.8rem', boxShadow: '0 4px 6px rgba(0,0,0,0.3)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ fontSize: '1.2rem', fontWeight: 'bold', color: '#f5fbff' }}>{cleanFlightNumber}</span>
          {isSimulated && (
            <span style={{ background: '#ff4d4d', color: '#fff', padding: '2px 6px', borderRadius: '4px', fontSize: '0.65rem', fontWeight: 'bold', letterSpacing: '1px' }}>
              SIMULATED
            </span>
          )}
        </div>
        <span style={{ color: flight.late_risk === 'High' ? '#ff8d8d' : '#5ff8bf', fontSize: '0.75rem', fontWeight: 'bold', textTransform: 'uppercase' }}>
          Risk: {flight.late_risk || 'Moderate'}
        </span>
      </div>
      
      <div style={{ display: 'flex', justifyContent: 'space-between', color: '#82a4cb', fontSize: '0.85rem' }}>
        <span>Predicted ETA: {eta} min</span>
        <span>Confidence: ± {variance} min</span>
      </div>

      <div style={{ background: '#101d36', padding: '1rem', borderRadius: '8px', border: '1px solid #1f3958' }}>
        <div style={{ color: '#7ea5d6', fontSize: '0.75rem', textTransform: 'uppercase', marginBottom: '0.5rem' }}>Dispatch Intelligence</div>
        <div style={{ color: '#fff', fontSize: '1.05rem', fontWeight: 'bold' }}>
          Acceptable Window: {minWindow}m – {maxWindow}m
        </div>
        <div style={{ color: '#9bb6d6', fontSize: '0.85rem', marginTop: '0.2rem' }}>
          Expected Wait: {flight.expected_wait_min || 10} min
        </div>
      </div>
      
      <div style={{ color: '#82a4cb', fontSize: '0.75rem', marginTop: '0.5rem', display: 'flex', justifyContent: 'space-between' }}>
        <span>Advisory: <span style={{ color: flight.performance_advisory !== 'NOMINAL' ? '#ffd27a' : '#5ff8bf' }}>{flight.performance_advisory || 'NOMINAL'}</span></span>
        <span style={{ color: '#2fcaff', cursor: 'pointer', fontWeight: 'bold' }} onClick={() => navigator.clipboard.writeText(`${window.location.origin}/driver/${flight.hex_id}`)}>
          📋 Copy Driver Link
        </span>
      </div>
    </div>
  );
}
