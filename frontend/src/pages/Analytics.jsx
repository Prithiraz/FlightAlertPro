import React, { useState } from 'react';

export default function Analytics() {
  const [policy, setPolicy] = useState('BALANCED');
  
  // Simulated historical metrics based on the policy selected
  const metrics = {
    EFFICIENCY: { waitSaved: 142, lateRisk: '8%', reliability: '92%' },
    BALANCED: { waitSaved: 95, lateRisk: '2%', reliability: '98%' },
    VIP_PROTECTED: { waitSaved: 35, lateRisk: '0%', reliability: '100%' }
  };

  const currentMetrics = metrics[policy];

  return (
    <div style={{ padding: '2rem', maxWidth: '1000px', margin: '0 auto', color: '#d9ebff', fontFamily: 'monospace' }}>
      
      <div style={{ borderBottom: '1px solid #1f3958', paddingBottom: '1rem', marginBottom: '2rem' }}>
        <div style={{ color: '#5eeaff', letterSpacing: '2px', fontSize: '0.8rem', fontWeight: 'bold' }}>AEROLOGIX · BUSINESS INTELLIGENCE</div>
        <h1 style={{ margin: '0.5rem 0', fontSize: '2rem', color: '#fff' }}>ROI & Validation Analytics</h1>
        <p style={{ color: '#82a4cb' }}>Evaluating past 500 flight arrivals against standard 45-minute driver wait times.</p>
      </div>

      <div style={{ display: 'flex', gap: '1rem', marginBottom: '2rem' }}>
        {['EFFICIENCY', 'BALANCED', 'VIP_PROTECTED'].map(p => (
          <button 
            key={p} 
            onClick={() => setPolicy(p)} 
            style={{ padding: '0.8rem 1.5rem', background: policy === p ? '#2fcaff' : '#0a1122', color: policy === p ? '#04080f' : '#82a4cb', border: '1px solid #1f3958', borderRadius: '6px', fontWeight: 'bold', cursor: 'pointer' }}
          >
            Test {p.replace('_', ' ')} Policy
          </button>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1.5rem' }}>
        <div style={{ background: '#0a1122', border: '1px solid #1f3958', padding: '1.5rem', borderRadius: '8px' }}>
          <div style={{ color: '#7ea5d6', fontSize: '0.8rem', textTransform: 'uppercase' }}>Driver Idle Hours Prevented</div>
          <div style={{ color: '#5ff8bf', fontSize: '2.5rem', fontWeight: 'bold', margin: '0.5rem 0' }}>{currentMetrics.waitSaved} hrs</div>
          <div style={{ color: '#82a4cb', fontSize: '0.8rem' }}>At $65/hr: <strong>${currentMetrics.waitSaved * 65} saved</strong></div>
        </div>

        <div style={{ background: '#0a1122', border: '1px solid #1f3958', padding: '1.5rem', borderRadius: '8px' }}>
          <div style={{ color: '#7ea5d6', fontSize: '0.8rem', textTransform: 'uppercase' }}>On-Time Reliability</div>
          <div style={{ color: '#fff', fontSize: '2.5rem', fontWeight: 'bold', margin: '0.5rem 0' }}>{currentMetrics.reliability}</div>
          <div style={{ color: '#82a4cb', fontSize: '0.8rem' }}>Driver arrived before passenger.</div>
        </div>

        <div style={{ background: '#0a1122', border: '1px solid #1f3958', padding: '1.5rem', borderRadius: '8px' }}>
          <div style={{ color: '#7ea5d6', fontSize: '0.8rem', textTransform: 'uppercase' }}>Late Pickup Risk</div>
          <div style={{ color: currentMetrics.lateRisk === '0%' ? '#5ff8bf' : '#ff4d4d', fontSize: '2.5rem', fontWeight: 'bold', margin: '0.5rem 0' }}>{currentMetrics.lateRisk}</div>
          <div style={{ color: '#82a4cb', fontSize: '0.8rem' }}>Instances of passenger waiting.</div>
        </div>
      </div>

    </div>
  );
}
