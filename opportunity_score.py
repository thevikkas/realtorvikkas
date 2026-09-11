"""Opportunity Score™ — Proprietary opportunity identification system.

Week 8 System 8: Multi-factor opportunity scoring, risk analysis, and
investment recommendations based on market intelligence.

Zero external dependencies — uses only Python standard library.
"""

import json
from database import get_conn, now


def calculate_opportunity_score(property_id):
    """Calculate Opportunity Score™ for a property (0-100 scale).

    Combines location, market, financial, demand, and timing factors.
    """
    conn = get_conn()

    # Get property
    prop = conn.execute("SELECT * FROM properties WHERE id = ?", (property_id,)).fetchone()
    if not prop:
        conn.close()
        return None

    prop_dict = dict(prop)

    # Get property intelligence
    intel = conn.execute(
        "SELECT * FROM property_intelligence WHERE property_id = ?",
        (property_id,)
    ).fetchone()

    # Get location data
    loc_data = conn.execute(
        "SELECT * FROM location_data WHERE city = ? AND locality = ?",
        (prop_dict['city'], prop_dict['locality'])
    ).fetchone()

    # Get market data
    market = conn.execute(
        "SELECT * FROM market_insights WHERE city = ?",
        (prop_dict['city'],)
    ).fetchone()

    # Convert to dict if needed
    intel_dict = dict(intel) if intel else None
    loc_data_dict = dict(loc_data) if loc_data else None
    market_dict = dict(market) if market else None

    # LOCATION COMPONENT (25% weight) ========================
    location_score = 60  # Base
    if intel_dict:
        location_score = int(intel_dict.get('location_score', 60)) if intel_dict.get('location_score') else 60
    if loc_data_dict:
        if loc_data_dict.get('infrastructure_score'):
            location_score = (location_score + int(loc_data_dict['infrastructure_score'])) // 2

    # MARKET COMPONENT (25% weight) ========================
    market_score = 60  # Base
    if market_dict:
        # Sentiment affects score
        if market_dict.get('market_sentiment') == 'bullish':
            market_score = 75
        elif market_dict.get('market_sentiment') == 'bearish':
            market_score = 45
        # Demand adjustment
        if market_dict.get('demand_level') == 'high':
            market_score = min(100, market_score + 15)
        elif market_dict.get('demand_level') == 'low':
            market_score = max(0, market_score - 15)

    # FINANCIAL COMPONENT (25% weight) ========================
    financial_score = 60  # Base
    if prop_dict.get('price', 0) > 0:
        if intel_dict and intel_dict.get('price_positioning_score'):
            financial_score = int(intel_dict['price_positioning_score'])

    # DEMAND COMPONENT (15% weight) ========================
    demand_score = 50  # Base
    if intel_dict:
        demand_score = int(intel_dict.get('liquidity_score', 50))

    # TIMING COMPONENT (10% weight) ========================
    timing_score = 50  # Base
    if market_dict:
        growth_5yr = market_dict.get('price_appreciation_5yr', 0)
        if growth_5yr > 0.05:
            timing_score = 80
        elif growth_5yr > 0.03:
            timing_score = 65
        elif growth_5yr > 0.01:
            timing_score = 50
        else:
            timing_score = 35

    # OVERALL OPPORTUNITY SCORE (weighted) ========================
    overall_score = int(
        location_score * 0.25 +
        market_score * 0.25 +
        financial_score * 0.25 +
        demand_score * 0.15 +
        timing_score * 0.10
    )

    overall_score = max(0, min(100, overall_score))

    # DETERMINE OPPORTUNITY TYPE ========================
    listing = prop_dict.get('listing', 'buy')
    opportunity_type = 'rent' if listing == 'rent' else 'buy'

    # RISK LEVEL ========================
    if overall_score >= 75:
        risk_level = 'low'
    elif overall_score >= 60:
        risk_level = 'medium'
    else:
        risk_level = 'high'

    # POTENTIAL RETURN ========================
    roi_potential = (overall_score / 100) * 15  # Scale to 0-15% annual potential

    # ACTION PRIORITY ========================
    if overall_score >= 80:
        action_priority = 'strong_buy'
    elif overall_score >= 70:
        action_priority = 'consider'
    elif overall_score >= 50:
        action_priority = 'monitor'
    else:
        action_priority = 'pass'

    # TIME SENSITIVITY ========================
    if overall_score >= 80 and timing_score >= 75:
        time_sensitivity = 'urgent'
    elif overall_score >= 70 and timing_score >= 65:
        time_sensitivity = 'high'
    elif overall_score >= 50:
        time_sensitivity = 'medium'
    else:
        time_sensitivity = 'low'

    # MARKET CONTEXT ========================
    market_sentiment = 'neutral'
    if market_dict:
        market_sentiment = market_dict.get('market_sentiment', 'neutral')

    market_cycle_stage = 'steady'
    if market_dict:
        growth = market_dict.get('price_appreciation_5yr', 0)
        if growth > 0.07:
            market_cycle_stage = 'growing'
        elif growth > 0.05:
            market_cycle_stage = 'steady'
        elif growth > 0.02:
            market_cycle_stage = 'declining'

    # SAVE OR UPDATE ========================
    existing = conn.execute(
        "SELECT id FROM opportunity_scores WHERE property_id = ?",
        (property_id,)
    ).fetchone()

    if existing:
        conn.execute(
            "UPDATE opportunity_scores SET "
            "location_score=?, market_score=?, financial_score=?, demand_score=?, timing_score=?, "
            "opportunity_score=?, opportunity_type=?, risk_level=?, potential_return=?, "
            "action_priority=?, time_sensitivity=?, market_sentiment=?, market_cycle_stage=?, "
            "updated_at=? WHERE property_id=?",
            (location_score, market_score, financial_score, demand_score, timing_score,
             overall_score, opportunity_type, risk_level, roi_potential, action_priority,
             time_sensitivity, market_sentiment, market_cycle_stage, now(), property_id)
        )
    else:
        conn.execute(
            "INSERT INTO opportunity_scores "
            "(property_id, location_score, market_score, financial_score, demand_score, timing_score, "
            "opportunity_score, opportunity_type, risk_level, potential_return, action_priority, "
            "time_sensitivity, market_sentiment, market_cycle_stage, calculated_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (property_id, location_score, market_score, financial_score, demand_score, timing_score,
             overall_score, opportunity_type, risk_level, roi_potential, action_priority,
             time_sensitivity, market_sentiment, market_cycle_stage, now(), now())
        )

    conn.commit()
    conn.close()

    return {
        'property_id': property_id,
        'opportunity_score': overall_score,
        'location_score': location_score,
        'market_score': market_score,
        'financial_score': financial_score,
        'demand_score': demand_score,
        'timing_score': timing_score,
        'opportunity_type': opportunity_type,
        'risk_level': risk_level,
        'roi_potential': roi_potential,
        'action_priority': action_priority,
        'time_sensitivity': time_sensitivity,
    }


