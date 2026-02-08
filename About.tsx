import { Plane, Search, Bell, TrendingUp } from 'lucide-react';

interface Props {
  isDark: boolean;
}

export default function About({ isDark }: Props) {
  return (
    <div className={`py-16 ${isDark ? 'bg-gray-900' : 'bg-gray-50'} min-h-screen`}>
      <div className="max-w-4xl mx-auto px-4">
        <h2 className="text-4xl font-bold mb-8">About FlightAlertPro</h2>

        <div className={`${isDark ? 'bg-gray-800' : 'bg-white'} rounded-lg shadow-lg p-8 mb-8`}>
          <p className="text-lg mb-4">
            FlightAlertPro is your intelligent flight search and price alert companion.
            We aggregate flights from multiple providers to help you find the best deals.
          </p>
          <p className="text-lg">
            Our AI-powered price predictions and real-time alerts ensure you never miss a great deal.
          </p>
        </div>

        <h3 className="text-2xl font-bold mb-6">Features</h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          <div className={`${isDark ? 'bg-gray-800' : 'bg-white'} rounded-lg shadow-lg p-6`}>
            <Search className="w-12 h-12 text-blue-600 mb-4" />
            <h4 className="text-xl font-bold mb-2">Multi-Provider Search</h4>
            <p>Search flights from Duffel, RapidAPI, and more providers in one place.</p>
          </div>

          <div className={`${isDark ? 'bg-gray-800' : 'bg-white'} rounded-lg shadow-lg p-6`}>
            <Bell className="w-12 h-12 text-blue-600 mb-4" />
            <h4 className="text-xl font-bold mb-2">Price Alerts</h4>
            <p>Get notified via email, WhatsApp, or Telegram when prices drop.</p>
          </div>

          <div className={`${isDark ? 'bg-gray-800' : 'bg-white'} rounded-lg shadow-lg p-6`}>
            <TrendingUp className="w-12 h-12 text-blue-600 mb-4" />
            <h4 className="text-xl font-bold mb-2">AI Predictions</h4>
            <p>Smart price predictions powered by machine learning.</p>
          </div>

          <div className={`${isDark ? 'bg-gray-800' : 'bg-white'} rounded-lg shadow-lg p-6`}>
            <Plane className="w-12 h-12 text-blue-600 mb-4" />
            <h4 className="text-xl font-bold mb-2">Multi-City Support</h4>
            <p>Plan complex itineraries with multiple destinations.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
