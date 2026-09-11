"""AI Property Matchmaker Engine.

Week 3 System 3: Intelligent matching algorithm that connects buyers
with perfect properties based on their requirements.

Zero external dependencies — uses only Python standard library.
"""

import json
from database import get_conn, now


def calculate_price_fit(property_price, budget_min, budget_max):
    """Calculate price fit score (0-100).

    100 = perfect match within budget
    0 = way outside budget
    """
    if budget_min <= property_price <= budget_max:
        # Within budget - find how centered
        mid_budget = (budget_min + budget_max) / 2
        variance = abs(property_price - mid_budget)
        range_size = (budget_max - budget_min) / 2
        return max(90, 100 - int((variance / range_size) * 10))

    # Outside budget - calculate how far
    if property_price < budget_min:
        variance_pct = (budget_min - property_price) / budget_min
    else:
        variance_pct = (property_price - budget_max) / budget_max

    # Penalize progressively
    if variance_pct < 0.1:  # Within 10%
        return 85
    elif variance_pct < 0.2:  # Within 20%
        return 70
    elif variance_pct < 0.3:  # Within 30%
        return 50
    else:
        return max(10, 100 - int(variance_pct * 100))


def calculate_location_fit(property_city, property_locality, location_prefs):
    """Calculate location fit score (0-100).

    100 = exact match with preference
    0 = different city entirely
    """
    if not location_prefs:
        return 50  # Neutral if no preference

    # Parse location preferences (comma-separated or JSON list)
    try:
        if isinstance(location_prefs, str):
            if location_prefs.startswith('['):
                prefs = json.loads(location_prefs)
            else:
                prefs = [p.strip() for p in location_prefs.split(',')]
    except:
        prefs = [location_prefs]

    # Check city match
    for pref in prefs:
        pref = pref.strip().lower()
        if pref == property_city.lower():
            return 100
        if pref == (property_locality or '').lower():
            return 95
        # Partial match (city name substring)
        if property_city.lower() in pref or pref in property_city.lower():
            return 75

    return 20  # Different location


def calculate_property_type_fit(property_type, wanted_types):
    """Calculate property type fit (0-100).

    100 = exact type match
    0 = unwanted type
    """
    if not wanted_types:
        return 50

    try:
        if isinstance(wanted_types, str):
            if wanted_types.startswith('['):
                types = json.loads(wanted_types)
            else:
                types = [t.strip() for t in wanted_types.split(',')]
    except:
        types = [wanted_types]

    for t in types:
        if t.strip().lower() == property_type.lower():
            return 100

    return 0


def calculate_amenity_fit(property_amenities, wanted_amenities):
    """Calculate amenity match score (0-100).

    Based on percentage of wanted amenities present.
    """
    if not wanted_amenities:
        return 50  # Neutral if no preference

    try:
        if isinstance(wanted_amenities, str):
            if wanted_amenities.startswith('['):
                wanted = json.loads(wanted_amenities)
            else:
                wanted = [a.strip().lower() for a in wanted_amenities.split(',')]
    except:
        wanted = [wanted_amenities]

    if not wanted:
        return 50

    # Parse property amenities
    try:
        if isinstance(property_amenities, str):
            if property_amenities.startswith('['):
                present = json.loads(property_amenities)
            else:
                present = [a.strip().lower() for a in property_amenities.split(',')]
    except:
        present = [property_amenities] if property_amenities else []

    # Calculate match percentage
    if len(wanted) == 0:
        return 50

    matches = sum(1 for w in wanted if any(w in p or p in w for p in present))
    match_pct = (matches / len(wanted)) * 100

    return int(match_pct)


def calculate_bed_bath_fit(prop_bed, prop_bath, min_bed, min_bath):
    """Calculate bedroom/bathroom fit (0-100).

    100 = exceeds minimums
    0 = below minimums
    """
    bed_score = 100 if (prop_bed or 0) >= min_bed else max(0, 100 - ((min_bed - (prop_bed or 0)) * 20))
    bath_score = 100 if (prop_bath or 0) >= min_bath else max(0, 100 - ((min_bath - (prop_bath or 0)) * 20))

    return int((bed_score + bath_score) / 2)


def calculate_investment_fit(property_id, investment_purpose, expected_roi_min, expected_yield_min):
    """Calculate investment potential fit (0-100).

    Uses property intelligence scores if available.
    """
    if investment_purpose != 'investment':
        return 50  # Neutral for personal use

    # Try to get property intelligence score
    conn = get_conn()
    intel = conn.execute(
        "SELECT investment_fit_score FROM property_intelligence WHERE property_id = ?",
        (property_id,)
    ).fetchone()
    conn.close()

    if intel:
        return int(intel[0])

    return 60  # Default moderate fit


