"""Concierge Foundation — Premium client services and advisory.

Week 7 System 7: Personalized concierge services, property matching,
transaction support, and dedicated advisor relationships.

Zero external dependencies — uses only Python standard library.
"""

import json
from database import get_conn, now


def create_concierge_request(client_id, request_type, title, description='', service_tier='standard', priority='normal'):
    """Create a new concierge service request."""
    conn = get_conn()

    cursor = conn.execute(
        "INSERT INTO concierge_requests "
        "(client_id, request_type, title, description, service_tier, priority, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (client_id, request_type, title, description, service_tier, priority, 'pending', now(), now())
    )

    request_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return request_id


def get_concierge_request(request_id):
    """Get concierge request details."""
    conn = get_conn()

    request = conn.execute(
        "SELECT * FROM concierge_requests WHERE id = ?",
        (request_id,)
    ).fetchone()

    conn.close()

    return dict(request) if request else None


def list_client_requests(client_id, status=None, limit=50):
    """List all requests for a client."""
    conn = get_conn()

    if status:
        requests = conn.execute(
            "SELECT * FROM concierge_requests WHERE client_id = ? AND status = ? ORDER BY created_at DESC LIMIT ?",
            (client_id, status, limit)
        ).fetchall()
    else:
        requests = conn.execute(
            "SELECT * FROM concierge_requests WHERE client_id = ? ORDER BY created_at DESC LIMIT ?",
            (client_id, limit)
        ).fetchall()

    conn.close()

    return [dict(r) for r in requests]


def assign_advisor(request_id, advisor_id):
    """Assign an advisor to a request."""
    conn = get_conn()

    request = conn.execute("SELECT client_id FROM concierge_requests WHERE id = ?", (request_id,)).fetchone()
    if not request:
        conn.close()
        return False

    # Create or update advisor relationship
    existing_advisor = conn.execute(
        "SELECT id FROM personal_advisors WHERE client_id = ?",
        (request['client_id'],)
    ).fetchone()

    if not existing_advisor:
        # Get advisor info
        advisor_user = conn.execute(
            "SELECT name, email, phone FROM users WHERE id = ?",
            (advisor_id,)
        ).fetchone()

        if advisor_user:
            conn.execute(
                "INSERT INTO personal_advisors (client_id, advisor_id, advisor_name, advisor_email, advisor_phone, relationship_start, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (request['client_id'], advisor_id, advisor_user['name'], advisor_user['email'], advisor_user['phone'], now(), now(), now())
            )

    # Assign advisor to request
    conn.execute(
        "UPDATE concierge_requests SET assigned_advisor_id = ?, assignment_date = ?, status = 'assigned', updated_at = ? WHERE id = ?",
        (advisor_id, now(), now(), request_id)
    )

    conn.commit()
    conn.close()

    return True


def get_client_advisor(client_id):
    """Get the personal advisor for a client."""
    conn = get_conn()

    advisor = conn.execute(
        "SELECT * FROM personal_advisors WHERE client_id = ?",
        (client_id,)
    ).fetchone()

    conn.close()

    return dict(advisor) if advisor else None


def set_client_preferences(client_id, preferences_dict):
    """Set or update client preferences."""
    conn = get_conn()

    # Check if preferences exist
    existing = conn.execute(
        "SELECT id FROM client_preferences WHERE client_id = ?",
        (client_id,)
    ).fetchone()

    if existing:
        # Build update query dynamically
        updates = []
        params = []
        for key, value in preferences_dict.items():
            if key in ['preferred_cities', 'preferred_localities', 'property_types', 'desired_amenities']:
                value = json.dumps(value) if isinstance(value, (list, dict)) else value
            updates.append(f"{key} = ?")
            params.append(value)

        updates.append("updated_at = ?")
        params.append(now())
        params.append(client_id)

        conn.execute(
            f"UPDATE client_preferences SET {', '.join(updates)} WHERE client_id = ?",
            params
        )
    else:
        # Build insert with all provided preferences
        columns = ['client_id', 'created_at', 'updated_at']
        values = [client_id, now(), now()]

        for key, value in preferences_dict.items():
            if key in ['preferred_cities', 'preferred_localities', 'property_types', 'desired_amenities']:
                value = json.dumps(value) if isinstance(value, (list, dict)) else value
            columns.append(key)
            values.append(value)

        placeholders = ', '.join(['?'] * len(values))
        conn.execute(
            f"INSERT INTO client_preferences ({', '.join(columns)}) VALUES ({placeholders})",
            values
        )

    conn.commit()
    conn.close()

    return True