def get_opportunity_score(property_id):
    """Get calculated opportunity score."""
    conn = get_conn()

    score = conn.execute(
        "SELECT * FROM opportunity_scores WHERE property_id = ?",
        (property_id,)
    ).fetchone()

    conn.close()

    return dict(score) if score else None


def get_best_opportunities(limit=20, min_score=70):
    """Get top opportunities ranked by score."""
    conn = get_conn()

    scores = conn.execute(
        "SELECT * FROM opportunity_scores WHERE opportunity_score >= ? ORDER BY opportunity_score DESC LIMIT ?",
        (min_score, limit)
    ).fetchall()

    conn.close()

    results = []
    for score in scores:
        score_dict = dict(score)
        prop = conn.execute(
            "SELECT title, city, locality, price FROM properties WHERE id = ?",
            (score_dict['property_id'],)
        ).fetchone()

        if prop:
            score_dict['property'] = dict(prop)

        results.append(score_dict)

    return results


def get_opportunities_by_priority(priority='consider', limit=20):
    """Get opportunities filtered by action priority."""
    conn = get_conn()

    scores = conn.execute(
        "SELECT * FROM opportunity_scores WHERE action_priority = ? ORDER BY opportunity_score DESC LIMIT ?",
        (priority, limit)
    ).fetchall()

    conn.close()

    return [dict(s) for s in scores]


def identify_market_signals(city):
    """Identify market signals (bullish/bearish) for a city."""
    conn = get_conn()

    market = conn.execute(
        "SELECT * FROM market_insights WHERE city = ?",
        (city,)
    ).fetchone()

    if not market:
        conn.close()
        return []

    market_dict = dict(market)
    signals = []

    # Growth signal
    growth_5yr = market_dict.get('price_appreciation_5yr', 0)
    if growth_5yr > 0.05:
        signals.append({
            'type': 'strong_growth',
            'direction': 'bullish',
            'strength': 'strong',
            'description': f'5-year growth: {growth_5yr:.1%}',
        })
    elif growth_5yr < 0.01:
        signals.append({
            'type': 'weak_growth',
            'direction': 'bearish',
            'strength': 'medium',
            'description': f'Minimal growth: {growth_5yr:.1%}',
        })

    # Demand signal
    if market_dict.get('demand_level') == 'high':
        signals.append({
            'type': 'high_demand',
            'direction': 'bullish',
            'strength': 'strong',
            'description': 'High market demand',
        })
    elif market_dict.get('demand_level') == 'low':
        signals.append({
            'type': 'low_demand',
            'direction': 'bearish',
            'strength': 'medium',
            'description': 'Low market demand',
        })

    # Sentiment signal
    if market_dict.get('market_sentiment') == 'bullish':
        signals.append({
            'type': 'bullish_sentiment',
            'direction': 'bullish',
            'strength': 'medium',
            'description': 'Positive market sentiment',
        })

    conn.close()

    return signals


