"""Mega Investment Desk — Portfolio management and investment strategy.

Week 6 System 6: Advanced portfolio analytics, scenario modeling, and
investment strategy optimization with risk analysis.

Zero external dependencies — uses only Python standard library.
"""

import json
from database import get_conn, now


def create_portfolio(name, portfolio_type='mixed', owner_id=None, investment_strategy='balanced', risk_profile='moderate'):
    """Create a new investment portfolio."""
    conn = get_conn()

    cursor = conn.execute(
        "INSERT INTO investment_portfolios "
        "(name, portfolio_type, owner_id, investment_strategy, risk_profile, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (name, portfolio_type, owner_id, investment_strategy, risk_profile, now(), now())
    )

    portfolio_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return portfolio_id


def get_portfolio(portfolio_id):
    """Get portfolio details by ID."""
    conn = get_conn()

    portfolio = conn.execute(
        "SELECT * FROM investment_portfolios WHERE id = ?",
        (portfolio_id,)
    ).fetchone()

    conn.close()

    return dict(portfolio) if portfolio else None


def list_portfolios(owner_id=None, limit=50):
    """List all portfolios, optionally filtered by owner."""
    conn = get_conn()

    if owner_id:
        portfolios = conn.execute(
            "SELECT * FROM investment_portfolios WHERE owner_id = ? ORDER BY created_at DESC LIMIT ?",
            (owner_id, limit)
        ).fetchall()
    else:
        portfolios = conn.execute(
            "SELECT * FROM investment_portfolios ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()

    conn.close()

    return [dict(p) for p in portfolios]


def add_property_to_portfolio(portfolio_id, property_id, acquisition_price=0, allocation_percentage=0, acquisition_date=None):
    """Add a property to an investment portfolio."""
    conn = get_conn()

    cursor = conn.execute(
        "INSERT INTO portfolio_properties "
        "(portfolio_id, property_id, acquisition_price, allocation_percentage, acquisition_date, added_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (portfolio_id, property_id, acquisition_price, allocation_percentage, acquisition_date, now(), now())
    )

    property_port_id = cursor.lastrowid

    # Update portfolio property count
    count = conn.execute(
        "SELECT COUNT(*) as cnt FROM portfolio_properties WHERE portfolio_id = ? AND status = 'active'",
        (portfolio_id,)
    ).fetchone()

    conn.execute(
        "UPDATE investment_portfolios SET num_properties = ?, updated_at = ? WHERE id = ?",
        (count['cnt'], now(), portfolio_id)
    )

    conn.commit()
    conn.close()

    return property_port_id


def get_portfolio_properties(portfolio_id):
    """Get all properties in a portfolio."""
    conn = get_conn()

    properties = conn.execute(
        "SELECT pp.*, p.title, p.city, p.locality, p.ptype "
        "FROM portfolio_properties pp "
        "JOIN properties p ON pp.property_id = p.id "
        "WHERE pp.portfolio_id = ? AND pp.status = 'active' "
        "ORDER BY pp.added_at",
        (portfolio_id,)
    ).fetchall()

    conn.close()

    return [dict(p) for p in properties]


def calculate_portfolio_performance(portfolio_id):
    """Calculate comprehensive portfolio performance metrics."""
    conn = get_conn()

    portfolio = conn.execute(
        "SELECT * FROM investment_portfolios WHERE id = ?",
        (portfolio_id,)
    ).fetchone()

    if not portfolio:
        conn.close()
        return None

    # Get all active properties in portfolio
    properties = conn.execute(
        "SELECT * FROM portfolio_properties WHERE portfolio_id = ? AND status = 'active'",
        (portfolio_id,)
    ).fetchall()

    total_value = 0
    total_rental_income = 0
    total_operating_costs = 0
    total_investment = 0

    for prop in properties:
        prop_dict = dict(prop)
        total_value += prop_dict.get('current_value', 0)
        total_rental_income += prop_dict.get('rental_income_annual', 0)
        total_operating_costs += prop_dict.get('operating_costs_annual', 0)
        total_investment += prop_dict.get('acquisition_price', 0)

    net_cash_flow = total_rental_income - total_operating_costs

    # Calculate returns
    total_gain = total_value - total_investment if total_investment > 0 else 0
    total_return_pct = (total_gain / total_investment * 100) if total_investment > 0 else 0
    annualized_return = total_return_pct / 3  # Simplified: assume 3 year holding
    cash_on_cash = (net_cash_flow / total_investment * 100) if total_investment > 0 else 0

    # Save performance
    existing = conn.execute(
        "SELECT id FROM portfolio_performance WHERE portfolio_id = ? AND period_start = DATE('now')",
        (portfolio_id,)
    ).fetchone()

    period_start = now()[:10]  # Today's date

    if existing:
        conn.execute(
            "UPDATE portfolio_performance SET "
            "total_properties_value=?, total_rental_income=?, total_operating_costs=?, "
            "net_cash_flow=?, total_return_amount=?, total_return_percentage=?, "
            "annualized_return=?, cash_on_cash_return=?, calculated_at=? "
            "WHERE portfolio_id=? AND period_start=?",
            (total_value, total_rental_income, total_operating_costs, net_cash_flow,
             total_gain, total_return_pct, annualized_return, cash_on_cash, now(), portfolio_id, period_start)
        )
    else:
        conn.execute(
            "INSERT INTO portfolio_performance "
            "(portfolio_id, total_properties_value, total_rental_income, total_operating_costs, "
            "net_cash_flow, total_return_amount, total_return_percentage, annualized_return, "
            "cash_on_cash_return, period_start, period_end, calculated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (portfolio_id, total_value, total_rental_income, total_operating_costs, net_cash_flow,
             total_gain, total_return_pct, annualized_return, cash_on_cash, period_start, period_start, now())
        )

    # Update portfolio summary
    conn.execute(
        "UPDATE investment_portfolios SET "
        "total_investment=?, current_value=?, total_return=?, annual_return=? "
        "WHERE id=?",
        (total_investment, total_value, total_return_pct, annualized_return, portfolio_id)
    )

    conn.commit()
    conn.close()

    return {
        'total_investment': total_investment,
        'current_value': total_value,
        'total_gain': total_gain,
        'total_return_pct': total_return_pct,
        'annualized_return': annualized_return,
        'total_rental_income': total_rental_income,
        'total_operating_costs': total_operating_costs,
        'net_cash_flow': net_cash_flow,
        'cash_on_cash_return': cash_on_cash,
    }


