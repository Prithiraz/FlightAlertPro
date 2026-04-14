import { buildHotelUrl } from '../lib/hotelAffiliate';

export default function FlightResultCard({ offer, cabinClass, onCreateAlert, subscriptionTier }) {
  const destination = offer.to_iata || '';
  const checkinDate = offer.arrival
    ? new Date(offer.arrival).toISOString().slice(0, 10)
    : offer.departure
      ? new Date(offer.departure).toISOString().slice(0, 10)
      : '';
  const hotelUrl = buildHotelUrl(destination, checkinDate);

  const tier = subscriptionTier || 'free';
  const hasAiAccess = tier === 'elite' || tier === 'business';
  const isErrorFare = Boolean(offer.is_error_fare);

  const cardBorderStyle = isErrorFare && hasAiAccess
    ? {
        boxShadow: '0 0 0 3px #ef4444, 0 0 18px 4px rgba(239,68,68,0.45)',
        border: '2px solid #f97316',
      }
    : {};

  return (
    <div
      className="bg-white rounded-lg p-5 shadow-md flex flex-col gap-1.5"
      style={cardBorderStyle}
    >
      {/* Error Fare badge — elite/business only */}
      {isErrorFare && hasAiAccess && (
        <div
          className="self-start text-xs font-bold px-3 py-1 rounded-full"
          style={{
            background: 'linear-gradient(90deg, #ef4444, #f97316)',
            color: '#fff',
            letterSpacing: '0.03em',
          }}
        >
          🔥 PROBABLE ERROR FARE
        </div>
      )}

      <div className="flex items-center gap-2 text-xl font-bold">
        <span className="text-blue-700">{offer.from_iata}</span>
        <span className="text-gray-400">→</span>
        <span className="text-blue-700">{offer.to_iata}</span>
      </div>

      <div className="text-sm text-gray-500">
        {offer.airline_name || offer.airline || '—'}&nbsp;|&nbsp;
        {offer.stops ?? 0} stop(s)&nbsp;|&nbsp;
        {offer.cabin_class || cabinClass}
      </div>

      {offer.departure && (
        <div className="text-sm text-gray-500">
          Dep: {new Date(offer.departure).toLocaleString()}
          {offer.arrival && ` · Arr: ${new Date(offer.arrival).toLocaleString()}`}
        </div>
      )}

      <div className="text-2xl font-bold text-green-600 mt-1">
        {offer.currency || 'USD'} {Number(offer.price).toFixed(2)}
      </div>

      {/* AI Market Advice — elite/business only */}
      {isErrorFare && (
        hasAiAccess ? (
          <div
            className="mt-2 rounded-lg px-3 py-2 text-sm"
            style={{ background: '#f0fdf4', border: '1px solid #bbf7d0' }}
          >
            <div className="font-semibold mb-1 text-gray-700">🤖 AI Market Advice</div>
            <div className="flex items-center gap-2">
              {offer.ai_action === 'BUY NOW' ? (
                <span
                  className="text-xs font-bold px-2 py-0.5 rounded"
                  style={{ background: '#16a34a', color: '#fff' }}
                >
                  ✅ BUY NOW
                </span>
              ) : (
                <span
                  className="text-xs font-bold px-2 py-0.5 rounded"
                  style={{ background: '#ca8a04', color: '#fff' }}
                >
                  ⏳ WAIT
                </span>
              )}
              <span className="text-gray-600">{offer.ai_advice}</span>
            </div>
          </div>
        ) : (
          <div
            className="mt-2 rounded-lg px-3 py-2 text-sm relative overflow-hidden"
            style={{ background: '#f8fafc', border: '1px solid #e2e8f0' }}
          >
            <div className="font-semibold mb-1 text-gray-700">🤖 AI Market Advice</div>
            <div
              style={{
                filter: 'blur(4px)',
                userSelect: 'none',
                pointerEvents: 'none',
              }}
            >
              ✅ BUY NOW — This price is significantly below the 14-day average,
              making it an exceptional deal worth booking immediately.
            </div>
            <div
              className="absolute inset-0 flex items-center justify-center"
              style={{ background: 'rgba(248,250,252,0.75)' }}
            >
              <a
                href="/pricing"
                className="text-xs font-semibold px-3 py-1.5 rounded-md"
                style={{ background: '#1d4ed8', color: '#fff', textDecoration: 'none' }}
              >
                🔒 Upgrade to Elite to see AI Advice
              </a>
            </div>
          </div>
        )
      )}

      <div className="flex gap-2 mt-1 flex-wrap">
        {offer.booking_link ? (
          <a
            href={offer.booking_link}
            target="_blank"
            rel="noopener noreferrer"
            className="px-4 py-2 bg-blue-700 text-white rounded-md text-sm font-semibold hover:bg-blue-800 transition"
          >
            Book Now
          </a>
        ) : (
          <span className="text-sm text-gray-400 self-center">Contact airline</span>
        )}
        <button
          onClick={() => onCreateAlert(offer)}
          className="px-3.5 py-1.5 bg-blue-50 text-blue-700 border border-blue-200 rounded-md text-sm font-semibold hover:bg-blue-100 transition"
        >
          Create alert
        </button>
        <a
          href={hotelUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="px-3.5 py-1.5 bg-amber-50 text-amber-700 border border-amber-200 rounded-md text-sm font-semibold hover:bg-amber-100 transition"
        >
          🏨 View Hotels in {destination}
        </a>
      </div>
    </div>
  );
}
