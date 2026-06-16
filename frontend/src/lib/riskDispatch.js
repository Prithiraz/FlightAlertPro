// Client-side mirror of the backend newsvendor dispatch optimiser
// (weather_service.calculate_optimal_dispatch). Kept in sync so the dispatcher's
// cost sliders recompute the risk-adjusted dispatch time instantly, without a
// round-trip per slider tick.

// Peter Acklam's rational approximation of the standard-normal quantile (probit).
export function inverseStandardNormalCdf(p) {
  if (p <= 0) return -Infinity;
  if (p >= 1) return Infinity;

  const a = [-3.969683028665376e1, 2.209460984245205e2, -2.759285104469687e2,
    1.38357751867269e2, -3.066479806614716e1, 2.506628277459239e0];
  const b = [-5.447609879822406e1, 1.615858368580409e2, -1.556989798598866e2,
    6.680131188771972e1, -1.328068155288572e1];
  const c = [-7.784894002430293e-3, -3.223964580411365e-1, -2.400758277161838e0,
    -2.549732539343734e0, 4.374664141464968e0, 2.938163982698783e0];
  const d = [7.784695709041462e-3, 3.224671290700398e-1, 2.445134137142996e0,
    3.754408661907416e0];

  const pLow = 0.02425;
  const pHigh = 1 - pLow;
  let q;
  let r;

  if (p < pLow) {
    q = Math.sqrt(-2 * Math.log(p));
    return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) /
      ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1);
  }
  if (p <= pHigh) {
    q = p - 0.5;
    r = q * q;
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q /
      (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1);
  }
  q = Math.sqrt(-2 * Math.log(1 - p));
  return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) /
    ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1);
}

// Risk-adjusted dispatch via the critical fractile P(R<=T) = wait/(wait+late).
// Returns { recommendedPresence: Date, bufferMinutes, criticalFractile, z }.
export function calculateOptimalDispatch(expectedReadyTime, uncertaintyMinutes, waitCostPerMin, lateCostPerMin) {
  const expected = expectedReadyTime instanceof Date ? expectedReadyTime : new Date(expectedReadyTime);
  if (Number.isNaN(expected.getTime())) {
    return { recommendedPresence: null, bufferMinutes: 0, criticalFractile: 0.5, z: 0 };
  }
  const sigma = Math.max(0, Number(uncertaintyMinutes) || 0);
  const wait = Math.max(0, Number(waitCostPerMin) || 0);
  const late = Math.max(0, Number(lateCostPerMin) || 0);

  const denom = wait + late;
  let fractile = denom > 0 ? wait / denom : 0.5;
  fractile = Math.min(Math.max(fractile, 1e-6), 1 - 1e-6);

  const z = inverseStandardNormalCdf(fractile);
  const offsetMin = z * sigma; // negative => stage earlier than median
  const recommended = new Date(expected.getTime() + offsetMin * 60000);
  recommended.setSeconds(0, 0);

  return {
    recommendedPresence: recommended,
    bufferMinutes: Math.round(-offsetMin),
    criticalFractile: Number(fractile.toFixed(4)),
    z: Number(z.toFixed(4)),
  };
}

// Subtract the drive time from the staged presence to get the leave-by time.
export function riskAdjustedDispatchTime(expectedReadyTime, uncertaintyMinutes, waitCostPerMin, lateCostPerMin, driveTimeMin) {
  const { recommendedPresence, bufferMinutes, criticalFractile } = calculateOptimalDispatch(
    expectedReadyTime, uncertaintyMinutes, waitCostPerMin, lateCostPerMin,
  );
  if (!recommendedPresence) {
    return { dispatchTime: null, presenceTime: null, bufferMinutes: 0, criticalFractile };
  }
  const drive = Math.max(0, Number(driveTimeMin) || 0);
  const dispatchTime = new Date(recommendedPresence.getTime() - drive * 60000);
  dispatchTime.setSeconds(0, 0);
  return { dispatchTime, presenceTime: recommendedPresence, bufferMinutes, criticalFractile };
}

function normPdf(x) {
  return Math.exp(-0.5 * x * x) / Math.sqrt(2 * Math.PI);
}