def generate_portfolio_metrics(portfolio_id):
    """Generate comprehensive portfolio metrics and analysis."""
    conn = get_conn()

    portfolio = conn.execute(
        "SELECT * FROM investment_portfolios WHERE id = ?",
        (portfolio_id,)
    ).fetchone()

    if not portfolio:
        conn.close()
        return None

    portfolio_dict = dict(portfolio)

    # Get properties
    properties = conn.execute(
        "SELECT * FROM portfolio_properties WHERE portfolio_id = ? AND status = 'active'",
        (portfolio_id,)
    ).fetchall()

    property_list = [dict(p) for p in properties]

    # Calculate weighted metrics
    total_value = sum(p.get('current_value', 0) for p in property_list)

    avg_roi = 0
    if property_list:
        roi_sum = sum(p.get('roi_contribution', 0) for p in property_list)
        avg_roi = roi_sum / len(property_list)

    # Calculate cap rate (weighted)
    weighted_cap_rate = 0
    if total_value > 0:
        cap_rate_sum = 0
        for prop in property_list:
            prop_value = prop.get('current_value', 0)
            net_income = prop.get('net_income_annual', 0)
            if prop_value > 0:
                prop_cap_rate = (net_income / prop_value * 100)
                weight = prop_value / total_value
                cap_rate_sum += prop_cap_rate * weight
        weighted_cap_rate = cap_rate_sum

    # Diversification analysis
    type_dist = {}
    city_dist = {}
    for prop in property_list:
        ptype = prop.get('ptype', 'unknown')
        type_dist[ptype] = type_dist.get(ptype, 0) + 1

    # Diversification score: Higher is better (more diversification)
    num_types = len(type_dist)
    diversification_score = min(100, 20 + (num_types * 25))  # 0-100 scale

    # Update portfolio
    conn.execute(
        "UPDATE investment_portfolios SET "
        "average_roi=?, weighted_cap_rate=?, diversification_score=?, "
        "property_distribution=?, updated_at=? WHERE id=?",
        (avg_roi, weighted_cap_rate, diversification_score,
         json.dumps(type_dist), now(), portfolio_id)
    )

    conn.commit()
    conn.close()

    return {
        'num_properties': len(property_list),
        'total_value': total_value,
        'average_roi': avg_roi,
        'weighted_cap_rate': weighted_cap_rate,
        'diversification_score': diversification_score,
        'property_types': type_dist,
        'properties': property_list,
    }


