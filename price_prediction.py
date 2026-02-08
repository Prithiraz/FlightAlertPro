import logging
import statistics
from typing import List, Dict, Optional, Tuple
from backend.config import config

logger = logging.getLogger(__name__)

class PricePredictor:
    def __init__(self, dry_run: bool = False):
        self.openai_api_key = config.OPENAI_API_KEY
        self.dry_run = dry_run
        self.use_openai = self.openai_api_key and not dry_run

    def _statistical_prediction(self, price_points: List[float]) -> Tuple[float, str]:
        if len(price_points) < 3:
            return 0.5, "wait"

        avg_price = statistics.mean(price_points)
        recent_avg = statistics.mean(price_points[-3:])

        try:
            volatility = statistics.stdev(price_points) / avg_price if avg_price > 0 else 0
        except statistics.StatisticsError:
            volatility = 0

        current_price = price_points[-1]

        if current_price < avg_price * 0.9:
            probability = 0.8
            recommendation = "buy"
        elif current_price < avg_price * 0.95:
            probability = 0.65
            recommendation = "buy"
        elif current_price > avg_price * 1.1:
            probability = 0.7
            recommendation = "wait"
        elif volatility > 0.15:
            probability = 0.6
            recommendation = "wait"
        else:
            probability = 0.5
            recommendation = "wait"

        logger.info(f"Statistical prediction: {recommendation} (probability: {probability:.2f}, volatility: {volatility:.2f})")
        return probability, recommendation

    def _openai_prediction(self, price_points: List[float]) -> Tuple[float, str]:
        if not self.use_openai:
            logger.info("OpenAI prediction disabled (dry_run or no API key)")
            return 0.5, "wait"

        try:
            import openai

            openai.api_key = self.openai_api_key

            last_12 = price_points[-12:] if len(price_points) >= 12 else price_points
            price_str = ", ".join([f"£{p:.2f}" for p in last_12])

            prompt = f"""Analyze these flight prices over time: {price_str}

Current price is the last one. Based on the trend, should I buy now or wait?
Respond with JSON: {{"probability": 0.0-1.0, "recommendation": "buy" or "wait"}}"""

            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a flight price prediction expert."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=100
            )

            content = response.choices[0].message.content.strip()

            import json
            result = json.loads(content)

            probability = float(result.get("probability", 0.5))
            recommendation = result.get("recommendation", "wait")

            logger.info(f"OpenAI prediction: {recommendation} (probability: {probability:.2f})")
            return probability, recommendation

        except Exception as e:
            logger.error(f"OpenAI prediction failed: {str(e)}")
            return 0.5, "wait"

    def predict(self, price_points: List[float]) -> Dict[str, any]:
        if not price_points:
            return {
                "recommendation": "wait",
                "probability": 0.5,
                "method": "default",
                "details": "No price history available"
            }

        stat_prob, stat_rec = self._statistical_prediction(price_points)

        if self.use_openai:
            ai_prob, ai_rec = self._openai_prediction(price_points)

            blended_prob = (stat_prob * 0.4) + (ai_prob * 0.6)

            if stat_rec == ai_rec:
                final_rec = stat_rec
            else:
                final_rec = ai_rec if ai_prob > 0.6 else stat_rec

            method = "blended"
        else:
            blended_prob = stat_prob
            final_rec = stat_rec
            method = "statistical"

        return {
            "recommendation": final_rec,
            "probability": round(blended_prob, 2),
            "method": method,
            "details": f"Based on {len(price_points)} price points"
        }

def create_predictor(dry_run: bool = False) -> PricePredictor:
    return PricePredictor(dry_run=dry_run)