def get_client_preferences(client_id):
    """Get client preferences."""
    conn = get_conn()

    prefs = conn.execute(
        "SELECT * FROM client_preferences WHERE client_id = ?",
        (client_id,)
    ).fetchone()

    conn.close()

    return dict(prefs) if prefs else None


def generate_recommendations(client_id, num_recommendations=5):
    """Generate personalized recommendations for a client."""
    conn = get_conn()

    # Get client preferences
    prefs = conn.execute(
        "SELECT * FROM client_preferences WHERE client_id = ?",
        (client_id,)
    ).fetchone()

    if not prefs:
        conn.close()
        return []

    prefs_dict = dict(prefs)

    # Parse preferences
    try:
        preferred_cities = json.loads(prefs_dict.get('preferred_cities', '[]') or '[]')
    except:
        preferred_cities = []

    try:
        property_types = json.loads(prefs_dict.get('property_types', '[]') or '[]')
    except:
        property_types = []

    # Get matching properties
    query = "SELECT * FROM properties WHERE status = 'available'"
    params = []

    if preferred_cities:
        placeholders = ','.join(['?' for _ in preferred_cities])
        query += f" AND city IN ({placeholders})"
        params.extend(preferred_cities)

    if property_types:
        placeholders = ','.join(['?' for _ in property_types])
        query += f" AND ptype IN ({placeholders})"
        params.extend(property_types)

    query += f" LIMIT {num_recommendations}"

    properties = conn.execute(query, params).fetchall()

    # Create recommendations
    recommendations = []
    for prop in properties:
        prop_dict = dict(prop)

        # Calculate confidence score
        confidence = 70  # Base score
        if prop_dict['price'] >= prefs_dict.get('min_price', 0) and prop_dict['price'] <= prefs_dict.get('max_price', 999999999):
            confidence += 15

        if prop_dict['bedrooms'] >= prefs_dict.get('min_bedrooms', 0):
            confidence += 10

        confidence = min(100, confidence)

        cursor = conn.execute(
            "INSERT INTO advisory_recommendations "
            "(client_id, recommendation_type, title, description, related_property_id, confidence_score, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (client_id, 'property_suggestion', f"Property Recommendation: {prop_dict['title']}",
             f"This {prop_dict['ptype']} matches your preferences", prop_dict['id'], confidence, now(), now())
        )

        recommendations.append({
            'recommendation_id': cursor.lastrowid,
            'property_id': prop_dict['id'],
            'title': prop_dict['title'],
            'type': 'property_suggestion',
            'confidence': confidence,
        })

    conn.commit()
    conn.close()

    return recommendations


def get_client_recommendations(client_id, limit=10, status='active'):
    """Get recommendations for a client."""
    conn = get_conn()

    recs = conn.execute(
        "SELECT * FROM advisory_recommendations WHERE client_id = ? AND status = ? ORDER BY confidence_score DESC, created_at DESC LIMIT ?",
        (client_id, status, limit)
    ).fetchall()

    conn.close()

    return [dict(r) for r in recs]


