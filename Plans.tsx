import { useState, useEffect } from 'react';
import { Check, Loader2 } from 'lucide-react';
import { initiateCheckout } from '../lib/api';
import { type Currency, formatMoney, convertAmount } from '../lib/currency';

interface Props {
  isDark: boolean;
  currentPlan?: string;
  onUpgrade: (plan: string) => void;
  currency: Currency;
}

const PRICE_IDS = {
  'pro': 'price_1SWhPFDVVhYzpoXcDPJRecoW',
  'elite': 'price_1SWglVDVVhYzpoXc234uDqxW',
  'business': 'price_1SWgo6DVVhYzpoXcJL4CggwU'
};

const PLANS = [
  {
    name: 'Basic',
    priceUSD: 0,
    priceId: null,
    features: [
      '10 searches per month',
      'Email alerts',
      'Basic support',
      '1 price alert'
    ]
  },
  {
    name: 'Pro',
    priceUSD: 9.99,
    priceId: PRICE_IDS.pro,
    features: [
      '100 searches per month',
      'Email + WhatsApp alerts',
      'Priority support',
      '10 price alerts',
      'Price predictions'
    ]
  },
  {
    name: 'Elite',
    priceUSD: 19.99,
    priceId: PRICE_IDS.elite,
    features: [
      'Unlimited searches',
      'All notification channels',
      'Premium support',
      'Unlimited alerts',
      'Advanced analytics',
      'Multi-city search'
    ]
  },
  {
    name: 'Business',
    priceUSD: 49.99,
    priceId: PRICE_IDS.business,
    features: [
      'Everything in Elite',
      'API access',
      'Custom integrations',
      'Dedicated support',
      'Team management',
      'White-label options'
    ]
  }
];

export default function Plans({ isDark, currentPlan = 'basic', onUpgrade, currency }: Props) {
  const [convertedPrices, setConvertedPrices] = useState<Record<string, number>>({});
  const [isConverting, setIsConverting] = useState(false);

  useEffect(() => {
    const convertPrices = async () => {
      setIsConverting(true);
      const converted: Record<string, number> = {};

      for (const plan of PLANS) {
        if (plan.priceUSD > 0) {
          converted[plan.name] = await convertAmount(plan.priceUSD, 'USD', currency);
        }
      }

      setConvertedPrices(converted);
      setIsConverting(false);
    };

    convertPrices();
  }, [currency]);

  const handlePlanSelect = async (plan: typeof PLANS[0]) => {
    if (!plan.priceId) {
      onUpgrade('basic');
      return;
    }

    const result = await initiateCheckout(plan.priceId);

    if (result.url) {
      window.location.href = result.url;
    } else if (result.error) {
      alert(result.error);
    }
  };

  return (
    <div className={`py-16 ${isDark ? 'bg-gray-900' : 'bg-gray-50'}`}>
      <div className="max-w-7xl mx-auto px-4">
        <h2 className="text-4xl font-bold text-center mb-4">Choose Your Plan</h2>
        <p className="text-center text-gray-600 mb-12">Upgrade or downgrade anytime</p>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {PLANS.map((plan) => (
            <div
              key={plan.name}
              className={`${
                isDark ? 'bg-gray-800' : 'bg-white'
              } rounded-lg shadow-lg p-6 ${
                currentPlan.toLowerCase() === plan.name.toLowerCase()
                  ? 'ring-2 ring-blue-600'
                  : ''
              }`}
            >
              {currentPlan.toLowerCase() === plan.name.toLowerCase() && (
                <div className="text-sm font-semibold text-blue-600 mb-2">CURRENT PLAN</div>
              )}

              <h3 className="text-2xl font-bold mb-2">{plan.name}</h3>
              <div className="text-3xl font-bold text-blue-600 mb-6">
                {plan.priceUSD === 0 ? (
                  'Free'
                ) : isConverting ? (
                  <div className="flex items-center gap-2">
                    <Loader2 className="w-5 h-5 animate-spin" />
                    <span className="text-sm">Converting...</span>
                  </div>
                ) : (
                  `${formatMoney(convertedPrices[plan.name] || plan.priceUSD, currency)}/mo`
                )}
              </div>

              <ul className="space-y-3 mb-6">
                {plan.features.map((feature, idx) => (
                  <li key={idx} className="flex items-start gap-2">
                    <Check className="w-5 h-5 text-green-500 flex-shrink-0 mt-0.5" />
                    <span className="text-sm">{feature}</span>
                  </li>
                ))}
              </ul>

              <button
                onClick={() => handlePlanSelect(plan)}
                disabled={currentPlan.toLowerCase() === plan.name.toLowerCase()}
                className={`w-full py-3 rounded-lg font-semibold ${
                  currentPlan.toLowerCase() === plan.name.toLowerCase()
                    ? 'bg-gray-300 text-gray-600 cursor-not-allowed'
                    : 'bg-blue-600 hover:bg-blue-700 text-white'
                }`}
              >
                {currentPlan.toLowerCase() === plan.name.toLowerCase()
                  ? 'Current Plan'
                  : 'Select Plan'}
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
