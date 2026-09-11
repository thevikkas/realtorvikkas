"""Command Center — Executive dashboard aggregating all platform systems.

Week 10 System 10: Platform integration and executive analytics.
"""

from database import get_conn


def get_platform_dashboard():
    """Get comprehensive platform metrics across all systems."""
    conn = get_conn()

    # PROPERTIES & OPPORTUNITIES
    total_properties = conn.execute("SELECT COUNT(*) as cnt FROM properties").fetchone()
    high_opportunity = conn.execute("SELECT COUNT(*) as cnt FROM opportunity_scores WHERE opportunity_score >= 80").fetchone()

    # INVESTMENTS
    total_portfolios = conn.execute("SELECT COUNT(*) as cnt FROM investment_portfolios").fetchone()
    portfolio_value = conn.execute("SELECT COALESCE(SUM(current_value), 0) as total FROM investment_portfolios").fetchone()

    # DEALS
    active_deals = conn.execute("SELECT COUNT(*) as cnt FROM deals WHERE status IN ('prospecting', 'offer', 'negotiation')").fetchone()
    closed_deals = conn.execute("SELECT COUNT(*) as cnt FROM deals WHERE status = 'closed'").fetchone()
    deal_value = conn.execute("SELECT COALESCE(SUM(agreed_price), 0) as total FROM deals WHERE status = 'closed'").fetchone()

    # CRM
    total_leads = conn.execute("SELECT COUNT(*) as cnt FROM crm_leads").fetchone()
    hot_leads = conn.execute("SELECT COUNT(*) as cnt FROM crm_leads WHERE lead_score >= 80").fetchone()

    # CONCIERGE
    active_requests = conn.execute("SELECT COUNT(*) as cnt FROM concierge_requests WHERE status != 'completed'").fetchone()

    # MARKETS
    markets = conn.execute("SELECT COUNT(DISTINCT city) as cnt FROM location_data").fetchone()

    conn.close()

    return {
        'properties': {'total': total_properties['cnt'] or 0, 'high_opportunity': high_opportunity['cnt'] or 0},
        'portfolios': {'total': total_portfolios['cnt'] or 0, 'value': portfolio_value['total'] or 0},
        'deals': {
            'active': active_deals['cnt'] or 0,
            'closed': closed_deals['cnt'] or 0,
            'closed_value': deal_value['total'] or 0
        },
        'crm': {'total_leads': total_leads['cnt'] or 0, 'hot': hot_leads['cnt'] or 0},
        'concierge': {'active_requests': active_requests['cnt'] or 0},
        'markets': {'coverage': markets['cnt'] or 0},
    }


def get_executive_summary():
    """Get executive summary across all systems."""
    data = get_platform_dashboard()

    summary = {
        'platform_status': 'operational',
        'systems_active': 9,
        'total_properties': data['properties']['total'],
        'high_opportunity_count': data['properties']['high_opportunity'],
        'portfolio_value': data['portfolios']['value'],
        'active_deals': data['deals']['active'],
        'closed_deals_count': data['deals']['closed'],
        'revenue_from_closed': data['deals']['closed_value'],
        'lead_pipeline': data['crm']['total_leads'],
        'hot_leads': data['crm']['hot'],
        'markets_covered': data['markets']['coverage'],
        'key_metrics': {
            'opp_conversion_rate': (data['properties']['high_opportunity'] / max(data['properties']['total'], 1) * 100),
            'lead_hot_ratio': (data['crm']['hot'] / max(data['crm']['total_leads'], 1) * 100),
            'deal_success_rate': (data['deals']['closed'] / max(data['deals']['active'] + data['deals']['closed'], 1) * 100),
        }
    }

    return summary
