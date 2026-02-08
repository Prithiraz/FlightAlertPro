import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import statistics
from backend.config import config

logger = logging.getLogger(__name__)

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI package not installed")

class PredictionService:
    def __init__(self, api_key: Optional[str] = None, dry_run: bool = False):
        self.api_key = api_key or config.OPENAI_API_KEY
        self.dry_run = dry_run or config.DRY_RUN
        self.enabled = self.api_key is not None and OPENAI_AVAILABLE

        if self.enabled and not self.dry_run:
            openai.api_key = self.api_key

    def _compute_stats(self, historical_prices: List[float]) -> Dict[str, float]:
        if not historical_prices or len(historical_prices) < 2:
            return {
                "mean": 0,
                "median": 0,
                "std_dev": 0,
                "volatility": 0,
                "trend": 0
            }

        mean = statistics.mean(historical_prices)
        median = statistics.median(historical_prices)
        std_dev = statistics.stdev(historical_prices) if len(historical_prices) > 1 else 0

        volatility = (std_dev / mean * 100) if mean > 0 else 0

        if len(historical_prices) >= 3:
            recent_avg = statistics.mean(historical_prices[-3:])
            older_avg = statistics.mean(historical_prices[:-3])
            trend = ((recent_avg - older_avg) / older_avg * 100) if older_avg > 0 else 0
        else:
            trend = 0

        return {
            "mean": round(mean, 2),
            "median": round(median, 2),
            "std_dev": round(std_dev, 2),
            "volatility": round(volatility, 2),
            "trend": round(trend, 2)
        }

    def _query_openai(self, route: str, current_price: float, stats: Dict[str, float],
                     days_until_flight: int) -> Optional[Dict[str, Any]]:
        if not self.enabled or self.dry_run:
            logger.info("OpenAI prediction skipped (disabled or dry-run)")
            return None

        try:
            prompt = f"""Analyze this flight price and predict if the user should buy now or wait.

Route: {route}
Current Price: ${current_price}
Historical Average: ${stats['mean']}
Price Volatility: {stats['volatility']}%
Recent Trend: {stats['trend']}%
Days Until Flight: {days_until_flight}

Provide:
1. Recommendation (BUY_NOW or WAIT)
2. Confidence score (0-100)
3. Brief reasoning (max 50 words)

Format: JSON with keys: recommendation, confidence, reasoning"""

            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a flight price prediction expert."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=150
            )

            content = response.choices[0].message.content
            logger.info(f"OpenAI prediction: {content}")

            return {
                "source": "openai",
                "raw_response": content
            }

        except Exception as e:
            logger.error(f"OpenAI prediction failed: {str(e)}")
            return None

    def predict(self, route: str, current_price: float, historical_prices: List[float],
               departure_date: str, dry_run: Optional[bool] = None) -> Dict[str, Any]:

        is_dry_run = dry_run if dry_run is not None else self.dry_run

        stats = self._compute_stats(historical_prices)

        try:
            dep_date = datetime.fromisoformat(departure_date.split('T')[0])
            days_until_flight = (dep_date - datetime.now()).days
        except:
            days_until_flight = 30

        openai_prediction = None if is_dry_run else self._query_openai(route, current_price, stats, days_until_flight)

        price_deviation = ((current_price - stats['mean']) / stats['mean'] * 100) if stats['mean'] > 0 else 0

        if days_until_flight < 7:
            recommendation = "BUY_NOW"
            confidence = 85
            reasoning = "Limited time remaining"
        elif days_until_flight > 90:
            if price_deviation > 10:
                recommendation = "WAIT"
                confidence = 72
                reasoning = "Early booking with high price"
            else:
                recommendation = "BUY_NOW"
                confidence = 68
                reasoning = "Good early bird price"
        else:
            if price_deviation > 15:
                recommendation = "WAIT"
                confidence = 70
                reasoning = "Price significantly above average"
            elif price_deviation < -15:
                recommendation = "BUY_NOW"
                confidence = 78
                reasoning = "Price significantly below average"
            else:
                recommendation = "UNCERTAIN"
                confidence = 55
                reasoning = "Price near historical average"

        if openai_prediction and not is_dry_run:
            confidence = min(95, int(confidence * 0.6 + 40))
            logger.info("Blended AI + stats prediction")

        return {
            "recommendation": recommendation,
            "confidence": confidence,
            "reasoning": reasoning,
            "stats": stats,
            "current_price": current_price,
            "price_deviation": round(price_deviation, 2),
            "days_until_flight": days_until_flight,
            "ai_prediction": openai_prediction,
            "is_dry_run": is_dry_run
        }

prediction_service = PredictionService()
