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
  const hasEliteAccess = tier === 'elite' || tier === 'business';
  const hasPointsAccess = tier === 'elite' || tier === 'business';
  const isErrorFare = Boolean(offer.is_error_fare);
  const isHackerFare = Boolean(offer.is_hacker_fare);

  // Card border/style
  const cardBorderStyle = isHackerFare
    ? {
        boxShadow: '0 0 0 2px #a855f7, 0 0 22px 6px rgba(168,85,247,0.35)',
        border: '2px solid #7c3aed',
        background: 'linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%)',
        color: '#e2d9f3',
      }
    : isErrorFare && hasAiAccess
      ? {
          boxShadow: '0 0 0 3px #ef4444, 0 0 18px 4px rgba(239,68,68,0.45)',
          border: '2px solid #f97316',
        }
      : {};

  const textClass = isHackerFare ? '#e2d9f3' : undefined;

  return (
    <div
      className="rounded-lg p-5 shadow-md flex flex-col gap-1.5"
      style={{ ...cardBorderStyle, ...(isHackerFare ? {} : { background: '#fff' }) }}
    >
      {/* Hacker Fare badge */}
      {isHackerFare && (
        <div
          className="self-start text-xs font-bold px-3 py-1 rounded-full"
          style={{
            background: 'linear-gradient(90deg, #7c3aed, #a855f7)',
            color: '#fff',
            letterSpacing: '0.04em',
          }}
        >
          🥷 Hacker Fare
        </div>
      )}

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
        <span style={{ color: isHackerFare ? '#c084fc' : '#1d4ed8' }}>{offer.from_iata}</span>
        <span style={{ color: '#9ca3af' }}>→</span>
        <span style={{ color: isHackerFare ? '#c084fc' : '#1d4ed8' }}>{offer.to_iata}</span>
      </div>

      {/* Hacker Fare: two-ticket display */}
      {isHackerFare ? (
        hasEliteAccess ? (
          <div className="flex flex-col gap-2 mt-1">
            <div
              className="rounded-md px-3 py-2 text-sm"
              style={{ background: 'rgba(124,58,237,0.2)', border: '1px solid #7c3aed' }}
            >
              <span className="font-semibold" style={{ color: '#c084fc' }}>Ticket 1 — Outbound: </span>
              <span style={{ color: '#e2d9f3' }}>{offer.outbound_airline_name || offer.outbound_airline_iata || '—'}</span>
              {offer.outbound_departure && (
                <span className="ml-2" style={{ color: '#a78bfa' }}>
                  Dep: {new Date(offer.outbound_departure).toLocaleString()}
                </span>
              )}
              <span className="ml-2 font-bold" style={{ color: '#86efac' }}>
                ${Number(offer.outbound_price).toFixed(2)}
              </span>
            </div>
            <div
              className="rounded-md px-3 py-2 text-sm"
              style={{ background: 'rgba(124,58,237,0.2)', border: '1px solid #7c3aed' }}
            >
              <span className="font-semibold" style={{ color: '#c084fc' }}>Ticket 2 — Inbound: </span>
              <span style={{ color: '#e2d9f3' }}>{offer.inbound_airline_name || offer.inbound_airline_iata || '—'}</span>
              {offer.inbound_departure && (
                <span className="ml-2" style={{ color: '#a78bfa' }}>
                  Dep: {new Date(offer.inbound_departure).toLocaleString()}
                </span>
              )}
              <span className="ml-2 font-bold" style={{ color: '#86efac' }}>
                ${Number(offer.inbound_price).toFixed(2)}
              </span>
            </div>
          </div>
        ) : (
          <div className="relative mt-1">
            <div
              className="rounded-md px-3 py-2 text-sm"
              style={{
                background: 'rgba(124,58,237,0.2)',
                border: '1px solid #7c3aed',
                filter: 'blur(4px)',
                userSelect: 'none',
                pointerEvents: 'none',
              }}
            >
              <div>Ticket 1 — Outbound: [Airline Name] · $–––</div>
              <div className="mt-1">Ticket 2 — Inbound: [Airline Name] · $–––</div>
            </div>
            <div
              className="absolute inset-0 flex items-center justify-center rounded-md"
              style={{ background: 'rgba(15,12,41,0.75)' }}
            >
              <a
                href="/pricing"
                className="text-xs font-semibold px-3 py-1.5 rounded-md text-center"
                style={{ background: '#7c3aed', color: '#fff', textDecoration: 'none' }}
              >
                🔒 Upgrade to Elite to unlock airlines & book
              </a>
            </div>
          </div>
        )
      ) : (
        <div className="text-sm text-gray-500">
          {offer.airline_name || offer.airline || '—'}&nbsp;|&nbsp;
          {offer.stops ?? 0} stop(s)&nbsp;|&nbsp;
          {offer.cabin_class || cabinClass}
        </div>
      )}

      {!isHackerFare && offer.departure && (
        <div className="text-sm text-gray-500">
          Dep: {new Date(offer.departure).toLocaleString()}
          {offer.arrival && ` · Arr: ${new Date(offer.arrival).toLocaleString()}`}
        </div>
      )}

      <div className="text-2xl font-bold mt-1" style={{ color: isHackerFare ? '#86efac' : '#16a34a' }}>
        {offer.currency || 'USD'} {Number(offer.price).toFixed(2)}
        {isHackerFare && offer.savings > 0 && (
          <span className="text-base font-semibold ml-2" style={{ color: '#a3e635' }}>
            (saves ${Number(offer.savings).toFixed(2)})
          </span>
        )}
      </div>

      {/* Points & Miles Valuation */}
      {offer.estimated_points_cost > 0 && (
        hasPointsAccess ? (
          <div className="flex items-center gap-2 flex-wrap mt-0.5">
            <span
              className="text-xs font-semibold px-2 py-0.5 rounded-full"
              style={{ background: '#eff6ff', color: '#1d4ed8', border: '1px solid #bfdbfe' }}
            >
              or ~{Number(offer.estimated_points_cost).toLocaleString()} pts
            </span>
            {offer.cpp_value > 1.5 && (
              <span
                className="text-xs font-semibold px-2 py-0.5 rounded-full"
                style={{ background: '#f0fdf4', color: '#15803d', border: '1px solid #bbf7d0' }}
              >
                💎 High Point Value ({Number(offer.cpp_value).toFixed(2)} cpp)
              </span>
            )}
          </div>
        ) : (
          <div className="relative mt-0.5">
            <div
              className="inline-flex items-center gap-2"
              style={{ filter: 'blur(4px)', userSelect: 'none', pointerEvents: 'none' }}
            >
              <span
                className="text-xs font-semibold px-2 py-0.5 rounded-full"
                style={{ background: '#eff6ff', color: '#1d4ed8', border: '1px solid #bfdbfe' }}
              >
                or ~40,000 pts
              </span>
              <span
                className="text-xs font-semibold px-2 py-0.5 rounded-full"
                style={{ background: '#f0fdf4', color: '#15803d', border: '1px solid #bbf7d0' }}
              >
                💎 High Point Value (1.8 cpp)
              </span>
            </div>
            <div className="mt-1">
              <a
                href="/pricing"
                className="text-xs font-semibold px-3 py-1 rounded-md"
                style={{ background: '#7c3aed', color: '#fff', textDecoration: 'none' }}
              >
                🔒 Are you a points maximizer? Upgrade to Elite to unlock Points Valuation.
              </a>
            </div>
          </div>
        )
      )}

      {/* AI Market Advice — elite/business only (non-hacker fares) */}
      {!isHackerFare && isErrorFare && (
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
        {isHackerFare ? (
          hasEliteAccess ? (
            <>
              {offer.outbound_booking_url && (
                <a
                  href={offer.outbound_booking_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-4 py-2 rounded-md text-sm font-semibold transition"
                  style={{ background: '#7c3aed', color: '#fff', textDecoration: 'none' }}
                >
                  Book Outbound
                </a>
              )}
              {offer.inbound_booking_url && (
                <a
                  href={offer.inbound_booking_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-4 py-2 rounded-md text-sm font-semibold transition"
                  style={{ background: '#a855f7', color: '#fff', textDecoration: 'none' }}
                >
                  Book Inbound
                </a>
              )}
            </>
          ) : null
        ) : (
          offer.booking_link || offer.booking_url ? (
            <a
              href={offer.booking_link || offer.booking_url}
              target="_blank"
              rel="noopener noreferrer"
              className="px-4 py-2 bg-blue-700 text-white rounded-md text-sm font-semibold hover:bg-blue-800 transition"
            >
              Book Now
            </a>
          ) : (
            <span className="text-sm text-gray-400 self-center">Contact airline</span>
          )
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