def create_scenario(portfolio_id, scenario_name, scenario_type='base', property_appreciation=0.05, rental_growth=0.03, inflation=0.03):
    """Create a what-if scenario for portfolio projection."""
    conn = get_conn()

    # Get current portfolio value
    portfolio = conn.execute(
        "SELECT * FROM investment_portfolios WHERE id = ?",
        (portfolio_id,)
    ).fetchone()

    if not portfolio:
        conn.close()
        return None

    current_value = portfolio['current_value']
    holding_period = 5

    # Calculate projections
    projected_value = current_value * ((1 + property_appreciation) ** holding_period)
    projected_gain = projected_value - current_value
    projected_return = (projected_gain / current_value * 100) if current_value > 0 else 0

    # Projected income (with growth)
    current_income = portfolio['total_investment'] * 0.04  # Estimate 4% current yield
    projected_income = current_income * ((1 + rental_growth) ** holding_period)

    # IRR estimation (simplified)
    irr = (property_appreciation + (current_income / current_value)) * 100 if current_value > 0 else 0

    cursor = conn.execute(
        "INSERT INTO portfolio_scenarios "
        "(portfolio_id, scenario_name, scenario_type, property_appreciation_rate, "
        "rental_growth_rate, inflation_rate, sale_timeline_years, "
        "projected_portfolio_value, projected_annual_income, projected_total_return, "
        "projected_irr, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (portfolio_id, scenario_name, scenario_type, property_appreciation, rental_growth,
         inflation, holding_period, int(projected_value), int(projected_income),
         projected_return, irr, now(), now())
    )

    scenario_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return scenario_id


def get_portfolio_scenarios(portfolio_id):
    """Get all scenarios for a portfolio."""
    conn = get_conn()

    scenarios = conn.execute(
        "SELECT * FROM portfolio_scenarios WHERE portfolio_id = ? ORDER BY created_at DESC",
        (portfolio_id,)
    ).fetchall()

    conn.close()

    return [dict(s) for s in scenarios]


def compare_scenarios(scenario_ids):
    """Compare multiple scenarios side-by-side."""
    conn = get_conn()

    scenarios = []
    for sid in scenario_ids:
        scenario = conn.execute(
            "SELECT * FROM portfolio_scenarios WHERE id = ?",
            (sid,)
        ).fetchone()
        if scenario:
            scenarios.append(dict(scenario))

    conn.close()

    # Compile comparison
    comparison = {
        'scenarios': scenarios,
        'best_by_return': max(scenarios, key=lambda x: x['projected_total_return'], default=None),
        'best_by_income': max(scenarios, key=lambda x: x['projected_annual_income'], default=None),
        'safest': min(scenarios, key=lambda x: x['projected_irr'], default=None),
    }

    return comparison


