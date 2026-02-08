// Public app URL for stable redirect URLs
export const PUBLIC_APP_URL = import.meta.env.VITE_PUBLIC_APP_URL || 'https://sb1-e2tqgyfq.stackblitz.io';

export function getRuntimeOrigin(): string {
  return window.location.origin;
}

export function getApiBaseUrl(): string {
  return '/api';
}

export function isHostedEnvironment(): boolean {
  return !window.location.hostname.includes('localhost') && !window.location.hostname.includes('127.0.0.1');
}

export function getAuthRedirectUrl(): string {
  return `${PUBLIC_APP_URL}/auth/callback`;
}

export function logRuntimeInfo(): void {
  const origin = getRuntimeOrigin();
  const isHosted = isHostedEnvironment();
  console.log('[Runtime] Origin:', origin);
  console.log('[Runtime] Hosted environment:', isHosted);
  console.log('[Runtime] API base:', getApiBaseUrl());
  console.log('[Runtime] PUBLIC_APP_URL:', PUBLIC_APP_URL);
  console.log('[Runtime] Auth redirect URL:', getAuthRedirectUrl());
}
