import { NavLink, useNavigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { supabase } from '../lib/supabase';
import { useAuth } from '../App';
import { getAdminMe } from '../lib/api';
import MobileMenu from './MobileMenu';

const BASE_LINKS = [
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/search', label: 'Search' },
  { to: '/alerts', label: 'Alerts' },
  { to: '/saved', label: 'Saved' },
  { to: '/notifications', label: 'Notifications' },
  { to: '/billing', label: 'Billing' },
  { to: '/settings', label: 'Settings' },
];

const ADMIN_LINKS = [
  { to: '/admin', label: 'Admin' },
  { to: '/analytics', label: 'Analytics' },
];

export default function Header() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [isAdmin, setIsAdmin] = useState(false);
  const [isMobile, setIsMobile] = useState(() => window.innerWidth < 640);

  useEffect(() => {
    if (!user) { setIsAdmin(false); return; }
    getAdminMe().then((d) => setIsAdmin(d.is_admin === true)).catch(() => setIsAdmin(false));
  }, [user]);

  useEffect(() => {
    const handler = () => setIsMobile(window.innerWidth < 640);
    window.addEventListener('resize', handler);
    return () => window.removeEventListener('resize', handler);
  }, []);

  const handleLogout = async () => {
    await supabase.auth.signOut();
    navigate('/');
  };

  const navLinkStyle = ({ isActive }) => ({
    ...styles.link,
    ...(isActive ? styles.activeLink : {}),
  });

  const allLinks = isAdmin ? [...BASE_LINKS, ...ADMIN_LINKS] : BASE_LINKS;

  return (
    <header style={styles.header}>
      <div style={styles.logo}>✈️ FlightAlertPro</div>

      {isMobile ? (
        <MobileMenu links={allLinks} onLogout={handleLogout} userEmail={user?.email} />
      ) : (
        <nav style={styles.nav}>
          {allLinks.map(({ to, label }) => (
            <NavLink key={to} to={to} style={navLinkStyle}>{label}</NavLink>
          ))}
          {user?.email && <span style={styles.userEmail}>{user.email}</span>}
          <button onClick={handleLogout} style={styles.logoutBtn}>Logout</button>
        </nav>
      )}
    </header>
  );
}

const styles = {
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '0.875rem 1.25rem',
    background: '#1d4ed8',
    color: '#fff',
    position: 'sticky',
    top: 0,
    zIndex: 100,
    boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
  },
  logo: {
    fontWeight: 'bold',
    fontSize: '1.15rem',
    whiteSpace: 'nowrap',
  },
  nav: {
    display: 'flex',
    alignItems: 'center',
    gap: '1.25rem',
    flexWrap: 'wrap',
  },
  link: {
    color: '#fff',
    textDecoration: 'none',
    fontWeight: '500',
    fontSize: '0.9rem',
  },
  activeLink: {
    textDecoration: 'underline',
    fontWeight: '700',
  },
  userEmail: {
    fontSize: '0.8rem',
    opacity: 0.8,
    maxWidth: '160px',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  logoutBtn: {
    background: 'transparent',
    border: '1px solid rgba(255,255,255,0.7)',
    color: '#fff',
    padding: '0.35rem 0.75rem',
    borderRadius: '4px',
    cursor: 'pointer',
    fontWeight: '500',
    fontSize: '0.875rem',
  },
};
