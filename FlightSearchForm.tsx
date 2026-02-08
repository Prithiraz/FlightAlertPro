import { useState, useEffect } from 'react';
import { Search, Loader2, AlertCircle, Plus, X } from 'lucide-react';
import { searchCities, type Airport, type CityGroup } from '../lib/airports';
import { searchAirlines, type Airline } from '../lib/airlines';
import { searchFlights } from '../lib/api';

interface Props {
  onSearchResults: (results: any) => void;
  isDark: boolean;
}

let airlineDebounceTimer: NodeJS.Timeout;
let cityDebounceTimer: NodeJS.Timeout;

export default function FlightSearchForm({ onSearchResults, isDark }: Props) {
  const [tripType, setTripType] = useState<'oneway' | 'return' | 'multicity'>('return');

  const [segments, setSegments] = useState<Array<{
    from: string;
    to: string;
    date: string;
    airline: string;
    fromCities: CityGroup[];
    toCities: CityGroup[];
    showFromDropdown: boolean;
    showToDropdown: boolean;
  }>>([
    { from: '', to: '', date: '', airline: '', fromCities: [], toCities: [], showFromDropdown: false, showToDropdown: false }
  ]);

  const [airlineQuery, setAirlineQuery] = useState('');
  const [airlineSuggestions, setAirlineSuggestions] = useState<Airline[]>([]);
  const [showAirlineDropdown, setShowAirlineDropdown] = useState(false);
  const [selectedAirline, setSelectedAirline] = useState<Airline | null>(null);

  const [adults, setAdults] = useState(1);
  const [children, setChildren] = useState(0);
  const [infants, setInfants] = useState(0);

  const [minBaggage, setMinBaggage] = useState<number>(0);
  const [maxBaggage, setMaxBaggage] = useState<number>(30);

  const [isSearching, setIsSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (airlineQuery.length >= 1) {
      clearTimeout(airlineDebounceTimer);
      airlineDebounceTimer = setTimeout(async () => {
        const results = await searchAirlines(airlineQuery);
        setAirlineSuggestions(results);
      }, 200);
    } else {
      setAirlineSuggestions([]);
    }
  }, [airlineQuery]);

  useEffect(() => {
    if (tripType === 'return' && segments.length === 1) {
      setSegments([
        segments[0],
        { from: '', to: '', date: '', airline: '', fromCities: [], toCities: [], showFromDropdown: false, showToDropdown: false }
      ]);
    } else if (tripType === 'oneway' && segments.length > 1) {
      setSegments([segments[0]]);
    }
  }, [tripType]);

  const updateSegment = (index: number, field: string, value: any) => {
    const newSegments = [...segments];
    newSegments[index] = { ...newSegments[index], [field]: value };

    if (field === 'from' && value.length >= 1) {
      clearTimeout(cityDebounceTimer);
      cityDebounceTimer = setTimeout(async () => {
        const cities = await searchCities(value);
        setSegments(prev => {
          const updated = [...prev];
          updated[index].fromCities = cities;
          updated[index].showFromDropdown = true;
          return updated;
        });
      }, 200);
    } else if (field === 'from') {
      newSegments[index].fromCities = [];
      newSegments[index].showFromDropdown = false;
    }

    if (field === 'to' && value.length >= 1) {
      clearTimeout(cityDebounceTimer);
      cityDebounceTimer = setTimeout(async () => {
        const cities = await searchCities(value);
        setSegments(prev => {
          const updated = [...prev];
          updated[index].toCities = cities;
          updated[index].showToDropdown = true;
          return updated;
        });
      }, 200);
    } else if (field === 'to') {
      newSegments[index].toCities = [];
      newSegments[index].showToDropdown = false;
    }

    setSegments(newSegments);
  };

  const selectCity = (index: number, field: 'from' | 'to', city: CityGroup, allAirports: boolean) => {
    const newSegments = [...segments];

    if (allAirports) {
      newSegments[index][field] = `${city.city}, ${city.country} (All airports)`;
    } else if (city.airports.length === 1) {
      newSegments[index][field] = `${city.airports[0].iata} - ${city.city}`;
    }

    newSegments[index][field === 'from' ? 'showFromDropdown' : 'showToDropdown'] = false;
    setSegments(newSegments);
  };

  const selectAirport = (index: number, field: 'from' | 'to', airport: Airport) => {
    const newSegments = [...segments];
    newSegments[index][field] = `${airport.iata} - ${airport.city}`;
    newSegments[index][field === 'from' ? 'showFromDropdown' : 'showToDropdown'] = false;
    setSegments(newSegments);
  };

  const selectAirlineOption = (airline: Airline) => {
    setSelectedAirline(airline);
    setAirlineQuery(`${airline.iata} - ${airline.name}`);
    setShowAirlineDropdown(false);
  };

  const addSegment = () => {
    setSegments([...segments, {
      from: '',
      to: '',
      date: '',
      airline: '',
      fromCities: [],
      toCities: [],
      showFromDropdown: false,
      showToDropdown: false
    }]);
  };

  const removeSegment = (index: number) => {
    if (segments.length > 1) {
      setSegments(segments.filter((_, i) => i !== index));
    }
  };

  const handleSearch = async () => {
    if (tripType === 'multicity') {
      const invalidSegments = segments.filter(s => !s.from || !s.to || !s.date);
      if (invalidSegments.length > 0) {
        setError('Please fill all segment details');
        return;
      }
    } else {
      const seg = segments[0];
      if (!seg.from || !seg.to || !seg.date) {
        setError('Please fill all required fields');
        return;
      }
    }

    setIsSearching(true);
    setError(null);

    try {
      const fromIata = segments[0].from.split(' ')[0].trim();
      const toIata = segments[0].to.split(' ')[0].trim();

      const results = await searchFlights({
        from_iata: fromIata,
        to_iata: toIata,
        departure_date: segments[0].date,
        return_date: tripType === 'return' && segments[1]?.date ? segments[1].date : undefined,
        passengers: adults + children + infants,
        cabin_class: 'economy',
        airline: selectedAirline?.iata,
        adults,
        children,
        infants,
        min_baggage_kg: minBaggage,
        max_baggage_kg: maxBaggage,
        segments: tripType === 'multicity' ? segments.map(s => ({
          from_iata: s.from.split(' ')[0].trim(),
          to_iata: s.to.split(' ')[0].trim(),
          departure_date: s.date,
          airline: selectedAirline?.iata
        })) : undefined
      });

      onSearchResults(results);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed');
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <div className={`${isDark ? 'bg-gray-800' : 'bg-white'} rounded-xl shadow-2xl p-6 ${isDark ? 'text-white' : 'text-gray-900'}`}>
      <div className="flex gap-4 mb-6">
        <button
          onClick={() => setTripType('oneway')}
          className={`px-4 py-2 rounded-lg ${tripType === 'oneway' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600'}`}
        >
          One Way
        </button>
        <button
          onClick={() => setTripType('return')}
          className={`px-4 py-2 rounded-lg ${tripType === 'return' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600'}`}
        >
          Return
        </button>
        <button
          onClick={() => setTripType('multicity')}
          className={`px-4 py-2 rounded-lg ${tripType === 'multicity' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600'}`}
        >
          Multi-City
        </button>
      </div>

      {segments.map((segment, index) => (
        <div key={index} className="mb-4 p-4 border rounded-lg relative">
          {tripType === 'multicity' && segments.length > 1 && (
            <button
              onClick={() => removeSegment(index)}
              className="absolute top-2 right-2 text-red-500 hover:text-red-700"
            >
              <X className="w-5 h-5" />
            </button>
          )}

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="relative">
              <label className="block text-sm font-medium mb-2">
                From {tripType === 'multicity' && `(Flight ${index + 1})`}
              </label>
              <input
                type="text"
                value={segment.from}
                onChange={(e) => updateSegment(index, 'from', e.target.value)}
                placeholder="Type city name"
                className={`w-full px-4 py-3 rounded-lg border ${isDark ? 'bg-gray-700 border-gray-600' : 'bg-white border-gray-300'}`}
              />
              {segment.showFromDropdown && (
                <div className={`absolute z-20 w-full mt-1 ${isDark ? 'bg-gray-700' : 'bg-white'} border rounded-lg shadow-lg max-h-96 overflow-y-auto`}>
                  {segment.fromCities.length === 0 ? (
                    <div className="px-4 py-3 text-center text-gray-500">
                      <AlertCircle className="w-5 h-5 mx-auto mb-1" />
                      <div className="text-sm">No results (backend unreachable or no matches)</div>
                    </div>
                  ) : (
                    segment.fromCities.map((cityGroup, cidx) => (
                      <div key={cidx} className="border-b last:border-b-0">
                        <div className="px-4 py-2 font-semibold bg-gray-100 dark:bg-gray-800">
                          {cityGroup.city}, {cityGroup.country}
                        </div>
                        <button
                          onClick={() => selectCity(index, 'from', cityGroup, true)}
                          className={`w-full text-left px-6 py-2 hover:bg-blue-50 ${isDark ? 'hover:bg-gray-600' : ''} italic`}
                        >
                          All airports in {cityGroup.city}
                        </button>
                        {cityGroup.airports.map((airport, aidx) => (
                          <button
                            key={aidx}
                            onClick={() => selectAirport(index, 'from', airport)}
                            className={`w-full text-left px-6 py-2 hover:bg-blue-50 ${isDark ? 'hover:bg-gray-600' : ''}`}
                          >
                            <div>{airport.iata} - {airport.name}</div>
                          </button>
                        ))}
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>

            <div className="relative">
              <label className="block text-sm font-medium mb-2">To</label>
              <input
                type="text"
                value={segment.to}
                onChange={(e) => updateSegment(index, 'to', e.target.value)}
                placeholder="Type city name"
                className={`w-full px-4 py-3 rounded-lg border ${isDark ? 'bg-gray-700 border-gray-600' : 'bg-white border-gray-300'}`}
              />
              {segment.showToDropdown && (
                <div className={`absolute z-20 w-full mt-1 ${isDark ? 'bg-gray-700' : 'bg-white'} border rounded-lg shadow-lg max-h-96 overflow-y-auto`}>
                  {segment.toCities.length === 0 ? (
                    <div className="px-4 py-3 text-center text-gray-500">
                      <AlertCircle className="w-5 h-5 mx-auto mb-1" />
                      <div className="text-sm">No results (backend unreachable or no matches)</div>
                    </div>
                  ) : (
                    segment.toCities.map((cityGroup, cidx) => (
                      <div key={cidx} className="border-b last:border-b-0">
                        <div className="px-4 py-2 font-semibold bg-gray-100 dark:bg-gray-800">
                          {cityGroup.city}, {cityGroup.country}
                        </div>
                        <button
                          onClick={() => selectCity(index, 'to', cityGroup, true)}
                          className={`w-full text-left px-6 py-2 hover:bg-blue-50 ${isDark ? 'hover:bg-gray-600' : ''} italic`}
                        >
                          All airports in {cityGroup.city}
                        </button>
                        {cityGroup.airports.map((airport, aidx) => (
                          <button
                            key={aidx}
                            onClick={() => selectAirport(index, 'to', airport)}
                            className={`w-full text-left px-6 py-2 hover:bg-blue-50 ${isDark ? 'hover:bg-gray-600' : ''}`}
                          >
                            <div>{airport.iata} - {airport.name}</div>
                          </button>
                        ))}
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">
                {tripType === 'return' && index === 1 ? 'Return Date' : 'Date'}
              </label>
              <input
                type="date"
                value={segment.date}
                onChange={(e) => updateSegment(index, 'date', e.target.value)}
                className={`w-full px-4 py-3 rounded-lg border ${isDark ? 'bg-gray-700 border-gray-600' : 'bg-white border-gray-300'}`}
              />
            </div>
          </div>
        </div>
      ))}

      {tripType === 'multicity' && (
        <button
          onClick={addSegment}
          className="mb-4 flex items-center gap-2 text-blue-600 hover:text-blue-700"
        >
          <Plus className="w-5 h-5" />
          Add another flight
        </button>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
        <div className="relative">
          <label className="block text-sm font-medium mb-2">Airline (Optional)</label>
          <input
            type="text"
            value={airlineQuery}
            onChange={(e) => {
              setAirlineQuery(e.target.value);
              setShowAirlineDropdown(true);
            }}
            onFocus={() => setShowAirlineDropdown(true)}
            placeholder="Type airline name or code"
            className={`w-full px-4 py-3 rounded-lg border ${isDark ? 'bg-gray-700 border-gray-600' : 'bg-white border-gray-300'}`}
          />
          {showAirlineDropdown && airlineQuery.length >= 1 && (
            <div className={`absolute z-20 w-full mt-1 ${isDark ? 'bg-gray-700' : 'bg-white'} border rounded-lg shadow-lg max-h-60 overflow-y-auto`}>
              {airlineSuggestions.length === 0 ? (
                <div className="px-4 py-3 text-center text-gray-500">
                  <AlertCircle className="w-5 h-5 mx-auto mb-1" />
                  <div className="text-sm">No results (backend unreachable or no matches)</div>
                </div>
              ) : (
                airlineSuggestions.map((airline, idx) => (
                  <button
                    key={idx}
                    onClick={() => selectAirlineOption(airline)}
                    className={`w-full text-left px-4 py-2 hover:bg-blue-50 ${isDark ? 'hover:bg-gray-600' : ''}`}
                  >
                    <div className="font-semibold">{airline.iata} - {airline.name}</div>
                    <div className="text-sm text-gray-500">{airline.country}</div>
                  </button>
                ))
              )}
            </div>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium mb-2">Passengers</label>
          <div className="grid grid-cols-3 gap-2">
            <div>
              <label className="text-xs">Adults</label>
              <input
                type="number"
                min="1"
                value={adults}
                onChange={(e) => setAdults(Number(e.target.value))}
                className={`w-full px-2 py-2 rounded border ${isDark ? 'bg-gray-700 border-gray-600' : 'bg-white border-gray-300'}`}
              />
            </div>
            <div>
              <label className="text-xs">Children</label>
              <input
                type="number"
                min="0"
                value={children}
                onChange={(e) => setChildren(Number(e.target.value))}
                className={`w-full px-2 py-2 rounded border ${isDark ? 'bg-gray-700 border-gray-600' : 'bg-white border-gray-300'}`}
              />
            </div>
            <div>
              <label className="text-xs">Infants</label>
              <input
                type="number"
                min="0"
                value={infants}
                onChange={(e) => setInfants(Number(e.target.value))}
                className={`w-full px-2 py-2 rounded border ${isDark ? 'bg-gray-700 border-gray-600' : 'bg-white border-gray-300'}`}
              />
            </div>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium mb-2">Baggage (kg)</label>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-xs">Min</label>
              <input
                type="number"
                min="0"
                value={minBaggage}
                onChange={(e) => setMinBaggage(Number(e.target.value))}
                className={`w-full px-2 py-2 rounded border ${isDark ? 'bg-gray-700 border-gray-600' : 'bg-white border-gray-300'}`}
              />
            </div>
            <div>
              <label className="text-xs">Max</label>
              <input
                type="number"
                min="0"
                value={maxBaggage}
                onChange={(e) => setMaxBaggage(Number(e.target.value))}
                className={`w-full px-2 py-2 rounded border ${isDark ? 'bg-gray-700 border-gray-600' : 'bg-white border-gray-300'}`}
              />
            </div>
          </div>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-100 text-red-700 rounded-lg flex items-center gap-2">
          <AlertCircle className="w-5 h-5" />
          {error}
        </div>
      )}

      <button
        onClick={handleSearch}
        disabled={isSearching}
        className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-semibold py-4 rounded-lg flex items-center justify-center gap-2 transition"
      >
        {isSearching ? (
          <>
            <Loader2 className="w-5 h-5 animate-spin" />
            Searching flights...
          </>
        ) : (
          <>
            <Search className="w-5 h-5" />
            Search Flights
          </>
        )}
      </button>
    </div>
  );
}
