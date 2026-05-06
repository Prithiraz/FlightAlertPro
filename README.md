# FlightAlertPro — Aerospace Operational Intelligence Platform

> **Physics-based flight intelligence for operators and analysts who demand
> accuracy that commercial aggregators and airlines deliberately withhold.**

---

## Value Proposition

### Who This Is Built For

| Audience | Use Case |
|---|---|
| **High-Utility Business Operations** | Compliance-grade carbon reporting, predictive trip budgeting, SLA-aware scheduling around weather-driven delays |
| **Aviation Enthusiasts & Analysts** | Route efficiency auditing, real-time aerodynamic ETA validation, thermodynamic departure risk assessment |

### Static Data vs. Physics-Based Intelligence

Most flight-search applications query a price database and stop there. They
surface a departure time, a fare, and an opaque "on-time" percentage that is
self-reported by the same carrier profiting from the booking. **This platform
does not do that.**

| Capability | Standard Aggregator | FlightAlertPro |
|---|---|---|
| ETA accuracy | Airline-padded schedule | Haversine GCD + wind-triangle ground speed |
| Departure risk | Not modelled | Density-altitude thermodynamic analysis via live METAR |
| Carbon footprint | Estimate or absent | ICAO/DEFRA factors × 1.9× Radiative Forcing multiplier |
| Data origin | Opaque upstream cache | Live CheckWX METAR/TAF + airportsdata geodetics |

Airlines routinely pad scheduled block times by 10–20 minutes to inflate
on-time statistics. High-altitude airports suppress aircraft performance on hot
days in ways that cascade into load restrictions, fuel stops, and schedule
slippage — none of which appear in a booking portal. This platform surfaces that
physics and puts it in the hands of the operator.

---

## Technical Feature Breakdown

### 1 · Aerodynamic ETA — Wind Triangle & Vector Math

**Implementation:** `weather_service.py` → `get_aerodynamic_performance()`

Standard ETAs are block-time estimates padded by the carrier. The actual
elapsed time is governed by the ground speed of the aircraft, which is the
vector sum of its True Airspeed (TAS) and the prevailing wind.

#### Algorithm

1. **True Course Bearing** — the initial forward azimuth between origin and
   destination is derived from the spherical-Earth forward-azimuth formula:

   ```
   θ = atan2( sin(Δλ)·cos(φ₂),
              cos(φ₁)·sin(φ₂) − sin(φ₁)·cos(φ₂)·cos(Δλ) )
   ```

2. **Winds Aloft** — forecast wind direction and speed are fetched from the
   CheckWX TAF endpoint for the departure airport's ICAO station.

3. **Wind Triangle Solution** — the headwind/tailwind component along the true
   course is solved via the Law of Cosines projection:

   ```
   wind_component = −V_wind × cos(WindDir − Course)
   ```

   A positive result indicates a **tailwind** (ground speed > TAS); negative
   indicates a **headwind** (ground speed < TAS).

4. **True ETA** — effective ground speed is:

   ```
   GS = TAS + wind_component   (TAS baseline: 450 kt at FL300)
   ```

   The resulting ETA reflects actual physics, not airline schedule padding.

#### What This Exposes

Airlines and aggregators do not publish the wind data that determines block
time. This engine makes that calculation transparent, revealing when a
scheduled arrival is artificially inflated and when adverse upper-level winds
will cause a genuine late arrival.

---

### 2 · Thermodynamic Risk Profiling — Density Altitude

**Implementation:** `weather_service.py` → `get_departure_performance()`

Aircraft performance — lift, climb rate, engine thrust — degrades as air
density decreases. The standard metric is **Density Altitude (DA)**: the
altitude in the International Standard Atmosphere (ISA) that corresponds to
the actual air density at the field. A high DA on a hot, low-pressure day
means the aircraft performs as if it were operating from a much higher airport,
forcing weight restrictions, fuel burn penalties, and potential schedule breaks.

#### Algorithm

Live METAR data (temperature °C, altimeter setting inHg) is fetched via
CheckWX for the departure airport's ICAO station, then the standard FAA/ICAO
formulas are applied:

```
Pressure Altitude (PA)  = Field Elevation + (29.92 − Altimeter_inHg) × 1000
ISA Temperature (°C)    = 15 − (2 × Elevation_ft / 1000)
Density Altitude (DA)   = PA + 120 × (T_actual − T_ISA)
```

#### Risk Classification

