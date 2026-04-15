import { Link } from 'react-router-dom';

/* ── SVG Icons ─────────────────────────────────────────────────── */
function SearchIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" className="h-10 w-10 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z" />
    </svg>
  );
}

function BellIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" className="h-10 w-10 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0 1 18 14.158V11a6 6 0 0 0-5-5.917V4a1 1 0 1 0-2 0v1.083A6 6 0 0 0 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 1 1-6 0v-1m6 0H9" />
    </svg>
  );
}

function EnvelopeIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" className="h-10 w-10 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 0 1-2.25 2.25H4.5a2.25 2.25 0 0 1-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0 0 19.5 4.5H4.5a2.25 2.25 0 0 0-2.25 2.25m19.5 0-9.75 6.75L2.25 6.75" />
    </svg>
  );
}

/* ── Testimonials data ──────────────────────────────────────────── */
const TESTIMONIALS = [
  {
    name: 'Sarah M.',
    role: 'Frequent Flyer',
    avatar: 'SM',
    quote: 'FlightAlertPro saved me $340 on my Paris trip! I set my target price and got a Telegram ping within 48 hours. Absolute game-changer.',
  },
  {
    name: 'James K.',
    role: 'Digital Nomad',
    avatar: 'JK',
    quote: 'I travel 10+ times a year and this is now my secret weapon. The background monitoring means I never have to manually check fares again.',
  },
  {
    name: 'Priya L.',
    role: 'Budget Traveler',
    avatar: 'PL',
    quote: "Booked Tokyo for $480 round-trip thanks to the alert. My friends paid over $700. I'll never buy a flight without setting an alert first!",
  },
];

/* ── Landing Page ───────────────────────────────────────────────── */
export default function Landing() {
  return (
    <div className="font-sans antialiased text-gray-900 bg-white">

      {/* ── Nav ── */}
      <nav className="flex items-center justify-between px-6 py-4 max-w-6xl mx-auto">
        <div className="flex items-center gap-2 font-bold text-blue-700 text-xl tracking-tight">
          <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
          </svg>
          FlightAlertPro
        </div>
        <div className="flex items-center gap-4">
          <Link to="/pricing" className="text-sm font-medium text-gray-600 hover:text-blue-700 transition-colors">
            Pricing
          </Link>
          <Link
            to="/auth"
            className="text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 transition-colors px-4 py-2 rounded-lg"
          >
            Sign In
          </Link>
        </div>
      </nav>

      {/* ── Hero ── */}
      <section className="bg-gradient-to-br from-blue-700 via-blue-600 to-indigo-700 text-white py-28 px-6 text-center">
        <div className="max-w-3xl mx-auto">
          <span className="inline-block bg-white/20 text-white text-xs font-semibold uppercase tracking-widest px-4 py-1.5 rounded-full mb-6">
            ✈ Flight Price Alerts
          </span>
          <h1 className="text-5xl sm:text-6xl font-extrabold leading-tight mb-6 drop-shadow">
            Never Miss a Flight Deal Again.
          </h1>
          <p className="text-xl sm:text-2xl text-blue-100 mb-10 leading-relaxed">
            Set your price. We check the airlines 24/7. You get the alert.
          </p>
          <Link
            to="/auth"
            className="inline-block bg-white text-blue-700 font-bold text-lg px-10 py-4 rounded-xl shadow-lg hover:bg-blue-50 transition-colors"
          >
            Start Tracking for Free
          </Link>
          <p className="mt-4 text-blue-200 text-sm">No credit card required · Free plan available</p>
        </div>
      </section>

      {/* ── How It Works ── */}
      <section className="py-24 px-6 bg-gray-50">
        <div className="max-w-5xl mx-auto text-center mb-14">
          <h2 className="text-3xl sm:text-4xl font-extrabold text-gray-900 mb-4">How It Works</h2>
          <p className="text-lg text-gray-500">Three simple steps stand between you and your cheapest flight ever.</p>
        </div>
        <div className="max-w-5xl mx-auto grid grid-cols-1 sm:grid-cols-3 gap-8">
          {/* Step 1 */}
          <div className="bg-white rounded-2xl p-8 shadow-sm flex flex-col items-center text-center gap-4 border border-gray-100">
            <div className="bg-blue-50 rounded-xl p-4">
              <SearchIcon />
            </div>
            <h3 className="text-xl font-bold text-gray-900">1. Search</h3>
            <p className="text-gray-500 text-sm leading-relaxed">
              Enter your origin, destination, and travel dates — just like Kayak. We search across all major airlines in seconds.
            </p>
          </div>
          {/* Step 2 */}
          <div className="bg-white rounded-2xl p-8 shadow-sm flex flex-col items-center text-center gap-4 border border-gray-100">
            <div className="bg-blue-50 rounded-xl p-4">
              <BellIcon />
            </div>
            <h3 className="text-xl font-bold text-gray-900">2. Set an Alert</h3>
            <p className="text-gray-500 text-sm leading-relaxed">
              Set your target price. Our background worker checks airline prices around the clock so you never have to.
            </p>
          </div>
          {/* Step 3 */}
          <div className="bg-white rounded-2xl p-8 shadow-sm flex flex-col items-center text-center gap-4 border border-gray-100">
            <div className="bg-blue-50 rounded-xl p-4">
              <EnvelopeIcon />
            </div>
            <h3 className="text-xl font-bold text-gray-900">3. Get Notified</h3>
            <p className="text-gray-500 text-sm leading-relaxed">
              The moment the price drops below your target, we notify you via Email and Telegram — instantly.
            </p>
          </div>
        </div>
      </section>

      {/* ── Social Proof ── */}
      <section className="py-24 px-6 bg-white">
        <div className="max-w-5xl mx-auto text-center mb-14">
          <h2 className="text-3xl sm:text-4xl font-extrabold text-gray-900 mb-4">Travelers Who Saved Big</h2>
          <p className="text-lg text-gray-500">Join thousands of smart travelers already using FlightAlertPro.</p>
        </div>
        <div className="max-w-5xl mx-auto grid grid-cols-1 sm:grid-cols-3 gap-8">
          {TESTIMONIALS.map((t) => (
            <div key={t.name} className="bg-gray-50 rounded-2xl p-8 flex flex-col gap-5 border border-gray-100 shadow-sm">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-full bg-blue-600 text-white font-bold text-base flex items-center justify-center flex-shrink-0">
                  {t.avatar}
                </div>
                <div>
                  <p className="font-semibold text-gray-900 text-sm">{t.name}</p>
                  <p className="text-gray-400 text-xs">{t.role}</p>
                </div>
              </div>
              <p className="text-gray-600 text-sm leading-relaxed italic">"{t.quote}"</p>
              <div className="flex gap-0.5 text-amber-400 text-base">
                {'★★★★★'}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── Final CTA Banner ── */}
      <section className="bg-gray-900 py-20 px-6 text-center text-white">
        <div className="max-w-2xl mx-auto">
          <h2 className="text-3xl sm:text-4xl font-extrabold mb-4">Upgrade your travel game today.</h2>
          <p className="text-gray-400 text-lg mb-10">
            Unlock unlimited alerts, instant Telegram notifications, and priority support.
          </p>
          <Link
            to="/pricing"
            className="inline-block bg-blue-600 hover:bg-blue-500 transition-colors text-white font-bold text-lg px-10 py-4 rounded-xl shadow-lg"
          >
            View Pricing Plans
          </Link>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="bg-gray-950 text-gray-500 text-sm py-8 px-6 text-center">
        © {new Date().getFullYear()} FlightAlertPro. All rights reserved.
      </footer>
    </div>
  );
}
