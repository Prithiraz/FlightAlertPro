import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { listSavedSearches, deleteSavedSearch } from '../lib/api';

export default function SavedSearches() {
  const navigate = useNavigate();
  const [searches, setSearches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchSearches();
  }, []);

  const fetchSearches = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await listSavedSearches();
      setSearches(data.saved_searches || []);
    } catch (err) {
      setError(err.message || 'Failed to load saved searches');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this saved search?')) return;
    try {
      await deleteSavedSearch(id);
      setSearches((prev) => prev.filter((s) => s.id !== id));
    } catch (err) {
      alert(err.message || 'Failed to delete');
    }
  };

  const handleRunSearch = (params) => {
    navigate('/search', { state: { prefill: params } });
  };

  const handleCreateAlert = (params) => {
    navigate('/alerts', {
      state: {
        prefill: {
          from_iata: params.from_iata,
          to_iata: params.to_iata,
          departure_date: params.departure_date,
          currency: params.currency,
        },
      },
    });
  };

  return (
    <div style={styles.page}>
      <div style={styles.container}>
        <h1 style={styles.heading}>Saved Searches</h1>
        <p style={styles.subheading}>Run your favorite searches again or turn them into alerts in one click.</p>

        {loading && <p style={styles.muted}>Loading…</p>}
        {error && <p style={styles.error}>{error}</p>}

        {!loading && searches.length === 0 && (
          <div style={styles.empty}>
            <p>No saved searches yet.</p>
            <button onClick={() => navigate('/search')} style={styles.primaryBtn}>Go to Search</button>
          </div>
        )}

        <div style={styles.grid}>
          {searches.map((s) => {
            const p = s.params_json || {};
            return (
              <div key={s.id} style={styles.card}>
                <div style={styles.cardTitle}>{s.name}</div>
                <div style={styles.cardMeta}>
                  {p.from_iata && p.to_iata ? `${p.from_iata} → ${p.to_iata}` : ''}
                  {p.departure_date ? ` · ${p.departure_date}` : ''}
                  {p.cabin_class ? ` · ${p.cabin_class}` : ''}
                  {p.passengers ? ` · ${p.passengers} pax` : ''}
                </div>
                <div style={styles.cardActions}>
                  <button onClick={() => handleRunSearch(p)} style={styles.actionBtn}>🔍 Run</button>
                  <button onClick={() => handleCreateAlert(p)} style={styles.actionBtn}>🔔 Alert</button>
                  <button onClick={() => handleDelete(s.id)} style={styles.deleteBtn}>✕ Delete</button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

const styles = {
  page: { minHeight: '100vh', background: '#f9fafb', padding: '2rem' },
  container: { maxWidth: '900px', margin: '0 auto' },
  heading: { fontSize: '1.75rem', fontWeight: '700', color: '#111827', marginBottom: '0.5rem' },
  subheading: { color: '#6b7280', marginBottom: '2rem' },
  muted: { color: '#6b7280' },
  error: { color: '#dc2626' },
  empty: {
    textAlign: 'center', padding: '3rem', background: '#fff',
    borderRadius: '8px', color: '#6b7280',
  },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '1rem' },
  card: {
    background: '#fff', borderRadius: '8px', padding: '1.25rem',
    boxShadow: '0 1px 4px rgba(0,0,0,0.07)',
  },
  cardTitle: { fontWeight: '600', fontSize: '1rem', marginBottom: '0.35rem', color: '#111827' },
  cardMeta: { fontSize: '0.85rem', color: '#6b7280', marginBottom: '1rem' },
  cardActions: { display: 'flex', gap: '0.5rem', flexWrap: 'wrap' },
  actionBtn: {
    padding: '0.35rem 0.75rem', background: '#eff6ff', color: '#1d4ed8',
    border: '1px solid #bfdbfe', borderRadius: '4px', cursor: 'pointer', fontSize: '0.85rem',
  },
  deleteBtn: {
    padding: '0.35rem 0.75rem', background: '#fef2f2', color: '#dc2626',
    border: '1px solid #fecaca', borderRadius: '4px', cursor: 'pointer', fontSize: '0.85rem',
    marginLeft: 'auto',
  },
  primaryBtn: {
    marginTop: '1rem', padding: '0.6rem 1.5rem', background: '#1d4ed8', color: '#fff',
    border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: '600',
  },
};
