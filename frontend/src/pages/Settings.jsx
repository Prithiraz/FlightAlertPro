import { useState, useEffect, useRef } from 'react';
import { useAuth } from '../App';
import { getProfile, updateProfile, subscribePush, unsubscribePush } from '../lib/api';

const VAPID_PUBLIC_KEY = import.meta.env.VITE_VAPID_PUBLIC_KEY || '';

function urlBase64ToUint8Array(base64String) {
  // Add padding to make the length a multiple of 4 (required for atob)
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const raw = atob(base64);
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
}

export default function Settings() {
  const { user } = useAuth();
  const [lifecycleEmails, setLifecycleEmails] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

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
      })
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
      <h2 style={styles.heading}>Settings</h2>
      <div style={styles.card}>
        <h3 style={styles.subHeading}>Account</h3>
        <p style={styles.label}>Email</p>
        <p style={styles.value}>{user?.email ?? '—'}</p>
      </div>

      <div style={styles.card}>
        <h3 style={styles.subHeading}>Email Preferences</h3>
        <label style={styles.checkboxRow}>
          <input
            type="checkbox"
            checked={lifecycleEmails}
            onChange={handleToggle}
            disabled={saving}
            style={styles.checkbox}
          />
          <span style={styles.checkboxLabel}>
            Email me tips, product updates, and re-engagement nudges
          </span>
        </label>
        {saved && <p style={styles.savedMsg}>✓ Saved</p>}
        <p style={styles.note}>
          You will always receive transactional emails (price alerts, account security). This setting only controls marketing and lifecycle emails.
        </p>
      </div>

      {/* Push Notifications */}
      <div style={styles.card}>
        <h3 style={styles.subHeading}>Push Notifications</h3>
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
                Enable browser push notifications for price alerts
              </span>
            </label>
            {pushMsg && (
              <p style={{ ...styles.note, color: pushMsg.includes('enabled') ? '#16a34a' : '#374151' }}>
                {pushMsg}
              </p>
            )}
            <p style={styles.note}>
              Receive instant push notifications when a price alert triggers, even when the app is not open.
            </p>
          </>
        ) : (
          <p style={styles.note}>
            Push notifications are not supported in your current browser. Please use a modern browser (Chrome, Edge, Firefox) to enable this feature.
          </p>
        )}
      </div>

      {/* Install App */}
      {!isInstalled && (
        <div style={styles.card}>
          <h3 style={styles.subHeading}>Install App</h3>
          <p style={styles.note}>
            Install FlightAlertPro on your device for a native-app experience — works offline and adds to your home screen.
          </p>
          {installPrompt ? (
            <button onClick={handleInstall} style={styles.installBtn}>
              📲 Install App
            </button>
          ) : (
            <p style={styles.note}>
              To install, use your browser's "Add to Home Screen" option (usually in the address bar or share menu).
            </p>
          )}
        </div>
      )}
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
  checkboxRow: { display: 'flex', alignItems: 'flex-start', gap: '0.625rem', cursor: 'pointer', marginBottom: '0.75rem' },
  checkbox: { marginTop: '0.15rem', flexShrink: 0, width: '1rem', height: '1rem', cursor: 'pointer' },
  checkboxLabel: { fontSize: '0.9rem', color: '#111827', lineHeight: 1.5 },
  savedMsg: { fontSize: '0.8rem', color: '#16a34a', margin: '0 0 0.5rem', fontWeight: '600' },
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
};