def log_communication(request_id, sender_id, message_type, content, channel='email', subject=''):
    """Log a communication in concierge system."""
    conn = get_conn()

    conn.execute(
        "INSERT INTO concierge_communications "
        "(request_id, sender_id, message_type, subject, content, channel, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (request_id, sender_id, message_type, subject, content, channel, now(), now())
    )

    conn.commit()
    conn.close()

    return True


def get_request_communications(request_id):
    """Get all communications for a request."""
    conn = get_conn()

    comms = conn.execute(
        "SELECT * FROM concierge_communications WHERE request_id = ? ORDER BY created_at DESC",
        (request_id,)
    ).fetchall()

    conn.close()

    return [dict(c) for c in comms]


def update_request_status(request_id, new_status):
    """Update request status (pending → assigned → in_progress → completed)."""
    valid_statuses = ['pending', 'assigned', 'in_progress', 'completed', 'cancelled']

    if new_status not in valid_statuses:
        return False

    conn = get_conn()

    completion_date = now() if new_status == 'completed' else None

    conn.execute(
        "UPDATE concierge_requests SET status = ?, completion_date = ?, updated_at = ? WHERE id = ?",
        (new_status, completion_date, now(), request_id)
    )

    conn.commit()
    conn.close()

    return True


def record_activity(client_id, activity_type, activity_description='', advisor_id=None, related_property_id=None):
    """Record client activity in concierge system."""
    conn = get_conn()

    conn.execute(
        "INSERT INTO concierge_activity_log "
        "(client_id, advisor_id, activity_type, activity_description, related_property_id, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (client_id, advisor_id, activity_type, activity_description, related_property_id, now())
    )

    conn.commit()
    conn.close()

    return True


def get_client_activity_history(client_id, limit=50):
    """Get activity history for a client."""
    conn = get_conn()

    activities = conn.execute(
        "SELECT * FROM concierge_activity_log WHERE client_id = ? ORDER BY created_at DESC LIMIT ?",
        (client_id, limit)
    ).fetchall()

    conn.close()

    return [dict(a) for a in activities]


def calculate_advisor_metrics(advisor_id):
    """Calculate performance metrics for an advisor."""
    conn = get_conn()

    # Get assigned requests
    requests = conn.execute(
        "SELECT * FROM concierge_requests WHERE assigned_advisor_id = ?",
        (advisor_id,)
    ).fetchall()

    # Get ratings
    ratings = conn.execute(
        "SELECT AVG(satisfaction_rating) as avg_rating FROM concierge_requests WHERE assigned_advisor_id = ? AND satisfaction_rating > 0",
        (advisor_id,)
    ).fetchone()

    # Count various metrics
    total_requests = len(requests)
    completed = sum(1 for r in requests if dict(r)['status'] == 'completed')
    on_time = sum(1 for r in requests if dict(r)['completion_date'] and dict(r)['created_at'] < dict(r)['completion_date'])

    completion_rate = (completed / total_requests * 100) if total_requests > 0 else 0
    on_time_rate = (on_time / completed * 100) if completed > 0 else 0
    avg_satisfaction = ratings['avg_rating'] if ratings['avg_rating'] else 0.0

    # Determine tier
    if avg_satisfaction >= 4.8:
        tier = 'elite'
    elif avg_satisfaction >= 4.5:
        tier = 'senior'
    elif avg_satisfaction >= 4.0:
        tier = 'standard'
    else:
        tier = 'emerging'

    # Save metrics
    period_start = now()[:10]
    existing = conn.execute(
        "SELECT id FROM advisor_performance WHERE advisor_id = ? AND period_start = ?",
        (advisor_id, period_start)
    ).fetchone()

    if existing:
        conn.execute(
            "UPDATE advisor_performance SET "
            "total_requests_handled=?, average_satisfaction=?, on_time_completion_rate=?, "
            "performance_tier=?, updated_at=? WHERE advisor_id=? AND period_start=?",
            (total_requests, avg_satisfaction, on_time_rate, tier, now(), advisor_id, period_start)
        )
    else:
        conn.execute(
            "INSERT INTO advisor_performance "
            "(advisor_id, total_requests_handled, average_satisfaction, on_time_completion_rate, "
            "performance_tier, period_start, period_end, calculated_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (advisor_id, total_requests, avg_satisfaction, on_time_rate, tier, period_start, period_start, now(), now())
        )

    conn.commit()
    conn.close()

    return {
        'total_requests': total_requests,
        'completed_requests': completed,
        'completion_rate': completion_rate,
        'on_time_rate': on_time_rate,
        'average_satisfaction': avg_satisfaction,
        'performance_tier': tier,
    }


