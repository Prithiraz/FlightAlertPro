import { useState, useEffect } from 'react';
import { Bell, Plus, Trash2, Power, X, Check, AlertCircle, Mail, MessageCircle } from 'lucide-react';
import {
  getPriceAlerts,
  togglePriceAlertActive,
  deletePriceAlert,
  createPriceAlert,
  getSupabaseAuth,
  PriceAlert
} from '../lib/liveApi';

interface Props {
  isDark: boolean;
  onOpenAuth: () => void;
}

interface CreateAlertForm {
  from_iata: string;
  to_iata: string;
  max_price: string;
  departure_date: string;
  channels: string[];
  phone: string;
}

export default function Alerts({ isDark, onOpenAuth }: Props) {
  const [alerts, setAlerts] = useState<PriceAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const [formData, setFormData] = useState<CreateAlertForm>({
    from_iata: '',
    to_iata: '',
    max_price: '',
    departure_date: '',
    channels: ['email'],
    phone: ''
  });

  const [formErrors, setFormErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    checkAuthAndLoadAlerts();
  }, []);

  const checkAuthAndLoadAlerts = async () => {
    try {
      const auth = getSupabaseAuth();
      const { data: { user } } = await auth.getUser();

      if (user?.email) {
        setUserEmail(user.email);
        await loadAlerts(user.email);
      } else {
        setUserEmail(null);
        setLoading(false);
      }
    } catch (err) {
      console.error('Auth check failed:', err);
      setError('AUTH: Failed to verify authentication');
      setLoading(false);
    }
  };

  const loadAlerts = async (email: string) => {
    try {
      setLoading(true);
      setError(null);
      const data = await getPriceAlerts(email);
      setAlerts(data);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load alerts';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const validateForm = (): boolean => {
    const errors: Record<string, string> = {};

    if (!formData.from_iata || formData.from_iata.length !== 3) {
      errors.from_iata = 'Origin must be a 3-letter IATA code';
    }

    if (!formData.to_iata || formData.to_iata.length !== 3) {
      errors.to_iata = 'Destination must be a 3-letter IATA code';
    }

    const price = parseFloat(formData.max_price);
    if (!formData.max_price || isNaN(price) || price <= 0) {
      errors.max_price = 'Max price must be a positive number';
    }

    if (formData.channels.includes('whatsapp') && !formData.phone) {
      errors.phone = 'Phone number required for WhatsApp alerts';
    }

    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleCreateAlert = async () => {
    if (!validateForm() || !userEmail) return;

    setCreating(true);
    setError(null);

    try {
      const result = await createPriceAlert({
        user_email: userEmail,
        from_iata: formData.from_iata.toUpperCase(),
        to_iata: formData.to_iata.toUpperCase(),
        max_price: parseFloat(formData.max_price),
        departure_date: formData.departure_date || undefined,
        channels: formData.channels,
        phone: formData.phone || undefined
      });

      if (result.success) {
        setSuccessMessage('Alert created successfully');
        setShowCreateModal(false);
        setFormData({
          from_iata: '',
          to_iata: '',
          max_price: '',
          departure_date: '',
          channels: ['email'],
          phone: ''
        });
        setFormErrors({});
        await loadAlerts(userEmail);

        setTimeout(() => setSuccessMessage(null), 3000);
      } else {
        setError(result.error || 'Failed to create alert');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'NETWORK: Failed to create alert');
    } finally {
      setCreating(false);
    }
  };

  const handleToggleActive = async (alertId: string, currentActive: boolean) => {
    if (!userEmail) return;

    const result = await togglePriceAlertActive(alertId, !currentActive);

    if (result.success) {
      setAlerts(alerts.map(alert =>
        alert.id === alertId ? { ...alert, active: !currentActive } : alert
      ));
      setSuccessMessage(`Alert ${!currentActive ? 'activated' : 'deactivated'}`);
      setTimeout(() => setSuccessMessage(null), 2000);
    } else {
      setError(result.error || 'Failed to toggle alert');
      setTimeout(() => setError(null), 3000);
    }
  };

  const handleDeleteAlert = async (alertId: string) => {
    if (!userEmail || !confirm('Are you sure you want to delete this alert?')) return;

    const result = await deletePriceAlert(alertId);

    if (result.success) {
      setAlerts(alerts.filter(alert => alert.id !== alertId));
      setSuccessMessage('Alert deleted successfully');
      setTimeout(() => setSuccessMessage(null), 2000);
    } else {
      setError(result.error || 'Failed to delete alert');
      setTimeout(() => setError(null), 3000);
    }
  };

  const toggleChannel = (channel: string) => {
    setFormData(prev => ({
      ...prev,
      channels: prev.channels.includes(channel)
        ? prev.channels.filter(c => c !== channel)
        : [...prev.channels, channel]
    }));
  };

  if (loading) {
    return (
      <div className={`py-16 ${isDark ? 'bg-gray-900' : 'bg-gray-50'} min-h-screen flex items-center justify-center`}>
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading alerts...</p>
        </div>
      </div>
    );
  }

  if (!userEmail) {
    return (
      <div className={`py-16 ${isDark ? 'bg-gray-900' : 'bg-gray-50'} min-h-screen`}>
        <div className="max-w-7xl mx-auto px-4">
          <div className={`${isDark ? 'bg-gray-800' : 'bg-white'} rounded-lg shadow-lg p-12 text-center`}>
            <AlertCircle className="w-16 h-16 text-yellow-500 mx-auto mb-4" />
            <h2 className="text-3xl font-bold mb-4">Sign In Required</h2>
            <p className="text-gray-600 mb-6">
              You need to sign in to manage price alerts. Create an account or log in to get notified when flight prices drop.
            </p>
            <button
              onClick={onOpenAuth}
              className="bg-blue-600 hover:bg-blue-700 text-white px-8 py-3 rounded-lg font-semibold"
            >
              Sign In
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`py-16 ${isDark ? 'bg-gray-900' : 'bg-gray-50'} min-h-screen`}>
      <div className="max-w-7xl mx-auto px-4">
        <div className="flex items-center justify-between mb-8">
          <h2 className="text-4xl font-bold flex items-center gap-3">
            <Bell className="w-10 h-10 text-blue-600" />
            Price Alerts
          </h2>
          <button
            onClick={() => setShowCreateModal(true)}
            className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-lg flex items-center gap-2 font-semibold"
          >
            <Plus className="w-5 h-5" />
            Create Alert
          </button>
        </div>

        {successMessage && (
          <div className="mb-6 bg-green-50 border border-green-200 rounded-lg p-4 flex items-center gap-3">
            <Check className="w-5 h-5 text-green-600" />
            <p className="text-green-800">{successMessage}</p>
          </div>
        )}

        {error && (
          <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-red-600" />
            <p className="text-red-800">{error}</p>
          </div>
        )}

        {alerts.length === 0 ? (
          <div className={`${isDark ? 'bg-gray-800' : 'bg-white'} rounded-lg shadow-lg p-12 text-center`}>
            <Bell className="w-16 h-16 text-gray-400 mx-auto mb-4" />
            <h3 className="text-2xl font-bold mb-2">No alerts yet</h3>
            <p className="text-gray-600 mb-6">
              Create price alerts to get notified when flight prices drop below your target price
            </p>
            <button
              onClick={() => setShowCreateModal(true)}
              className="bg-blue-600 hover:bg-blue-700 text-white px-8 py-3 rounded-lg font-semibold"
            >
              Create Your First Alert
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            {alerts.map((alert) => (
              <div
                key={alert.id}
                className={`${isDark ? 'bg-gray-800' : 'bg-white'} rounded-lg shadow-lg p-6`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-3">
                      <h3 className="text-2xl font-bold">
                        {alert.from_iata} → {alert.to_iata}
                      </h3>
                      <span
                        className={`px-3 py-1 rounded-full text-sm font-semibold ${
                          alert.active
                            ? 'bg-green-100 text-green-800'
                            : 'bg-gray-100 text-gray-800'
                        }`}
                      >
                        {alert.active ? 'Active' : 'Inactive'}
                      </span>
                    </div>

                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                      <div>
                        <span className="text-gray-500">Max Price:</span>
                        <p className="font-semibold">
                          {alert.max_price.toFixed(2)} {alert.currency || 'USD'}
                        </p>
                      </div>
                      <div>
                        <span className="text-gray-500">Departure:</span>
                        <p className="font-semibold">
                          {alert.departure_date || 'Any date'}
                        </p>
                      </div>
                      <div>
                        <span className="text-gray-500">Channels:</span>
                        <div className="flex gap-2 mt-1">
                          {alert.channels.map((channel) => (
                            <span
                              key={channel}
                              className="flex items-center gap-1 text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded"
                            >
                              {channel === 'email' && <Mail className="w-3 h-3" />}
                              {channel === 'whatsapp' && <MessageCircle className="w-3 h-3" />}
                              {channel}
                            </span>
                          ))}
                        </div>
                      </div>
                      <div>
                        <span className="text-gray-500">Created:</span>
                        <p className="font-semibold">
                          {new Date(alert.created_at).toLocaleDateString()}
                        </p>
                      </div>
                    </div>
                  </div>

                  <div className="flex gap-2 ml-4">
                    <button
                      onClick={() => handleToggleActive(alert.id, alert.active)}
                      className={`p-2 rounded-lg ${
                        alert.active
                          ? 'bg-gray-200 hover:bg-gray-300 text-gray-700'
                          : 'bg-green-100 hover:bg-green-200 text-green-700'
                      }`}
                      title={alert.active ? 'Deactivate' : 'Activate'}
                    >
                      <Power className="w-5 h-5" />
                    </button>
                    <button
                      onClick={() => handleDeleteAlert(alert.id)}
                      className="p-2 rounded-lg bg-red-100 hover:bg-red-200 text-red-700"
                      title="Delete"
                    >
                      <Trash2 className="w-5 h-5" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {showCreateModal && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
            <div className={`${isDark ? 'bg-gray-800' : 'bg-white'} rounded-lg shadow-2xl max-w-md w-full p-6`}>
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-2xl font-bold">Create Price Alert</h3>
                <button
                  onClick={() => setShowCreateModal(false)}
                  className="text-gray-500 hover:text-gray-700"
                >
                  <X className="w-6 h-6" />
                </button>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-semibold mb-2">
                    From (IATA Code)
                  </label>
                  <input
                    type="text"
                    value={formData.from_iata}
                    onChange={(e) => setFormData({ ...formData, from_iata: e.target.value.toUpperCase() })}
                    maxLength={3}
                    placeholder="LAX"
                    className={`w-full px-4 py-2 rounded-lg border ${
                      formErrors.from_iata ? 'border-red-500' : 'border-gray-300'
                    } ${isDark ? 'bg-gray-700' : 'bg-white'}`}
                  />
                  {formErrors.from_iata && (
                    <p className="text-red-500 text-xs mt-1">{formErrors.from_iata}</p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-semibold mb-2">
                    To (IATA Code)
                  </label>
                  <input
                    type="text"
                    value={formData.to_iata}
                    onChange={(e) => setFormData({ ...formData, to_iata: e.target.value.toUpperCase() })}
                    maxLength={3}
                    placeholder="JFK"
                    className={`w-full px-4 py-2 rounded-lg border ${
                      formErrors.to_iata ? 'border-red-500' : 'border-gray-300'
                    } ${isDark ? 'bg-gray-700' : 'bg-white'}`}
                  />
                  {formErrors.to_iata && (
                    <p className="text-red-500 text-xs mt-1">{formErrors.to_iata}</p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-semibold mb-2">
                    Max Price
                  </label>
                  <input
                    type="number"
                    value={formData.max_price}
                    onChange={(e) => setFormData({ ...formData, max_price: e.target.value })}
                    placeholder="500"
                    min="0"
                    step="0.01"
                    className={`w-full px-4 py-2 rounded-lg border ${
                      formErrors.max_price ? 'border-red-500' : 'border-gray-300'
                    } ${isDark ? 'bg-gray-700' : 'bg-white'}`}
                  />
                  {formErrors.max_price && (
                    <p className="text-red-500 text-xs mt-1">{formErrors.max_price}</p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-semibold mb-2">
                    Departure Date (Optional)
                  </label>
                  <input
                    type="date"
                    value={formData.departure_date}
                    onChange={(e) => setFormData({ ...formData, departure_date: e.target.value })}
                    className={`w-full px-4 py-2 rounded-lg border border-gray-300 ${isDark ? 'bg-gray-700' : 'bg-white'}`}
                  />
                </div>

                <div>
                  <label className="block text-sm font-semibold mb-2">
                    Notification Channels
                  </label>
                  <div className="space-y-2">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={formData.channels.includes('email')}
                        onChange={() => toggleChannel('email')}
                        className="w-4 h-4"
                      />
                      <Mail className="w-4 h-4 text-blue-600" />
                      <span>Email</span>
                    </label>
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={formData.channels.includes('whatsapp')}
                        onChange={() => toggleChannel('whatsapp')}
                        className="w-4 h-4"
                      />
                      <MessageCircle className="w-4 h-4 text-green-600" />
                      <span>WhatsApp</span>
                    </label>
                  </div>
                </div>

                {formData.channels.includes('whatsapp') && (
                  <div>
                    <label className="block text-sm font-semibold mb-2">
                      Phone Number
                    </label>
                    <input
                      type="tel"
                      value={formData.phone}
                      onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                      placeholder="+1234567890"
                      className={`w-full px-4 py-2 rounded-lg border ${
                        formErrors.phone ? 'border-red-500' : 'border-gray-300'
                      } ${isDark ? 'bg-gray-700' : 'bg-white'}`}
                    />
                    {formErrors.phone && (
                      <p className="text-red-500 text-xs mt-1">{formErrors.phone}</p>
                    )}
                  </div>
                )}
              </div>

              <div className="flex gap-3 mt-6">
                <button
                  onClick={() => setShowCreateModal(false)}
                  className="flex-1 px-4 py-2 rounded-lg border border-gray-300 hover:bg-gray-100"
                >
                  Cancel
                </button>
                <button
                  onClick={handleCreateAlert}
                  disabled={creating}
                  className="flex-1 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold disabled:bg-gray-400"
                >
                  {creating ? 'Creating...' : 'Create Alert'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
