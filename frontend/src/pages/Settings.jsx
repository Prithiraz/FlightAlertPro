import { useAuth } from '../App';

export default function Settings() {
  const { user } = useAuth();

  return (
    <div style={styles.page}>
      <h2 style={styles.heading}>Settings</h2>
      <div style={styles.card}>
        <h3 style={styles.subHeading}>Account</h3>
        <p style={styles.label}>Email</p>
        <p style={styles.value}>{user?.email ?? '—'}</p>
        <p style={styles.note}>
          Account settings and notification preferences coming soon.
        </p>
      </div>
    </div>
  );
}

const styles = {
  page: { maxWidth: '600px', margin: '2rem auto', padding: '0 1rem' },
  heading: { fontSize: '1.75rem', marginBottom: '1.5rem', color: '#1d4ed8' },
  card: {
    background: '#fff',
    borderRadius: '8px',
    padding: '1.5rem',
    boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
  },
  subHeading: { fontSize: '1.125rem', fontWeight: '700', marginBottom: '1rem', color: '#374151' },
  label: { fontSize: '0.875rem', fontWeight: '600', color: '#374151', margin: '0 0 0.25rem' },
  value: { fontSize: '1rem', color: '#111827', margin: '0 0 1rem' },
  note: { fontSize: '0.875rem', color: '#6b7280', marginTop: '1rem', fontStyle: 'italic' },
};
