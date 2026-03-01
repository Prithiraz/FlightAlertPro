import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { updateProfile, createAlert } from '../lib/api';
import AirportAutocomplete from '../components/AirportAutocomplete';

const CURRENCIES = ['USD', 'EUR', 'GBP', 'CAD', 'AUD', 'INR'];
const CHANNELS = ['email', 'whatsapp', 'telegram'];
const TOTAL_STEPS = 3;

export default function Onboarding({ onComplete }) {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [currency, setCurrency] = useState('USD');
  const [channels, setChannels] = useState(['email']);
  const [alertForm, setAlertForm] = useState({ from_iata: '', to_iata: '', max_price: '' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const toggleChannel = (ch) => {
    setChannels((prev) =>
      prev.includes(ch) ? prev.filter((c) => c !== ch) : [...prev, ch]
    );
  };

  const handleSkip = async () => {
    await finishOnboarding(false);
  };

  const finishOnboarding = async (createFirstAlert) => {
    setSaving(true);
    setError('');
    try {
      await updateProfile({ home_currency: currency, default_channels: channels, onboarded: true });
      if (createFirstAlert && alertForm.from_iata && alertForm.to_iata && alertForm.max_price) {
        await createAlert({
          from_iata: alertForm.from_iata.toUpperCase(),
          to_iata: alertForm.to_iata.toUpperCase(),
          max_price: Number(alertForm.max_price),
          currency,
          notification_channels: channels,
        });
      }
      if (onComplete) onComplete();
      navigate('/dashboard', { replace: true });
    } catch (err) {
      setError(err.message || 'Something went wrong. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={styles.overlay}>
      <div style={styles.card}>
        <h2 style={styles.title}>Welcome to FlightAlertPro ✈️</h2>
        <p style={styles.subtitle}>Let's set up your account in a few quick steps.</p>

        <div style={styles.stepIndicator}>
          {[1, 2, 3].map((s) => (
            <span key={s} style={{ ...styles.dot, ...(s === step ? styles.dotActive : {}) }} />
          ))}
        </div>

        {error && <p style={styles.error}>{error}</p>}

        {step === 1 && (
          <div>
            <h3 style={styles.stepTitle}>Step 1 of {TOTAL_STEPS}: Home Currency</h3>
            <p style={styles.hint}>Choose the currency you'd like to see prices in.</p>
            <div style={styles.row}>
              {CURRENCIES.map((c) => (
                <button
                  key={c}
                  onClick={() => setCurrency(c)}
                  style={{ ...styles.chip, ...(currency === c ? styles.chipActive : {}) }}
                >
                  {c}
                </button>
              ))}
            </div>
            <div style={styles.actions}>
              <button onClick={() => setStep(2)} style={styles.primaryBtn}>Next →</button>
              <button onClick={handleSkip} style={styles.skipBtn} disabled={saving}>Skip setup</button>
            </div>
          </div>
        )}

        {step === 2 && (
          <div>
            <h3 style={styles.stepTitle}>Step 2 of {TOTAL_STEPS}: Notification Channels</h3>
            <p style={styles.hint}>How should we notify you when a deal is found?</p>
            <div style={styles.row}>
              {CHANNELS.map((ch) => (
                <button
                  key={ch}
                  onClick={() => toggleChannel(ch)}
                  style={{ ...styles.chip, ...(channels.includes(ch) ? styles.chipActive : {}) }}
                >
                  {ch.charAt(0).toUpperCase() + ch.slice(1)}
                </button>
              ))}
            </div>
            <div style={styles.actions}>
              <button onClick={() => setStep(1)} style={styles.secondaryBtn}>← Back</button>
              <button onClick={() => setStep(3)} style={styles.primaryBtn}>Next →</button>
            </div>
          </div>
        )}

        {step === 3 && (
          <div>
            <h3 style={styles.stepTitle}>Step 3 of {TOTAL_STEPS}: Create Your First Alert (optional)</h3>
            <p style={styles.hint}>Set a price alert and we'll notify you when a deal appears.</p>
            <div style={styles.formGroup}>
              <label style={styles.label}>From</label>
              <AirportAutocomplete
                value={alertForm.from_iata}
                onChange={(val) => setAlertForm((p) => ({ ...p, from_iata: val }))}
                placeholder="Origin airport"
              />
            </div>
            <div style={styles.formGroup}>
              <label style={styles.label}>To</label>
              <AirportAutocomplete
                value={alertForm.to_iata}
                onChange={(val) => setAlertForm((p) => ({ ...p, to_iata: val }))}
                placeholder="Destination airport"
              />
            </div>
            <div style={styles.formGroup}>
              <label style={styles.label}>Max Price ({currency})</label>
              <input
                type="number"
                min="1"
                value={alertForm.max_price}
                onChange={(e) => setAlertForm((p) => ({ ...p, max_price: e.target.value }))}
                placeholder="e.g. 300"
                style={styles.input}
              />
            </div>
            <div style={styles.actions}>
              <button onClick={() => setStep(2)} style={styles.secondaryBtn}>← Back</button>
              <button onClick={() => finishOnboarding(true)} style={styles.primaryBtn} disabled={saving}>
                {saving ? 'Saving…' : 'Finish & Start Exploring'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

const styles = {
  overlay: {
    minHeight: '100vh',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: '#f0f4ff',
    padding: '2rem',
  },
  card: {
    background: '#fff',
    borderRadius: '12px',
    padding: '2.5rem',
    maxWidth: '520px',
    width: '100%',
    boxShadow: '0 4px 24px rgba(0,0,0,0.1)',
  },
  title: { fontSize: '1.5rem', fontWeight: '700', marginBottom: '0.5rem', color: '#1d4ed8' },
  subtitle: { color: '#6b7280', marginBottom: '1.5rem' },
  stepIndicator: { display: 'flex', gap: '0.5rem', marginBottom: '1.5rem' },
  dot: {
    width: '10px', height: '10px', borderRadius: '50%',
    background: '#d1d5db', display: 'inline-block',
  },
  dotActive: { background: '#1d4ed8' },
  stepTitle: { fontSize: '1.1rem', fontWeight: '600', marginBottom: '0.5rem', color: '#111827' },
  hint: { color: '#6b7280', marginBottom: '1rem', fontSize: '0.9rem' },
  row: { display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '1.5rem' },
  chip: {
    padding: '0.4rem 0.9rem', borderRadius: '20px', border: '1px solid #d1d5db',
    background: '#f9fafb', cursor: 'pointer', fontWeight: '500', fontSize: '0.9rem',
  },
  chipActive: { background: '#1d4ed8', color: '#fff', borderColor: '#1d4ed8' },
  formGroup: { marginBottom: '1rem' },
  label: { display: 'block', fontWeight: '500', marginBottom: '0.25rem', fontSize: '0.9rem' },
  input: {
    width: '100%', padding: '0.5rem 0.75rem', borderRadius: '6px',
    border: '1px solid #d1d5db', fontSize: '0.95rem', boxSizing: 'border-box',
  },
  actions: { display: 'flex', gap: '0.75rem', marginTop: '1.5rem', alignItems: 'center' },
  primaryBtn: {
    padding: '0.6rem 1.5rem', background: '#1d4ed8', color: '#fff',
    border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: '600',
  },
  secondaryBtn: {
    padding: '0.6rem 1.2rem', background: '#f3f4f6', color: '#374151',
    border: '1px solid #d1d5db', borderRadius: '6px', cursor: 'pointer',
  },
  skipBtn: {
    background: 'none', border: 'none', color: '#6b7280',
    cursor: 'pointer', fontSize: '0.875rem', textDecoration: 'underline',
  },
  error: { color: '#dc2626', marginBottom: '1rem', fontSize: '0.9rem' },
};
