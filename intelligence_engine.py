"""Property Intelligence Scoring Engine.

Week 1 System 1: Calculates proprietary scores for properties based on location,
market data, and investment potential. All scores are on a 0-100 scale.

Zero external dependencies — uses only Python standard library.
"""

from database import get_conn, now


def calculate_location_score(location_data):
    """Calculate location quality score (0-100)."""
    if not location_data:
        return 0

    score = 0

    # Connectivity factor (40% weight)
    connectivity_base = 0
    if location_data["nearest_metro_km"] < 5:
        connectivity_base = 100
    elif location_data["nearest_metro_km"] < 10:
        connectivity_base = 85
    elif location_data["nearest_metro_km"] < 15:
        connectivity_base = 70
    else:
        connectivity_base = 50

    if location_data["public_transport"] == "excellent":
        connectivity_base = min(100, connectivity_base + 15)
    elif location_data["public_transport"] == "good":
        connectivity_base = min(100, connectivity_base + 5)

    score += connectivity_base * 0.40

    # Infrastructure factor (35% weight)
    infrastructure_base = 0
    if location_data["nearest_mall_km"] < 2:
        infrastructure_base += 25
    elif location_data["nearest_mall_km"] < 5:
        infrastructure_base += 15

    if location_data["nearest_hospital_km"] < 2:
        infrastructure_base += 25
    elif location_data["nearest_hospital_km"] < 5:
        infrastructure_base += 15

    if location_data["nearest_school_km"] < 1:
        infrastructure_base += 25
    elif location_data["nearest_school_km"] < 2:
        infrastructure_base += 15

    infrastructure_base = min(100, infrastructure_base)
    score += infrastructure_base * 0.35

    # Growth trajectory (25% weight)
    growth_base = 0
    if location_data["metro_planned"]:
        growth_base += 40
    if location_data["infrastructure_under_development"]:
        growth_base += 30
    if location_data["demand_level"] == "high":
        growth_base += 20
    elif location_data["demand_level"] == "medium":
        growth_base += 10

    growth_base = min(100, growth_base)
    score += growth_base * 0.25

    return min(100, int(score))


def calculate_appreciation_score(location_data):
    """Calculate appreciation potential score (0-100)."""
    if not location_data:
        return 0

    score = 0

    # Historical growth (40% weight)
    growth_5yr = location_data["price_growth_5yr"]
    if growth_5yr > 4.0:
        score += 100 * 0.40
    elif growth_5yr > 3.0:
        score += 80 * 0.40
    elif growth_5yr > 2.0:
        score += 60 * 0.40
    else:
        score += 40 * 0.40

    # Infrastructure pipeline (35% weight)
    pipeline_score = 50
    if location_data["metro_planned"]:
        pipeline_score += 30
    if location_data["infrastructure_under_development"]:
        pipeline_score += 15
    if location_data["commercial_development"]:
        pipeline_score += 5

    pipeline_score = min(100, pipeline_score)
    score += pipeline_score * 0.35

    # Demand factor (25% weight)
    if location_data["demand_level"] == "high":
        score += 90 * 0.25
    elif location_data["demand_level"] == "medium":
        score += 60 * 0.25
    else:
        score += 30 * 0.25

    return min(100, int(score))


def calculate_rental_score(location_data):
    """Calculate rental yield potential score (0-100)."""
    if not location_data:
        return 0

    score = 0

    # Current rental yield (50% weight)
    rental_yield = location_data["avg_rental_yield"]
    yield_score = min(100, int(rental_yield * 12))  # Convert to annual %
    score += yield_score * 0.50

    # Area average yield (35% weight)
    area_score = 50 if location_data["demand_level"] == "high" else 35
    score += area_score * 0.35

    # Tenant demand (15% weight)
    if location_data["demand_level"] == "high":
        score += 85 * 0.15
    elif location_data["demand_level"] == "medium":
        score += 60 * 0.15
    else:
        score += 40 * 0.15

    return min(100, int(score))


