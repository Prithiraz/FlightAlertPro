import { useState, useEffect } from 'react';

/**
 * OfflineBanner – shows a banner when the browser reports navigator.onLine === false.
 */
export default function OfflineBanner() {
  const [offline, setOffline] = useState(() => !navigator.onLine);

  useEffect(() => {
    const goOffline = () => setOffline(true);
    const goOnline = () => setOffline(false);
    window.addEventListener('offline', goOffline);
    window.addEventListener('online', goOnline);
    return () => {
      window.removeEventListener('offline', goOffline);
      window.removeEventListener('online', goOnline);
    };
  }, []);

  if (!offline) return null;

  return (
    <div style={styles.banner} role="alert" aria-live="polite">
      📡 You are offline. Showing cached data where available.
    </div>
  );
}

const styles = {
  banner: {
    background: 'var(--color-warning-bg, #92400e)',
    color: 'var(--color-warning-text, #fef3c7)',
    textAlign: 'center',
    padding: '0.6rem 1rem',
    fontSize: '0.875rem',
    fontWeight: '600',
    position: 'sticky',
    top: 0,
    zIndex: 99,
  },
};
