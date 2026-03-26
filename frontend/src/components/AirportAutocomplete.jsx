import { useState, useEffect, useRef } from 'react';
import { searchAirports } from '../lib/api';

/**
 * Premium airport autocomplete input (Kayak-style).
 *
 * Props:
 *   placeholder  – input placeholder text
 *   value        – currently-selected IATA code (controlled)
 *   onChange     – called with the selected IATA code string
 */
export default function AirportAutocomplete({ placeholder = 'City or airport', value, onChange }) {
  const [inputText, setInputText] = useState('');
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const debounceRef = useRef(null);
  const wrapperRef = useRef(null);

  // Keep display text in sync when the parent resets value to empty string
  useEffect(() => {
    if (!value) {
      setInputText('');
    }
  }, [value]);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(e) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleInput = (e) => {
    const text = e.target.value;
    setInputText(text);
    setOpen(true);

    clearTimeout(debounceRef.current);

    if (text.length < 2) {
      setResults([]);
      setLoading(false);
      return;
    }

    setLoading(true);
    debounceRef.current = setTimeout(async () => {
      try {
        const data = await searchAirports(text);
        setResults(Array.isArray(data) ? data : []);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 300);
  };

  const handleSelect = (item) => {
    setInputText(`${item.city} (${item.iata})`);
    setResults([]);
    setOpen(false);
    onChange(item.iata);
  };

  const showDropdown = open && (loading || results.length > 0 || inputText.length >= 2);

  return (
    <div ref={wrapperRef} style={styles.wrapper}>
      <input
        type="text"
        value={inputText}
        onChange={handleInput}
        onFocus={() => inputText.length >= 2 && setOpen(true)}
        placeholder={placeholder}
        autoComplete="off"
        style={styles.input}
      />
      {showDropdown && (
        <div style={styles.dropdown}>
          {loading && (
            <div style={styles.hint}>Searching…</div>
          )}
          {!loading && results.length === 0 && inputText.length >= 2 && (
            <div style={styles.hint}>No airports found</div>
          )}
          {!loading && results.map((item) => (
            <button
              key={item.iata}
              type="button"
              onMouseDown={(e) => {
                // Prevent the wrapper's blur from firing before onClick
                e.preventDefault();
                handleSelect(item);
              }}
              style={styles.item}
              onMouseEnter={(e) => Object.assign(e.currentTarget.style, styles.itemHover)}
              onMouseLeave={(e) => Object.assign(e.currentTarget.style, styles.itemBase)}
            >
              <div style={styles.itemLeft}>
                <span style={styles.city}>{item.city}, {item.country}</span>
                <span style={styles.name}>{item.name}</span>
              </div>
              <span style={styles.badge}>{item.iata}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

const styles = {
  wrapper: {
    position: 'relative',
    width: '100%',
  },
  input: {
    width: '100%',
    padding: '0.5rem 0.75rem',
    border: '1px solid #d1d5db',
    borderRadius: '6px',
    fontSize: '1rem',
    boxSizing: 'border-box',
    outline: 'none',
    transition: 'border-color 0.15s',
  },
  dropdown: {
    position: 'absolute',
    top: 'calc(100% + 4px)',
    left: 0,
    right: 0,
    background: '#fff',
    border: '1px solid #e5e7eb',
    borderRadius: '8px',
    boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
    zIndex: 50,
    maxHeight: '320px',
    overflowY: 'auto',
  },
  hint: {
    padding: '0.75rem 1rem',
    fontSize: '0.875rem',
    color: '#9ca3af',
    textAlign: 'center',
  },
  itemBase: {
    background: '#fff',
  },
  itemHover: {
    background: '#eff6ff',
  },
  item: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    width: '100%',
    padding: '0.625rem 1rem',
    border: 'none',
    borderBottom: '1px solid #f3f4f6',
    background: '#fff',
    cursor: 'pointer',
    textAlign: 'left',
    transition: 'background 0.1s',
    boxSizing: 'border-box',
  },
  itemLeft: {
    display: 'flex',
    flexDirection: 'column',
    gap: '2px',
    minWidth: 0,
    flex: 1,
    overflow: 'hidden',
  },
  city: {
    fontWeight: '600',
    fontSize: '0.9rem',
    color: '#111827',
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  },
  name: {
    fontSize: '0.875rem',
    color: '#6b7280',
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  },
  badge: {
    marginLeft: '0.75rem',
    flexShrink: 0,
    padding: '2px 8px',
    background: '#f3f4f6',
    color: '#374151',
    borderRadius: '4px',
    fontSize: '0.75rem',
    fontWeight: '700',
    letterSpacing: '0.05em',
    fontFamily: 'monospace',
  },
};
