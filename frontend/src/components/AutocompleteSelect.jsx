import { useState, useRef, useEffect, useCallback } from 'react';

// Module-level cache: maps fetchItems function reference -> Map of query -> result
// Prevents repeated API calls for the same query across component re-renders.
const _queryCache = new WeakMap();
const _QUERY_CACHE_MAX = 200;

function cachedFetch(fetchItems, query) {
  if (!_queryCache.has(fetchItems)) {
    _queryCache.set(fetchItems, new Map());
  }
  const fnCache = _queryCache.get(fetchItems);
  if (fnCache.has(query)) return Promise.resolve(fnCache.get(query));
  return fetchItems(query).then((result) => {
    if (fnCache.size >= _QUERY_CACHE_MAX) {
      // Evict oldest entry
      fnCache.delete(fnCache.keys().next().value);
    }
    fnCache.set(query, result);
    return result;
  });
}

/**
 * Reusable accessible autocomplete dropdown.
 *
 * Props:
 *   value         – controlled text shown in the input
 *   onChange      – called with new text value when user types
 *   onSelect      – called with the chosen item object when user picks one
 *   fetchItems    – async (query) => array-of-groups | array-of-items
 *   renderGroup   – (group) => string  — optional group header renderer
 *   renderItem    – (item) => string   — label for each item
 *   getItemValue  – (item) => string   — the IATA/code stored in the form
 *   placeholder   – input placeholder
 *   required      – HTML required attribute
 *   inputStyle    – extra inline styles for the <input>
 *   minChars      – minimum chars before fetching (default 2)
 */
