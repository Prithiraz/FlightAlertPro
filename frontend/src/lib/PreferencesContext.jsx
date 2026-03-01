/**
 * UserPreferences context – provides locale, timezone, and homeCurrency
 * loaded from the user's profile to all child components.
 */

import { createContext, useContext, useState, useEffect } from 'react';
import { getProfile } from '../lib/api';

const PreferencesContext = createContext({
  locale: 'en-US',
  timezone: 'UTC',
  homeCurrency: 'USD',
  setPreferences: () => {},
});

export function usePreferences() {
  return useContext(PreferencesContext);
}

export function PreferencesProvider({ user, children }) {
  const [locale, setLocaleState] = useState('en-US');
  const [timezone, setTimezoneState] = useState('UTC');
  const [homeCurrency, setHomeCurrencyState] = useState('USD');

  useEffect(() => {
    if (!user) return;
    getProfile()
      .then((profile) => {
        if (profile.locale) setLocaleState(profile.locale);
        if (profile.timezone) setTimezoneState(profile.timezone);
        if (profile.home_currency) setHomeCurrencyState(profile.home_currency);
      })
      .catch(() => {});
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id]);

  const setPreferences = ({ locale: l, timezone: tz, homeCurrency: hc }) => {
    if (l) setLocaleState(l);
    if (tz) setTimezoneState(tz);
    if (hc) setHomeCurrencyState(hc);
  };

  return (
    <PreferencesContext.Provider value={{ locale, timezone, homeCurrency, setPreferences }}>
      {children}
    </PreferencesContext.Provider>
  );
}