def calculate_price_positioning_score(property_data, location_data):
    """Calculate price positioning score (0-100)."""
    if not property_data or not location_data:
        return 0

    # Compare property price/sqft against area average
    if location_data["avg_price_per_sqft"] == 0:
        return 75  # Default if no data

    property_price_per_sqft = property_data["price"] / property_data["area_sqft"] if property_data[
        "area_sqft"] > 0 else 0

    if property_price_per_sqft == 0:
        return 75

    variance_pct = ((property_price_per_sqft - location_data["avg_price_per_sqft"]) /
                    location_data["avg_price_per_sqft"]) * 100

    if abs(variance_pct) < 5:  # Within 5% is excellent
        return 95
    elif abs(variance_pct) < 10:  # Within 10% is good
        return 85
    elif abs(variance_pct) < 15:  # Within 15% is acceptable
        return 75
    elif variance_pct < 20:  # Under market
        return 85
    else:  # Significantly over market
        return 55


def calculate_liquidity_score(location_data, property_type):
    """Calculate liquidity score (0-100) - how easy to sell."""
    if not location_data:
        return 0

    score = 50

    # Demand level heavily influences liquidity
    if location_data["demand_level"] == "high":
        score += 35
    elif location_data["demand_level"] == "medium":
        score += 15

    # Property type influences liquidity
    liquidity_by_type = {
        "Flat": 20,
        "Townhouse": 15,
        "Villa": 10,
        "Plot": 5,
        "Commercial": 8,
    }
    score += liquidity_by_type.get(property_type, 0)

    # Location connectivity matters for selling speed
    if location_data["nearest_metro_km"] < 5:
        score += 10
    elif location_data["nearest_metro_km"] < 10:
        score += 5

    return min(100, score)


def calculate_risk_score(location_data, property_type):
    """Calculate risk score (0-100, where 100 = low risk)."""
    if not location_data:
        return 0

    score = 50

    # Location quality reduces risk
    if location_data["road_quality"] == "excellent":
        score += 20
    elif location_data["road_quality"] == "good":
        score += 10

    # Metro planning reduces risk
    if location_data["metro_planned"]:
        score += 15

    # Infrastructure development reduces risk
    if location_data["infrastructure_under_development"]:
        score += 10

    # Demand level affects risk
    if location_data["demand_level"] == "high":
        score += 10
    elif location_data["demand_level"] == "medium":
        score += 5

    # Property type risk factors
    # Flats are lower risk than plots in terms of regulation
    if property_type == "Flat":
        score += 5
    elif property_type == "Plot":
        score -= 5

    return min(100, score)


def get_investor_profile_match(scores, property_type, bedrooms):
    """Determine which investor types this property is best for."""
    profiles = {}

    # First-time buyer score
    first_time_score = min(100, (
        scores["location_score"] * 0.3 +
        scores["price_positioning_score"] * 0.3 +
        scores["liquidity_score"] * 0.2 +
        scores["risk_score"] * 0.2
    ))
    profiles["first-time buyer"] = int(first_time_score)

    # Investor score (focus on appreciation and rental)
    investor_score = min(100, (
        scores["appreciation_potential_score"] * 0.4 +
        scores["rental_potential_score"] * 0.3 +
        scores["price_positioning_score"] * 0.2 +
        scores["liquidity_score"] * 0.1
    ))
    profiles["investor"] = int(investor_score)

    # NRI score (focus on capital appreciation and ease of selling)
    nri_score = min(100, (
        scores["appreciation_potential_score"] * 0.35 +
        scores["liquidity_score"] * 0.35 +
        scores["location_score"] * 0.2 +
        scores["price_positioning_score"] * 0.1
    ))
    profiles["NRI"] = int(nri_score)

    # HNI score (focus on premium features, liquidity, low risk)
    hni_score = min(100, (
        scores["location_score"] * 0.3 +
        scores["liquidity_score"] * 0.3 +
        scores["risk_score"] * 0.2 +
        scores["appreciation_potential_score"] * 0.2
    ))
    profiles["HNI"] = int(hni_score)

    return profiles


