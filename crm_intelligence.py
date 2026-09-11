"""CRM Intelligence — Customer relationship management & lead scoring.

Week 9 System 9: Lead scoring, engagement tracking, and advisor recommendations.
"""

import json
from database import get_conn, now


def calculate_lead_score(lead_id):
    """Calculate comprehensive lead score (0-100)."""
    conn = get_conn()

    lead = conn.execute("SELECT * FROM crm_leads WHERE id = ?", (lead_id,)).fetchone()
    if not lead:
        conn.close()
        return None

    lead_dict = dict(lead)

    # BUDGET ALIGNMENT (25%) - Based on property interest vs opportunity scores
    budget_score = 60
    if lead_dict.get('interested_properties'):
        try:
            props = json.loads(lead_dict['interested_properties'])
            if props:
                # Get opportunity scores for interested properties
                prop_ids = ','.join(['?' for _ in props])
                opp_scores = conn.execute(
                    f"SELECT AVG(opportunity_score) as avg FROM opportunity_scores WHERE property_id IN ({prop_ids})",
                    props
                ).fetchone()
                if opp_scores and opp_scores['avg']:
                    budget_score = int(opp_scores['avg'])
        except:
            pass

    # ENGAGEMENT SCORE (25%) - Based on interaction frequency
    engagement_score = 50
    interactions = conn.execute(
        "SELECT COUNT(*) as count FROM crm_interactions WHERE lead_id = ?",
        (lead_id,)
    ).fetchone()

    if interactions:
        count = interactions['count']
        if count >= 5:
            engagement_score = 85
        elif count >= 3:
            engagement_score = 70
        elif count >= 1:
            engagement_score = 50

    # DECISION READINESS (20%) - Based on lead status
    decision_score = 40
    status = lead_dict.get('lead_status', 'new')
    status_map = {
        'closed': 100,
        'negotiating': 90,
        'interested': 70,
        'qualified': 60,
        'contacted': 40,
        'new': 20,
    }
    decision_score = status_map.get(status, 40)

    # MATCH QUALITY (20%) - Based on opportunity scores
    match_score = 60
    if lead_dict.get('interested_properties'):
        try:
            props = json.loads(lead_dict['interested_properties'])
            if props:
                prop_ids = ','.join(['?' for _ in props])
                scores = conn.execute(
                    f"SELECT AVG(opportunity_score) as avg FROM opportunity_scores WHERE property_id IN ({prop_ids})",
                    props
                ).fetchone()
                if scores and scores['avg']:
                    match_score = int(scores['avg'])
        except:
            pass

    # OPPORTUNITY SCORE (10%) - Based on concierge/recommendation quality
    opp_score = 50

    # OVERALL LEAD SCORE
    overall = int(
        budget_score * 0.25 +
        engagement_score * 0.25 +
        decision_score * 0.20 +
        match_score * 0.20 +
        opp_score * 0.10
    )

    # LEAD QUALITY TIER
    if overall >= 80:
        quality_tier = 'hot'
    elif overall >= 60:
        quality_tier = 'warm'
    else:
        quality_tier = 'cold'

    # SAVE
    existing = conn.execute("SELECT id FROM lead_scores WHERE lead_id = ?", (lead_id,)).fetchone()

    if existing:
        conn.execute(
            "UPDATE lead_scores SET total_lead_score=?, lead_quality_tier=?, "
            "budget_alignment_score=?, engagement_score=?, decision_readiness=?, "
            "match_quality_score=?, calculated_at=? WHERE lead_id=?",
            (overall, quality_tier, budget_score, engagement_score, decision_score, match_score, now(), lead_id)
        )
    else:
        conn.execute(
            "INSERT INTO lead_scores (lead_id, total_lead_score, lead_quality_tier, "
            "budget_alignment_score, engagement_score, decision_readiness, match_quality_score, calculated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (lead_id, overall, quality_tier, budget_score, engagement_score, decision_score, match_score, now())
        )

    # Update lead score
    conn.execute("UPDATE crm_leads SET lead_score = ?, lead_quality = ?, updated_at = ? WHERE id = ?",
                (overall, quality_tier, now(), lead_id))

    conn.commit()
    conn.close()

    return {'lead_id': lead_id, 'score': overall, 'tier': quality_tier}


def get_hot_leads(limit=20):
    """Get hot leads (score >= 80) for immediate action."""
    conn = get_conn()

    leads = conn.execute(
        "SELECT * FROM crm_leads WHERE lead_score >= 80 ORDER BY lead_score DESC LIMIT ?",
        (limit,)
    ).fetchall()

    conn.close()

    return [dict(l) for l in leads]


def track_interaction(lead_id, interaction_type, subject='', notes='', contacted_by=None):
    """Track lead interaction."""
    conn = get_conn()

    conn.execute(
        "INSERT INTO crm_interactions (lead_id, interaction_type, subject, notes, contacted_by, interaction_date, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (lead_id, interaction_type, subject, notes, contacted_by, now(), now())
    )

    # Update lead contact info
    conn.execute("UPDATE crm_leads SET contact_count = contact_count + 1, last_contacted = ? WHERE id = ?",
                (now(), lead_id))

    conn.commit()
    conn.close()

    return True


def get_lead_history(lead_id, limit=20):
    """Get interaction history for a lead."""
    conn = get_conn()

    interactions = conn.execute(
        "SELECT * FROM crm_interactions WHERE lead_id = ? ORDER BY interaction_date DESC LIMIT ?",
        (lead_id, limit)
    ).fetchall()

    conn.close()

    return [dict(i) for i in interactions]


def get_crm_dashboard_stats():
    """Get CRM dashboard statistics."""
    conn = get_conn()

    total_leads = conn.execute("SELECT COUNT(*) as count FROM crm_leads").fetchone()
    hot_leads = conn.execute("SELECT COUNT(*) as count FROM crm_leads WHERE lead_score >= 80").fetchone()
    warm_leads = conn.execute("SELECT COUNT(*) as count FROM crm_leads WHERE lead_score >= 60 AND lead_score < 80").fetchone()
    closed = conn.execute("SELECT COUNT(*) as count FROM crm_leads WHERE lead_status = 'closed'").fetchone()

    # By source
    by_source = conn.execute(
        "SELECT lead_source, COUNT(*) as count FROM crm_leads GROUP BY lead_source ORDER BY count DESC"
    ).fetchall()

    conn.close()

    return {
        'total_leads': total_leads['count'] if total_leads else 0,
        'hot_leads': hot_leads['count'] if hot_leads else 0,
        'warm_leads': warm_leads['count'] if warm_leads else 0,
        'closed_deals': closed['count'] if closed else 0,
        'leads_by_source': [dict(s) for s in by_source],
    }
