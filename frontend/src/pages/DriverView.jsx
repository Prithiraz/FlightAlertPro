import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { supabase } from '../lib/supabase';

export default function DriverView() {
  const { flightId } = useParams();
  const [status, setStatus] = useState('pending');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchStatus = async () => {
      const { data } = await supabase.from('operational_ledger').select('status').eq('flight_id', flightId).single();
      if (data) setStatus(data.status);
    };
    fetchStatus();
  }, [flightId]);

  const updateLedger = async (newStatus, timestampColumn) => {
    setLoading(true);
    const updateData = { status: newStatus, updated_at: new Date().toISOString() };
    if (timestampColumn) updateData[timestampColumn] = new Date().toISOString();
    const { error } = await supabase.from('operational_ledger').update(updateData).eq('flight_id', flightId);
    if (!error) setStatus(newStatus);
    setLoading(false);
  };

  return (
    <div style={{ minHeight: '100vh', background: '#04080f', color: '#fff', fontFamily: 'ui-monospace, SFMono-Regular, monospace', padding: '2rem 1rem', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
        <div style={{ color: '#5eeaff', fontSize: '0.8rem', letterSpacing: '2px' }}>SECURE DISPATCH NODE</div>
        <h1 style={{ fontSize: '1.5rem', margin: '0.5rem 0', color: '#7ea5d6' }}>Link: {flightId.substring(0,8)}...</h1>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', width: '100%', maxWidth: '400px' }}>
        <button disabled={loading || status !== 'pending'} onClick={() => updateLedger('in_position', 'driver_in_position_at')} style={{ padding: '1.2rem', fontSize: '1.1rem', fontWeight: 'bold', background: status === 'pending' ? '#1f3958' : '#0a1122', color: '#fff', border: '1px solid #2fcaff', borderRadius: '8px' }}>
          {status === 'pending' ? '1. Driver in Position' : '✓ In Position'}
        </button>
        <button disabled={loading || status !== 'in_position'} onClick={() => updateLedger('passenger_met', 'passenger_met_at')} style={{ padding: '1.2rem', fontSize: '1.1rem', fontWeight: 'bold', background: status === 'in_position' ? '#1f3958' : '#0a1122', color: '#fff', border: '1px solid #ffd27a', borderRadius: '8px' }}>
          {status === 'in_position' || status === 'departed' ? '✓ Passenger Met' : '2. Passenger Met'}
        </button>
        <button disabled={loading || status !== 'passenger_met'} onClick={() => updateLedger('departed', 'vehicle_departed_at')} style={{ padding: '1.2rem', fontSize: '1.1rem', fontWeight: 'bold', background: status === 'passenger_met' ? '#5ff8bf' : '#0a1122', color: status === 'passenger_met' ? '#04080f' : '#fff', border: status === 'passenger_met' ? 'none' : '1px solid #1f3958', borderRadius: '8px' }}>
          {status === 'departed' ? '✓ Vehicle Departed' : '3. Vehicle Departed'}
        </button>
      </div>
    </div>
  );
}
