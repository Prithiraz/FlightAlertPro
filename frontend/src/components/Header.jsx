import { NavLink, useNavigate } from 'react-router-dom';
import { supabase } from '../lib/supabase';
import { useAuth } from '../App';

export default function Header() {
  const navigate = useNavigate();
  const { user } = useAuth();

  const handleLogout = async () => {
    await supabase.auth.signOut();
    navigate('/');
  };

  const navLinkStyle = ({ isActive }) => ({
    color: isActive ? '#5eeaff' : '#9bb6d6',
    textDecoration: 'none',
    fontWeight: isActive ? '700' : '500',
    transition: 'color 0.2s',
  });

  return (
    <header style={{ 
      background: '#0a1122', 
      padding: '1rem 2rem', 
      borderBottom: '1px solid #1f3958', 
      display: 'flex', 
      justifyContent: 'space-between', 
      alignItems: 'center',
      fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace'
    }}>
      <div style={{ color: '#5eeaff', fontSize: '1.4rem', fontWeight: '800', letterSpacing: '1px' }}>
        AeroLogix <span style={{ color: '#7ea5d6', fontSize: '1rem', fontWeight: '500' }}>Dispatch</span>
      </div>
      
      <nav style={{ display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
        <NavLink to="/dashboard" style={navLinkStyle}>Command Center</NavLink>
        <NavLink to="/settings" style={navLinkStyle}>Settings</NavLink>
        
        {user?.email && <span style={{ color: '#82a4cb', fontSize: '0.875rem' }}>{user.email}</span>}
        
        <button 
          onClick={handleLogout} 
          style={{ 
            background: 'rgba(47, 202, 255, 0.1)', 
            border: '1px solid #2fcaff', 
            color: '#2fcaff', 
            padding: '0.4rem 1rem', 
            borderRadius: '6px', 
            cursor: 'pointer', 
            fontWeight: 'bold',
          }}
        >
          Logout
        </button>
      </nav>
    </header>
  );
}
