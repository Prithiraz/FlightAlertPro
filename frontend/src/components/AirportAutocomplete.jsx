import { useState, useCallback, useEffect } from 'react';
import AutocompleteSelect from './AutocompleteSelect';
import { searchAirports } from '../lib/api';

const IATA_CODE_MAX_LENGTH = 3;

/**
 * Airport autocomplete input.
 *
 * Props:
 *   value      – IATA code stored in the form (e.g. "LHR")
 *   onChange   – called with new IATA code string when selection changes
 *   label      – label text (e.g. "From")
 *   placeholder
 *   required
 *   inputStyle
 */
export default function AirportAutocomplete({
  value,
  onChange,
  label,
  placeholder = 'City, airport or IATA',
  required = false,
  inputStyle = {},
}) {
  // The visible text shown in the input (may be the full label or raw typed text)
  const [display, setDisplay] = useState(value || '');

  // Sync display when value is updated externally (e.g. prefill)
  useEffect(() => {
    // Only sync if display looks like a raw IATA (≤3 chars) or is empty
    if (value && value.length <= IATA_CODE_MAX_LENGTH && value !== display) {
      setDisplay(value);
    } else if (!value) {
      setDisplay('');
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  const fetchItems = useCallback((q) => searchAirports(q), []);

  const renderItem = (item) =>
    `${item.name} (${item.iata}) — ${item._city}, ${item._country}`;

  const getItemValue = (item) => item.iata || '';

  const handleSelect = (item) => {
    const iata = item.iata || '';
    const label = renderItem(item);
    setDisplay(label);
    onChange(iata);
  };

  const handleTextChange = (text) => {
    setDisplay(text);
    // If user clears the field or types raw IATA, propagate it directly
    onChange(text.length <= IATA_CODE_MAX_LENGTH ? text.toUpperCase() : '');
  };

  const styles = {
    wrapper: { display: 'flex', flexDirection: 'column', gap: '0.25rem', flex: 1, minWidth: '160px' },
    label: { fontWeight: '600', fontSize: '0.875rem', color: '#374151' },
  };

  return (
    <div style={styles.wrapper}>
      {label && <label style={styles.label}>{label}</label>}
      <AutocompleteSelect
        value={display}
        onChange={handleTextChange}
        onSelect={handleSelect}
        fetchItems={fetchItems}
        renderItem={renderItem}
        getItemValue={getItemValue}
        placeholder={placeholder}
        required={required}
        inputStyle={inputStyle}
      />
    </div>
  );
}
