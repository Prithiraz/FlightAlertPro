import math
from datetime import datetime, timedelta

def calculate_arrival_metrics(altitude_ft: float, speed_kt: float, distance_nm: float):
    """
    Generates physics-informed arrival milestones and confidence intervals.
    """
    # 1. Sanitize Inputs & Handle Edge Cases
    if speed_kt < 50 or altitude_ft < 0:
        return None
        
    # 2. Base Flight Time Calculation (Minutes)
    speed_nm_per_min = speed_kt / 60.0
    base_flight_time_min = distance_nm / speed_nm_per_min
    
    # 3. Add standard approach vectoring penalty based on altitude
    if altitude_ft > 10000:
        vector_penalty = 12.0
    elif altitude_ft > 5000:
        vector_penalty = 6.0
    else:
        vector_penalty = 2.0
        
    logistics_eta_min = base_flight_time_min + vector_penalty
    
    # 4. Dynamic Confidence Interval Calculation
    base_uncertainty = 3.0
    altitude_variance = (altitude_ft / 10000.0) * 1.5
    confidence_interval = math.ceil(base_uncertainty + altitude_variance)
    
    # 5. Generate Performance Advisories
    advisory = "NOMINAL"
    if speed_kt > 250 and altitude_ft < 10000:
        advisory = "HIGH_ENERGY_APPROACH"
        
    return {
        "logistics_eta_min": logistics_eta_min,
        "confidence_interval_min": confidence_interval,
        "performance_advisory": advisory
    }
