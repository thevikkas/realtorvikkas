"""Deal Room Engine — High-value deal management and collaboration.

Week 5 System 5: Centralized deal management for premium transactions with
team collaboration, document tracking, and deal metrics.

Zero external dependencies — uses only Python standard library.
"""

import json
from database import get_conn, now


def create_deal(property_id, title, deal_type='purchase', buyer_id=None, seller_id=None, agent_id=None):
    """Create a new deal.

    Returns deal_id on success, None on error.
    """
    conn = get_conn()

    cursor = conn.execute(
        "INSERT INTO deals (property_id, title, deal_type, buyer_id, seller_id, agent_id, "
        "status, offer_date, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (property_id, title, deal_type, buyer_id, seller_id, agent_id, 'prospecting', now(), now(), now())
    )

    deal_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return deal_id


def get_deal(deal_id):
    """Get deal details by ID."""
    conn = get_conn()

    deal = conn.execute(
        "SELECT * FROM deals WHERE id = ?",
        (deal_id,)
    ).fetchone()

    conn.close()

    return dict(deal) if deal else None


def update_deal_status(deal_id, new_status):
    """Update deal status.

    Valid statuses: prospecting, offer, negotiation, closing, closed, cancelled
    """
    valid_statuses = ['prospecting', 'offer', 'negotiation', 'closing', 'closed', 'cancelled']

    if new_status not in valid_statuses:
        return False

    conn = get_conn()

    deal = conn.execute("SELECT status FROM deals WHERE id = ?", (deal_id,)).fetchone()
    if not deal:
        conn.close()
        return False

    # Progress tracking
    stage_completion = {
        'prospecting': 10,
        'offer': 30,
        'negotiation': 60,
        'closing': 90,
        'closed': 100,
        'cancelled': 0
    }

    closed_at = now() if new_status == 'closed' else None

    conn.execute(
        "UPDATE deals SET status = ?, deal_stage_completion = ?, updated_at = ?, closed_at = ? WHERE id = ?",
        (new_status, stage_completion.get(new_status, 0), now(), closed_at, deal_id)
    )

    conn.commit()
    conn.close()

    return True


def list_deals(status=None, deal_type=None, limit=50):
    """List all deals, optionally filtered by status or type."""
    conn = get_conn()

    query = "SELECT * FROM deals WHERE 1=1"
    params = []

    if status:
        query += " AND status = ?"
        params.append(status)

    if deal_type:
        query += " AND deal_type = ?"
        params.append(deal_type)

    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    deals = conn.execute(query, params).fetchall()
    conn.close()

    return [dict(d) for d in deals]


def add_stakeholder(deal_id, user_id, role, name, email='', phone='', organization='', is_primary=False):
    """Add a stakeholder to a deal."""
    conn = get_conn()

    conn.execute(
        "INSERT INTO deal_stakeholders "
        "(deal_id, user_id, role, name, email, phone, organization, is_primary, added_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (deal_id, user_id, role, name, email, phone, organization, is_primary, now())
    )

    conn.commit()
    conn.close()

    return True


def get_deal_stakeholders(deal_id):
    """Get all stakeholders for a deal."""
    conn = get_conn()

    stakeholders = conn.execute(
        "SELECT * FROM deal_stakeholders WHERE deal_id = ? ORDER BY is_primary DESC, role",
        (deal_id,)
    ).fetchall()

    conn.close()

    return [dict(s) for s in stakeholders]


def upload_document(deal_id, doc_type, title, file_path, file_size, mime_type='application/pdf'):
    """Upload a document for a deal."""
    conn = get_conn()

    # Check if version exists (for document updates)
    latest = conn.execute(
        "SELECT MAX(version) as max_version FROM deal_documents WHERE deal_id = ? AND document_type = ? AND is_latest = 1",
        (deal_id, doc_type)
    ).fetchone()

    # Mark old versions as not latest
    if latest and latest['max_version']:
        conn.execute(
            "UPDATE deal_documents SET is_latest = 0 WHERE deal_id = ? AND document_type = ?",
            (deal_id, doc_type)
        )

    new_version = (latest['max_version'] or 0) + 1

    conn.execute(
        "INSERT INTO deal_documents "
        "(deal_id, document_type, title, file_path, file_size, mime_type, version, is_latest, status, uploaded_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (deal_id, doc_type, title, file_path, file_size, mime_type, new_version, 1, 'pending', now())
    )

    conn.commit()
    conn.close()

    return True


def get_deal_documents(deal_id, doc_type=None):
    """Get documents for a deal."""
    conn = get_conn()

    if doc_type:
        docs = conn.execute(
            "SELECT * FROM deal_documents WHERE deal_id = ? AND document_type = ? ORDER BY uploaded_at DESC",
            (deal_id, doc_type)
        ).fetchall()
    else:
        docs = conn.execute(
            "SELECT * FROM deal_documents WHERE deal_id = ? ORDER BY document_type, uploaded_at DESC",
            (deal_id,)
        ).fetchall()

    conn.close()

    return [dict(d) for d in docs]


