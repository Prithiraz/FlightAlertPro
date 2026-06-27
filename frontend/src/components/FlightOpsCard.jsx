import React, { useState } from 'react';
import { supabase } from '../lib/supabase';

export default function FlightOpsCard({ flight }) {
  const [copying, setCopying] = useState(false);
  const isSimulated = flight.flight_number?.includes('[SIMULATED]');
  const cleanFlightNumber = flight.flight_number?.replace('[SIMULATED]', '').trim() || flight.hex_id;
  
  const eta = flight.logistics_eta_min ? Math.round(flight.logistics_eta_min) : 30;
  const variance = flight.confidence_interval_min || 5;
  const minWindow = eta - variance;
  const maxWindow = eta + variance;

  const copySecureLink = async () => {
    setCopying(true);
    // Ask Supabase for the cryptographic token assigned to this flight
    const { data } = await supabase
      .from('operational_ledger')
      .select('session_token')
      .eq('flight_id', flight.hex_id)
      .single();

    if (data?.session_token) {
      navigator.clipboard.writeText(`${window.location.origin}/driver/session/${data.session_token}`);
      alert('Secure encrypted driver link copied to clipboard!');
    } else {
      alert('Awaiting uplink. Session token not yet generated for this flight.');
    }
    setCopying(false);
  };

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
        <button 
          disabled={copying}
          onClick={copySecureLink} 
          style={{ background: 'none', border: 'none', color: copying ? '#82a4cb' : '#2fcaff', cursor: 'pointer', fontWeight: 'bold', padding: 0 }}
        >
          {copying ? 'Encrypting...' : '📋 Copy Secure Link'}
        </button>
      </div>
    </div>
  );
}
