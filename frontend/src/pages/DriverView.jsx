import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { supabase } from '../lib/supabase';

export default function DriverView() {
  const { flightId } = useParams();
  const [status, setStatus] = useState('pending');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchStatus = async () => {
      const { data } = await supabase
        .from('operational_ledger')
        .select('status')
        .eq('flight_id', flightId)
        .single();
      
      if (data) setStatus(data.status);
    };
    fetchStatus();
  }, [flightId]);

  const updateLedger = async (newStatus, timestampColumn) => {
    setLoading(true);
    const updateData = { status: newStatus, updated_at: new Date().toISOString() };
    if (timestampColumn) {
      updateData[timestampColumn] = new Date().toISOString();
    }

    const { error: supabaseError } = await supabase
      .from('operational_ledger')
      .update(updateData)
      .eq('flight_id', flightId);

    if (supabaseError) {
      setError('Database uplink failed. Try again.');
    } else {
      setStatus(newStatus);
      setError(null);
    }
    setLoading(false);
  };

  return (
    <div style={{ minHeight: '100vh', background: '#04080f', color: '#fff', fontFamily: 'ui-monospace, SFMono-Regular, monospace', padding: '2rem 1rem', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      <div style={{ textAlign: 'center', marginBottom: '3rem' }}>
        <div style={{ color: '#5eeaff', fontSize: '0.8rem', letterSpacing: '2px' }}>AEROLOGIX FIELD OPS</div>
        <h1 style={{ fontSize: '2rem', margin: '0.5rem 0' }}>Flight {flightId}</h1>
      </div>

      {error && <div style={{ color: '#ff8d8d', marginBottom: '1rem' }}>{error}</div>}

      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', width: '100%', maxWidth: '400px' }}>
        <button 
          disabled={loading || status !== 'pending'}
          onClick={() => updateLedger('dispatched', null)}
          style={{ padding: '1.5rem', fontSize: '1.2rem', fontWeight: 'bold', borderRadius: '12px', background: status === 'pending' ? '#1f3958' : '#0a1122', color: status === 'pending' ? '#fff' : '#4a5b75', border: '1px solid #2fcaff', cursor: 'pointer', transition: 'all 0.2s' }}
        >
          {status === 'pending' ? 'Confirm Dispatch' : 'Dispatched ✓'}
        </button>

        <button 
          disabled={loading || status !== 'dispatched'}
          onClick={() => updateLedger('at_fbo', 'arrived_at_fbo_at')}
          style={{ padding: '1.5rem', fontSize: '1.2rem', fontWeight: 'bold', borderRadius: '12px', background: status === 'dispatched' ? '#1f3958' : '#0a1122', color: status === 'dispatched' ? '#fff' : '#4a5b75', border: '1px solid #5ff8bf', cursor: 'pointer', transition: 'all 0.2s' }}
        >
          {status === 'at_fbo' || status === 'completed' ? 'At FBO ✓' : 'I Have Arrived at FBO'}
        </button>

        <button 
          disabled={loading || status !== 'at_fbo'}
          onClick={() => updateLedger('completed', 'passenger_collected_at')}
          style={{ padding: '1.5rem', fontSize: '1.2rem', fontWeight: 'bold', borderRadius: '12px', background: status === 'at_fbo' ? '#5eeaff' : '#0a1122', color: status === 'at_fbo' ? '#04080f' : '#4a5b75', border: 'none', cursor: 'pointer', transition: 'all 0.2s' }}
        >
          {status === 'completed' ? 'Mission Complete ✓' : 'Passenger Collected'}
        </button>
      </div>
    </div>
  );
}