def analyze_diversification(portfolio_id):
    """Analyze portfolio diversification metrics."""
    conn = get_conn()

    properties = conn.execute(
        "SELECT pp.*, p.ptype, p.city FROM portfolio_properties pp "
        "JOIN properties p ON pp.property_id = p.id "
        "WHERE pp.portfolio_id = ? AND pp.status = 'active'",
        (portfolio_id,)
    ).fetchall()

    conn.close()

    # Type distribution
    type_dist = {}
    city_dist = {}
    total_value = 0

    for prop in properties:
        prop_dict = dict(prop)
        ptype = prop_dict.get('ptype', 'unknown')
        city = prop_dict.get('city', 'unknown')
        value = prop_dict.get('current_value', 0)

        type_dist[ptype] = type_dist.get(ptype, 0) + value
        city_dist[city] = city_dist.get(city, 0) + value
        total_value += value

    # Normalize to percentages
    type_dist_pct = {k: (v / total_value * 100) if total_value > 0 else 0 for k, v in type_dist.items()}
    city_dist_pct = {k: (v / total_value * 100) if total_value > 0 else 0 for k, v in city_dist.items()}

    # Diversification score
    num_properties = len(properties)
    num_types = len(type_dist)
    num_cities = len(city_dist)

    # Herfindahl index for concentration (lower is better diversified)
    hhi_type = sum((pct ** 2) for pct in type_dist_pct.values())
    hhi_city = sum((pct ** 2) for pct in city_dist_pct.values())

    # Diversification score (0-100): Higher is more diversified
    diversification_score = min(100, max(0, 100 - ((hhi_type + hhi_city) / 2)))

    return {
        'num_properties': num_properties,
        'num_types': num_types,
        'num_cities': num_cities,
        'type_distribution': type_dist_pct,
        'city_distribution': city_dist_pct,
        'diversification_score': diversification_score,
        'is_well_diversified': diversification_score >= 60,
        'concentration_risk': 100 - diversification_score,
    }


def analyze_risk(portfolio_id):
    """Analyze portfolio risk profile and stress test."""
    conn = get_conn()

    properties = conn.execute(
        "SELECT * FROM portfolio_properties WHERE portfolio_id = ? AND status = 'active'",
        (portfolio_id,)
    ).fetchall()

    portfolio = conn.execute(
        "SELECT * FROM investment_portfolios WHERE id = ?",
        (portfolio_id,)
    ).fetchone()

    if not portfolio:
        conn.close()
        return None

    property_list = [dict(p) for p in properties]

    # Calculate risk metrics
    total_value = sum(p.get('current_value', 0) for p in property_list)
    max_property_value = max((p.get('current_value', 0) for p in property_list), default=0)
    concentration_risk = (max_property_value / total_value * 100) if total_value > 0 else 0

    # Stress test: 10% market downturn
    stress_test_value = total_value * 0.90
    stress_test_loss = total_value - stress_test_value

    # Recovery estimate (months at current cash flow)
    current_income = sum(p.get('net_income_annual', 0) for p in property_list)
    recovery_months = int((stress_test_loss / (current_income / 12))) if current_income > 0 else 0

    # Risk score (0-100): Higher = more risky
    risk_score = min(100, int(concentration_risk * 0.7 + (100 - dict(portfolio).get('diversification_score', 50)) * 0.3))

    # Recommendations
    recommendations = []
    if concentration_risk > 30:
        recommendations.append("Diversify: Single property exceeds 30% of portfolio")
    if len(property_list) < 3:
        recommendations.append("Add more properties: 3+ properties recommended")

    # Save analysis
    existing = conn.execute(
        "SELECT id FROM portfolio_risk_analysis WHERE portfolio_id = ?",
        (portfolio_id,)
    ).fetchone()

    if existing:
        conn.execute(
            "UPDATE portfolio_risk_analysis SET "
            "concentration_risk=?, market_risk=?, diversification_score=?, "
            "value_at_risk_10pct=?, max_drawdown_pct=?, recovery_time_months=?, "
            "risk_mitigation_actions=?, analyzed_at=? WHERE portfolio_id=?",
            (int(concentration_risk), 0.8, 100 - risk_score, stress_test_loss, 10.0,
             recovery_months, json.dumps(recommendations), now(), portfolio_id)
        )
    else:
        conn.execute(
            "INSERT INTO portfolio_risk_analysis "
            "(portfolio_id, concentration_risk, market_risk, diversification_score, "
            "value_at_risk_10pct, max_drawdown_pct, recovery_time_months, "
            "risk_mitigation_actions, analyzed_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (portfolio_id, int(concentration_risk), 0.8, 100 - risk_score, stress_test_loss,
             10.0, recovery_months, json.dumps(recommendations), now(), now())
        )

    conn.commit()
    conn.close()

    return {
        'risk_score': risk_score,
        'concentration_risk': concentration_risk,
        'diversification_score': 100 - risk_score,
        'stress_test_10pct_loss': stress_test_loss,
        'recovery_months': recovery_months,
        'recommendations': recommendations,
    }