def calculate_lifestyle_fit(property_city, walkability_important, transit_important):
    """Calculate lifestyle fit (0-100).

    Based on connectivity preferences.
    """
    score = 50  # Base score

    # Get location data for walkability/transit info
    conn = get_conn()
    loc = conn.execute(
        "SELECT road_quality, public_transport FROM location_data WHERE city = ?",
        (property_city,)
    ).fetchone()
    conn.close()

    if not loc:
        return score

    if walkability_important:
        if loc[0] == 'excellent':
            score += 25
        elif loc[0] == 'good':
            score += 15
        else:
            score -= 10

    if transit_important:
        if loc[1] == 'excellent':
            score += 25
        elif loc[1] == 'good':
            score += 15
        else:
            score -= 10

    return max(10, min(100, score))


def calculate_match_score(requirement, property_data):
    """Calculate overall match score (0-100).

    Weighted average of component scores.
    """
    # Component scores
    price_score = calculate_price_fit(
        property_data['price'],
        requirement['budget_min'],
        requirement['budget_max']
    )

    location_score = calculate_location_fit(
        property_data['city'],
        property_data['locality'],
        requirement['location_preferences']
    )

    type_score = calculate_property_type_fit(
        property_data['ptype'],
        requirement['property_types']
    )

    amenity_score = calculate_amenity_fit(
        property_data['amenities'],
        requirement['amenities_wanted']
    )

    bed_bath_score = calculate_bed_bath_fit(
        property_data['bedrooms'],
        property_data['bathrooms'],
        requirement['min_bedrooms'],
        requirement['min_bathrooms']
    )

    investment_score = calculate_investment_fit(
        property_data['id'],
        requirement['investment_purpose'],
        requirement['expected_roi_min'],
        requirement['expected_rental_yield']
    )

    lifestyle_score = calculate_lifestyle_fit(
        property_data['city'],
        requirement['walkability_important'],
        requirement['public_transit_important']
    )

    # Weighted average
    # Price: 25%, Location: 25%, Type: 15%, Amenities: 10%, Bed/Bath: 10%, Investment: 10%, Lifestyle: 5%
    overall_score = int(
        price_score * 0.25 +
        location_score * 0.25 +
        type_score * 0.15 +
        amenity_score * 0.10 +
        bed_bath_score * 0.10 +
        investment_score * 0.10 +
        lifestyle_score * 0.05
    )

    return {
        'overall_score': overall_score,
        'components': {
            'price': price_score,
            'location': location_score,
            'type': type_score,
            'amenities': amenity_score,
            'bed_bath': bed_bath_score,
            'investment': investment_score,
            'lifestyle': lifestyle_score,
        }
    }


def generate_match_reasons_and_concerns(req, prop, scores):
    """Generate human-readable reasons and concerns."""
    reasons = []
    concerns = []

    comp = scores['components']

    # Reasons
    if comp['price'] >= 90:
        reasons.append("Perfect price fit within your budget")
    elif comp['price'] >= 75:
        reasons.append("Good price alignment with your budget")

    if comp['location'] >= 95:
        reasons.append("Exact match for your preferred location")
    elif comp['location'] >= 85:
        reasons.append("In or near your preferred location")

    if comp['type'] == 100:
        reasons.append("Exactly the property type you want")

    if comp['amenities'] >= 80:
        reasons.append("Has most of your desired amenities")

    if comp['bed_bath'] >= 90:
        reasons.append("Excellent bedroom/bathroom count")

    if comp['investment'] >= 75 and req['investment_purpose'] == 'investment':
        reasons.append("Strong investment potential")

    # Concerns
    if comp['price'] < 50:
        concerns.append("Price is significantly outside your budget")
    elif comp['price'] < 75:
        concerns.append("Price is somewhat higher than budget")

    if comp['location'] < 50:
        concerns.append("Not in your preferred locations")

    if comp['type'] == 0:
        concerns.append("Different property type than you wanted")

    if comp['amenities'] < 50:
        concerns.append("Missing many desired amenities")

    if comp['bed_bath'] < 70:
        concerns.append("May not have enough rooms for your needs")

    if req['investment_purpose'] == 'investment' and comp['investment'] < 60:
        concerns.append("Limited investment potential")

    return reasons, concerns