function normCdf(x) {
  // Abramowitz & Stegun 7.1.26 erf approximation.
  const t = 1 / (1 + 0.3275911 * Math.abs(x) / Math.SQRT2);
  const y = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-(x * x) / 2);
  const erf = x >= 0 ? y : -y;
  return 0.5 * (1 + erf);
}

// Expected per-trip cost of staging the driver `t` minutes from the median ready
// time, with ready time R ~ N(0, sigma): wait*(G - t) + late*G where
// G = E[(t - R)+] = t*Phi(t/sigma) + sigma*phi(t/sigma).
function expectedCost(t, sigma, wait, late) {
  if (sigma <= 0) return late * Math.max(0, t) + wait * Math.max(0, -t);
  const z = t / sigma;
  const g = t * normCdf(z) + sigma * normPdf(z);
  return wait * (g - t) + late * g;
}

function expectedDriverWait(t, sigma) {
  if (sigma <= 0) return Math.max(0, -t);
  const z = t / sigma;
  const g = t * normCdf(z) + sigma * normPdf(z);
  return g - t;
}

function confidenceLabel(sigma) {
  if (sigma <= 6) return 'High';
  if (sigma <= 14) return 'Moderate';
  return 'Low';
}

// Acceptable dispatch *window* (not a single minute): every leave-by time whose
// expected cost is within `costTolerance` of the minimum. Mirrors the backend
// physics_engine.calculate_dispatch_window.
export function calculateDispatchWindow(expectedReadyTime, uncertaintyMinutes, waitCostPerMin, lateCostPerMin, driveTimeMin, costTolerance = 0.10) {
  const expected = expectedReadyTime instanceof Date ? expectedReadyTime : new Date(expectedReadyTime);
  if (Number.isNaN(expected.getTime())) {
    return { start: null, end: null, recommended: null, expectedDriverWaitMinutes: 0, confidence: 'Low' };
  }
  const sigma = Math.max(0, Number(uncertaintyMinutes) || 0);
  const wait = Math.max(0, Number(waitCostPerMin) || 0);
  const late = Math.max(0, Number(lateCostPerMin) || 0);
  const drive = Math.max(0, Number(driveTimeMin) || 0);

  const span = Math.max(8, 4 * sigma);
  const step = 0.25;
  const offsets = [];
  for (let o = -span; o <= span + 1e-9; o += step) offsets.push(o);
  const costs = offsets.map((o) => [o, expectedCost(o, sigma, wait, late)]);
  let best = costs[0];
  for (const oc of costs) if (oc[1] < best[1]) best = oc;
  const budget = best[1] * (1 + costTolerance);
  const accepted = costs.filter(([, c]) => c <= budget).map(([o]) => o);
  const lowOffset = accepted.length ? Math.min(...accepted) : best[0];
  const highOffset = accepted.length ? Math.max(...accepted) : best[0];

  const dispatchAt = (offset) => {
    const d = new Date(expected.getTime() + (offset - drive) * 60000);
    d.setSeconds(0, 0);
    return d;
  };

  return {
    start: dispatchAt(lowOffset),
    end: dispatchAt(highOffset),
    recommended: dispatchAt(best[0]),
    expectedDriverWaitMinutes: Math.max(0, Math.round(expectedDriverWait(best[0], sigma))),
    confidence: confidenceLabel(sigma),
  };
}

// Two-sided ready-time window (median ± z(conf) * sigma).
export function readyTimeWindow(expectedReadyTime, uncertaintyMinutes, confidence = 0.8) {
  const expected = expectedReadyTime instanceof Date ? expectedReadyTime : new Date(expectedReadyTime);
  if (Number.isNaN(expected.getTime())) {
    return { median: null, start: null, end: null, halfWidthMinutes: 0 };
  }
  const sigma = Math.max(0, Number(uncertaintyMinutes) || 0);
  const conf = Math.min(Math.max(Number(confidence) || 0, 0), 0.999999);
  const tail = (1 - conf) / 2;
  const halfWidth = sigma > 0 ? Math.abs(inverseStandardNormalCdf(1 - tail)) * sigma : 0;
  const median = new Date(expected.getTime()); median.setSeconds(0, 0);
  const start = new Date(expected.getTime() - halfWidth * 60000); start.setSeconds(0, 0);
  const end = new Date(expected.getTime() + halfWidth * 60000); end.setSeconds(0, 0);
  return { median, start, end, halfWidthMinutes: Math.round(halfWidth) };
}
