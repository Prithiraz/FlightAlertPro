/*
  # Add flight_price_cache table

  1. New Table
    - `flight_price_cache` — stores the latest API response for each unique
      route + date combination so that multiple users tracking the same flight
      share a single external API call.

  2. Columns
    - `origin`            — departure airport IATA code
    - `destination`       — arrival airport IATA code
    - `departure_date`    — flight date (DATE)
    - `lowest_price`      — cheapest price returned by the external API
    - `api_response_json` — full JSON payload from the external API (JSONB)
    - `updated_at`        — timestamp of the last cache refresh

  3. Notes
    - The composite primary key (origin, destination, departure_date) enforces
      one cache row per route/date pair and makes upserts simple.
    - An index on `updated_at` speeds up the cache-staleness check performed
      by the worker (< 6 hours old).
*/

CREATE TABLE IF NOT EXISTS flight_price_cache (
  origin            text        NOT NULL,
  destination       text        NOT NULL,
  departure_date    date        NOT NULL,
  lowest_price      numeric(10, 2),
  api_response_json jsonb,
  updated_at        timestamptz NOT NULL DEFAULT now(),

  PRIMARY KEY (origin, destination, departure_date)
);

-- Speed up the "is cache fresh?" look-up used by the worker
CREATE INDEX IF NOT EXISTS idx_flight_price_cache_updated_at
  ON flight_price_cache (updated_at);
