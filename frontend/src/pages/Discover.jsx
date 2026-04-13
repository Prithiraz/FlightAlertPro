import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { exploreFlights, getPreferences, createAlert } from '../lib/api';
import { useAuth } from '../App';

export default function Discover() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [origin, setOrigin] = useState('');
  const [destinations, setDestinations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [trackingStatus, setTrackingStatus] = useState({});

  // Load home airport from preferences, then trigger explore
  useEffect(() => {
    if (!user?.email) return;
    getPreferences(user.email)
      .then((prefs) => {
        const home = prefs.home_airport || '';
        setOrigin(home);
        if (home) {
          fetchDestinations(home);
        }
      })
      .catch(() => {});
  }, [user?.email]);

  async function fetchDestinations(iata) {
    if (!iata || iata.length !== 3) return;
    setLoading(true);
    setError('');
    setDestinations([]);
    try {
      const data = await exploreFlights(iata.toUpperCase());
      setDestinations(data.destinations || []);
    } catch (err) {
      setError(err.message || 'Failed to load destinations');
    } finally {
      setLoading(false);
    }
  }

  async function handleTrack(dest) {
    if (!user?.email) return;
    const key = dest.iata;
    setTrackingStatus((prev) => ({ ...prev, [key]: 'loading' }));
    try {
      await createAlert({
        user_email: user.email,
        from_iata: origin.toUpperCase(),
        to_iata: dest.iata,
        max_price: Math.ceil(dest.price * 1.1), // 10% above current cheapest so minor price rises still trigger the alert
        currency: dest.currency || 'USD',
      });
      setTrackingStatus((prev) => ({ ...prev, [key]: 'tracked' }));
    } catch (err) {
      setTrackingStatus((prev) => ({ ...prev, [key]: 'error' }));
    }
  }

  const handleOriginChange = (e) => {
    const val = e.target.value.toUpperCase().slice(0, 3);
    setOrigin(val);
  };

  const handleSearch = (e) => {
    e.preventDefault();
    fetchDestinations(origin);
  };

  return (
    <div style={styles.page}>
      {/* Hero */}
      <div style={styles.hero}>
        <h1 style={styles.heroTitle}>✈️ Explore Anywhere</h1>
        <p style={styles.heroSubtitle}>
          Discover the cheapest flights from your home airport to the world's top destinations.
        </p>

        <form onSubmit={handleSearch} style={styles.searchBar}>
          <div style={styles.inputWrapper}>
            <span style={styles.inputIcon}>🏠</span>
            <input
              type="text"
              placeholder="Your home airport (e.g. JFK)"
              value={origin}
              onChange={handleOriginChange}
              maxLength={3}
              style={styles.originInput}
            />
          </div>
          <button type="submit" disabled={loading || origin.length !== 3} style={styles.exploreBtn}>
            {loading ? 'Searching…' : 'Explore'}
          </button>
        </form>
      </div>

      {/* Content area */}
      <div style={styles.content}>
        {error && <p style={styles.error}>{error}</p>}

        {loading && (
          <div style={styles.grid}>
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} style={styles.skeletonCard} />
            ))}
          </div>
        )}

        {!loading && destinations.length === 0 && !error && origin && (
          <p style={styles.empty}>No results found. Try a different origin airport.</p>
        )}

        {!loading && !origin && (
          <p style={styles.empty}>
            Enter your home airport code above to discover cheap flights around the world.
          </p>
        )}

        {!loading && destinations.length > 0 && (
          <>
            <p style={styles.resultsLabel}>
              {destinations.length} destinations found from <strong>{origin}</strong>
            </p>
            <div style={styles.grid}>
              {destinations.map((dest) => (
                <DestinationCard
                  key={dest.iata}
                  dest={dest}
                  trackStatus={trackingStatus[dest.iata]}
                  onTrack={() => handleTrack(dest)}
                />
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function DestinationCard({ dest, trackStatus, onTrack }) {
  const imgUrl = `https://source.unsplash.com/400x300/?${encodeURIComponent(dest.city)},travel`;
  const priceLabel = dest.price
    ? `From $${Math.round(dest.price).toLocaleString()}`
    : 'Price unavailable';

  let btnLabel = '+ Track This Route';
  let btnStyle = { ...styles.trackBtn };
  if (trackStatus === 'loading') {
    btnLabel = 'Saving…';
    btnStyle = { ...btnStyle, ...styles.trackBtnLoading };
  } else if (trackStatus === 'tracked') {
    btnLabel = '✓ Alert Saved';
    btnStyle = { ...btnStyle, ...styles.trackBtnDone };
  } else if (trackStatus === 'error') {
    btnLabel = 'Error – Retry';
    btnStyle = { ...btnStyle, ...styles.trackBtnError };
  }

  return (
    <div style={styles.card}>
      {/* Background image */}
      <div
        style={{
          ...styles.cardImg,
          backgroundImage: `url(${imgUrl})`,
        }}
      />
      {/* Gradient overlay */}
      <div style={styles.cardOverlay} />
      {/* Card content */}
      <div style={styles.cardBody}>
        <div>
          <h2 style={styles.cityName}>{dest.city}</h2>
          <p style={styles.iataCode}>{dest.iata}</p>
        </div>
        <div style={styles.cardBottom}>
          <span style={styles.priceBadge}>{priceLabel}</span>
          {dest.airline_name && (
            <span style={styles.airlineTag}>{dest.airline_name}</span>
          )}
          <button
            onClick={onTrack}
            disabled={trackStatus === 'loading' || trackStatus === 'tracked'}
            style={btnStyle}
          >
            {btnLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

const styles = {
  page: {
    minHeight: '100vh',
    background: '#0f172a',
    color: '#f8fafc',
  },
  hero: {
    textAlign: 'center',
    padding: '4rem 1rem 3rem',
    background: 'linear-gradient(135deg, #1e3a5f 0%, #1d4ed8 100%)',
  },
  heroTitle: {
    fontSize: '2.5rem',
    fontWeight: '800',
    margin: '0 0 0.75rem',
    color: '#fff',
  },
  heroSubtitle: {
    fontSize: '1.125rem',
    color: 'rgba(255,255,255,0.8)',
    margin: '0 0 2rem',
    maxWidth: '520px',
    marginLeft: 'auto',
    marginRight: 'auto',
  },
  searchBar: {
    display: 'flex',
    gap: '0.75rem',
    justifyContent: 'center',
    flexWrap: 'wrap',
  },
  inputWrapper: {
    position: 'relative',
    display: 'flex',
    alignItems: 'center',
  },
  inputIcon: {
    position: 'absolute',
    left: '0.75rem',
    fontSize: '1rem',
    pointerEvents: 'none',
  },
  originInput: {
    padding: '0.75rem 1rem 0.75rem 2.5rem',
    fontSize: '1.125rem',
    fontWeight: '700',
    letterSpacing: '0.1em',
    textTransform: 'uppercase',
    borderRadius: '8px',
    border: 'none',
    width: '220px',
    outline: 'none',
  },
  exploreBtn: {
    padding: '0.75rem 2rem',
    fontSize: '1rem',
    fontWeight: '700',
    background: '#f59e0b',
    color: '#1e293b',
    border: 'none',
    borderRadius: '8px',
    cursor: 'pointer',
    transition: 'opacity 0.2s',
  },
  content: {
    maxWidth: '1200px',
    margin: '0 auto',
    padding: '2rem 1rem',
  },
  resultsLabel: {
    fontSize: '1rem',
    color: '#94a3b8',
    marginBottom: '1.5rem',
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
    gap: '1.5rem',
  },
  skeletonCard: {
    height: '280px',
    borderRadius: '12px',
    background: 'linear-gradient(90deg, #1e293b 25%, #334155 50%, #1e293b 75%)',
    backgroundSize: '200% 100%',
    animation: 'shimmer 1.5s infinite',
  },
  error: {
    color: '#f87171',
    textAlign: 'center',
    fontSize: '1rem',
    marginBottom: '1rem',
  },
  empty: {
    textAlign: 'center',
    color: '#94a3b8',
    fontSize: '1rem',
    marginTop: '2rem',
  },
  // Card
  card: {
    position: 'relative',
    height: '280px',
    borderRadius: '12px',
    overflow: 'hidden',
    boxShadow: '0 4px 20px rgba(0,0,0,0.5)',
    cursor: 'default',
    transition: 'transform 0.2s',
  },
  cardImg: {
    position: 'absolute',
    inset: 0,
    backgroundSize: 'cover',
    backgroundPosition: 'center',
    backgroundColor: '#1e3a5f',
  },
  cardOverlay: {
    position: 'absolute',
    inset: 0,
    background: 'linear-gradient(to top, rgba(0,0,0,0.85) 0%, rgba(0,0,0,0.1) 60%)',
  },
  cardBody: {
    position: 'absolute',
    inset: 0,
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'space-between',
    padding: '1.25rem',
  },
  cityName: {
    margin: 0,
    fontSize: '1.6rem',
    fontWeight: '800',
    color: '#fff',
    textShadow: '0 2px 8px rgba(0,0,0,0.6)',
  },
  iataCode: {
    margin: '0.15rem 0 0',
    fontSize: '0.875rem',
    fontWeight: '600',
    color: 'rgba(255,255,255,0.7)',
    letterSpacing: '0.05em',
  },
  cardBottom: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.5rem',
  },
  priceBadge: {
    display: 'inline-block',
    background: '#f59e0b',
    color: '#1e293b',
    fontWeight: '800',
    fontSize: '1rem',
    padding: '0.3rem 0.75rem',
    borderRadius: '999px',
    alignSelf: 'flex-start',
  },
  airlineTag: {
    fontSize: '0.75rem',
    color: 'rgba(255,255,255,0.7)',
  },
  trackBtn: {
    padding: '0.5rem 1rem',
    background: 'rgba(255,255,255,0.15)',
    backdropFilter: 'blur(4px)',
    color: '#fff',
    border: '1px solid rgba(255,255,255,0.3)',
    borderRadius: '6px',
    fontWeight: '600',
    fontSize: '0.875rem',
    cursor: 'pointer',
    width: '100%',
    transition: 'background 0.2s',
  },
  trackBtnLoading: {
    opacity: 0.7,
    cursor: 'not-allowed',
  },
  trackBtnDone: {
    background: 'rgba(34,197,94,0.3)',
    border: '1px solid rgba(34,197,94,0.6)',
    cursor: 'default',
  },
  trackBtnError: {
    background: 'rgba(239,68,68,0.3)',
    border: '1px solid rgba(239,68,68,0.6)',
  },
};