| DA above Field Elevation | Risk Level | Operational Implication |
|---|---|---|
| ≥ 3,500 ft | **HIGH** | Significant payload restriction; probable weight-limit delay |
| ≥ 2,000 ft | **MODERATE** | Reduced performance margins; possible fuel stop or passenger offload |
| < 2,000 ft | **LOW** | Standard operating conditions |

#### What This Exposes

Airlines silently absorb density-altitude penalties into load planning. When a
flight is delayed at a high-altitude airport on a hot afternoon, the actual
cause — thermodynamic performance limits — never appears in the booking portal.
This engine quantifies that risk before the passenger arrives at the gate.

---

### 3 · Trajectory Efficiency & Carbon Auditing

**Implementation:** `skyscanner_service.py` → `calculate_haversine_distance()`,
`estimate_carbon_footprint()`

#### Great-Circle Distance — Haversine Formula

The shortest possible path between two points on a spherical Earth is the
great-circle distance (GCD). This is the geometric baseline against which
actual route efficiency is measured. The Haversine formula is used for
numerical stability at small angular separations:

```
a = sin²(Δφ/2) + cos(φ₁)·cos(φ₂)·sin²(Δλ/2)
GCD = 2R · arcsin(√a)       R = 6,371 km
```

#### Trajectory Efficiency Score

```
efficiency = GCD / (GCD + 100 km)
```

The 100 km overhead term represents estimated ATC vectoring and terminal
area routing. An efficiency score of 1.0 is a perfect great-circle trajectory;
real-world commercial routes typically score 0.90–0.97.

#### CO₂ Emissions — ICAO/DEFRA Factors + Radiative Forcing Multiplier

Aircraft emissions at cruise altitude have a climate impact beyond the CO₂
molecule alone — NOₓ formation, contrail cirrus, and water vapour effects
together produce a **Radiative Forcing** (RF) approximately **1.9×** the CO₂-
only value (Lee et al., *Atmospheric Environment*, 2021; consistent with DEFRA
conversion guidance).

```
CO₂_equivalent = GCD × emissions_factor × 1.9

emissions_factor:
  short-haul (< 3,700 km) → 0.15 kg/km   (ICAO/DEFRA)
  long-haul  (≥ 3,700 km) → 0.11 kg/km   (ICAO/DEFRA)
```

#### What This Exposes

Airline and aggregator carbon estimates either omit the Radiative Forcing
correction entirely or apply an undisclosed, self-serving multiplier. This
implementation uses published ICAO/DEFRA emission factors and the peer-reviewed
1.9× RF coefficient, producing figures that are directly comparable across
carriers and routes for compliance-grade sustainability reporting.

---

## Subscription Tiers

FlightAlertPro operates on a freemium model. Aerospace intelligence features are
progressively unlocked as you move up tiers.

| Feature | Free | Pro (£9.99/mo) | Elite (£19.99/mo) | Business (£39.99/mo) |
|---|:---:|:---:|:---:|:---:|
| Active Alerts | 1 | 5 | 20 | Unlimited |
| Email Notifications | ✓ | ✓ | ✓ | ✓ |
| Telegram Notifications | ✗ | ✓ | ✓ | ✓ |
| Instant Background Checking | ✗ | ✓ | ✓ | ✓ |
| AI Flight Insights | ✗ | ✗ | ✓ | ✓ |
| Flexible Date Alerts | ✗ | ✗ | ✓ | ✓ |
| EU261 Auto-Claim | ✗ | ✗ | ✓ | ✓ |
| **💨 Wind Vectors & Aerodynamic ETA** | ✗ | **✓** | ✓ | ✓ |
| **🌿 Phase 1 Sustainability Auditing & Trajectory Efficiency** | ✗ | ✗ | **✓** | ✓ |
| **🔥 Phase 2 Thermodynamic Risk (Density Altitude)** | ✗ | ✗ | ✗ | **✓** |
| **📊 CSV Export** | ✗ | ✗ | ✗ | **✓** |
| Agent Dashboard | ✗ | ✗ | ✗ | ✓ |
| Team Access | ✗ | ✗ | ✗ | ✓ |

### Aerospace Feature Details by Tier

#### Pro (£9.99/month) — Wind Vectors & Aerodynamic ETA

Unlocks the **Wind Triangle** analysis for every flight result:

- **Wind component** — headwind or tailwind component (knots) along the true
  course bearing derived from live CheckWX TAF data.
- **Time delta** — minutes saved or lost versus the scheduled block time due to
  the prevailing wind.
- **Aerodynamic ETA** — physics-corrected arrival time accounting for actual
  ground speed (TAS ± wind component).

#### Elite (£19.99/month) — Phase 1 Sustainability Auditing & Trajectory Efficiency

