import { createContext, useContext, useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { supabase } from './lib/supabase';
import Header from './components/Header';
import ProtectedRoute from './components/ProtectedRoute';
import Auth from './pages/Auth';
import ResetPassword from './pages/ResetPassword';
import Settings from './pages/Settings';
import Dashboard from './pages/Dashboard'; // Pointing to your REAL telemetry dashboard
import DriverView from './pages/DriverView';

const AuthContext = createContext(null);

export function useAuth() {
  return useContext(AuthContext);
}

async function fetchSubscriptionTier(userId) {
  if (!userId) return 'free';
  const { data, error } = await supabase
    .from('user_profiles')
    .select('subscription_tier, elite_until')
    .eq('id', userId)
    .maybeSingle(); // FIX: Prevents the 406 error if a profile doesn't exist yet

  if (error || !data) return 'pro'; // Default to pro for logistics access

  if (data.elite_until) {
    const eliteUntil = new Date(data.elite_until);
    if (eliteUntil > new Date()) return 'pro';
  }

  return data.subscription_tier ?? 'pro';
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
          <Route path="/" element={user ? <Navigate to="/dashboard" replace /> : <Auth />} />
          <Route path="/auth" element={user ? <Navigate to="/dashboard" replace /> : <Auth />} />
          <Route path="/login" element={<Navigate to="/auth" replace />} />
          <Route path="/reset" element={<ResetPassword />} />
          
          <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
          <Route path="/settings" element={<ProtectedRoute><Settings /></ProtectedRoute>} />
          <Route path="/driver/:flightId" element={<DriverView />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthContext.Provider>
  );
}

export default App;