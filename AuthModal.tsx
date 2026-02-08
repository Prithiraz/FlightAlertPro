import { useState } from 'react';
import { X, Mail, Check, AlertCircle, RefreshCw } from 'lucide-react';
import { supabase, getSupabaseHost } from '../lib/db';
import { PUBLIC_APP_URL, getAuthRedirectUrl } from '../lib/runtimeConfig';

interface Props {
  isDark: boolean;
  onClose: () => void;
}

export default function AuthModal({ isDark, onClose }: Props) {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [emailSent, setEmailSent] = useState(false);

  const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || '';
  const supabaseAnonKeyPresent = Boolean(import.meta.env.VITE_SUPABASE_ANON_KEY);
  const origin = window.location.origin;
  const redirectUrl = getAuthRedirectUrl();

  const initializedHost = getSupabaseHost();
  const supabaseHost = supabaseUrl ? new URL(supabaseUrl).host : 'Not configured';

  const restartRequired = initializedHost !== supabaseHost;

  const handleSignIn = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!email || !email.includes('@')) {
      setError('Please enter a valid email address');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const redirectTo = getAuthRedirectUrl();
      console.log('[Auth] Sending magic link with redirect:', redirectTo);

      const { error: signInError } = await supabase.auth.signInWithOtp({
        email,
        options: {
          emailRedirectTo: redirectTo,
        },
      });

      if (signInError) {
        throw signInError;
      }

      setEmailSent(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send magic link');
    } finally {
      setLoading(false);
    }
  };

  if (emailSent) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
        <div
          className={`${
            isDark ? 'bg-gray-800' : 'bg-white'
          } rounded-lg shadow-2xl max-w-md w-full p-8`}
        >
          <div className="text-center">
            <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <Check className="w-8 h-8 text-green-600" />
            </div>
            <h3 className="text-2xl font-bold mb-2">Check your email</h3>
            <p className={`${isDark ? 'text-gray-300' : 'text-gray-600'} mb-6`}>
              We sent a magic link to <strong>{email}</strong>
            </p>
            <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'} mb-6`}>
              Click the link in the email to sign in. You can close this window.
            </p>
            <button
              onClick={onClose}
              className="w-full bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-lg font-semibold"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div
        className={`${
          isDark ? 'bg-gray-800' : 'bg-white'
        } rounded-lg shadow-2xl max-w-md w-full p-8`}
      >
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-2xl font-bold">Sign In</h3>
          <button
            onClick={onClose}
            className={`${
              isDark ? 'text-gray-400 hover:text-gray-200' : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        <div className="mb-6">
          <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center mb-4">
            <Mail className="w-6 h-6 text-blue-600" />
          </div>
          <p className={`${isDark ? 'text-gray-300' : 'text-gray-600'}`}>
            Enter your email address and we'll send you a magic link to sign in. No password required!
          </p>
        </div>

        {error && (
          <div className="mb-4 bg-red-50 border border-red-200 rounded-lg p-3 flex items-start gap-2">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
            <p className="text-red-800 text-sm">{error}</p>
          </div>
        )}

        <form onSubmit={handleSignIn}>
          <div className="mb-6">
            <label className="block text-sm font-semibold mb-2">
              Email Address
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
              className={`w-full px-4 py-3 rounded-lg border ${
                isDark
                  ? 'bg-gray-700 border-gray-600 text-white'
                  : 'bg-white border-gray-300'
              } focus:outline-none focus:ring-2 focus:ring-blue-500`}
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-lg font-semibold disabled:bg-gray-400 disabled:cursor-not-allowed"
          >
            {loading ? 'Sending...' : 'Send Magic Link'}
          </button>
        </form>

        <p className={`text-xs ${isDark ? 'text-gray-400' : 'text-gray-500'} mt-4 text-center`}>
          By signing in, you agree to our Terms of Service and Privacy Policy
        </p>

        <div className={`mt-6 p-4 rounded-lg border ${isDark ? 'bg-gray-900 border-gray-700' : 'bg-gray-50 border-gray-200'}`}>
          <div className="text-xs font-semibold mb-2 text-gray-500 uppercase">Auth Debug Info</div>
          <div className="space-y-1 text-xs font-mono">
            <div className="flex justify-between">
              <span className="text-gray-500">PUBLIC_APP_URL:</span>
              <span className={isDark ? 'text-gray-300' : 'text-gray-700'}>{PUBLIC_APP_URL}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Redirect URL:</span>
              <span className={isDark ? 'text-gray-300' : 'text-gray-700'}>{redirectUrl}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Supabase host:</span>
              <span className={isDark ? 'text-gray-300' : 'text-gray-700'}>{supabaseHost}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Anon key present:</span>
              <span className={supabaseAnonKeyPresent ? 'text-green-600' : 'text-red-600'}>
                {supabaseAnonKeyPresent ? 'Yes' : 'No'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Origin:</span>
              <span className={isDark ? 'text-gray-300' : 'text-gray-700'}>{origin}</span>
            </div>
          </div>
          {!supabaseUrl && (
            <div className="mt-3 p-2 bg-red-100 border border-red-300 rounded text-xs text-red-800">
              <strong>Error:</strong> VITE_SUPABASE_URL is not set. Please configure it in your .env file.
            </div>
          )}
          {restartRequired && (
            <div className="mt-3 p-2 bg-orange-100 border border-orange-300 rounded text-xs text-orange-800 flex items-center gap-2">
              <RefreshCw className="w-4 h-4 flex-shrink-0" />
              <div>
                <strong>Restart required:</strong> Supabase URL changed. Restart the dev server to apply changes.
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