def add_timeline_event(deal_id, event_type, title, description='', created_by=None, assigned_to=None, scheduled_date=None):
    """Add an event to deal timeline."""
    conn = get_conn()

    conn.execute(
        "INSERT INTO deal_timeline "
        "(deal_id, event_type, title, description, created_by, assigned_to, scheduled_date, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (deal_id, event_type, title, description, created_by, assigned_to, scheduled_date, now(), now())
    )

    conn.commit()
    conn.close()

    return True


def get_deal_timeline(deal_id):
    """Get timeline events for a deal."""
    conn = get_conn()

    events = conn.execute(
        "SELECT * FROM deal_timeline WHERE deal_id = ? ORDER BY scheduled_date ASC, created_at DESC",
        (deal_id,)
    ).fetchall()

    conn.close()

    return [dict(e) for e in events]


def mark_event_completed(event_id):
    """Mark a timeline event as completed."""
    conn = get_conn()

    conn.execute(
        "UPDATE deal_timeline SET completed = 1, status = 'completed', updated_at = ? WHERE id = ?",
        (now(), event_id)
    )

    conn.commit()
    conn.close()

    return True


def add_communication(deal_id, sender_id, message_type, content, subject='', visibility='team', related_event_id=None, related_document_id=None):
    """Add a communication/note to a deal."""
    conn = get_conn()

    conn.execute(
        "INSERT INTO deal_communications "
        "(deal_id, sender_id, message_type, subject, content, visibility, related_event_id, related_document_id, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (deal_id, sender_id, message_type, subject, content, visibility, related_event_id, related_document_id, now(), now())
    )

    conn.commit()
    conn.close()

    return True


def get_deal_communications(deal_id, limit=50):
    """Get communications for a deal."""
    conn = get_conn()

    comms = conn.execute(
        "SELECT * FROM deal_communications WHERE deal_id = ? ORDER BY created_at DESC LIMIT ?",
        (deal_id, limit)
    ).fetchall()

    conn.close()

    return [dict(c) for c in comms]


def calculate_deal_metrics(deal_id, purchase_price, down_payment, holding_period_months=12, monthly_rental_income=0, monthly_costs=0, property_appreciation_annual=0.05):
    """Calculate financial metrics for a deal."""
    if purchase_price <= 0:
        return None

    total_investment = purchase_price + (purchase_price * 0.04)  # Add 4% closing costs estimate
    actual_down_payment = down_payment if down_payment > 0 else purchase_price * 0.20

    # Monthly income/expenses
    annual_rental_income = monthly_rental_income * 12
    annual_costs = monthly_costs * 12

    # Cash on cash return
    annual_cash_flow = annual_rental_income - annual_costs
    cash_on_cash = (annual_cash_flow / actual_down_payment * 100) if actual_down_payment > 0 else 0

    # Expected ROI (simplified - doesn't account for principal paydown)
    appreciation_gain = purchase_price * property_appreciation_annual
    total_annual_gain = appreciation_gain + annual_cash_flow
    expected_roi = (total_annual_gain / total_investment * 100) if total_investment > 0 else 0

    # Break-even: How many months of cash flow to recover down payment
    monthly_cash_flow = annual_cash_flow / 12
    break_even_months = int(actual_down_payment / monthly_cash_flow) if monthly_cash_flow > 0 else 0

    # Equity buildup estimates
    equity_1yr = int(purchase_price * property_appreciation_annual) + (annual_cash_flow * 0.2)  # Principal + appreciation
    equity_5yr = int(purchase_price * property_appreciation_annual * 5) + (annual_cash_flow * 2)

    # Cap rate (annual NOI / purchase price)
    cap_rate = (annual_rental_income - annual_costs) / purchase_price * 100 if purchase_price > 0 else 0

    # Rental yield (annual income / purchase price)
    rental_yield = annual_rental_income / purchase_price * 100 if purchase_price > 0 else 0

    # Check if metrics already exist
    conn = get_conn()

    existing = conn.execute("SELECT id FROM deal_metrics WHERE deal_id = ?", (deal_id,)).fetchone()

    if existing:
        conn.execute(
            "UPDATE deal_metrics SET "
            "purchase_price=?, total_investment=?, expected_monthly_income=?, expected_monthly_costs=?, "
            "cash_on_cash_return=?, expected_roi_annual=?, break_even_months=?, "
            "equity_buildup_1yr=?, equity_buildup_5yr=?, rental_yield=?, cap_rate=?, updated_at=? "
            "WHERE deal_id=?",
            (purchase_price, total_investment, monthly_rental_income, monthly_costs,
             cash_on_cash, expected_roi, break_even_months, equity_1yr, equity_5yr,
             rental_yield, cap_rate, now(), deal_id)
        )
    else:
        conn.execute(
            "INSERT INTO deal_metrics "
            "(deal_id, purchase_price, total_investment, expected_monthly_income, expected_monthly_costs, "
            "cash_on_cash_return, expected_roi_annual, break_even_months, equity_buildup_1yr, equity_buildup_5yr, "
            "rental_yield, cap_rate, calculated_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (deal_id, purchase_price, total_investment, monthly_rental_income, monthly_costs,
             cash_on_cash, expected_roi, break_even_months, equity_1yr, equity_5yr,
             rental_yield, cap_rate, now(), now())
        )

    conn.commit()
    conn.close()

    return {
        'purchase_price': purchase_price,
        'total_investment': total_investment,
        'down_payment': actual_down_payment,
        'cash_on_cash_return': cash_on_cash,
        'expected_roi_annual': expected_roi,
        'break_even_months': break_even_months,
        'equity_buildup_1yr': equity_1yr,
        'equity_buildup_5yr': equity_5yr,
        'rental_yield': rental_yield,
        'cap_rate': cap_rate,
        'monthly_cash_flow': monthly_cash_flow,
    }


