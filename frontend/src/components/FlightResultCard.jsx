export default function FlightResultCard({ offer, cabinClass, onCreateAlert }) {
  return (
    <div className="bg-white rounded-lg p-5 shadow-md flex flex-col gap-1.5">
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
      </div>
    </div>
  );
}
