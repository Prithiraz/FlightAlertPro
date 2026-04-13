/*
  # Add price_history_logs table

  1. New Table
    - `price_history_logs` — records a snapshot of the lowest observed price
      for a route each time the worker fetches a live price from the external
      API (cache miss).

  2. Columns
    - `id`            — auto-incrementing primary key
    - `route_group`   — route identifier in the form 'ORIGIN-DESTINATION'
                        (e.g. 'LGW-JFK')
    - `lowest_price`  — cheapest price returned by the external API at the
                        time of logging
    - `recorded_at`   — UTC timestamp when the price was observed

  3. Notes
    - An index on (route_group, recorded_at) supports the common query pattern
      of retrieving the last N data points for a given route ordered by time.
*/

CREATE TABLE IF NOT EXISTS price_history_logs (
  id            bigserial   PRIMARY KEY,
  route_group   text        NOT NULL,
  lowest_price  numeric(10, 2) NOT NULL,
  recorded_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_price_history_logs_route_recorded
  ON price_history_logs (route_group, recorded_at DESC);
