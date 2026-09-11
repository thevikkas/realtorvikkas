"""Real Estate Growth Map Engine.

Week 4 System 4: Market intelligence, growth tracking, and opportunity visualization.

Zero external dependencies — uses only Python standard library.
"""

import json
from database import get_conn, now


def get_city_statistics(city):
    """Calculate market statistics for a city."""
    conn = get_conn()

    # Get all properties in city
    properties = conn.execute(
        "SELECT price, listing, ptype, area_sqft FROM properties WHERE city = ? AND status = 'available'",
        (city,)
    ).fetchall()

    if not properties:
        conn.close()
        return None

    properties_list = [dict(p) for p in properties]

    # Calculate statistics
    prices = [p['price'] for p in properties_list if p['price'] > 0]
    avg_price = sum(prices) / len(prices) if prices else 0
    prices_sorted = sorted(prices)
    median_price = prices_sorted[len(prices_sorted) // 2] if prices_sorted else 0

    # Property type distribution
    type_dist = {}
    for p in properties_list:
        ptype = p['ptype']
        type_dist[ptype] = type_dist.get(ptype, 0) + 1

    # Listing type ratio
    buy_count = sum(1 for p in properties_list if p['listing'] == 'buy')
    rent_count = sum(1 for p in properties_list if p['listing'] == 'rent')
    rent_ratio = rent_count / buy_count if buy_count > 0 else 0

    # Get location data for growth metrics
    loc_data = conn.execute(
        "SELECT price_growth_1yr, price_growth_3yr, price_growth_5yr, demand_level "
        "FROM location_data WHERE city = ? LIMIT 1",
        (city,)
    ).fetchone()

    conn.close()

    growth_1yr = loc_data['price_growth_1yr'] if loc_data else 0
    growth_3yr = loc_data['price_growth_3yr'] if loc_data else 0
    growth_5yr = loc_data['price_growth_5yr'] if loc_data else 0
    demand = loc_data['demand_level'] if loc_data else 'medium'

    # Determine sentiment
    if growth_5yr >= 4.0:
        sentiment = 'bullish'
    elif growth_5yr >= 2.0:
        sentiment = 'neutral'
    else:
        sentiment = 'bearish'

    return {
        'city': city,
        'total_properties': len(properties_list),
        'avg_price': int(avg_price),
        'median_price': int(median_price),
        'price_range_min': min(prices) if prices else 0,
        'price_range_max': max(prices) if prices else 0,
        'property_type_distribution': json.dumps(type_dist),
        'rent_vs_buy_ratio': rent_ratio,
        'price_appreciation_1yr': growth_1yr,
        'price_appreciation_3yr': growth_3yr,
        'price_appreciation_5yr': growth_5yr,
        'market_sentiment': sentiment,
        'demand_level': demand,
    }


def get_locality_statistics(city, locality):
    """Calculate statistics for specific locality."""
    conn = get_conn()

    # Get location data
    loc_data = conn.execute(
        "SELECT * FROM location_data WHERE city = ? AND locality = ?",
        (city, locality)
    ).fetchone()

    if not loc_data:
        conn.close()
        return None

    # Get properties in locality
    properties = conn.execute(
        "SELECT price, listing, bedrooms, bathrooms FROM properties "
        "WHERE city = ? AND locality = ? AND status = 'available'",
        (city, locality)
    ).fetchall()

    conn.close()

    loc_dict = dict(loc_data) if loc_data else {}

    return {
        'city': city,
        'locality': locality,
        'properties_available': len(properties),
        'connectivity': {
            'nearest_metro_km': loc_dict.get('nearest_metro_km', 0),
            'nearest_mall_km': loc_dict.get('nearest_mall_km', 0),
            'nearest_hospital_km': loc_dict.get('nearest_hospital_km', 0),
            'nearest_school_km': loc_dict.get('nearest_school_km', 0),
            'road_quality': loc_dict.get('road_quality', ''),
            'public_transport': loc_dict.get('public_transport', ''),
        },
        'growth': {
            '1yr': loc_dict.get('price_growth_1yr', 0),
            '3yr': loc_dict.get('price_growth_3yr', 0),
            '5yr': loc_dict.get('price_growth_5yr', 0),
        },
        'market': {
            'avg_price_per_sqft': loc_dict.get('avg_price_per_sqft', 0),
            'avg_rental_yield': loc_dict.get('avg_rental_yield', 0),
            'demand_level': loc_dict.get('demand_level', 'medium'),
        },
        'infrastructure': {
            'metro_planned': loc_dict.get('metro_planned', False),
            'development': loc_dict.get('infrastructure_under_development', ''),
            'commercial': loc_dict.get('commercial_development', ''),
        },
    }


def get_all_cities():
    """Get list of all cities with basic stats."""
    conn = get_conn()

    # Get unique cities from location_data
    cities = conn.execute(
        "SELECT DISTINCT city FROM location_data ORDER BY city"
    ).fetchall()

    conn.close()

    result = []
    for city_row in cities:
        city = city_row['city']
        stats = get_city_statistics(city)
        if stats:
            result.append({
                'city': city,
                'total_properties': stats['total_properties'],
                'avg_price': stats['avg_price'],
                'growth_5yr': stats['price_appreciation_5yr'],
                'sentiment': stats['market_sentiment'],
                'demand': stats['demand_level'],
            })

    return sorted(result, key=lambda x: x['growth_5yr'], reverse=True)


def get_localities_for_city(city):
    """Get all localities in a city with stats."""
    conn = get_conn()

    localities = conn.execute(
        "SELECT locality FROM location_data WHERE city = ? ORDER BY price_growth_5yr DESC",
        (city,)
    ).fetchall()

    conn.close()

    result = []
    for loc_row in localities:
        locality = loc_row['locality']
        stats = get_locality_statistics(city, locality)
        if stats:
            result.append({
                'locality': locality,
                'properties': stats['properties_available'],
                'growth_5yr': stats['growth']['5yr'],
                'demand': stats['market']['demand_level'],
                'price_per_sqft': stats['market']['avg_price_per_sqft'],
            })

    return result


def get_infrastructure_projects(city=None, locality=None):
    """Get infrastructure projects for area."""
    conn = get_conn()

    if locality:
        projects = conn.execute(
            "SELECT * FROM infrastructure_projects WHERE city = ? AND locality = ? ORDER BY completion_date",
            (city, locality)
        ).fetchall()
    elif city:
        projects = conn.execute(
            "SELECT * FROM infrastructure_projects WHERE city = ? ORDER BY completion_date",
            (city,)
        ).fetchall()
    else:
        projects = conn.execute(
            "SELECT * FROM infrastructure_projects ORDER BY completion_date"
        ).fetchall()

    conn.close()

    return [dict(p) for p in projects]


def calculate_growth_opportunity_score(growth_5yr, demand_level, infrastructure_pipeline):
    """Calculate opportunity score based on growth metrics.

    0-100 scale
    """
    score = 50  # Base score

    # Growth factor (40% weight)
    if growth_5yr >= 5.0:
        score += 40
    elif growth_5yr >= 4.0:
        score += 30
    elif growth_5yr >= 3.0:
        score += 20
    elif growth_5yr >= 2.0:
        score += 10

    # Demand factor (40% weight)
    if demand_level == 'high':
        score += 40
    elif demand_level == 'medium':
        score += 20
    else:
        score += 5

    # Infrastructure factor (20% weight)
    if infrastructure_pipeline:
        score += 20

    return min(100, score)


def save_market_insight(city, locality=None, data=None):
    """Save market insight to database."""
    if not data:
        data = get_locality_statistics(city, locality) if locality else get_city_statistics(city)

    if not data:
        return False

    conn = get_conn()

    conn.execute(
        "INSERT OR REPLACE INTO market_insights "
        "(city, locality, total_properties, avg_price, market_sentiment, "
        "price_appreciation_1yr, price_appreciation_3yr, price_appreciation_5yr, last_updated) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (
            city,
            locality,
            data.get('total_properties', 0),
            data.get('avg_price', 0),
            data.get('market_sentiment', 'neutral'),
            data.get('price_appreciation_1yr', 0),
            data.get('price_appreciation_3yr', 0),
            data.get('price_appreciation_5yr', 0),
            now(),
        )
    )

    conn.commit()
    conn.close()

    return True