def get_client_summary(client_id):
    """Get comprehensive client summary for concierge."""
    conn = get_conn()

    # Basic client info
    client = conn.execute("SELECT * FROM users WHERE id = ?", (client_id,)).fetchone()
    if not client:
        conn.close()
        return None

    client_dict = dict(client)

    # Get advisor
    advisor = conn.execute(
        "SELECT * FROM personal_advisors WHERE client_id = ?",
        (client_id,)
    ).fetchone()

    # Get preferences
    prefs = conn.execute(
        "SELECT * FROM client_preferences WHERE client_id = ?",
        (client_id,)
    ).fetchone()

    # Get requests
    requests = conn.execute(
        "SELECT * FROM concierge_requests WHERE client_id = ? ORDER BY created_at DESC LIMIT 5",
        (client_id,)
    ).fetchall()

    # Get recommendations
    recs = conn.execute(
        "SELECT * FROM advisory_recommendations WHERE client_id = ? AND status = 'active' ORDER BY confidence_score DESC LIMIT 5",
        (client_id,)
    ).fetchall()

    # Get activity
    activity = conn.execute(
        "SELECT * FROM concierge_activity_log WHERE client_id = ? ORDER BY created_at DESC LIMIT 10",
        (client_id,)
    ).fetchall()

    conn.close()

    client_dict['advisor'] = dict(advisor) if advisor else None
    client_dict['preferences'] = dict(prefs) if prefs else None
    client_dict['requests'] = [dict(r) for r in requests]
    client_dict['recommendations'] = [dict(r) for r in recs]
    client_dict['activity_history'] = [dict(a) for a in activity]

    return client_dict


def get_concierge_dashboard_stats():
    """Get statistics for concierge foundation dashboard."""
    conn = get_conn()

    total_clients = conn.execute("SELECT COUNT(DISTINCT client_id) as count FROM concierge_requests").fetchone()
    active_requests = conn.execute("SELECT COUNT(*) as count FROM concierge_requests WHERE status IN ('pending', 'assigned', 'in_progress')").fetchone()
    completed_requests = conn.execute("SELECT COUNT(*) as count FROM concierge_requests WHERE status = 'completed'").fetchone()

    # Average satisfaction
    avg_satisfaction = conn.execute("SELECT AVG(satisfaction_rating) as avg FROM concierge_requests WHERE satisfaction_rating > 0").fetchone()

    # Top advisors
    top_advisors = conn.execute(
        "SELECT assigned_advisor_id as advisor_id, COUNT(*) as request_count FROM concierge_requests WHERE assigned_advisor_id IS NOT NULL GROUP BY assigned_advisor_id ORDER BY request_count DESC LIMIT 5"
    ).fetchall()

    # Request types breakdown
    by_type = conn.execute(
        "SELECT request_type, COUNT(*) as count FROM concierge_requests GROUP BY request_type ORDER BY count DESC"
    ).fetchall()

    conn.close()

    return {
        'total_clients': total_clients['count'] if total_clients else 0,
        'active_requests': active_requests['count'] if active_requests else 0,
        'completed_requests': completed_requests['count'] if completed_requests else 0,
        'average_satisfaction': avg_satisfaction['avg'] or 0,
        'top_advisors': [dict(a) for a in top_advisors],
        'requests_by_type': [dict(r) for r in by_type],
    }
