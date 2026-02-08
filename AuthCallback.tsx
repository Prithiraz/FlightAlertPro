import { useEffect, useState } from 'react';
import { Check, X, Loader2, AlertCircle } from 'lucide-react';
import { supabase } from '../lib/db';

interface Props {
  isDark: boolean;
  onComplete: () => void;
}

export default function AuthCallback({ isDark, onComplete }: Props) {
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [message, setMessage] = useState('Processing authentication...');
  const [details, setDetails] = useState('');

  useEffect(() => {
    const handleAuthCallback = async () => {
      try {
        const hash = window.location.hash;
        const params = new URLSearchParams(window.location.search);
        const code = params.get('code');

        console.log('[AuthCallback] Processing callback');
        console.log('[AuthCallback] Hash present:', !!hash);
        console.log('[AuthCallback] Code present:', !!code);

        if (hash && hash.includes('access_token')) {
          console.log('[AuthCallback] Processing hash-based auth (access_token + refresh_token)');

          const hashParams = new URLSearchParams(hash.substring(1));
          const accessToken = hashParams.get('access_token');
          const refreshToken = hashParams.get('refresh_token');

          if (accessToken && refreshToken) {
            const { data, error } = await supabase.auth.setSession({
              access_token: accessToken,
              refresh_token: refreshToken,
            });

            if (error) {
              throw new Error(`Session setup failed: ${error.message}`);
            }

            window.history.replaceState({}, document.title, '/auth/callback');

            console.log('[AuthCallback] Hash auth successful:', data.user?.email);
            setStatus('success');
            setMessage('Signed in successfully!');
            setDetails(`Welcome, ${data.user?.email}`);

            setTimeout(() => {
              onComplete();
            }, 2000);
          } else {
            throw new Error('Missing access_token or refresh_token in hash');
          }
        } else if (code) {
          console.log('[AuthCallback] Processing code-based auth (PKCE flow)');

          const { data, error } = await supabase.auth.exchangeCodeForSession(code);

          if (error) {
            throw new Error(`Code exchange failed: ${error.message}`);
          }

          window.history.replaceState({}, document.title, '/auth/callback');

          console.log('[AuthCallback] Code auth successful:', data.user?.email);
          setStatus('success');
          setMessage('Signed in successfully!');
          setDetails(`Welcome, ${data.user?.email}`);

          setTimeout(() => {
            onComplete();
          }, 2000);
        } else {
          throw new Error('No authentication data found in URL (missing both hash tokens and code parameter)');
        }
      } catch (error) {
        console.error('[AuthCallback] Authentication failed:', error);
        setStatus('error');
        setMessage('Authentication failed');
        setDetails(error instanceof Error ? error.message : 'Unknown error occurred');
      }
    };

    handleAuthCallback();
  }, [onComplete]);

  return (
    <div className={`min-h-screen flex items-center justify-center ${isDark ? 'bg-gray-900' : 'bg-gray-50'}`}>
      <div className={`${isDark ? 'bg-gray-800' : 'bg-white'} rounded-lg shadow-2xl max-w-md w-full p-8 mx-4`}>
        <div className="text-center">
          {status === 'loading' && (
            <>
              <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <Loader2 className="w-8 h-8 text-blue-600 animate-spin" />
              </div>
              <h3 className="text-2xl font-bold mb-2">Authenticating</h3>
              <p className={`${isDark ? 'text-gray-300' : 'text-gray-600'}`}>{message}</p>
            </>
          )}

          {status === 'success' && (
            <>
              <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <Check className="w-8 h-8 text-green-600" />
              </div>
              <h3 className="text-2xl font-bold mb-2 text-green-600">{message}</h3>
              <p className={`${isDark ? 'text-gray-300' : 'text-gray-600'} mb-2`}>{details}</p>
              <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                Redirecting to your alerts...
              </p>
            </>
          )}

          {status === 'error' && (
            <>
              <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <X className="w-8 h-8 text-red-600" />
              </div>
              <h3 className="text-2xl font-bold mb-2 text-red-600">{message}</h3>
              <div className={`${isDark ? 'bg-red-900/20' : 'bg-red-50'} border ${isDark ? 'border-red-800' : 'border-red-200'} rounded-lg p-4 mb-4`}>
                <div className="flex items-start gap-2">
                  <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
                  <p className={`text-sm ${isDark ? 'text-red-300' : 'text-red-800'} text-left`}>{details}</p>
                </div>
              </div>
              <button
                onClick={onComplete}
                className="w-full bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-lg font-semibold"
              >
                Return to Home
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