Adds **route sustainability** metrics on top of all Pro features:

- **Trajectory Efficiency Score** — ratio of the great-circle distance (GCD) to
  the GCD plus an ATC vectoring overhead term; 1.0 = perfect great-circle path.
- **CO₂ Equivalent Emissions** — calculated using ICAO/DEFRA emission factors
  with a peer-reviewed 1.9× Radiative Forcing multiplier, suitable for
  compliance-grade sustainability reporting.

#### Business (£39.99/month) — Phase 2 Thermodynamic Risk (Density Altitude) & CSV Export

Adds **departure performance risk** on top of all Elite features:

- **Density Altitude (DA)** — derived from live METAR data using the FAA/ICAO
  formulas; quantifies how thin air at the departure airport will degrade
  engine thrust and wing lift.
- **Takeoff Risk Classification** — LOW / MODERATE (≥ 2,000 ft DA above field)
  / HIGH (≥ 3,500 ft DA above field), flagging probable weight restrictions or
  schedule delays before the passenger arrives at the gate.
- **CSV Export** — download full itinerary and analytics data for offline
  analysis or integration with corporate travel management systems.

---



| Layer | Technology | Role |
|---|---|---|
| **API Server** | Python 3.11 + FastAPI | REST endpoints, background workers, business logic |
| **Frontend** | React (Vite) | SPA UI; protected routes, Stripe checkout, alert management |
| **Flight Data** | Skyscanner via `sky-scrapper` (elis-lab / RapidAPI) | Live itinerary search and fare aggregation |
| **Weather & Winds** | CheckWX METAR/TAF API | Real-time surface weather and terminal-area wind forecasts |
| **Airport Geodetics** | `airportsdata` library (PyPI) | IATA → lat/lon/ICAO/elevation lookup for all calculations |
| **Auth & Database** | Supabase (PostgreSQL + Auth) | User accounts, alert persistence, price history |
| **Payments** | Stripe | Subscription tiers (Pro / Elite / Business) |
| **Notifications** | Gmail SMTP + Telegram Bot | Price-drop and risk alert delivery |

---

## Quickstart

### Prerequisites
- Python 3.11+
- Node.js 18+
- A Supabase project
- (Optional) Stripe, Duffel, RapidAPI, Gmail, Telegram accounts

### 1. Clone & configure

```bash
git clone https://github.com/Prithiraz/FlightAlertPro.git
cd FlightAlertPro
```

**Backend environment** – the backend reads its `.env` from _one directory above_ the repo root (see `config.py`):

```bash
cp .env.example ../.env
# Edit ../.env and fill in real values
```

Minimum required variables:

```
VITE_SUPABASE_URL=https://YOUR_PROJECT_ID.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
```

### 2. Backend

```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Run the background alert worker:

```bash
python worker.py
```

Verify all components:

```bash
curl http://localhost:8000/api/systemcheck
```

### 3. Frontend

```bash
cd frontend
cp .env.example .env          # already has sane defaults
# Edit VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY to match your project
npm install
npm run dev                    # development server on :5173
npm run build                  # production build → frontend/dist/
```

Frontend environment variables (`frontend/.env`):

```
VITE_SUPABASE_URL=https://YOUR_PROJECT_ID.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
VITE_API_BASE_URL=http://localhost:8000
```

### 4. Example API calls

Search flights (segments contract):
```bash
curl -X POST http://localhost:8000/api/search \
  -H 'Content-Type: application/json' \
  -d '{
    "segments": [{"from_iata":"LAX","to_iata":"JFK","departure_date":"2026-05-01"}],
    "passengers": {"adults":1},
    "cabin_class": "economy"
  }'
```

Search flights (legacy flat contract):
```bash
curl -X POST http://localhost:8000/api/search/simple \
  -H 'Content-Type: application/json' \
  -d '{"from_iata":"LAX","to_iata":"JFK","departure_date":"2026-05-01","passengers":1}'
```

Create a price alert:
```bash
curl -X POST http://localhost:8000/api/alerts/create \
  -H 'Content-Type: application/json' \
  -d '{
    "user_email":"you@example.com",
    "from_iata":"LAX",
    "to_iata":"JFK",
    "max_price":400,
    "currency":"USD",
    "notification_channels":["email"]
  }'
```

Start a Stripe checkout (plan: pro | elite | business):
```bash
curl -X POST "http://localhost:8000/api/payments/checkout?user_email=you@example.com&plan=pro&success_url=https://example.com/success&cancel_url=https://example.com/cancel"
```
