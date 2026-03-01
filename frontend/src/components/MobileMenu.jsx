import { useState, useEffect, useRef } from 'react';
import { NavLink } from 'react-router-dom';

/**
 * MobileMenu – hamburger navigation for small screens (<640 px).
 * Renders a ☰ button that toggles a slide-down menu. No external libs.
 */
export default function MobileMenu({ links, onLogout, userEmail }) {
  const [open, setOpen] = useState(false);
  const menuRef = useRef(null);

  // Close on outside click
  useEffect(() => {
    const handler = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  // Close on route change (NavLink click)
  const close = () => setOpen(false);

  const navLinkStyle = ({ isActive }) => ({
    ...styles.link,
    ...(isActive ? styles.activeLink : {}),
  });

  return (
    <div style={styles.wrapper} ref={menuRef}>
      <button
        onClick={() => setOpen((o) => !o)}
        style={styles.hamburger}
        aria-label={open ? 'Close menu' : 'Open menu'}
        aria-expanded={open}
      >
        {open ? '✕' : '☰'}
      </button>

      {open && (
        <nav style={styles.dropdown} role="navigation">
          {links.map(({ to, label }) => (
            <NavLink key={to} to={to} style={navLinkStyle} onClick={close}>
              {label}
            </NavLink>
          ))}
          {userEmail && <span style={styles.email}>{userEmail}</span>}
          <button
            onClick={() => { close(); onLogout(); }}
            style={styles.logoutBtn}
          >
            Logout
          </button>
        </nav>
      )}
    </div>
  );
}

const styles = {
  wrapper: {
    position: 'relative',
  },
  hamburger: {
    background: 'transparent',
    border: '1px solid rgba(255,255,255,0.6)',
    color: '#fff',
    fontSize: '1.25rem',
    lineHeight: 1,
    padding: '0.375rem 0.625rem',
    borderRadius: '4px',
    cursor: 'pointer',
    minWidth: '2.5rem',
    minHeight: '2.5rem',
  },
  dropdown: {
    position: 'absolute',
    top: 'calc(100% + 8px)',
    right: 0,
    background: '#1d4ed8',
    border: '1px solid rgba(255,255,255,0.2)',
    borderRadius: '8px',
    boxShadow: '0 8px 24px rgba(0,0,0,0.2)',
    display: 'flex',
    flexDirection: 'column',
    minWidth: '180px',
    zIndex: 1000,
    overflow: 'hidden',
  },
  link: {
    color: '#fff',
    textDecoration: 'none',
    padding: '0.75rem 1.25rem',
    fontSize: '0.95rem',
    fontWeight: '500',
    borderBottom: '1px solid rgba(255,255,255,0.1)',
    display: 'block',
  },
  activeLink: {
    fontWeight: '700',
    background: 'rgba(255,255,255,0.15)',
  },
  email: {
    fontSize: '0.8rem',
    color: 'rgba(255,255,255,0.7)',
    padding: '0.625rem 1.25rem',
    borderBottom: '1px solid rgba(255,255,255,0.1)',
    display: 'block',
    wordBreak: 'break-all',
  },
  logoutBtn: {
    background: 'transparent',
    border: 'none',
    color: '#fff',
    padding: '0.75rem 1.25rem',
    fontSize: '0.95rem',
    fontWeight: '500',
    textAlign: 'left',
    cursor: 'pointer',
  },
};
