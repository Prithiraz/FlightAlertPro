/**
 * Lightweight i18n translation system.
 * Currently supports English (en). Additional locales can be added
 * by importing their JSON and selecting based on the active locale.
 *
 * Usage:
 *   import { t } from '../i18n';
 *   t('settings.title')           // → "Settings"
 *   t('dashboard.flightsFound', { n: 5 }) // → "5 flights found"
 */

import en from './en.json';

// In the future: dynamically import locale files based on user locale.
const translations = en;

/**
 * Look up a translation key with optional interpolation.
 * Falls back to the key itself if not found.
 * @param {string} key
 * @param {Record<string, string|number>} [vars]
 * @returns {string}
 */
export function t(key, vars) {
  let str = translations[key] ?? key;
  if (vars) {
    Object.entries(vars).forEach(([k, v]) => {
      str = str.replace(new RegExp(`\\{${k}\\}`, 'g'), String(v));
    });
  }
  return str;
}
