import { useState, useEffect } from 'react';
import { useAuth } from '../App';
import AirportAutocomplete from '../components/AirportAutocomplete';
import Toast from '../components/Toast';
import { getPreferences, updatePreferences } from '../lib/api';

const CABIN_CLASSES = ['economy', 'premium_economy', 'business', 'first'];
const CURRENCIES = ['USD', 'EUR', 'GBP', 'CAD', 'AUD', 'INR', 'JPY', 'CHF', 'SEK', 'NOK', 'DKK', 'SGD', 'HKD', 'NZD', 'ZAR'];
const REWARD_PROGRAMS = [
  { value: 'none', label: 'None' },
  { value: 'chase_ur', label: 'Chase Ultimate Rewards' },
  { value: 'amex_mr', label: 'Amex Membership Rewards' },
  { value: 'capital_one', label: 'Capital One Miles' },
];

// Common passport-issuing countries; users can also type a custom value
const NATIONALITIES = [
  'Afghanistan', 'Albania', 'Algeria', 'Andorra', 'Angola', 'Antigua and Barbuda',
  'Argentina', 'Armenia', 'Australia', 'Austria', 'Azerbaijan',
  'Bahamas', 'Bahrain', 'Bangladesh', 'Barbados', 'Belarus', 'Belgium', 'Belize',
  'Benin', 'Bhutan', 'Bolivia', 'Bosnia and Herzegovina', 'Botswana', 'Brazil',
  'Brunei', 'Bulgaria', 'Burkina Faso', 'Burundi',
  'Cabo Verde', 'Cambodia', 'Cameroon', 'Canada', 'Central African Republic', 'Chad',
  'Chile', 'China', 'Colombia', 'Comoros', 'Congo', 'Costa Rica', 'Croatia', 'Cuba',
  'Cyprus', 'Czech Republic',
  'Denmark', 'Djibouti', 'Dominica', 'Dominican Republic',
  'Ecuador', 'Egypt', 'El Salvador', 'Equatorial Guinea', 'Eritrea', 'Estonia',
  'Eswatini', 'Ethiopia',
  'Fiji', 'Finland', 'France',
  'Gabon', 'Gambia', 'Georgia', 'Germany', 'Ghana', 'Greece', 'Grenada', 'Guatemala',
  'Guinea', 'Guinea-Bissau', 'Guyana',
  'Haiti', 'Honduras', 'Hungary',
  'Iceland', 'India', 'Indonesia', 'Iran', 'Iraq', 'Ireland', 'Israel', 'Italy',
  'Jamaica', 'Japan', 'Jordan',
  'Kazakhstan', 'Kenya', 'Kiribati', 'Kuwait', 'Kyrgyzstan',
  'Laos', 'Latvia', 'Lebanon', 'Lesotho', 'Liberia', 'Libya', 'Liechtenstein',
  'Lithuania', 'Luxembourg',
  'Madagascar', 'Malawi', 'Malaysia', 'Maldives', 'Mali', 'Malta', 'Marshall Islands',
  'Mauritania', 'Mauritius', 'Mexico', 'Micronesia', 'Moldova', 'Monaco', 'Mongolia',
  'Montenegro', 'Morocco', 'Mozambique', 'Myanmar',
  'Namibia', 'Nauru', 'Nepal', 'Netherlands', 'New Zealand', 'Nicaragua', 'Niger',
  'Nigeria', 'North Korea', 'North Macedonia', 'Norway',
  'Oman',
  'Pakistan', 'Palau', 'Palestine', 'Panama', 'Papua New Guinea', 'Paraguay', 'Peru',
  'Philippines', 'Poland', 'Portugal',
  'Qatar',
  'Romania', 'Russia', 'Rwanda',
  'Saint Kitts and Nevis', 'Saint Lucia', 'Saint Vincent and the Grenadines', 'Samoa',
  'San Marino', 'Sao Tome and Principe', 'Saudi Arabia', 'Senegal', 'Serbia',
  'Seychelles', 'Sierra Leone', 'Singapore', 'Slovakia', 'Slovenia',
  'Solomon Islands', 'Somalia', 'South Africa', 'South Korea', 'South Sudan', 'Spain',
  'Sri Lanka', 'Sudan', 'Suriname', 'Sweden', 'Switzerland', 'Syria',
  'Taiwan', 'Tajikistan', 'Tanzania', 'Thailand', 'Timor-Leste', 'Togo', 'Tonga',
  'Trinidad and Tobago', 'Tunisia', 'Turkey', 'Turkmenistan', 'Tuvalu',
  'Uganda', 'Ukraine', 'United Arab Emirates', 'United Kingdom', 'United States',
  'Uruguay', 'Uzbekistan',
  'Vanuatu', 'Vatican City', 'Venezuela', 'Vietnam',
  'Yemen',
  'Zambia', 'Zimbabwe',
];