def get_deal_metrics(deal_id):
    """Get calculated metrics for a deal."""
    conn = get_conn()

    metrics = conn.execute(
        "SELECT * FROM deal_metrics WHERE deal_id = ?",
        (deal_id,)
    ).fetchone()

    conn.close()

    return dict(metrics) if metrics else None


def get_deal_summary(deal_id):
    """Get comprehensive deal summary with all related data."""
    conn = get_conn()

    deal = conn.execute("SELECT * FROM deals WHERE id = ?", (deal_id,)).fetchone()
    if not deal:
        conn.close()
        return None

    deal_dict = dict(deal)

    # Get property details if linked
    if deal_dict['property_id']:
        prop = conn.execute(
            "SELECT title, city, locality, ptype, price FROM properties WHERE id = ?",
            (deal_dict['property_id'],)
        ).fetchone()
        deal_dict['property'] = dict(prop) if prop else None

    # Get stakeholders
    stakeholders = conn.execute(
        "SELECT * FROM deal_stakeholders WHERE deal_id = ? ORDER BY is_primary DESC",
        (deal_id,)
    ).fetchall()
    deal_dict['stakeholders'] = [dict(s) for s in stakeholders]

    # Get latest documents by type
    docs = conn.execute(
        "SELECT * FROM deal_documents WHERE deal_id = ? AND is_latest = 1 ORDER BY document_type",
        (deal_id,)
    ).fetchall()
    deal_dict['documents'] = [dict(d) for d in docs]

    # Get timeline events
    events = conn.execute(
        "SELECT * FROM deal_timeline WHERE deal_id = ? ORDER BY scheduled_date ASC",
        (deal_id,)
    ).fetchall()
    deal_dict['timeline'] = [dict(e) for e in events]

    # Get recent communications
    comms = conn.execute(
        "SELECT * FROM deal_communications WHERE deal_id = ? ORDER BY created_at DESC LIMIT 10",
        (deal_id,)
    ).fetchall()
    deal_dict['communications'] = [dict(c) for c in comms]

    # Get metrics
    metrics = conn.execute(
        "SELECT * FROM deal_metrics WHERE deal_id = ?",
        (deal_id,)
    ).fetchone()
    deal_dict['metrics'] = dict(metrics) if metrics else None

    conn.close()

    return deal_dict


def get_deal_dashboard_stats():
    """Get statistics for deal room dashboard."""
    conn = get_conn()

    total_deals = conn.execute("SELECT COUNT(*) as count FROM deals").fetchone()
    active_deals = conn.execute("SELECT COUNT(*) as count FROM deals WHERE status IN ('prospecting', 'offer', 'negotiation', 'closing')").fetchone()
    closed_deals = conn.execute("SELECT COUNT(*) as count FROM deals WHERE status = 'closed'").fetchone()

    # Total value of closed deals
    closed_value = conn.execute("SELECT COALESCE(SUM(agreed_price), 0) as total FROM deals WHERE status = 'closed'").fetchone()

    # Deals by status
    by_status = conn.execute(
        "SELECT status, COUNT(*) as count FROM deals GROUP BY status ORDER BY count DESC"
    ).fetchall()

    # Average holding period
    avg_holding = conn.execute(
        "SELECT AVG(holding_period_months) as avg_months FROM deals WHERE holding_period_months > 0"
    ).fetchone()

    conn.close()

    return {
        'total_deals': total_deals['count'] if total_deals else 0,
        'active_deals': active_deals['count'] if active_deals else 0,
        'closed_deals': closed_deals['count'] if closed_deals else 0,
        'total_value_closed': closed_value['total'] if closed_value else 0,
        'deals_by_status': [dict(s) for s in by_status],
        'average_holding_months': int(avg_holding['avg_months'] or 0),
    }


def generate_deal_report(deal_id):
    """Generate a comprehensive report for a deal."""
    summary = get_deal_summary(deal_id)
    if not summary:
        return None

    metrics = get_deal_metrics(deal_id)

    return {
        'deal': summary,
        'metrics': metrics,
        'document_count': len(summary.get('documents', [])),
        'stakeholder_count': len(summary.get('stakeholders', [])),
        'timeline_events': len(summary.get('timeline', [])),
        'communication_count': len(summary.get('communications', [])),
        'completion_percentage': summary.get('deal_stage_completion', 0),
    }