def rank_opportunities(property_ids=None):
    """Rank opportunities and return sorted list."""
    conn = get_conn()

    if property_ids:
        placeholders = ','.join(['?' for _ in property_ids])
        scores = conn.execute(
            f"SELECT * FROM opportunity_scores WHERE property_id IN ({placeholders}) ORDER BY opportunity_score DESC",
            property_ids
        ).fetchall()
    else:
        scores = conn.execute(
            "SELECT * FROM opportunity_scores ORDER BY opportunity_score DESC"
        ).fetchall()

    conn.close()

    results = []
    for i, score in enumerate(scores, 1):
        score_dict = dict(score)
        score_dict['rank'] = i
        results.append(score_dict)

    return results


def get_opportunity_analysis(property_id):
    """Get comprehensive opportunity analysis."""
    conn = get_conn()

    # Get score
    score = conn.execute(
        "SELECT * FROM opportunity_scores WHERE property_id = ?",
        (property_id,)
    ).fetchone()

    if not score:
        conn.close()
        return None

    score_dict = dict(score)

    # Get components
    components = conn.execute(
        "SELECT * FROM score_components WHERE opportunity_score_id = ?",
        (score['id'],)
    ).fetchone()

    # Get signals
    signals = conn.execute(
        "SELECT * FROM opportunity_signals WHERE opportunity_score_id = ? ORDER BY detected_at DESC",
        (score['id'],)
    ).fetchall()

    # Get recommendation
    rec = conn.execute(
        "SELECT * FROM opportunity_recommendations WHERE opportunity_score_id = ?",
        (score['id'],)
    ).fetchone()

    # Get tracking
    tracking = conn.execute(
        "SELECT * FROM opportunity_tracking WHERE opportunity_score_id = ?",
        (score['id'],)
    ).fetchone()

    # Get property
    prop = conn.execute(
        "SELECT * FROM properties WHERE id = ?",
        (property_id,)
    ).fetchone()

    conn.close()

    score_dict['components'] = dict(components) if components else None
    score_dict['signals'] = [dict(s) for s in signals]
    score_dict['recommendation'] = dict(rec) if rec else None
    score_dict['tracking'] = dict(tracking) if tracking else None
    score_dict['property'] = dict(prop) if prop else None

    return score_dict


def get_opportunity_dashboard_stats():
    """Get statistics for opportunity dashboard."""
    conn = get_conn()

    total_opportunities = conn.execute("SELECT COUNT(*) as count FROM opportunity_scores").fetchone()
    strong_buy = conn.execute("SELECT COUNT(*) as count FROM opportunity_scores WHERE action_priority = 'strong_buy'").fetchone()
    consider = conn.execute("SELECT COUNT(*) as count FROM opportunity_scores WHERE action_priority = 'consider'").fetchone()
    monitor = conn.execute("SELECT COUNT(*) as count FROM opportunity_scores WHERE action_priority = 'monitor'").fetchone()

    # Average score
    avg_score = conn.execute("SELECT AVG(opportunity_score) as avg FROM opportunity_scores").fetchone()

    # Best opportunities
    best = conn.execute(
        "SELECT id, property_id, opportunity_score FROM opportunity_scores ORDER BY opportunity_score DESC LIMIT 5"
    ).fetchall()

    # By risk level
    by_risk = conn.execute(
        "SELECT risk_level, COUNT(*) as count FROM opportunity_scores GROUP BY risk_level ORDER BY count DESC"
    ).fetchall()

    # By market sentiment
    by_sentiment = conn.execute(
        "SELECT market_sentiment, COUNT(*) as count FROM opportunity_scores GROUP BY market_sentiment"
    ).fetchall()

    conn.close()

    return {
        'total_opportunities': total_opportunities['count'] if total_opportunities else 0,
        'strong_buy_count': strong_buy['count'] if strong_buy else 0,
        'consider_count': consider['count'] if consider else 0,
        'monitor_count': monitor['count'] if monitor else 0,
        'average_score': avg_score['avg'] or 0,
        'best_opportunities': [dict(b) for b in best],
        'by_risk_level': [dict(r) for r in by_risk],
        'by_market_sentiment': [dict(s) for s in by_sentiment],
    }