def match_properties_to_requirement(requirement_id):
    """Find and score all properties against a requirement.

    Returns list of properties ranked by match score.
    """
    conn = get_conn()

    # Get requirement
    req = conn.execute(
        "SELECT * FROM buyer_requirements WHERE id = ?",
        (requirement_id,)
    ).fetchone()

    if not req:
        conn.close()
        return []

    req_dict = dict(req)

    # Get all properties
    properties = conn.execute(
        "SELECT * FROM properties WHERE status = 'available'"
    ).fetchall()

    matches = []

    for prop in properties:
        prop_dict = dict(prop)

        # Calculate match
        match_data = calculate_match_score(req_dict, prop_dict)
        overall_score = match_data['overall_score']

        # Skip very low matches
        if overall_score < 30:
            continue

        # Generate reasons and concerns
        reasons, concerns = generate_match_reasons_and_concerns(
            req_dict, prop_dict, match_data
        )

        # Save to database
        conn.execute(
            "INSERT OR REPLACE INTO property_matches "
            "(requirement_id, property_id, match_score, price_fit_score, "
            "location_fit_score, property_type_fit, amenity_fit_score, "
            "investment_fit_score, lifestyle_fit_score, match_explanation, "
            "match_reasons, potential_concerns, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                requirement_id,
                prop['id'],
                overall_score,
                match_data['components']['price'],
                match_data['components']['location'],
                match_data['components']['type'],
                match_data['components']['amenities'],
                match_data['components']['investment'],
                match_data['components']['lifestyle'],
                f"Great match for {req_dict['investor_profile']}",
                json.dumps(reasons),
                json.dumps(concerns),
                now(),
            )
        )

        matches.append({
            'property_id': prop['id'],
            'property_title': prop['title'],
            'property_type': prop['ptype'],
            'location': f"{prop['locality']}, {prop['city']}",
            'price': prop['price'],
            'match_score': overall_score,
            'reasons': reasons,
            'concerns': concerns,
            'match_details': match_data['components'],
        })

    conn.commit()
    conn.close()

    # Sort by match score descending
    matches.sort(key=lambda x: x['match_score'], reverse=True)

    # Add rank
    for i, match in enumerate(matches):
        match['rank'] = i + 1

    return matches


def get_matches_for_requirement(requirement_id, limit=20):
    """Get ranked matches for a requirement from database."""
    conn = get_conn()

    matches = conn.execute(
        "SELECT pm.*, p.title, p.ptype, p.city, p.locality, p.price "
        "FROM property_matches pm "
        "JOIN properties p ON pm.property_id = p.id "
        "WHERE pm.requirement_id = ? "
        "ORDER BY pm.match_score DESC "
        "LIMIT ?",
        (requirement_id, limit)
    ).fetchall()

    conn.close()

    results = []
    for i, match in enumerate(matches):
        results.append({
            'rank': i + 1,
            'property_id': match['property_id'],
            'title': match['title'],
            'type': match['ptype'],
            'location': f"{match['locality']}, {match['city']}",
            'price': match['price'],
            'match_score': match['match_score'],
            'reasons': json.loads(match['match_reasons'] or '[]'),
            'concerns': json.loads(match['potential_concerns'] or '[]'),
        })

    return results


def find_requirements_for_property(property_id, limit=10):
    """Reverse matching: Find buyer profiles that want this property."""
    conn = get_conn()

    # Get property
    prop = conn.execute(
        "SELECT * FROM properties WHERE id = ?",
        (property_id,)
    ).fetchone()

    if not prop:
        conn.close()
        return []

    prop_dict = dict(prop)

    # Get all requirements
    requirements = conn.execute(
        "SELECT * FROM buyer_requirements ORDER BY created_at DESC"
    ).fetchall()

    matches = []

    for req in requirements:
        req_dict = dict(req)

        # Calculate match
        match_data = calculate_match_score(req_dict, prop_dict)
        overall_score = match_data['overall_score']

        if overall_score < 50:
            continue

        reasons, concerns = generate_match_reasons_and_concerns(
            req_dict, prop_dict, match_data
        )

        matches.append({
            'requirement_id': req['id'],
            'buyer_profile': req['investor_profile'],
            'budget_range': f"₹{req['budget_min']:,} - ₹{req['budget_max']:,}",
            'match_score': overall_score,
            'reasons': reasons,
            'concerns': concerns,
        })

    # Sort by match score
    matches.sort(key=lambda x: x['match_score'], reverse=True)

    conn.close()

    return matches[:limit]
