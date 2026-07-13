import { useAuth } from '../App';
import { supabase } from '../lib/supabase';
import { Link, useLocation } from 'react-router-dom';

export default function Header() {
  const { user } = useAuth();
  const location = useLocation();

  const handleLogout = async () => {
    await supabase.auth.signOut();
  };

  const navLinkStyle = (path) => ({
    color: location.pathname === path ? '#2fcaff' : '#82a4cb',
    textDecoration: 'none',
    fontWeight: location.pathname === path ? 'bold' : 'normal',
    fontSize: '0.9rem',
    marginRight: '1.5rem'
  });

  return (
    <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1rem 2rem', background: '#0a1122', borderBottom: '1px solid #1f3958', fontFamily: 'ui-monospace, SFMono-Regular, monospace' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '2rem' }}>
        <h1 style={{ color: '#5eeaff', fontSize: '1.2rem', margin: 0 }}>AeroLogix <span style={{ color: '#7ea5d6', fontWeight: 'normal' }}>Dispatch</span></h1>
        <nav>
          <Link to="/" style={navLinkStyle('/')}>Command Center</Link>
          <Link to="/analytics" style={navLinkStyle('/analytics')}>Analytics & ROI</Link>
          <Link to="/settings" style={navLinkStyle('/settings')}>Settings</Link>
        </nav>
      </div>
      
      <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
        {user?.email && <span style={{ color: '#82a4cb', fontSize: '0.85rem' }}>{user.email}</span>}
        <button onClick={handleLogout} style={{ background: 'rgba(47, 202, 255, 0.1)', border: '1px solid #2fcaff', color: '#2fcaff', padding: '0.4rem 1rem', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }}>
          Logout
        </button>
      </div>
    </header>
  );
}
