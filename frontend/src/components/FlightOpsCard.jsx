import React, { useState } from 'react';
import { supabase } from '../lib/supabase';

export default function FlightOpsCard({ flight, policy }) {
  const [copying, setCopying] = useState(false);
  
  // Math logic
  const eta = flight.logistics_eta_min ? Math.round(flight.logistics_eta_min) : 30;
  const variance = flight.confidence_interval_min || 5;
  const minWindow = eta - variance;
  const maxWindow = eta + variance;

  // Apply Service Policy Buffer
  let policyBuffer = 15; // Balanced (Arrive 15 mins early)
  let policyName = "Standard Buffer";
  if (policy === 'EFFICIENCY') { policyBuffer = 5; policyName = "Just-in-Time (High Risk)"; }
  if (policy === 'VIP_PROTECTED') { policyBuffer = 45; policyName = "Zero-Wait Buffer"; }
  
  const recommendedDispatch = Math.max(0, minWindow - policyBuffer);

  const copySecureLink = async () => {
    setCopying(true);
    const { data } = await supabase.from('operational_ledger').select('session_token').eq('flight_id', flight.hex_id).single();
    if (data?.session_token) {
      navigator.clipboard.writeText(`${window.location.origin}/driver/session/${data.session_token}`);
      alert('Secure encrypted driver link copied!');
    } else {
      alert('Awaiting uplink. Session token not yet generated.');
    }
    setCopying(false);
  };

  return (
    <div style={{ border: '1px solid #1f3958', borderRadius: 12, padding: '1.2rem', background: '#0a1122', display: 'flex', flexDirection: 'column', gap: '0.8rem', boxShadow: '0 4px 12px rgba(0,0,0,0.2)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: '1.3rem', fontWeight: '900', color: '#fff', letterSpacing: '1px' }}>{flight.flight_number || flight.hex_id}</span>
        <span style={{ color: flight.late_risk === 'High' ? '#ff4d4d' : '#5ff8bf', fontSize: '0.7rem', fontWeight: 'bold', padding: '2px 6px', background: 'rgba(255,255,255,0.05)', borderRadius: 4 }}>
          RISK: {flight.late_risk || 'MODERATE'}
        </span>
      </div>
      
      <div style={{ display: 'flex', justifyContent: 'space-between', color: '#82a4cb', fontSize: '0.85rem' }}>
        <span>ETA: {eta} min</span>
        <span>Uncertainty: ±{variance}m</span>
      </div>

      <div style={{ background: '#060b18', padding: '1rem', borderRadius: 8, border: `1px solid ${policy === 'VIP_PROTECTED' ? '#ffd27a' : '#1f3958'}` }}>
        <div style={{ color: '#7ea5d6', fontSize: '0.7rem', textTransform: 'uppercase', marginBottom: '0.3rem' }}>Recommended Dispatch Time</div>
        <div style={{ color: '#fff', fontSize: '1.2rem', fontWeight: 'bold' }}>T-Minus {recommendedDispatch} min</div>
        <div style={{ color: policy === 'VIP_PROTECTED' ? '#ffd27a' : '#9bb6d6', fontSize: '0.75rem', marginTop: '0.3rem' }}>
          {policyName} applied to baseline {minWindow}m window.
        </div>
      </div>
      
      <div style={{ color: '#82a4cb', fontSize: '0.75rem', marginTop: '0.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span>Advisory: <span style={{ color: flight.performance_advisory !== 'NOMINAL' ? '#ff4d4d' : '#5ff8bf' }}>{flight.performance_advisory || 'NOMINAL'}</span></span>
        <button disabled={copying} onClick={copySecureLink} style={{ background: 'rgba(47, 202, 255, 0.1)', border: '1px solid #2fcaff', color: '#2fcaff', cursor: 'pointer', fontWeight: 'bold', padding: '0.3rem 0.6rem', borderRadius: 4 }}>
          {copying ? 'Encrypting...' : '📋 Driver Link'}
        </button>
      </div>
    </div>
  );
}