def get_heat_map_data():
    """Get data for heat map visualization.

    Returns list of cities with coordinates and growth metrics.
    """
    cities = get_all_cities()

    # Mock coordinates for Indian cities (would be real coords in production)
    city_coords = {
        'Jaipur': {'lat': 26.9124, 'lng': 75.7873, 'region': 'Rajasthan'},
        'Udaipur': {'lat': 24.5854, 'lng': 73.7125, 'region': 'Rajasthan'},
        'Delhi': {'lat': 28.7041, 'lng': 77.1025, 'region': 'NCR'},
        'Gurugram': {'lat': 28.4595, 'lng': 77.0266, 'region': 'NCR'},
    }

    result = []
    for city in cities:
        coords = city_coords.get(city['city'], None)
        if coords:
            heat_value = city['growth_5yr']  # Use growth as heat intensity
            result.append({
                'city': city['city'],
                'lat': coords['lat'],
                'lng': coords['lng'],
                'growth': city['growth_5yr'],
                'properties': city['total_properties'],
                'sentiment': city['sentiment'],
                'heat': max(0, min(100, heat_value * 10)),  # Scale to 0-100
            })

    return result


def get_top_opportunities(limit=5):
    """Get top growing areas for opportunity analysis."""
    cities = get_all_cities()

    # Score each by growth + demand
    scored = []
    for city in cities:
        opportunity_score = calculate_growth_opportunity_score(
            city['growth_5yr'],
            city['demand'],
            True  # Assume infrastructure pipeline
        )
        scored.append({
            'city': city['city'],
            'growth_5yr': city['growth_5yr'],
            'opportunity_score': opportunity_score,
            'sentiment': city['sentiment'],
            'properties': city['total_properties'],
        })

    # Sort by opportunity score
    scored.sort(key=lambda x: x['opportunity_score'], reverse=True)

    return scored[:limit]


def format_market_sentiment(growth_5yr):
    """Format sentiment as emoji and text."""
    if growth_5yr >= 4.0:
        return ('📈 Bullish', '#10b981')  # Green
    elif growth_5yr >= 2.0:
        return ('➡️ Neutral', '#3b82f6')  # Blue
    else:
        return ('📉 Bearish', '#ef4444')  # Red