export default function AutocompleteSelect({
  value,
  onChange,
  onSelect,
  fetchItems,
  renderGroup,
  renderItem,
  getItemValue,
  placeholder = '',
  required = false,
  inputStyle = {},
  minChars = 2,
}) {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState([]);   // flat list of { _group?, ...item }
  const [loading, setLoading] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const [activeIdx, setActiveIdx] = useState(-1);
  const inputRef = useRef(null);
  const listRef = useRef(null);
  const debounceRef = useRef(null);

  // Flatten grouped or flat results into a renderable list
  const buildFlatList = useCallback((data) => {
    if (!data) return [];
    // Grouped: { cities: [{city, country, airports:[...]}] }
    if (data.cities) {
      const flat = [];
      for (const group of data.cities) {
        flat.push({ _isGroup: true, _label: `${group.city}, ${group.country}` });
        for (const airport of group.airports || []) {
          flat.push({ ...airport, _city: group.city, _country: group.country });
        }
      }
      return flat;
    }
    // Airlines: { airlines: [...] }
    if (data.airlines) return data.airlines;
    // Flat airports: { airports: [...] }
    if (data.airports) return data.airports;
    // Already a plain array
    if (Array.isArray(data)) return data;
    return [];
  }, []);

  const runFetch = useCallback(async (q) => {
    if (q.length < minChars) {
      setOpen(false);
      setItems([]);
      return;
    }
    setLoading(true);
    setUnavailable(false);
    try {
      const data = await cachedFetch(fetchItems, q);
      const flat = buildFlatList(data);
      setItems(flat);
      setOpen(true);
      setActiveIdx(-1);
    } catch {
      setUnavailable(true);
      setItems([]);
      setOpen(true);
    } finally {
      setLoading(false);
    }
  }, [fetchItems, buildFlatList, minChars]);

  const handleInput = (e) => {
    const q = e.target.value;
    onChange(q);
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => runFetch(q), 250);
  };

  const selectItem = (item) => {
    if (item._isGroup) return;
    onSelect(item);
    setOpen(false);
    setItems([]);
  };

  const handleKeyDown = (e) => {
    if (!open) return;
    const selectables = items.filter((i) => !i._isGroup);
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIdx((prev) => {
        const next = prev + 1;
        return next >= selectables.length ? 0 : next;
      });
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIdx((prev) => {
        const next = prev - 1;
        return next < 0 ? selectables.length - 1 : next;
      });
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (activeIdx >= 0 && activeIdx < selectables.length) {
        selectItem(selectables[activeIdx]);
      }
    } else if (e.key === 'Escape') {
      setOpen(false);
    }
  };

  // Close dropdown when clicking outside
  useEffect(() => {
    const handler = (e) => {
      if (
        inputRef.current && !inputRef.current.contains(e.target) &&
        listRef.current && !listRef.current.contains(e.target)
      ) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  // Scroll active item into view
  useEffect(() => {
    if (listRef.current && activeIdx >= 0) {
      const el = listRef.current.querySelector(`[data-idx="${activeIdx}"]`);
      if (el) el.scrollIntoView({ block: 'nearest' });
    }
  }, [activeIdx]);

  // Build flat list of selectable items for keyboard nav
  const selectables = items.filter((i) => !i._isGroup);

  return (
    <div style={{ position: 'relative' }}>
      <input
        ref={inputRef}
        value={value}
        onChange={handleInput}
        onKeyDown={handleKeyDown}
        onFocus={() => { if (items.length > 0) setOpen(true); }}
        placeholder={placeholder}
        required={required}
        autoComplete="off"
        aria-autocomplete="list"
        aria-expanded={open}
        style={{ ...dropdownStyles.input, ...inputStyle }}
      />

      {open && (
        <div ref={listRef} style={dropdownStyles.dropdown} role="listbox">
          {loading && (
            <div style={dropdownStyles.status}>Loading…</div>
          )}
          {!loading && unavailable && (
            <div style={dropdownStyles.status}>Suggestions unavailable</div>
          )}
          {!loading && !unavailable && items.length === 0 && (
            <div style={dropdownStyles.status}>No results</div>
          )}
          {!loading && !unavailable && (() => {
            let selectableIdx = -1;
            return items.map((item, i) => {
              if (item._isGroup) {
                return (
                  <div key={`g-${i}`} style={dropdownStyles.groupHeader}>
                    {renderGroup ? renderGroup(item) : item._label}
                  </div>
                );
              }
              selectableIdx++;
              const si = selectableIdx;
              const isActive = si === activeIdx;
              return (
                <div
                  key={`i-${i}`}
                  data-idx={si}
                  role="option"
                  aria-selected={isActive}
                  style={{
                    ...dropdownStyles.item,
                    ...(isActive ? dropdownStyles.itemActive : {}),
                  }}
                  onMouseEnter={() => setActiveIdx(si)}
                  onMouseDown={(e) => { e.preventDefault(); selectItem(item); }}
                >
                  {renderItem ? renderItem(item) : getItemValue(item)}
                </div>
              );
            });
          })()}
        </div>
      )}
    </div>
  );
}

const dropdownStyles = {
  input: {
    padding: '0.5rem 0.75rem',
    border: '1px solid #d1d5db',
    borderRadius: '6px',
    fontSize: '1rem',
    width: '100%',
    boxSizing: 'border-box',
  },
  dropdown: {
    position: 'absolute',
    top: 'calc(100% + 4px)',
    left: 0,
    right: 0,
    background: '#fff',
    border: '1px solid #d1d5db',
    borderRadius: '8px',
    boxShadow: '0 4px 16px rgba(0,0,0,0.12)',
    zIndex: 1000,
    maxHeight: '280px',
    overflowY: 'auto',
  },
  groupHeader: {
    padding: '0.35rem 0.75rem',
    fontSize: '0.75rem',
    fontWeight: '700',
    color: '#6b7280',
    background: '#f9fafb',
    borderBottom: '1px solid #f3f4f6',
    textTransform: 'uppercase',
    letterSpacing: '0.04em',
  },
  item: {
    padding: '0.5rem 0.75rem 0.5rem 1.25rem',
    fontSize: '0.9rem',
    color: '#111827',
    cursor: 'pointer',
    borderBottom: '1px solid #f3f4f6',
  },
  itemActive: {
    background: '#eff6ff',
    color: '#1d4ed8',
  },
  status: {
    padding: '0.6rem 0.75rem',
    fontSize: '0.875rem',
    color: '#6b7280',
    fontStyle: 'italic',
  },
};
