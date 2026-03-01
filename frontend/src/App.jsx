import { createContext, useContext, useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { supabase } from './lib/supabase';
import { getProfile } from './lib/api';
import Header from './components/Header';
import ProtectedRoute from './components/ProtectedRoute';
import Login from './pages/Login';
import ResetPassword from './pages/ResetPassword';
import Dashboard from './pages/Dashboard';
import Search from './pages/Search';
import Alerts from './pages/Alerts';
import Settings from './pages/Settings';
import Billing from './pages/Billing';
import Onboarding from './pages/Onboarding';
import SavedSearches from './pages/SavedSearches';
import Notifications from './pages/Notifications';
import Admin from './pages/Admin';
import Analytics from './pages/Analytics';

const AuthContext = createContext(null);

export function useAuth() {
  return useContext(AuthContext);
}

function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [onboarded, setOnboarded] = useState(true); // default true to avoid flash

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setUser(session?.user ?? null);
      setLoading(false);
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null);
    });

    return () => subscription.unsubscribe();
  }, []);

  // Check onboarding status whenever user logs in
  useEffect(() => {
    if (!user) {
      setOnboarded(true);
      return;
    }
    let cancelled = false;
    getProfile()
      .then((profile) => { if (!cancelled) setOnboarded(profile.onboarded === true); })
      .catch(() => { if (!cancelled) setOnboarded(true); }); // fail open
    return () => { cancelled = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id]);

  return (
    <AuthContext.Provider value={{ user, loading }}>
      <BrowserRouter>
        {user && onboarded && <Header />}
        <Routes>
          <Route
            path="/"
            element={
              user
                ? onboarded
                  ? <Navigate to="/dashboard" replace />
                  : <Navigate to="/onboarding" replace />
                : <Login />
            }
          />
          <Route path="/reset" element={<ResetPassword />} />
          <Route
            path="/onboarding"
            element={
              <ProtectedRoute>
                <Onboarding onComplete={() => setOnboarded(true)} />
              </ProtectedRoute>
            }
          />
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
            path="/saved"
            element={
              <ProtectedRoute>
                <SavedSearches />
              </ProtectedRoute>
            }
          />
          <Route
            path="/notifications"
            element={
              <ProtectedRoute>
                <Notifications />
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
          <Route
            path="/billing"
            element={
              <ProtectedRoute>
                <Billing />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin"
            element={
              <ProtectedRoute>
                <Admin />
              </ProtectedRoute>
            }
          />
          <Route
            path="/analytics"
            element={
              <ProtectedRoute>
                <Analytics />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthContext.Provider>
  );
}

export default App;
