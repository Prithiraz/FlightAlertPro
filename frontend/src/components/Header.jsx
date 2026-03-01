import { NavLink, useNavigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { supabase } from '../lib/supabase';
import { useAuth } from '../App';
import { getAdminMe } from '../lib/api';

export default function Header() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [isAdmin, setIsAdmin] = useState(false);

  useEffect(() => {
    if (!user) { setIsAdmin(false); return; }
    getAdminMe().then((d) => setIsAdmin(d.is_admin === true)).catch(() => setIsAdmin(false));
  }, [user]);

  const handleLogout = async () => {
    await supabase.auth.signOut();
    navigate('/');
  };

  const navLinkStyle = ({ isActive }) => ({
    ...styles.link,
    ...(isActive ? styles.activeLink : {}),
  });

  return (
    <header style={styles.header}>
      <div style={styles.logo}>✈️ FlightAlertPro</div>
      <nav style={styles.nav}>
        <NavLink to="/dashboard" style={navLinkStyle}>Dashboard</NavLink>
        <NavLink to="/search" style={navLinkStyle}>Search</NavLink>
        <NavLink to="/alerts" style={navLinkStyle}>Alerts</NavLink>
        <NavLink to="/saved" style={navLinkStyle}>Saved</NavLink>
        <NavLink to="/notifications" style={navLinkStyle}>Notifications</NavLink>
        <NavLink to="/billing" style={navLinkStyle}>Billing</NavLink>
        <NavLink to="/settings" style={navLinkStyle}>Settings</NavLink>
        {isAdmin && <NavLink to="/admin" style={navLinkStyle}>Admin</NavLink>}
        {isAdmin && <NavLink to="/analytics" style={navLinkStyle}>Analytics</NavLink>}
        {user?.email && <span style={styles.userEmail}>{user.email}</span>}
        <button onClick={handleLogout} style={styles.logoutBtn}>Logout</button>
      </nav>
    </header>
  );
}

const styles = {
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '1rem 2rem',
    background: '#1d4ed8',
    color: '#fff',
  },
  logo: {
    fontWeight: 'bold',
    fontSize: '1.25rem',
  },
  nav: {
    display: 'flex',
    alignItems: 'center',
    gap: '1.5rem',
  },
  link: {
    color: '#fff',
    textDecoration: 'none',
    fontWeight: '500',
  },
  activeLink: {
    textDecoration: 'underline',
    opacity: 1,
    fontWeight: '700',
  },
  userEmail: {
    fontSize: '0.875rem',
    opacity: 0.85,
  },
  logoutBtn: {
    background: 'transparent',
    border: '1px solid #fff',
    color: '#fff',
    padding: '0.375rem 0.75rem',
    borderRadius: '4px',
    cursor: 'pointer',
    fontWeight: '500',
  },
};
