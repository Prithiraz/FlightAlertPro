import { useState, useEffect, useRef } from 'react';
import { useAuth } from '../App';
import { usePreferences } from '../lib/PreferencesContext';
import { useWorkspace } from '../lib/WorkspaceContext';
import { getProfile, updateProfile, subscribePush, unsubscribePush, getMe, apiFetch } from '../lib/api';
import { t } from '../i18n';

const VAPID_PUBLIC_KEY = import.meta.env.VITE_VAPID_PUBLIC_KEY || '';

const HOME_CURRENCIES = ['USD', 'EUR', 'GBP', 'CAD', 'AUD', 'INR', 'JPY', 'SGD', 'AED', 'CHF', 'NZD', 'ZAR'];

const LOCALES = [
  { value: 'en-US', label: 'English (US)' },
  { value: 'en-GB', label: 'English (UK)' },
  { value: 'en-AU', label: 'English (AU)' },
  { value: 'en-CA', label: 'English (CA)' },
  { value: 'en-IN', label: 'English (IN)' },
  { value: 'de-DE', label: 'Deutsch (DE)' },
  { value: 'fr-FR', label: 'Français (FR)' },
  { value: 'es-ES', label: 'Español (ES)' },
  { value: 'pt-BR', label: 'Português (BR)' },
  { value: 'ja-JP', label: '日本語 (JP)' },
  { value: 'zh-CN', label: '中文 (CN)' },
];

// Common IANA timezone list
const TIMEZONES = [
  'UTC',
  'Europe/London',
  'Europe/Paris',
  'Europe/Berlin',
  'Europe/Madrid',
  'Europe/Rome',
  'Europe/Amsterdam',
  'America/New_York',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'America/Toronto',
  'America/Vancouver',
  'America/Sao_Paulo',
  'America/Mexico_City',
  'Asia/Dubai',
  'Asia/Kolkata',
  'Asia/Singapore',
  'Asia/Tokyo',
  'Asia/Shanghai',
  'Asia/Seoul',
  'Australia/Sydney',
  'Australia/Melbourne',
  'Pacific/Auckland',
  'Africa/Johannesburg',
];

function urlBase64ToUint8Array(base64String) {
  // Add padding to make the length a multiple of 4 (required for atob)
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const raw = atob(base64);
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
}

