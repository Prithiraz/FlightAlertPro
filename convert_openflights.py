#!/usr/bin/env python3
"""Convert OpenFlights data to JSON format"""
import json
import csv

def parse_airports():
    """Parse airports.dat into structured JSON"""
    airports = []
    commercial_airports = []

    with open('airports.dat', 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 14:
                continue

            airport_id = row[0]
            name = row[1]
            city = row[2]
            country = row[3]
            iata = row[4]
            icao = row[5]
            lat = row[6]
            lon = row[7]
            altitude = row[8]
            timezone = row[9]
            dst = row[10]
            tz_name = row[11]
            type_code = row[12]
            source = row[13]

            # Skip if no IATA code
            if not iata or iata == '\\N':
                continue

            airport = {
                'id': airport_id,
                'name': name,
                'city': city,
                'country': country,
                'iata': iata,
                'icao': icao if icao != '\\N' else None,
                'latitude': float(lat) if lat != '\\N' else None,
                'longitude': float(lon) if lon != '\\N' else None,
                'altitude': int(altitude) if altitude != '\\N' else None,
                'timezone': timezone if timezone != '\\N' else None,
                'dst': dst,
                'tz_name': tz_name if tz_name != '\\N' else None,
                'type': type_code,
                'source': source
            }

            airports.append(airport)

            # Commercial airports filter
            is_commercial = (
                type_code == 'airport' and
                source == 'OurAirports' and
                airport['latitude'] is not None
            )

            # Include all UK airports
            is_uk = country == 'United Kingdom'

            # Major international airports (high traffic)
            major_cities = [
                'London', 'New York', 'Los Angeles', 'Chicago', 'Tokyo', 'Paris',
                'Dubai', 'Singapore', 'Hong Kong', 'Frankfurt', 'Amsterdam',
                'Madrid', 'Barcelona', 'Rome', 'Milan', 'Berlin', 'Munich',
                'Sydney', 'Melbourne', 'Toronto', 'Vancouver', 'Montreal',
                'Beijing', 'Shanghai', 'Seoul', 'Bangkok', 'Kuala Lumpur',
                'Istanbul', 'Moscow', 'Dublin', 'Edinburgh', 'Manchester',
                'Birmingham', 'Glasgow', 'Bristol', 'Liverpool', 'Leeds',
                'Newcastle', 'Belfast', 'Cardiff', 'Southampton', 'Nottingham',
                'San Francisco', 'Boston', 'Washington', 'Miami', 'Dallas',
                'Houston', 'Atlanta', 'Seattle', 'Denver', 'Las Vegas',
                'Orlando', 'Phoenix', 'Philadelphia', 'San Diego', 'Minneapolis',
                'Detroit', 'Portland', 'Austin', 'Nashville', 'Charlotte',
                'Mumbai', 'Delhi', 'Bangalore', 'Hyderabad', 'Chennai',
                'Kolkata', 'Pune', 'Ahmedabad', 'Jaipur', 'Kochi'
            ]

            is_major_city = any(major_city in city for major_city in major_cities)

            if is_commercial and (is_uk or is_major_city):
                commercial_airports.append(airport)

    print(f"✓ Parsed {len(airports)} total airports")
    print(f"✓ Filtered {len(commercial_airports)} commercial airports")

    return airports, commercial_airports

def parse_airlines():
    """Parse airlines.dat into structured JSON"""
    airlines = []

    with open('airlines.dat', 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 8:
                continue

            airline_id = row[0]
            name = row[1]
            alias = row[2]
            iata = row[3]
            icao = row[4]
            callsign = row[5]
            country = row[6]
            active = row[7]

            # Skip if no IATA code
            if not iata or iata == '\\N' or iata == '-':
                continue

            # Only include active airlines
            if active != 'Y':
                continue

            airline = {
                'id': airline_id,
                'name': name,
                'alias': alias if alias != '\\N' else None,
                'iata': iata,
                'icao': icao if icao != '\\N' else None,
                'callsign': callsign if callsign != '\\N' else None,
                'country': country,
                'active': active == 'Y'
            }

            airlines.append(airline)

    print(f"✓ Parsed {len(airlines)} active airlines with IATA codes")

    return airlines

if __name__ == '__main__':
    print("Converting OpenFlights data to JSON...")

    # Parse and save airports
    airports, commercial = parse_airports()

    with open('airports_openflights.json', 'w', encoding='utf-8') as f:
        json.dump(airports, f, ensure_ascii=False, indent=2)
    print(f"✓ Saved airports_openflights.json ({len(airports)} airports)")

    with open('airports_commercial.json', 'w', encoding='utf-8') as f:
        json.dump(commercial, f, ensure_ascii=False, indent=2)
    print(f"✓ Saved airports_commercial.json ({len(commercial)} airports)")

    # Parse and save airlines
    airlines = parse_airlines()

    with open('airlines_openflights.json', 'w', encoding='utf-8') as f:
        json.dump(airlines, f, ensure_ascii=False, indent=2)
    print(f"✓ Saved airlines_openflights.json ({len(airlines)} airlines)")

    print("\n✅ Conversion complete!")
