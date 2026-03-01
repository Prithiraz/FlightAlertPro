import { NavLink, useNavigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { supabase } from '../lib/supabase';
import { useAuth } from '../App';
import { useWorkspace } from '../lib/WorkspaceContext';
import { getAdminMe } from '../lib/api';
import { t } from '../i18n';
import MobileMenu from './MobileMenu';

const BASE_LINKS = [
  { to: '/dashboard', label: t('nav.dashboard') },
  { to: '/search', label: t('nav.search') },
  { to: '/alerts', label: t('nav.alerts') },
  { to: '/saved', label: t('nav.saved') },
  { to: '/notifications', label: t('nav.notifications') },
  { to: '/workspace', label: 'Team' },
  { to: '/billing', label: t('nav.billing') },
  { to: '/settings', label: t('nav.settings') },
];

const ADMIN_LINKS = [
  { to: '/admin', label: 'Admin' },
  { to: '/analytics', label: 'Analytics' },
];

export default function Header() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { workspaces, currentWorkspace, setCurrentWorkspace } = useWorkspace();
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

          {/* Workspace switcher */}
          {workspaces.length > 1 && (
            <select
              style={styles.wsSwitcher}
              value={currentWorkspace?.id || ''}
              onChange={(e) => {
                const ws = workspaces.find((w) => w.id === e.target.value);
                if (ws) setCurrentWorkspace(ws);
              }}
              title="Switch workspace"
            >
              {workspaces.map((ws) => (
                <option key={ws.id} value={ws.id}>{ws.name}</option>
              ))}
            </select>
          )}
          {workspaces.length === 1 && currentWorkspace && (
            <span style={styles.wsName} title="Current workspace">{currentWorkspace.name}</span>
          )}

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
  wsSwitcher: {
    background: 'rgba(255,255,255,0.15)',
    border: '1px solid rgba(255,255,255,0.5)',
    color: '#fff',
    padding: '0.3rem 0.5rem',
    borderRadius: '4px',
    fontSize: '0.8rem',
    cursor: 'pointer',
    maxWidth: '150px',
  },
  wsName: {
    fontSize: '0.8rem',
    opacity: 0.85,
    background: 'rgba(255,255,255,0.15)',
    padding: '0.25rem 0.5rem',
    borderRadius: '4px',
    maxWidth: '150px',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
};
