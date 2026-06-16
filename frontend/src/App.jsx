import { createContext, useContext, useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { supabase } from './lib/supabase';
import Header from './components/Header';
import ProtectedRoute from './components/ProtectedRoute';
import Landing from './pages/Landing';
import Auth from './pages/Auth';
import ResetPassword from './pages/ResetPassword';
import Dashboard from './pages/Dashboard';
import Search from './pages/Search';
import Alerts from './pages/Alerts';
import Settings from './pages/Settings';
import Pricing from './pages/Pricing';
import Discover from './pages/Discover';
import DestinationHub from './pages/DestinationHub';
import AgentDashboard from './pages/AgentDashboard';
import DispatcherView from './pages/DispatcherView';
import DriverApp from './pages/DriverApp';

const AuthContext = createContext(null);

export function useAuth() {
  return useContext(AuthContext);
}

async function fetchSubscriptionTier(userId) {
  if (!userId) return 'free';
  const { data } = await supabase
    .from('user_profiles')
    .select('subscription_tier, elite_until')
    .eq('id', userId)
    .single();
  if (!data) return 'free';

  // Referral rewards use elite_until as a temporary Pro-access expiry timestamp.
  if (data.elite_until) {
    const eliteUntil = new Date(data.elite_until);
    if (eliteUntil > new Date()) {
      if ((data.subscription_tier ?? 'free') === 'free') {
        return 'pro';
      }
      return data.subscription_tier ?? 'free';
    }
  }

  return data.subscription_tier ?? 'free';
}

function App() {
  const [user, setUser] = useState(null);
  const [subscriptionTier, setSubscriptionTier] = useState('free');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    supabase.auth.getSession().then(async ({ data: { session } }) => {
      const u = session?.user ?? null;
      setUser(u);
      if (u) {
        const tier = await fetchSubscriptionTier(u.id);
        setSubscriptionTier(tier);
      }
      setLoading(false);
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange(async (_event, session) => {
      const u = session?.user ?? null;
      setUser(u);
      if (u) {
        const tier = await fetchSubscriptionTier(u.id);
        setSubscriptionTier(tier);
      } else {
        setSubscriptionTier('free');
      }
    });

    return () => subscription.unsubscribe();
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, subscriptionTier }}>
      <BrowserRouter>
        {user && <Header />}
        <Routes>
          <Route
            path="/"
            element={user ? <Navigate to="/dashboard" replace /> : <Landing />}
          />
          <Route path="/auth" element={user ? <Navigate to="/dashboard" replace /> : <Auth />} />
          <Route path="/login" element={<Navigate to="/auth" replace />} />
          <Route path="/reset" element={<ResetPassword />} />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/search"
            element={
              <ProtectedRoute>
                <Search />
              </ProtectedRoute>
            }
          />
          <Route
            path="/alerts"
            element={
              <ProtectedRoute>
                <Alerts />
              </ProtectedRoute>
            }
          />
          <Route
            path="/settings"
            element={
              <ProtectedRoute>
                <Settings />
              </ProtectedRoute>
            }
          />
          <Route path="/pricing" element={<Pricing />} />
          <Route
            path="/discover"
            element={
              <ProtectedRoute>
                <Discover />
              </ProtectedRoute>
            }
          />
          <Route
            path="/hub/:alert_id"
            element={
              <ProtectedRoute>
                <DestinationHub />
              </ProtectedRoute>
            }
          />
          <Route
            path="/agent-dashboard"
            element={
              <ProtectedRoute>
                <AgentDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/dispatcher"
            element={
              <ProtectedRoute>
                <DispatcherView />
              </ProtectedRoute>
            }
          />
          <Route path="/driver/:id" element={<DriverApp />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthContext.Provider>
  );
}

export default App;
