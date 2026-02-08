import { useState, useEffect } from 'react';
import { Plane, Moon, Sun, User, AlertCircle, LogOut, LogIn, X, ChevronDown, ChevronUp } from 'lucide-react';
import { Currency, formatPrice, convertCurrencySync, convertCurrency, isFxApiAvailable } from './lib/currency';
import { supabase, getSupabaseHost } from './lib/db';
import { checkBackendHealth } from './lib/liveApi';
import { logRuntimeInfo, PUBLIC_APP_URL, getAuthRedirectUrl } from './lib/runtimeConfig';
import FlightSearchForm from './components/FlightSearchForm';
import Plans from './pages/Plans';
import Alerts from './pages/Alerts';
import About from './pages/About';
import SystemCheck from './pages/SystemCheck';
import AuthCallback from './pages/AuthCallback';
import AuthModal from './components/AuthModal';
import type { FlightOffer, SearchResponse } from './lib/api';
import type { User as SupabaseUser } from '@supabase/supabase-js';

function App() {
  const [currentPage, setCurrentPage] = useState<'search' | 'alerts' | 'about' | 'plans' | 'systemcheck' | 'authcallback'>('search');
  const [theme, setTheme] = useState<'light' | 'dark'>('light');
  const [currency, setCurrency] = useState<Currency>('USD');
  const [currentPlan, setCurrentPlan] = useState('basic');
  const [searchResults, setSearchResults] = useState<SearchResponse | null>(null);
  const [showProfileMenu, setShowProfileMenu] = useState(false);
  const [user, setUser] = useState<SupabaseUser | null>(null);
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [backendHealthy, setBackendHealthy] = useState(true);
  const [showBackendBanner, setShowBackendBanner] = useState(false);
  const [showAuthDebug, setShowAuthDebug] = useState(false);
  const [supabaseEnvError, setSupabaseEnvError] = useState<string | null>(null);
  const [wrongSupabaseProject, setWrongSupabaseProject] = useState<string | null>(null);
  const [dbHealthy, setDbHealthy] = useState(false);
  const [showDbBanner, setShowDbBanner] = useState(false);
  const [fxRateCached, setFxRateCached] = useState(false);

  const isDark = theme === 'dark';
  const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';

  useEffect(() => {
    logRuntimeInfo();

    const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
    const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

    if (!supabaseUrl) {
      setSupabaseEnvError('VITE_SUPABASE_URL is missing');
      return;
    }

    if (!supabaseAnonKey) {
      setSupabaseEnvError('VITE_SUPABASE_ANON_KEY is missing');
      return;
    }

    // Validate correct Supabase project
    try {
      const supabaseHost = new URL(supabaseUrl).host;
      if (supabaseHost !== 'aadzpnyxzyljvxoecdvo.supabase.co') {
        setWrongSupabaseProject(supabaseHost);
        return;
      }
    } catch {
      setSupabaseEnvError('VITE_SUPABASE_URL is invalid');
      return;
    }

    console.log('[Supabase] Environment variables present:', { url: !!supabaseUrl, key: !!supabaseAnonKey });

    console.log('===== AUTH DEBUG INFO =====');
    console.log('Origin:', window.location.origin);
    try {
      console.log('Supabase host:', supabaseUrl ? new URL(supabaseUrl).host : 'Not configured');
    } catch {
      console.log('Supabase host:', 'Invalid URL');
    }
    console.log('Anon key present:', !!supabaseAnonKey);
    console.log('Redirect target:', window.location.origin + '/auth/callback');
    console.log('==========================');

    if (window.location.pathname === '/auth/callback') {
      setCurrentPage('authcallback');
    }

    checkBackendHealth().then(({ healthy }) => {
      setBackendHealthy(healthy);
      setShowBackendBanner(!healthy);
      console.log('[Backend] System check result:', healthy ? 'PASS' : 'FAIL');
    });

    supabase.auth.getSession().then(async ({ data: { session }, error }) => {
      if (error) {
        console.error('[Auth] Session retrieval error:', error);
      }

      const currentUser = session?.user ?? null;
      setUser(currentUser);
      console.log('[Auth] Session status:', currentUser ? 'present' : 'absent');

      if (currentUser) {
        try {
          const { count, error: dbError } = await supabase
            .from('price_alerts')
            .select('*', { count: 'exact', head: true })
            .eq('user_email', currentUser.email!);

          if (dbError) {
            console.error('[DB] Smoke test failed:', dbError.message);
            setDbHealthy(false);
            setShowDbBanner(true);
          } else {
            console.log('[DB] price_alerts readable: true (count:', count ?? 0, ')');
            setDbHealthy(true);
          }
        } catch (err) {
          console.error('[DB] Smoke test exception:', err);
          setDbHealthy(false);
          setShowDbBanner(true);
        }
      }
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
      (() => {
        setUser(session?.user ?? null);
        if (event === 'SIGNED_IN') {
          console.log('[Auth] User signed in:', session?.user?.email);
        }
      })();
    });

    convertCurrency(1, 'USD', 'EUR').then(() => {
      setFxRateCached(true);
      console.log('[FX] Rate cached: true');
    }).catch(() => {
      console.warn('[FX] Initial cache load failed');
    });

    setTimeout(() => {
      console.log('===== VERIFICATION REPORT =====');
      console.log('Supabase connected:', !!supabaseUrl && !!supabaseAnonKey);
      console.log('Auth session:', user ? 'present' : 'absent');
      console.log('price_alerts readable:', dbHealthy);
      console.log('FX rate cached:', fxRateCached);
      console.log('===============================');
    }, 2000);

    return () => subscription.unsubscribe();
  }, []);

  useEffect(() => {
    const loadCurrencyRate = async () => {
      try {
        await convertCurrency(1, 'USD', currency);
      } catch (error) {
        console.warn(`[Currency] Failed to pre-load conversion rate for ${currency}`);
      }
    };

    loadCurrencyRate();
  }, [currency]);

  const handleUpgrade = (plan: string) => {
    setCurrentPlan(plan);
    alert(`Plan updated to ${plan}. In production, this would redirect to Stripe checkout.`);
  };

  const handleSignOut = async () => {
    await supabase.auth.signOut();
    setShowProfileMenu(false);
  };

  const renderPage = () => {
    switch (currentPage) {
      case 'authcallback':
        return (
          <AuthCallback
            isDark={isDark}
            onComplete={() => {
              setCurrentPage('alerts');
              window.history.pushState({}, '', '/');
            }}
          />
        );
      case 'alerts':
        return <Alerts isDark={isDark} onOpenAuth={() => setShowAuthModal(true)} />;
      case 'about':
        return <About isDark={isDark} />;
      case 'plans':
        return <Plans isDark={isDark} currentPlan={currentPlan} onUpgrade={handleUpgrade} currency={currency} />;
      case 'systemcheck':
        return <SystemCheck isDark={isDark} />;
      default:
        return (
          <>
            <section className="bg-gradient-to-br from-blue-600 to-blue-800 text-white py-20">
              <div className="max-w-5xl mx-auto px-4">
                <h2 className="text-5xl font-bold mb-4 text-center">Find Your Perfect Flight</h2>
                <p className="text-xl text-center mb-8 text-blue-100">
                  Search real flights from multiple providers with live pricing
                </p>
                <FlightSearchForm onSearchResults={setSearchResults} isDark={isDark} />
              </div>
            </section>

            {searchResults && searchResults.count > 0 && (
              <section className="py-16 max-w-7xl mx-auto px-4">
                <h3 className="text-3xl font-bold mb-4">
                  {searchResults.count} flights found for {searchResults.route}
                </h3>
                <p className="text-gray-600 mb-8">
                  Providers: {searchResults.providers.join(', ')}
                </p>

                <div className="space-y-4">
                  {searchResults.results.map((offer: FlightOffer) => (
                    <div
                      key={offer.id}
                      className={`${
                        isDark ? 'bg-gray-800' : 'bg-white'
                      } rounded-lg shadow-lg p-6 hover:shadow-xl transition`}
                    >
                      <div className="flex items-center justify-between flex-wrap gap-4">
                        <div className="flex-1 min-w-[300px]">
                          <div className="flex items-center gap-4 mb-2">
                            <div>
                              <div className="text-sm text-gray-500">From</div>
                              <div className="text-2xl font-bold">{offer.from_iata}</div>
                              <div className="text-sm">
                                {new Date(offer.departure).toLocaleTimeString([], {
                                  hour: '2-digit',
                                  minute: '2-digit'
                                })}
                              </div>
                            </div>
                            <div className="flex-1 flex flex-col items-center">
                              <Plane className="w-6 h-6 text-blue-600 rotate-90" />
                              <div className="text-sm text-gray-500">{offer.stops} stops</div>
                            </div>
                            <div>
                              <div className="text-sm text-gray-500">To</div>
                              <div className="text-2xl font-bold">{offer.to_iata}</div>
                              <div className="text-sm">
                                {new Date(offer.arrival).toLocaleTimeString([], {
                                  hour: '2-digit',
                                  minute: '2-digit'
                                })}
                              </div>
                            </div>
                          </div>
                          <div className="flex flex-wrap gap-4 text-sm text-gray-600">
                            <span>✈️ {offer.airline_name || offer.airline}</span>
                            <span>🔖 {offer.provider}</span>
                            {offer.duration_minutes && (
                              <span>
                                ⏱️ {Math.floor(offer.duration_minutes / 60)}h{' '}
                                {offer.duration_minutes % 60}m
                              </span>
                            )}
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-3xl font-bold text-blue-600">
                            {formatPrice(
                              convertCurrencySync(offer.price, offer.currency as Currency, currency),
                              currency
                            )}
                          </div>
                          {offer.booking_link ? (
                            <a
                              href={offer.booking_link}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="mt-2 inline-block bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded-lg transition"
                            >
                              Book Now
                            </a>
                          ) : (
                            <button className="mt-2 bg-gray-400 text-white px-6 py-2 rounded-lg cursor-not-allowed">
                              Contact Airline
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {searchResults && searchResults.count === 0 && (
              <section className="py-16 max-w-7xl mx-auto px-4 text-center">
                <AlertCircle className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                <h3 className="text-2xl font-bold mb-2">No flights found</h3>
                <p className="text-gray-600">Try different airports or dates</p>
              </section>
            )}
          </>
        );
    }
  };

  if (wrongSupabaseProject) {
    return (
      <div className="min-h-screen bg-red-50 flex items-center justify-center p-4">
        <div className="max-w-lg bg-white rounded-lg shadow-xl p-8 border-4 border-red-500">
          <div className="flex items-center gap-3 mb-4">
            <AlertCircle className="w-12 h-12 text-red-500" />
            <h1 className="text-2xl font-bold text-red-900">Wrong Supabase Project</h1>
          </div>
          <p className="text-red-800 mb-4 text-lg">
            Wrong Supabase project configured.
          </p>
          <div className="bg-red-100 rounded-lg p-4 border border-red-300 mb-4">
            <div className="text-sm text-red-800 space-y-2">
              <div className="flex justify-between">
                <span className="font-semibold">Currently configured:</span>
                <code className="bg-red-200 px-2 py-1 rounded font-mono">{wrongSupabaseProject}</code>
              </div>
              <div className="flex justify-between">
                <span className="font-semibold">Expected:</span>
                <code className="bg-green-100 px-2 py-1 rounded font-mono">aadzpnyxzyljvxoecdvo.supabase.co</code>
              </div>
            </div>
          </div>
          <div className="bg-red-100 rounded-lg p-4 border border-red-300">
            <p className="text-sm text-red-800 font-semibold mb-2">To fix this in StackBlitz:</p>
            <ol className="text-sm text-red-800 space-y-1 list-decimal list-inside">
              <li>Open the Environment Variables panel in StackBlitz</li>
              <li>Update <code className="bg-red-200 px-1 rounded">VITE_SUPABASE_URL</code> to <code className="bg-green-100 px-1 rounded">https://aadzpnyxzyljvxoecdvo.supabase.co</code></li>
              <li>Restart the development server</li>
            </ol>
          </div>
        </div>
      </div>
    );
  }

  if (supabaseEnvError) {
    return (
      <div className="min-h-screen bg-red-50 flex items-center justify-center p-4">
        <div className="max-w-lg bg-white rounded-lg shadow-xl p-8 border-4 border-red-500">
          <div className="flex items-center gap-3 mb-4">
            <AlertCircle className="w-12 h-12 text-red-500" />
            <h1 className="text-2xl font-bold text-red-900">Configuration Error</h1>
          </div>
          <p className="text-red-800 mb-4 text-lg">
            Missing required environment variable: <code className="bg-red-100 px-2 py-1 rounded font-mono">{supabaseEnvError}</code>
          </p>
          <div className="bg-red-100 rounded-lg p-4 border border-red-300">
            <p className="text-sm text-red-800 font-semibold mb-2">To fix this:</p>
            <ol className="text-sm text-red-800 space-y-1 list-decimal list-inside">
              <li>Create a <code className="bg-red-200 px-1 rounded">.env</code> file in the project root</li>
              <li>Add the missing variable with a valid Supabase URL and anon key</li>
              <li>Restart the development server</li>
            </ol>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      className={`min-h-screen ${
        isDark ? 'bg-gray-900 text-white' : 'bg-gray-50 text-gray-900'
      }`}
    >
      {showBackendBanner && (
        <div className="bg-yellow-500 text-black px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-5 h-5" />
            <span className="font-semibold">
              Backend not reachable: using offline airport/airline dataset
            </span>
          </div>
          <button
            onClick={() => setShowBackendBanner(false)}
            className="hover:bg-yellow-600 p-1 rounded"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      )}

      {showDbBanner && (
        <div className="bg-orange-500 text-white px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-5 h-5" />
            <span className="font-semibold">
              Database connected but table or RLS missing. Run Supabase migration.
            </span>
          </div>
          <button
            onClick={() => setShowDbBanner(false)}
            className="hover:bg-orange-600 p-1 rounded"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      )}

      {/* Auth Debug Panel */}
      {(isLocalhost || showAuthDebug) && currentPage !== 'authcallback' && (
        <div className={`${isDark ? 'bg-yellow-900/30' : 'bg-yellow-50'} border-b ${isDark ? 'border-yellow-800' : 'border-yellow-200'} px-4 py-2`}>
          <div className="max-w-7xl mx-auto">
            <button
              onClick={() => setShowAuthDebug(!showAuthDebug)}
              className="flex items-center gap-2 text-sm font-semibold mb-2 hover:text-blue-600"
            >
              {showAuthDebug ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              Auth Debug {isLocalhost ? '(Dev Mode)' : ''}
            </button>
            {showAuthDebug && (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
                <div>
                  <div className="font-semibold text-gray-700 dark:text-gray-300">PUBLIC_APP_URL:</div>
                  <div className={`font-mono text-xs ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                    {PUBLIC_APP_URL}
                  </div>
                </div>
                <div>
                  <div className="font-semibold text-gray-700 dark:text-gray-300">Redirect URL:</div>
                  <div className={`font-mono text-xs ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                    {getAuthRedirectUrl()}
                  </div>
                </div>
                <div>
                  <div className="font-semibold text-gray-700 dark:text-gray-300">Supabase Host:</div>
                  <div className={`font-mono text-xs ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                    {getSupabaseHost()}
                  </div>
                </div>
                <div>
                  <div className="font-semibold text-gray-700 dark:text-gray-300">Anon Key:</div>
                  <div className={`font-mono text-xs ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                    {import.meta.env.VITE_SUPABASE_ANON_KEY ? '✓ Present' : '✗ Missing'}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      <header className={`${isDark ? 'bg-gray-800' : 'bg-white'} shadow-sm sticky top-0 z-50`}>
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Plane className="w-6 h-6 text-blue-600" />
            <h1 className="text-xl font-bold cursor-pointer" onClick={() => setCurrentPage('search')}>
              FlightAlertPro
            </h1>
          </div>

          <nav className="flex items-center gap-6">
            <button
              onClick={() => setCurrentPage('search')}
              className={`hover:text-blue-600 ${currentPage === 'search' ? 'text-blue-600 font-semibold' : ''}`}
            >
              Search
            </button>
            <button
              onClick={() => setCurrentPage('alerts')}
              className={`hover:text-blue-600 ${currentPage === 'alerts' ? 'text-blue-600 font-semibold' : ''}`}
            >
              Alerts
            </button>
            <button
              onClick={() => setCurrentPage('about')}
              className={`hover:text-blue-600 ${currentPage === 'about' ? 'text-blue-600 font-semibold' : ''}`}
            >
              About
            </button>
            <button
              onClick={() => setCurrentPage('systemcheck')}
              className={`hover:text-blue-600 ${currentPage === 'systemcheck' ? 'text-blue-600 font-semibold' : ''}`}
            >
              System Check
            </button>

            <div className="flex items-center gap-3 ml-4 border-l pl-4">
              <div className="relative">
                <select
                  value={currency}
                  onChange={(e) => setCurrency(e.target.value as Currency)}
                  className={`px-2 py-1 rounded ${
                    isDark ? 'bg-gray-700' : 'bg-gray-100'
                  } text-sm`}
                >
                  <option value="USD">USD $</option>
                  <option value="GBP">GBP £</option>
                  <option value="EUR">EUR €</option>
                  <option value="CAD">CAD $</option>
                  <option value="AUD">AUD $</option>
                  <option value="INR">INR ₹</option>
                  <option value="JPY">JPY ¥</option>
                  <option value="SGD">SGD $</option>
                  <option value="AED">AED د.إ</option>
                </select>
                {currency !== 'USD' && !isFxApiAvailable() && (
                  <div className="absolute -bottom-6 left-0 text-xs text-yellow-600 whitespace-nowrap">
                    Live FX unavailable – showing USD
                  </div>
                )}
              </div>

              <button
                onClick={() => setTheme(isDark ? 'light' : 'dark')}
                className="p-2 rounded-full hover:bg-gray-200 dark:hover:bg-gray-700"
              >
                {isDark ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
              </button>

              <div className="relative">
                <button
                  onClick={() => setShowProfileMenu(!showProfileMenu)}
                  className="p-2 rounded-full hover:bg-gray-200 dark:hover:bg-gray-700"
                >
                  <User className="w-5 h-5" />
                </button>

                {showProfileMenu && (
                  <div
                    className={`absolute right-0 mt-2 w-48 ${
                      isDark ? 'bg-gray-800' : 'bg-white'
                    } rounded-lg shadow-lg border py-2`}
                  >
                    {user && (
                      <>
                        <div className="px-4 py-2 border-b">
                          <div className="text-xs text-gray-500">Signed in as</div>
                          <div className="text-sm font-semibold truncate">{user.email}</div>
                        </div>
                        <div className="px-4 py-2 border-b">
                          <div className="font-semibold">Current Plan</div>
                          <div className="text-sm text-blue-600">{currentPlan.toUpperCase()}</div>
                        </div>
                      </>
                    )}
                    {!user && (
                      <div className="px-4 py-2 border-b">
                        <div className="text-sm text-gray-500">Not signed in</div>
                      </div>
                    )}
                    <button
                      onClick={() => {
                        setCurrentPage('plans');
                        setShowProfileMenu(false);
                      }}
                      className="w-full text-left px-4 py-2 hover:bg-gray-100 dark:hover:bg-gray-700"
                    >
                      Manage Plan
                    </button>
                    <button
                      onClick={() => setShowProfileMenu(false)}
                      className="w-full text-left px-4 py-2 hover:bg-gray-100 dark:hover:bg-gray-700"
                    >
                      Settings
                    </button>
                  </div>
                )}

                {user ? (
                  <button
                    onClick={handleSignOut}
                    className="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 text-sm font-semibold"
                  >
                    <LogOut className="w-4 h-4" />
                    Sign Out
                  </button>
                ) : (
                  <button
                    onClick={() => setShowAuthModal(true)}
                    className="flex items-center gap-2 px-3 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold"
                  >
                    <LogIn className="w-4 h-4" />
                    Sign In
                  </button>
                )}
              </div>
            </div>
          </nav>
        </div>
      </header>

      <main>{renderPage()}</main>

      <footer className={`${isDark ? 'bg-gray-800' : 'bg-gray-900'} text-white py-8 mt-16`}>
        <div className="max-w-7xl mx-auto px-4 text-center">
          <p>© 2024 FlightAlertPro. All rights reserved.</p>
        </div>
      </footer>

      {showAuthModal && (
        <AuthModal
          isDark={isDark}
          onClose={() => setShowAuthModal(false)}
        />
      )}
    </div>
  );
}

export default App;