export default function Settings() {
  const { user } = useAuth();
  const { setPreferences } = usePreferences();
  const { currentWorkspace } = useWorkspace();
  const [lifecycleEmails, setLifecycleEmails] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [plan, setPlan] = useState('free');

  // Support bundle export
  const [bundleMsg, setBundleMsg] = useState('');

  // Display preferences
  const [homeCurrency, setHomeCurrency] = useState('USD');
  const [locale, setLocale] = useState('en-US');
  const [timezone, setTimezone] = useState('UTC');
  const [prefSaving, setPrefSaving] = useState(false);
  const [prefSaved, setPrefSaved] = useState(false);

  // Install prompt
  const [installPrompt, setInstallPrompt] = useState(null);
  const [isInstalled, setIsInstalled] = useState(false);

  // Push notifications
  const pushSupported = typeof window !== 'undefined' && 'PushManager' in window && 'serviceWorker' in navigator;
  const [pushEnabled, setPushEnabled] = useState(false);
  const [pushLoading, setPushLoading] = useState(false);
  const [pushMsg, setPushMsg] = useState('');
  const swRegRef = useRef(null);

  useEffect(() => {
    getProfile()
      .then((profile) => {
        if (profile.lifecycle_emails_opt_in !== undefined) {
          setLifecycleEmails(profile.lifecycle_emails_opt_in !== false);
        }
        if (profile.home_currency) setHomeCurrency(profile.home_currency);
        if (profile.locale) setLocale(profile.locale);
        if (profile.timezone) setTimezone(profile.timezone);
      })
      .catch(() => {});
    getMe()
      .then((me) => { if (me?.plan) setPlan(me.plan); })
      .catch(() => {});
  }, []);

  // Detect PWA install state
  useEffect(() => {
    const handler = (e) => {
      e.preventDefault();
      setInstallPrompt(e);
    };
    window.addEventListener('beforeinstallprompt', handler);

    // Check if already installed
    if (window.matchMedia('(display-mode: standalone)').matches) {
      setIsInstalled(true);
    }
    window.addEventListener('appinstalled', () => {
      setIsInstalled(true);
      setInstallPrompt(null);
    });

    return () => window.removeEventListener('beforeinstallprompt', handler);
  }, []);

  // Check existing push subscription
  useEffect(() => {
    if (!pushSupported) return;
    navigator.serviceWorker.ready.then((reg) => {
      swRegRef.current = reg;
      reg.pushManager.getSubscription().then((sub) => {
        setPushEnabled(!!sub);
      });
    }).catch(() => {});
  }, [pushSupported]);

  const handleInstall = async () => {
    if (!installPrompt) return;
    installPrompt.prompt();
    const { outcome } = await installPrompt.userChoice;
    if (outcome === 'accepted') setIsInstalled(true);
    setInstallPrompt(null);
  };

  const handleToggle = async (e) => {
    const val = e.target.checked;
    setLifecycleEmails(val);
    setSaving(true);
    setSaved(false);
    try {
      await updateProfile({ lifecycle_emails_opt_in: val });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {
      setLifecycleEmails(!val);
    } finally {
      setSaving(false);
    }
  };

  const handleSavePreferences = async () => {
    setPrefSaving(true);
    setPrefSaved(false);
    try {
      await updateProfile({ home_currency: homeCurrency, locale, timezone });
      setPreferences({ homeCurrency, locale, timezone });
      setPrefSaved(true);
      setTimeout(() => setPrefSaved(false), 2000);
    } catch {
      // ignore
    } finally {
      setPrefSaving(false);
    }
  };

  const handlePushToggle = async () => {
    if (!pushSupported) return;
    setPushLoading(true);
    setPushMsg('');
    try {
      const reg = swRegRef.current || await navigator.serviceWorker.ready;
      swRegRef.current = reg;

      if (pushEnabled) {
        // Unsubscribe
        const sub = await reg.pushManager.getSubscription();
        if (sub) {
          await sub.unsubscribe();
          try { await unsubscribePush(); } catch { /* endpoint may already be removed */ }
        }
        setPushEnabled(false);
        setPushMsg('Push notifications disabled.');
      } else {
        // Subscribe
        const permission = await Notification.requestPermission();
        if (permission !== 'granted') {
          setPushMsg('Permission denied. Please allow notifications in your browser settings.');
          return;
        }
        if (!VAPID_PUBLIC_KEY) {
          setPushMsg('Push not configured (missing VAPID key). Push notifications are unavailable.');
          return;
        }
        const sub = await reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY),
        });
        await subscribePush(sub.toJSON());
        setPushEnabled(true);
        setPushMsg('Push notifications enabled!');
      }
    } catch (err) {
      setPushMsg(err.message || 'Failed to update push notifications.');
    } finally {
      setPushLoading(false);
      setTimeout(() => setPushMsg(''), 4000);
    }
  };

  return (
    <div style={styles.page}>
      <h2 style={styles.heading}>{t('settings.title')}</h2>
      <div style={styles.card}>
        <h3 style={styles.subHeading}>{t('settings.account')}</h3>
        <p style={styles.label}>{t('settings.email')}</p>
        <p style={styles.value}>{user?.email ?? '—'}</p>
      </div>

      {/* Display Preferences */}
      <div style={styles.card}>
        <h3 style={styles.subHeading}>{t('settings.preferences')}</h3>
        <div style={styles.prefRow}>
          <div style={styles.prefField}>
            <label style={styles.label}>{t('settings.homeCurrency')}</label>
            <select
              value={homeCurrency}
              onChange={(e) => setHomeCurrency(e.target.value)}
              style={styles.select}
            >
              {HOME_CURRENCIES.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>
          <div style={styles.prefField}>
            <label style={styles.label}>{t('settings.locale')}</label>
            <select
              value={locale}
              onChange={(e) => setLocale(e.target.value)}
              style={styles.select}
            >
              {LOCALES.map((l) => (
                <option key={l.value} value={l.value}>{l.label}</option>
              ))}
            </select>
          </div>
          <div style={styles.prefField}>
            <label style={styles.label}>{t('settings.timezone')}</label>
            <select
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
              style={styles.select}
            >
              {TIMEZONES.map((tz) => (
                <option key={tz} value={tz}>{tz}</option>
              ))}
            </select>
          </div>
        </div>
        <button
          onClick={handleSavePreferences}
          disabled={prefSaving}
          style={styles.saveBtn}
        >
          {prefSaving ? t('settings.saving') : t('settings.savePreferences')}
        </button>
        {prefSaved && <p style={styles.savedMsg}>{t('settings.saved')}</p>}
      </div>

      <div style={styles.card}>
        <h3 style={styles.subHeading}>{t('settings.emailPrefs')}</h3>
        <label style={styles.checkboxRow}>
          <input
            type="checkbox"
            checked={lifecycleEmails}
            onChange={handleToggle}
            disabled={saving}
            style={styles.checkbox}
          />
          <span style={styles.checkboxLabel}>
            {t('settings.lifecycleEmails')}
          </span>
        </label>
        {saved && <p style={styles.savedMsg}>{t('settings.saved')}</p>}
        <p style={styles.note}>
          {t('settings.lifecycleNote')}
        </p>
      </div>

      {/* Push Notifications */}
      <div style={styles.card}>
        <h3 style={styles.subHeading}>{t('settings.pushNotifs')}</h3>
        {pushSupported ? (
          <>
            <label style={styles.checkboxRow}>
              <input
                type="checkbox"
                checked={pushEnabled}
                onChange={handlePushToggle}
                disabled={pushLoading}
                style={styles.checkbox}
              />
              <span style={styles.checkboxLabel}>
                {t('settings.pushEnable')}
              </span>
            </label>
            {pushMsg && (
              <p style={{ ...styles.note, color: pushMsg.includes('enabled') ? '#16a34a' : '#374151' }}>
                {pushMsg}
              </p>
            )}
            <p style={styles.note}>
              {t('settings.pushNote')}
            </p>
          </>
        ) : (
          <p style={styles.note}>
            {t('settings.pushUnsupported')}
          </p>
        )}
      </div>

      {/* Install App */}
      {!isInstalled && (
        <div style={styles.card}>
          <h3 style={styles.subHeading}>{t('settings.installApp')}</h3>
          <p style={styles.note}>
            {t('settings.installNote')}
          </p>
          {installPrompt ? (
            <button onClick={handleInstall} style={styles.installBtn}>
              {t('settings.installBtn')}
            </button>
          ) : (
            <p style={styles.note}>
              {t('settings.installManual')}
            </p>
          )}
        </div>
      )}

      {/* Support bundle export */}
      <div style={styles.card}>
        <h3 style={styles.subHeading}>Support</h3>
        <p style={styles.note}>Export a diagnostics bundle (no secrets) to share with support.</p>
        {bundleMsg && <p style={{ fontSize: '0.8rem', color: bundleMsg.startsWith('Error') ? '#dc2626' : '#16a34a', margin: '0.5rem 0' }}>{bundleMsg}</p>}
        <button
          style={styles.saveBtn}
          onClick={() => {
            setBundleMsg('Exporting…');
            apiFetch('/api/support/bundle')
              .then((data) => {
                const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `support-bundle-${new Date().toISOString().slice(0, 10)}.json`;
                a.click();
                URL.revokeObjectURL(url);
                setBundleMsg('Downloaded.');
                setTimeout(() => setBundleMsg(''), 4000);
              })
              .catch((e) => { setBundleMsg(`Error: ${e.message}`); setTimeout(() => setBundleMsg(''), 6000); });
          }}
        >📦 Export support bundle</button>
      </div>

      {/* Team — Business plan */}
      <div style={styles.card}>
        <h3 style={styles.subHeading}>Team &amp; Workspace</h3>
        {plan === 'business' || plan === 'elite' ? (
          <>
            <p style={styles.note}>
              Manage your team, invite members, and configure API keys from the Workspace page.
            </p>
            {currentWorkspace && (
              <p style={styles.note}>
                Current workspace: <strong>{currentWorkspace.name}</strong> ({currentWorkspace.plan})
              </p>
            )}
            <a href="/workspace" style={styles.teamLink}>
              Go to Workspace →
            </a>
          </>
        ) : (
          <>
            <p style={styles.note}>
              Team workspaces, member roles, and API keys are available on the <strong>Business</strong> plan.
            </p>
            <a href="/billing" style={styles.teamLink}>
              Upgrade to Business →
            </a>
          </>
        )}
      </div>
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
    marginBottom: '1.25rem',
  },
  subHeading: { fontSize: '1.125rem', fontWeight: '700', marginBottom: '1rem', color: '#374151' },
  label: { fontSize: '0.875rem', fontWeight: '600', color: '#374151', margin: '0 0 0.25rem' },
  value: { fontSize: '1rem', color: '#111827', margin: '0 0 1rem' },
  prefRow: { display: 'flex', gap: '1rem', flexWrap: 'wrap', marginBottom: '1rem' },
  prefField: { flex: '1', minWidth: '160px', display: 'flex', flexDirection: 'column', gap: '0.25rem' },
  select: { padding: '0.5rem 0.75rem', border: '1px solid #d1d5db', borderRadius: '6px', fontSize: '0.9rem', background: '#fff' },
  saveBtn: { padding: '0.5rem 1.25rem', background: '#1d4ed8', color: '#fff', border: 'none', borderRadius: '6px', fontSize: '0.9rem', fontWeight: '600', cursor: 'pointer' },
  checkboxRow: { display: 'flex', alignItems: 'flex-start', gap: '0.625rem', cursor: 'pointer', marginBottom: '0.75rem' },
  checkbox: { marginTop: '0.15rem', flexShrink: 0, width: '1rem', height: '1rem', cursor: 'pointer' },
  checkboxLabel: { fontSize: '0.9rem', color: '#111827', lineHeight: 1.5 },
  savedMsg: { fontSize: '0.8rem', color: '#16a34a', margin: '0.5rem 0 0', fontWeight: '600' },
  note: { fontSize: '0.8rem', color: '#9ca3af', margin: '0.5rem 0 0', lineHeight: 1.5 },
  installBtn: {
    marginTop: '0.75rem',
    padding: '0.625rem 1.5rem',
    background: '#1d4ed8',
    color: '#fff',
    border: 'none',
    borderRadius: '6px',
    fontSize: '1rem',
    fontWeight: '600',
    cursor: 'pointer',
    width: '100%',
  },
  teamLink: {
    display: 'inline-block',
    marginTop: '0.75rem',
    color: '#1d4ed8',
    fontWeight: '600',
    fontSize: '0.9rem',
    textDecoration: 'underline',
  },
};
