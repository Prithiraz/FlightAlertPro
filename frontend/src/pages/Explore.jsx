import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { exploreDestinations } from '../lib/api';

const INTEREST_TAGS = ['beach', 'city', 'culture', 'food', 'luxury', 'nature', 'budget', 'nightlife'];

export default function Explore() {
  const navigate = useNavigate();
  const [fromIata, setFromIata] = useState('');
  const [budget, setBudget] = useState('');
  const [selectedTags, setSelectedTags] = useState([]);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const toggleTag = (tag) => {
    setSelectedTags((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]
    );
  };

  const handleExplore = async (e) => {
    e.preventDefault();
    if (!fromIata.trim() || fromIata.trim().length < 3) {
      setError('Enter a valid 3-letter IATA code (e.g. LAX, JFK, LHR)');
      return;
    }
    setLoading(true);
    setError('');
    setResults(null);
    try {
      const data = await exploreDestinations({
        from_iata: fromIata.toUpperCase().trim(),
        budget: budget ? Number(budget) : undefined,
        tags: selectedTags.length ? selectedTags.join(',') : undefined,
        limit: 12,
      });
      setResults(data);
    } catch (err) {
      setError(err.message || 'Failed to load destinations');
    } finally {
      setLoading(false);
    }
  };

  const handleGoToSearch = (destIata) => {
    navigate('/search', {
      state: { prefill: { to_iata: destIata, from_iata: fromIata.toUpperCase().trim() } },
    });
  };

  return (
    <div style={styles.page}>
      <div style={styles.hero}>
        <h1 style={styles.heroTitle}>✈️ Explore Destinations</h1>
        <p style={styles.heroSub}>
          Tell us where you're flying from (and optionally a budget), and we'll show you popular
          destinations with estimated prices.
        </p>
      </div>

      {/* Filter form */}
      <div style={styles.filterCard}>
        <form onSubmit={handleExplore} style={styles.form}>
          <div style={styles.row}>
            <div style={styles.field}>
              <label style={styles.label}>Flying from (IATA code)</label>
              <input
                value={fromIata}
                onChange={(e) => setFromIata(e.target.value)}
                maxLength={3}
                placeholder="LAX"
                required
                style={styles.input}
              />
            </div>
            <div style={styles.field}>
              <label style={styles.label}>Max budget (USD, one-way) — optional</label>
              <input
                type="number"
                value={budget}
                onChange={(e) => setBudget(e.target.value)}
                min={1}
                placeholder="e.g. 500"
                style={styles.input}
              />
            </div>
          </div>

          <div style={styles.tagsSection}>
            <label style={styles.label}>Interests (optional)</label>
            <div style={styles.tagRow}>
              {INTEREST_TAGS.map((tag) => (
                <button
                  key={tag}
                  type="button"
                  onClick={() => toggleTag(tag)}
                  style={{
                    ...styles.tag,
                    background: selectedTags.includes(tag) ? '#1d4ed8' : '#f3f4f6',
                    color: selectedTags.includes(tag) ? '#fff' : '#374151',
                    border: selectedTags.includes(tag) ? '1px solid #1d4ed8' : '1px solid #d1d5db',
                  }}
                >
                  {tag}
                </button>
              ))}
            </div>
          </div>

          {error && <p style={styles.error}>{error}</p>}

          <button type="submit" disabled={loading} style={styles.searchBtn}>
            {loading ? 'Exploring…' : 'Explore destinations'}
          </button>
        </form>
      </div>

      {/* Results grid */}
      {results && (
        <div style={styles.resultsSection}>
          <p style={styles.resultsCount}>
            {results.destinations_found} destination{results.destinations_found !== 1 ? 's' : ''} found
            {results.budget_usd ? ` within $${results.budget_usd} budget` : ''}
            {results.tag_filter?.length ? ` · interests: ${results.tag_filter.join(', ')}` : ''}
          </p>
          <div style={styles.destGrid}>
            {results.destinations.map((dest) => (
              <div key={dest.iata} style={styles.destCard}>
                <div style={styles.destEmoji}>{dest.emoji}</div>
                <div style={styles.destCity}>{dest.city}</div>
                <div style={styles.destCountry}>{dest.country}</div>
                <div style={styles.destIata}>{dest.iata}</div>
                <div style={styles.priceTier}>{dest.price_tier}</div>
                <div style={styles.estPrice}>
                  From ~${dest.estimated_price_usd.toLocaleString()}
                </div>
                <div style={styles.tagRow2}>
                  {dest.tags.slice(0, 3).map((t) => (
                    <span key={t} style={styles.tagChip}>{t}</span>
                  ))}
                </div>
                <div style={styles.bestMonths}>
                  Best months: {dest.best_months.join(', ')}
                </div>
                <button
                  onClick={() => handleGoToSearch(dest.iata)}
                  style={styles.searchFlightsBtn}
                >
                  Search flights →
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

const styles = {
  page: { minHeight: '100vh', background: '#f9fafb', paddingBottom: '4rem' },
  hero: { textAlign: 'center', padding: '3rem 1rem 1.5rem', maxWidth: '680px', margin: '0 auto' },
  heroTitle: { fontSize: '2rem', fontWeight: '800', color: '#111827', margin: '0 0 0.75rem' },
  heroSub: { fontSize: '1.05rem', color: '#4b5563', lineHeight: 1.6 },
  filterCard: { maxWidth: '760px', margin: '0 auto 2rem', padding: '0 1rem' },
  form: { background: '#fff', borderRadius: '12px', padding: '1.75rem', boxShadow: '0 2px 8px rgba(0,0,0,0.08)', display: 'flex', flexDirection: 'column', gap: '1rem' },
  row: { display: 'flex', gap: '1rem', flexWrap: 'wrap' },
  field: { flex: 1, minWidth: '180px', display: 'flex', flexDirection: 'column', gap: '0.25rem' },
  label: { fontWeight: '600', fontSize: '0.875rem', color: '#374151' },
  input: { padding: '0.5rem 0.75rem', border: '1px solid #d1d5db', borderRadius: '6px', fontSize: '1rem' },
  tagsSection: { display: 'flex', flexDirection: 'column', gap: '0.5rem' },
  tagRow: { display: 'flex', flexWrap: 'wrap', gap: '0.5rem' },
  tag: { padding: '0.375rem 0.875rem', borderRadius: '9999px', fontSize: '0.875rem', fontWeight: '600', cursor: 'pointer', transition: 'all 0.15s' },
  error: { color: '#dc2626', fontSize: '0.875rem', margin: 0 },
  searchBtn: { alignSelf: 'flex-start', padding: '0.75rem 2rem', background: '#1d4ed8', color: '#fff', border: 'none', borderRadius: '8px', fontSize: '1rem', fontWeight: '700', cursor: 'pointer' },
  resultsSection: { maxWidth: '1200px', margin: '0 auto', padding: '0 1rem' },
  resultsCount: { fontSize: '0.95rem', color: '#6b7280', marginBottom: '1.25rem' },
  destGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '1.25rem' },
  destCard: { background: '#fff', borderRadius: '12px', padding: '1.5rem', boxShadow: '0 2px 8px rgba(0,0,0,0.07)', display: 'flex', flexDirection: 'column', gap: '0.375rem' },
  destEmoji: { fontSize: '2.5rem', lineHeight: 1 },
  destCity: { fontSize: '1.2rem', fontWeight: '700', color: '#111827' },
  destCountry: { fontSize: '0.875rem', color: '#6b7280' },
  destIata: { fontSize: '0.8rem', fontWeight: '700', color: '#1d4ed8' },
  priceTier: { fontSize: '0.85rem', fontWeight: '600', marginTop: '0.25rem' },
  estPrice: { fontSize: '1rem', fontWeight: '700', color: '#16a34a' },
  tagRow2: { display: 'flex', flexWrap: 'wrap', gap: '0.375rem', marginTop: '0.25rem' },
  tagChip: { background: '#f3f4f6', color: '#374151', padding: '0.2rem 0.6rem', borderRadius: '9999px', fontSize: '0.75rem', fontWeight: '600' },
  bestMonths: { fontSize: '0.8rem', color: '#9ca3af', marginTop: '0.25rem' },
  searchFlightsBtn: { marginTop: '0.75rem', padding: '0.5rem 1rem', background: '#eff6ff', color: '#1d4ed8', border: '1px solid #bfdbfe', borderRadius: '6px', cursor: 'pointer', fontWeight: '600', fontSize: '0.875rem', textAlign: 'center' },
};
