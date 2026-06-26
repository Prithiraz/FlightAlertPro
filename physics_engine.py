import math

def calculate_arrival_metrics(altitude_ft: float, speed_kt: float, distance_nm: float):
    if speed_kt < 50 or altitude_ft < 0: return None
        
    speed_nm_per_min = speed_kt / 60.0
    base_flight_time_min = distance_nm / speed_nm_per_min
    
    if altitude_ft > 10000: vector_penalty = 12.0
    elif altitude_ft > 5000: vector_penalty = 6.0
    else: vector_penalty = 2.0
        
    logistics_eta_min = base_flight_time_min + vector_penalty
    
    base_uncertainty = 3.0
    altitude_variance = (altitude_ft / 10000.0) * 1.5
    confidence_interval = math.ceil(base_uncertainty + altitude_variance)
    
    late_risk = "High" if confidence_interval > 8 else "Moderate" if confidence_interval > 5 else "Low"
    expected_wait = confidence_interval + 5
    
    advisory = "NOMINAL"
    if speed_kt > 250 and altitude_ft < 10000: advisory = "HIGH_ENERGY_APPROACH"
        
    return {
        "logistics_eta_min": logistics_eta_min,
        "confidence_interval_min": confidence_interval,
        "expected_wait_min": expected_wait,
        "late_risk": late_risk,
        "performance_advisory": advisory
    }
