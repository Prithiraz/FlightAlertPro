import { useState } from 'react';
import { supabase } from '../lib/supabase';
import { Link } from 'react-router-dom';

export default function Auth() {
  const [loading, setLoading] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isSignUp, setIsSignUp] = useState(false);
  const [message, setMessage] = useState('');

  const handleAuth = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage('');
    const { error } = isSignUp
      ? await supabase.auth.signUp({ email, password })
      : await supabase.auth.signInWithPassword({ email, password });
    if (error) setMessage(error.message);
    setLoading(false);
  };

  return (
    <div style={{ position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#04080f', fontFamily: 'ui-monospace, SFMono-Regular, monospace', zIndex: 9999 }}>
      <div style={{ width: '100%', maxWidth: '400px', padding: '2.5rem', background: '#0a1122', borderRadius: '12px', border: '1px solid #1f3958', boxShadow: '0 0 40px rgba(47, 202, 255, 0.1)' }}>
        <div style={{ textAlign: 'center', marginBottom: '2.5rem' }}>
          <h1 style={{ color: '#5eeaff', fontSize: '2rem', margin: 0, fontWeight: '800' }}>
            AeroLogix <span style={{ color: '#7ea5d6', fontWeight: '500', fontSize: '1.2rem' }}>Dispatch</span>
          </h1>
          <p style={{ color: '#82a4cb', fontSize: '0.9rem', marginTop: '0.5rem' }}>Secure Chauffeur Logistics Portal</p>
        </div>
        <form onSubmit={handleAuth} style={{ display: 'flex', flexDirection: 'column', gap: '1.2rem' }}>
          <div>
            <label style={{ display: 'block', color: '#9bb6d6', marginBottom: '0.5rem', fontSize: '0.85rem' }}>Dispatcher Email</label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required style={{ width: '100%', padding: '0.85rem', background: '#060b18', border: '1px solid #1f3958', borderRadius: '6px', color: '#fff', outline: 'none', boxSizing: 'border-box' }} />
          </div>
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
              <label style={{ color: '#9bb6d6', fontSize: '0.85rem' }}>Passcode</label>
              {!isSignUp && (
                <Link to="/reset" style={{ color: '#7ea5d6', fontSize: '0.85rem', textDecoration: 'none' }}>Forgot password?</Link>
              )}
            </div>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required style={{ width: '100%', padding: '0.85rem', background: '#060b18', border: '1px solid #1f3958', borderRadius: '6px', color: '#fff', outline: 'none', boxSizing: 'border-box' }} />
          </div>
          <button type="submit" disabled={loading} style={{ width: '100%', padding: '1rem', background: loading ? '#1f3958' : '#2fcaff', color: loading ? '#82a4cb' : '#04080f', border: 'none', borderRadius: '6px', fontWeight: 'bold', cursor: loading ? 'not-allowed' : 'pointer', marginTop: '1rem', fontSize: '1rem' }}>
            {loading ? 'Authenticating...' : (isSignUp ? 'Create Access Node' : 'Initialize Session')}
          </button>
        </form>
        {message && <p style={{ color: message.includes('successful') ? '#5ff8bf' : '#ff8d8d', textAlign: 'center', marginTop: '1.5rem', fontSize: '0.85rem' }}>{message}</p>}
        
        <div style={{ textAlign: 'center', marginTop: '1.5rem', paddingTop: '1.5rem', borderTop: '1px solid #1f3958' }}>
          <button onClick={() => setIsSignUp(!isSignUp)} style={{ background: 'none', border: 'none', color: '#7ea5d6', cursor: 'pointer', fontSize: '0.85rem' }}>
            {isSignUp ? 'Already have an account? Sign In' : 'Request Dispatcher Access (Sign Up)'}
          </button>
        </div>
      </div>
    </div>
  );
}
