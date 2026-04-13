export default function FlightCardSkeleton() {
  return (
    <div className="bg-white rounded-lg p-5 shadow-md flex flex-col gap-3 animate-pulse">
      {/* Route row */}
      <div className="flex items-center gap-2">
        <div className="h-6 w-12 bg-gray-200 rounded" />
        <div className="h-4 w-4 bg-gray-200 rounded" />
        <div className="h-6 w-12 bg-gray-200 rounded" />
      </div>

      {/* Airline / stops / cabin */}
      <div className="h-4 w-48 bg-gray-200 rounded" />

      {/* Departure / arrival */}
      <div className="h-4 w-64 bg-gray-200 rounded" />

      {/* Price */}
      <div className="h-8 w-28 bg-gray-200 rounded mt-1" />

      {/* Buttons */}
      <div className="flex gap-2 mt-1">
        <div className="h-9 w-24 bg-gray-200 rounded-md" />
        <div className="h-9 w-28 bg-gray-200 rounded-md" />
      </div>
    </div>
  );
}
