/**
 * Tier gating logic for FlightAlertPro.
 *
 * Tiers (ascending order of access):
 *   free → pro (£9.99) → elite (£19.99) → business (£39.99)
 *
 * Feature matrix:
 * ┌────────────────────────────────────────────────┬──────┬─────┬───────┬──────────┐
 * │ Feature                                        │ free │ pro │ elite │ business │
 * ├────────────────────────────────────────────────┼──────┼─────┼───────┼──────────┤
 * │ EU261 Auto-Claim                               │  ✗   │  ✗  │   ✓   │    ✓     │
 * │ Agent Dashboard                                │  ✗   │  ✗  │   ✗   │    ✓     │
 * │ Client fields on alerts                        │  ✗   │  ✗  │   ✗   │    ✓     │
 * │ Flexible Dates                                 │  ✗   │  ✗  │   ✓   │    ✓     │
 * │ AI Insights                                    │  ✗   │  ✗  │   ✓   │    ✓     │
 * │ Wind Vectors & Aerodynamic ETA                 │  ✗   │  ✓  │   ✓   │    ✓     │
 * │ Sustainability Auditing & Trajectory Efficiency│  ✗   │  ✗  │   ✓   │    ✓     │
 * │ Thermodynamic Risk (Density Altitude)          │  ✗   │  ✗  │   ✗   │    ✓     │
 * │ CSV Export                                     │  ✗   │  ✗  │   ✗   │    ✓     │
 * └────────────────────────────────────────────────┴──────┴─────┴───────┴──────────┘
 */

const TIER_RANK = { free: 0, pro: 1, elite: 2, business: 3 };

/**
 * Returns true if the supplied tier is at least the required tier.
 * @param {string} userTier   - e.g. 'free' | 'pro' | 'elite' | 'business'
 * @param {string} minTier    - minimum required tier
 */
export function hasMinTier(userTier, minTier) {
  return (TIER_RANK[userTier] ?? 0) >= (TIER_RANK[minTier] ?? 0);
}

/**
 * EU261 Auto-Claim: Elite ($19) and Business ($39) only.
 * Pro users cannot see the EU261 claim button.
 */
export function canUseEU261(tier) {
  return tier === 'elite' || tier === 'business';
}

/**
 * Agent Dashboard: Business ($39) only.
 * Elite users cannot see the Agent Dashboard.
 */
export function canUseAgentDashboard(tier) {
  return tier === 'business';
}

/**
 * Client fields on the Create Alert form: Business ($39) only.
 */
export function canUseClientFields(tier) {
  return tier === 'business';
}

/**
 * Flexible date ranges on alerts: Elite ($19) and Business ($39) only.
 */
export function canUseFlexibleDates(tier) {
  return tier === 'elite' || tier === 'business';
}

/**
 * AI Insights / price predictions: Elite and Business only.
 */
export function canUseAiInsights(tier) {
  return tier === 'elite' || tier === 'business';
}

/**
 * Wind Vectors & Aerodynamic ETA: Pro (£9.99), Elite, and Business only.
 * Free users cannot see wind component or aerodynamic arrival time.
 */
export function canUseWindVectors(tier) {
  return tier === 'pro' || tier === 'elite' || tier === 'business';
}

/**
 * Phase 1 Sustainability Auditing & Trajectory Efficiency: Elite (£19.99) and Business only.
 * Includes efficiency score and CO₂ emissions data.
 */
export function canUseSustainabilityAudit(tier) {
  return tier === 'elite' || tier === 'business';
}

/**
 * Phase 2 Thermodynamic Risk (Density Altitude) & CSV Export: Business (£39.99) only.
 * Includes density altitude, takeoff risk classification, and CSV export.
 */
export function canUseThermodynamicRisk(tier) {
  return tier === 'business';
}

/** Maximum number of concurrent alerts per tier. */
export const ALERT_LIMITS = {
  free: 1,
  pro: 5,
  elite: 20,
  business: Infinity,
};

export function alertLimit(tier) {
  return ALERT_LIMITS[tier] ?? 1;
}
