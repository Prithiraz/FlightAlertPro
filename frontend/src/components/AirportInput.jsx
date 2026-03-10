import { useState, useEffect, useRef, useCallback } from 'react';

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  (() => {
    const url = new URL(window.location.href);
    url.port = '8000';
    return url.origin;
  })();

/**
 * Kayak-style airport autocomplete input.
 *
 * Props:
 *   name        – form field name (e.g. "from_iata")
 *   value       – controlled IATA code string (e.g. "LAX")
 *   onChange    – called with (name, iataCode) when user picks an airport
 *   placeholder – input placeholder text
 *   label       – visible label rendered above the input
 */
export default function AirportInput({ name, value, onChange, placeholder = 'City or airport', label }) {
  const [query, setQuery] = useState('');
  const [cities, setCities] = useState([]);
  const [open, setOpen] = useState(false);
  const [highlighted, setHighlighted] = useState(-1);
  const [selectedLabel, setSelectedLabel] = useState('');
  const debounceRef = useRef(null);
  const containerRef = useRef(null);

  // When value is controlled externally (e.g. prefill), update the display label
  useEffect(() => {
    if (!value) {
      setSelectedLabel('');
      setQuery('');
    }
  }, [value]);

  const fetchSuggestions = useCallback(async (q) => {
    if (q.length < 1) {
      setCities([]);
      setOpen(false);
      return;
    }
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/metadata/airports?q=${encodeURIComponent(q)}&grouped=true&limit=8`
      );
      if (!res.ok) throw new Error('fetch failed');
      const data = await res.json();
      setCities(data.cities || []);
      setOpen((data.cities || []).length > 0);
      setHighlighted(-1);
    } catch {
      setCities([]);
      setOpen(false);
    }
  }, []);

  const handleInputChange = (e) => {
    const q = e.target.value;
    setQuery(q);
    setSelectedLabel('');
    // Debounce API calls by 200 ms
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => fetchSuggestions(q), 200);
  };

  const selectAirport = (airport, cityName) => {
    const label = `${airport.iata} — ${airport.name} (${cityName})`;
    setSelectedLabel(label);
    setQuery('');
    setCities([]);
    setOpen(false);
    onChange(name, airport.iata);
  };

  const handleKeyDown = (e) => {
    if (!open) return;
    // Flatten airports for keyboard navigation
    const flat = cities.flatMap((city) =>
      city.airports.map((ap) => ({ airport: ap, cityName: city.city }))
    );
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlighted((h) => Math.min(h + 1, flat.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlighted((h) => Math.max(h - 1, 0));
    } else if (e.key === 'Enter' && highlighted >= 0) {
      e.preventDefault();
      const { airport, cityName } = flat[highlighted];
      selectAirport(airport, cityName);
    } else if (e.key === 'Escape') {
      setOpen(false);
    }
  };

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  // Pre-compute flat list so keyboard highlight indices are stable across renders
  const flatAirports = cities.flatMap((city) =>
    city.airports.map((ap) => ({ airport: ap, cityName: city.city }))
  );
  // Map each airport object reference → its index in flatAirports
  const airportIndexMap = new Map(flatAirports.map((fa, i) => [fa.airport, i]));

  return (
    <div ref={containerRef} style={styles.wrapper}>
      {label && <label style={styles.label}>{label}</label>}
      <div style={styles.inputWrapper}>
        <input
          type="text"
          autoComplete="off"
          placeholder={selectedLabel || placeholder}
          value={selectedLabel ? '' : query}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          onFocus={() => { if (cities.length > 0) setOpen(true); }}
          style={{
            ...styles.input,
            color: selectedLabel ? '#111827' : undefined,
          }}
          aria-autocomplete="list"
          aria-expanded={open}
          aria-haspopup="listbox"
        />
        {selectedLabel && (
          <span style={styles.selected}>{selectedLabel}</span>
        )}
        {(selectedLabel || query) && (
          <button
            type="button"
            style={styles.clearBtn}
            onClick={() => {
              setSelectedLabel('');
              setQuery('');
              setCities([]);
              setOpen(false);
              onChange(name, '');
            }}
            aria-label="Clear"
          >
            ×
          </button>
        )}
      </div>

      {open && (
        <ul style={styles.dropdown} role="listbox">
          {cities.map((city) => (
            <li key={`${city.city}|${city.country}`} style={styles.cityGroup}>
              <div style={styles.cityHeader}>
                <span style={styles.cityName}>{city.city}</span>
                <span style={styles.countryName}>{city.country}</span>
              </div>
              {city.airports.map((ap) => {
                const globalIdx = airportIndexMap.get(ap) ?? -1;
                const isHighlighted = globalIdx === highlighted;
                return (
                  <div
                    key={ap.iata}
                    role="option"
                    aria-selected={isHighlighted}
                    style={{
                      ...styles.airportRow,
                      ...(isHighlighted ? styles.airportRowHighlighted : {}),
                    }}
                    onMouseDown={() => selectAirport(ap, city.city)}
                    onMouseEnter={() => setHighlighted(globalIdx)}
                  >
                    <span style={styles.iata}>{ap.iata}</span>
                    <span style={styles.airportName}>{ap.name}</span>
                  </div>
                );
              })}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

const styles = {
  wrapper: {
    position: 'relative',
    flex: 1,
    minWidth: '160px',
    display: 'flex',
    flexDirection: 'column',
    gap: '0.25rem',
  },
  label: {
    fontWeight: '600',
    fontSize: '0.875rem',
    color: '#374151',
  },
  inputWrapper: {
    position: 'relative',
    display: 'flex',
    alignItems: 'center',
  },
  input: {
    padding: '0.5rem 2rem 0.5rem 0.75rem',
    border: '1px solid #d1d5db',
    borderRadius: '6px',
    fontSize: '1rem',
    width: '100%',
    boxSizing: 'border-box',
  },
  selected: {
    position: 'absolute',
    left: '0.75rem',
    pointerEvents: 'none',
    fontSize: '0.9375rem',
    color: '#111827',
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    maxWidth: 'calc(100% - 2rem)',
  },
  clearBtn: {
    position: 'absolute',
    right: '0.5rem',
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    fontSize: '1.1rem',
    color: '#6b7280',
    lineHeight: 1,
    padding: '0 0.2rem',
  },
  dropdown: {
    position: 'absolute',
    top: 'calc(100% + 2px)',
    left: 0,
    right: 0,
    background: '#fff',
    border: '1px solid #d1d5db',
    borderRadius: '6px',
    boxShadow: '0 4px 16px rgba(0,0,0,0.12)',
    zIndex: 1000,
    listStyle: 'none',
    margin: 0,
    padding: '0.25rem 0',
    maxHeight: '320px',
    overflowY: 'auto',
  },
  cityGroup: {
    padding: 0,
  },
  cityHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    padding: '0.375rem 0.75rem 0.2rem',
    background: '#f9fafb',
    borderTop: '1px solid #f3f4f6',
  },
  cityName: {
    fontWeight: '700',
    fontSize: '0.8125rem',
    color: '#374151',
    textTransform: 'uppercase',
    letterSpacing: '0.04em',
  },
  countryName: {
    fontSize: '0.75rem',
    color: '#9ca3af',
  },
  airportRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.625rem',
    padding: '0.4rem 0.75rem 0.4rem 1.25rem',
    cursor: 'pointer',
    userSelect: 'none',
  },
  airportRowHighlighted: {
    background: '#eff6ff',
  },
  iata: {
    fontWeight: '700',
    fontSize: '0.875rem',
    color: '#1d4ed8',
    minWidth: '2.25rem',
  },
  airportName: {
    fontSize: '0.875rem',
    color: '#374151',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
};