export default function Settings() {
  const { user } = useAuth();
  const [prefs, setPrefs] = useState({
    home_airport: '',
    default_cabin: 'economy',
    currency: 'USD',
    preferred_reward_program: 'none',
    passport_nationality: '',
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState('');
  const [error, setError] = useState('');
  const [nationalitySearch, setNationalitySearch] = useState('');

  useEffect(() => {
    if (!user?.email) return;
    getPreferences(user.email)
      .then((data) => {
        setPrefs({
          home_airport: data.home_airport || '',
          default_cabin: data.default_cabin || 'economy',
          currency: data.currency || 'USD',
          preferred_reward_program: data.preferred_reward_program || 'none',
          passport_nationality: data.passport_nationality || '',
        });
        setNationalitySearch(data.passport_nationality || '');
      })
      .catch((err) => {
        console.error('Failed to load preferences:', err);
      })
      .finally(() => setLoading(false));
  }, [user?.email]);

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    try {
      await updatePreferences(user.email, {
        home_airport: prefs.home_airport || null,
        default_cabin: prefs.default_cabin,
        currency: prefs.currency,
        preferred_reward_program: prefs.preferred_reward_program,
        passport_nationality: prefs.passport_nationality || null,
      });
      setToast('Preferences saved successfully!');
    } catch (err) {
      setError(err.message || 'Failed to save preferences');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={styles.page}>
      <h2 style={styles.heading}>Settings</h2>

      {/* Account card */}
      <div style={styles.card}>
        <h3 style={styles.subHeading}>Account</h3>
        <p style={styles.label}>Email</p>
        <p style={styles.value}>{user?.email ?? '—'}</p>
      </div>

      {/* Travel Preferences card */}
      <div style={{ ...styles.card, marginTop: '1.5rem' }}>
        <h3 style={styles.subHeading}>Travel Preferences</h3>
        {loading ? (
          <p style={styles.note}>Loading preferences…</p>
        ) : (
          <form onSubmit={handleSave} style={styles.form}>
            <div style={styles.field}>
              <label style={styles.label}>Home Airport</label>
              <p style={styles.hint}>Your default departure airport — auto-fills search forms.</p>
              <AirportAutocomplete
                placeholder="e.g. LHR – London Heathrow"
                value={prefs.home_airport}
                onChange={(iata) => setPrefs((prev) => ({ ...prev, home_airport: iata }))}
              />
            </div>

            <div style={styles.field}>
              <label style={styles.label}>Preferred Cabin Class</label>
              <select
                value={prefs.default_cabin}
                onChange={(e) => setPrefs((prev) => ({ ...prev, default_cabin: e.target.value }))}
                style={styles.input}
              >
                {CABIN_CLASSES.map((c) => (
                  <option key={c} value={c}>
                    {c.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
                  </option>
                ))}
              </select>
            </div>

            <div style={styles.field}>
              <label style={styles.label}>Currency</label>
              <select
                value={prefs.currency}
                onChange={(e) => setPrefs((prev) => ({ ...prev, currency: e.target.value }))}
                style={styles.input}
              >
                {CURRENCIES.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>

            <div style={styles.field}>
              <label style={styles.label}>Reward Program (Optional)</label>
              <p style={styles.hint}>Select your preferred credit card reward system to see estimated point costs on flights.</p>
              <select
                value={prefs.preferred_reward_program}
                onChange={(e) => setPrefs((prev) => ({ ...prev, preferred_reward_program: e.target.value }))}
                style={styles.input}
              >
                {REWARD_PROGRAMS.map((rp) => (
                  <option key={rp.value} value={rp.value}>{rp.label}</option>
                ))}
              </select>
            </div>

            <div style={styles.field}>
              <label style={styles.label}>Passport Nationality</label>
              <p style={styles.hint}>Used to generate personalised visa requirements in your Destination Hub.</p>
              <input
                type="text"
                list="nationality-list"
                placeholder="e.g. United States, India, United Kingdom"
                value={nationalitySearch}
                onChange={(e) => {
                  setNationalitySearch(e.target.value);
                  setPrefs((prev) => ({ ...prev, passport_nationality: e.target.value }));
                }}
                style={styles.input}
              />
              <datalist id="nationality-list">
                {NATIONALITIES.filter((n) =>
                  n.toLowerCase().includes(nationalitySearch.toLowerCase())
                ).map((n) => (
                  <option key={n} value={n} />
                ))}
              </datalist>
            </div>

            {error && <p style={styles.error}>{error}</p>}

            <button type="submit" disabled={saving} style={styles.button}>
              {saving ? 'Saving…' : 'Save Preferences'}
            </button>
          </form>
        )}
      </div>

      <Toast message={toast} onClose={() => setToast('')} />
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
  hint: { fontSize: '0.8rem', color: '#6b7280', margin: '0 0 0.375rem' },
  value: { fontSize: '1rem', color: '#111827', margin: '0 0 1rem' },
  note: { fontSize: '0.875rem', color: '#6b7280', fontStyle: 'italic' },
  form: { display: 'flex', flexDirection: 'column', gap: '1rem' },
  field: { display: 'flex', flexDirection: 'column', gap: '0.25rem' },
  input: { padding: '0.5rem 0.75rem', border: '1px solid #d1d5db', borderRadius: '6px', fontSize: '1rem' },
  button: { alignSelf: 'flex-start', marginTop: '0.25rem', padding: '0.625rem 1.5rem', background: '#1d4ed8', color: '#fff', border: 'none', borderRadius: '6px', fontSize: '1rem', fontWeight: '600', cursor: 'pointer' },
  error: { color: '#dc2626', fontSize: '0.875rem', margin: 0 },
};