def get_portfolio_summary(portfolio_id):
    """Get comprehensive portfolio summary with all metrics."""
    conn = get_conn()

    portfolio = conn.execute(
        "SELECT * FROM investment_portfolios WHERE id = ?",
        (portfolio_id,)
    ).fetchone()

    if not portfolio:
        conn.close()
        return None

    portfolio_dict = dict(portfolio)

    # Get properties
    properties = get_portfolio_properties(portfolio_id)

    # Get latest performance
    perf = conn.execute(
        "SELECT * FROM portfolio_performance WHERE portfolio_id = ? ORDER BY period_start DESC LIMIT 1",
        (portfolio_id,)
    ).fetchone()

    # Get scenarios
    scenarios = conn.execute(
        "SELECT * FROM portfolio_scenarios WHERE portfolio_id = ? ORDER BY created_at DESC LIMIT 3",
        (portfolio_id,)
    ).fetchall()

    # Get risk analysis
    risk = conn.execute(
        "SELECT * FROM portfolio_risk_analysis WHERE portfolio_id = ?",
        (portfolio_id,)
    ).fetchone()

    conn.close()

    portfolio_dict['properties'] = properties
    portfolio_dict['performance'] = dict(perf) if perf else None
    portfolio_dict['scenarios'] = [dict(s) for s in scenarios]
    portfolio_dict['risk_analysis'] = dict(risk) if risk else None

    return portfolio_dict


def get_investment_desk_dashboard():
    """Get statistics for the Mega Investment Desk dashboard."""
    conn = get_conn()

    total_portfolios = conn.execute("SELECT COUNT(*) as count FROM investment_portfolios").fetchone()
    total_properties = conn.execute("SELECT COUNT(*) as count FROM portfolio_properties WHERE status = 'active'").fetchone()

    total_value = conn.execute("SELECT COALESCE(SUM(current_value), 0) as total FROM investment_portfolios").fetchone()
    total_rental_income = conn.execute(
        "SELECT COALESCE(SUM(rental_income_annual), 0) as total FROM portfolio_properties WHERE status = 'active'"
    ).fetchone()

    # Average returns
    avg_return = conn.execute("SELECT AVG(annual_return) as avg FROM investment_portfolios WHERE annual_return > 0").fetchone()

    # Top portfolios by value
    top_portfolios = conn.execute(
        "SELECT id, name, current_value, annual_return FROM investment_portfolios ORDER BY current_value DESC LIMIT 5"
    ).fetchall()

    conn.close()

    return {
        'total_portfolios': total_portfolios['count'] if total_portfolios else 0,
        'total_properties': total_properties['count'] if total_properties else 0,
        'total_value': total_value['total'] if total_value else 0,
        'total_rental_income': total_rental_income['total'] if total_rental_income else 0,
        'average_annual_return': avg_return['avg'] or 0,
        'top_portfolios': [dict(p) for p in top_portfolios],
    }
