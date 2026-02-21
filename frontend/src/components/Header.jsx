import { Link, useNavigate } from 'react-router-dom';
import { supabase } from '../lib/supabase';

export default function Header() {
  const navigate = useNavigate();

  const handleLogout = async () => {
    await supabase.auth.signOut();
    navigate('/');
  };

  return (
    <header style={styles.header}>
      <div style={styles.logo}>✈️ FlightAlertPro</div>
      <nav style={styles.nav}>
        <Link to="/search" style={styles.link}>Search</Link>
        <Link to="/alerts" style={styles.link}>Alerts</Link>
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
