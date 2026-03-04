import { useState, useCallback } from 'react';
import AutocompleteSelect from './AutocompleteSelect';
import { searchAirlines } from '../lib/api';

const AIRLINE_CODE_MAX_LENGTH = 4;

/**
 * Airline autocomplete input.
 *
 * Props:
 *   value      – airline IATA/ICAO code stored in the form (e.g. "EK")
 *   onChange   – called with new code string when selection changes
 *   label      – label text
 *   placeholder
 *   required
 *   inputStyle
 */
export default function AirlineAutocomplete({
  value,
  onChange,
  label,
  placeholder = 'Airline name or IATA code',
  required = false,
  inputStyle = {},
}) {
  const [display, setDisplay] = useState(value || '');

  const fetchItems = useCallback((q) => searchAirlines(q), []);

  const renderItem = (item) => {
    const code = item.iata || item.icao || '';
    const country = item.country || '';
    return `${item.name}${code ? ` (${code})` : ''}${country ? ` — ${country}` : ''}`;
  };

  const getItemValue = (item) => item.iata || item.icao || '';

  const handleSelect = (item) => {
    const code = getItemValue(item);
    setDisplay(renderItem(item));
    onChange(code);
  };

  const handleTextChange = (text) => {
    setDisplay(text);
    onChange(text.length <= AIRLINE_CODE_MAX_LENGTH ? text.toUpperCase() : '');
  };

  // Flat list: airlines response has { airlines: [...] } – AutocompleteSelect handles it
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