def calculate_property_opportunity_score(property_id):
    """Calculate complete opportunity score for a property.

    Returns dict with all scores and explanations.
    """
    conn = get_conn()

    # Get property data
    prop = conn.execute(
        "SELECT p.*, l.* FROM properties p LEFT JOIN location_data l "
        "ON p.city = l.city AND p.locality = l.locality WHERE p.id = ?",
        (property_id,)
    ).fetchone()

    if not prop:
        conn.close()
        return None

    # Get location data (fallback if not joined)
    location = conn.execute(
        "SELECT * FROM location_data WHERE city = ? AND locality = ?",
        (prop["city"], prop["locality"])
    ).fetchone()

    conn.close()

    # Calculate component scores
    location_score = calculate_location_score(location) if location else 50
    appreciation_score = calculate_appreciation_score(location) if location else 50
    rental_score = calculate_rental_score(location) if location else 50
    price_score = calculate_price_positioning_score(prop, location) if location else 75
    liquidity_score = calculate_liquidity_score(location, prop["ptype"]) if location else 60
    risk_score = calculate_risk_score(location, prop["ptype"]) if location else 60

    # Calculate overall opportunity score
    # Weights: location 25%, appreciation 20%, rental 20%, price 15%, liquidity 10%, risk 10%
    overall_score = min(100, int(
        location_score * 0.25 +
        appreciation_score * 0.20 +
        rental_score * 0.20 +
        price_score * 0.15 +
        liquidity_score * 0.10 +
        risk_score * 0.10
    ))

    # Get investor profile matches
    component_scores = {
        "location_score": location_score,
        "appreciation_potential_score": appreciation_score,
        "rental_potential_score": rental_score,
        "price_positioning_score": price_score,
        "liquidity_score": liquidity_score,
        "risk_score": risk_score,
    }

    investor_profiles = get_investor_profile_match(component_scores, prop["ptype"], prop["bedrooms"])

    return {
        "property_id": property_id,
        "overall_score": overall_score,
        "component_scores": {
            "location": location_score,
            "appreciation": appreciation_score,
            "rental": rental_score,
            "price": price_score,
            "liquidity": liquidity_score,
            "risk": risk_score,
        },
        "investor_profiles": investor_profiles,
        "location_name": f"{prop['locality']}, {prop['city']}",
        "property_type": prop["ptype"],
    }


def update_property_intelligence_in_db(property_id):
    """Calculate and store intelligence scores in database."""
    scores_data = calculate_property_opportunity_score(property_id)
    if not scores_data:
        return False

    conn = get_conn()

    # Build explanation text
    top_profile = max(scores_data["investor_profiles"].items(), key=lambda x: x[1])
    match_explanation = (
        f"Strong {top_profile[0]} opportunity (score: {top_profile[1]}/100). "
        f"Location score: {scores_data['component_scores']['location']}, "
        f"Appreciation potential: {scores_data['component_scores']['appreciation']}, "
        f"Rental potential: {scores_data['component_scores']['rental']}."
    )

    # Upsert into database
    existing = conn.execute(
        "SELECT id FROM property_intelligence WHERE property_id = ?",
        (property_id,)
    ).fetchone()

    if existing:
        conn.execute(
            "UPDATE property_intelligence SET "
            "location_score = ?, connectivity_score = ?, infrastructure_score = ?, "
            "appreciation_potential_score = ?, rental_potential_score = ?, price_positioning_score = ?, "
            "risk_score = ?, liquidity_score = ?, match_explanation = ?, last_updated = ? "
            "WHERE property_id = ?",
            (
                scores_data["component_scores"]["location"],
                scores_data["component_scores"]["location"],
                scores_data["component_scores"]["location"],
                scores_data["component_scores"]["appreciation"],
                scores_data["component_scores"]["rental"],
                scores_data["component_scores"]["price"],
                scores_data["component_scores"]["risk"],
                scores_data["component_scores"]["liquidity"],
                match_explanation,
                now(),
                property_id
            )
        )
    else:
        conn.execute(
            "INSERT INTO property_intelligence "
            "(property_id, location_score, connectivity_score, infrastructure_score, "
            "appreciation_potential_score, rental_potential_score, price_positioning_score, "
            "risk_score, liquidity_score, match_explanation, last_updated) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                property_id,
                scores_data["component_scores"]["location"],
                scores_data["component_scores"]["location"],
                scores_data["component_scores"]["location"],
                scores_data["component_scores"]["appreciation"],
                scores_data["component_scores"]["rental"],
                scores_data["component_scores"]["price"],
                scores_data["component_scores"]["risk"],
                scores_data["component_scores"]["liquidity"],
                match_explanation,
                now()
            )
        )

    conn.commit()
    conn.close()

    return True
