"""Real Estate Investment Calculator.

Week 2 System 2: Complete investment analysis with EMI, ROI, CAGR calculations
and scenario modeling (conservative/base/optimistic).

Zero external dependencies — uses only Python standard library.
"""

import math
from database import get_conn, now


def calculate_emi(principal, annual_rate, years):
    """Calculate monthly EMI using standard formula.

    EMI = P * r * (1+r)^n / ((1+r)^n - 1)
    where:
      P = principal
      r = monthly interest rate (annual_rate / 12 / 100)
      n = number of months
    """
    if principal <= 0 or years <= 0:
        return 0

    monthly_rate = (annual_rate / 12) / 100
    if monthly_rate == 0:
        return principal / (years * 12)

    num_months = years * 12
    numerator = principal * monthly_rate * math.pow(1 + monthly_rate, num_months)
    denominator = math.pow(1 + monthly_rate, num_months) - 1

    if denominator == 0:
        return 0

    return numerator / denominator


def calculate_investment(inputs):
    """Calculate complete investment analysis with all metrics.

    Returns dict with all calculated values.

    Input dict should contain:
    - property_name: str
    - investment_amount: int (total property price)
    - down_payment: int
    - loan_amount: int (auto-calculated if 0)
    - loan_rate: float (annual %)
    - loan_term_years: int
    - rental_income_monthly: int
    - rental_growth_annual: float (%)
    - property_appreciation_annual: float (%)
    - holding_period_years: int
    - annual_maintenance: int
    - annual_property_tax: int
    - annual_insurance: int
    - annual_vacancy_loss: float (% of rental income)
    """

    # Ensure loan_amount is calculated if not provided
    loan_amount = inputs.get('loan_amount', 0)
    if loan_amount == 0:
        loan_amount = inputs['investment_amount'] - inputs['down_payment']

    # Calculate monthly EMI
    emi = calculate_emi(loan_amount, inputs['loan_rate'], inputs['loan_term_years'])

    # Project rental income with growth
    total_rental_income = 0
    rental_schedule = []
    monthly_rental = inputs['rental_income_monthly']

    for year in range(inputs['holding_period_years']):
        # Apply annual growth to base rental
        annual_rental = monthly_rental * 12 * math.pow(1 + inputs['rental_growth_annual'] / 100, year)

        # Apply vacancy loss
        vacancy_reduction = annual_rental * (inputs['annual_vacancy_loss'] / 100)
        net_annual_rental = annual_rental - vacancy_reduction

        total_rental_income += net_annual_rental
        rental_schedule.append({
            'year': year + 1,
            'gross_rental': annual_rental,
            'vacancy_loss': vacancy_reduction,
            'net_rental': net_annual_rental
        })

    # Calculate total EMI paid (only during loan period)
    total_emi_paid = emi * 12 * inputs['loan_term_years']

    # Calculate total expenses
    total_expenses = (
        inputs['annual_maintenance'] +
        inputs['annual_property_tax'] +
        inputs['annual_insurance']
    ) * inputs['holding_period_years']

    # Calculate estimated resale value with appreciation
    estimated_resale_value = inputs['investment_amount'] * math.pow(
        1 + inputs['property_appreciation_annual'] / 100,
        inputs['holding_period_years']
    )

    # Calculate total return
    gross_proceeds = total_rental_income + estimated_resale_value
    total_costs = inputs['down_payment'] + total_emi_paid + total_expenses
    net_profit = gross_proceeds - total_costs
    total_return = gross_proceeds - inputs['down_payment']  # Excluding down payment from calculation

    # Calculate ROI
    if inputs['down_payment'] > 0:
        roi_percentage = (net_profit / inputs['down_payment']) * 100
    else:
        roi_percentage = 0

    # Calculate CAGR (Compound Annual Growth Rate)
    # CAGR = (Ending Value / Beginning Value) ^ (1 / Years) - 1
    if inputs['holding_period_years'] > 0 and inputs['down_payment'] > 0:
        ending_value = total_return
        beginning_value = inputs['down_payment']
        cagr = (math.pow(ending_value / beginning_value, 1 / inputs['holding_period_years']) - 1) * 100
    else:
        cagr = 0

    # Calculate Cash-on-Cash Return (annual rental income vs down payment)
    if inputs['holding_period_years'] > 0 and inputs['down_payment'] > 0:
        avg_annual_rental = total_rental_income / inputs['holding_period_years']
        cash_on_cash_return = (avg_annual_rental / inputs['down_payment']) * 100
    else:
        cash_on_cash_return = 0

    return {
        'property_name': inputs['property_name'],
        'investment_amount': inputs['investment_amount'],
        'down_payment': inputs['down_payment'],
        'loan_amount': loan_amount,
        'loan_rate': inputs['loan_rate'],
        'loan_term_years': inputs['loan_term_years'],
        'emi': emi,
        'rental_income_monthly': inputs['rental_income_monthly'],
        'rental_growth_annual': inputs['rental_growth_annual'],
        'property_appreciation_annual': inputs['property_appreciation_annual'],
        'holding_period_years': inputs['holding_period_years'],
        'annual_maintenance': inputs['annual_maintenance'],
        'annual_property_tax': inputs['annual_property_tax'],
        'annual_insurance': inputs['annual_insurance'],
        'annual_vacancy_loss': inputs['annual_vacancy_loss'],
        'total_rental_income': total_rental_income,
        'total_emi_paid': total_emi_paid,
        'total_expenses': total_expenses,
        'estimated_resale_value': estimated_resale_value,
        'gross_proceeds': gross_proceeds,
        'net_profit': net_profit,
        'total_return': total_return,
        'roi_percentage': roi_percentage,
        'cagr': cagr,
        'cash_on_cash_return': cash_on_cash_return,
        'rental_schedule': rental_schedule,
    }


def generate_scenarios(base_inputs):
    """Generate conservative, base, and optimistic scenarios.

    Adjusts appreciation and rental growth rates for different scenarios.
    """
    scenarios = {}

    # CONSERVATIVE SCENARIO
    conservative = base_inputs.copy()
    conservative['property_appreciation_annual'] = max(0.5, base_inputs['property_appreciation_annual'] * 0.5)
    conservative['rental_growth_annual'] = max(0, base_inputs['rental_growth_annual'] * 0.7)
    conservative['annual_vacancy_loss'] = min(30, base_inputs['annual_vacancy_loss'] + 5)
    scenarios['conservative'] = calculate_investment(conservative)

    # BASE SCENARIO (unchanged)
    scenarios['base'] = calculate_investment(base_inputs.copy())

    # OPTIMISTIC SCENARIO
    optimistic = base_inputs.copy()
    optimistic['property_appreciation_annual'] = base_inputs['property_appreciation_annual'] * 1.5
    optimistic['rental_growth_annual'] = base_inputs['rental_growth_annual'] * 1.3
    optimistic['annual_vacancy_loss'] = max(0, base_inputs['annual_vacancy_loss'] - 2)
    scenarios['optimistic'] = calculate_investment(optimistic)

    return scenarios


def save_calculation_to_db(user_id, calculation_data, scenario_type='base'):
    """Save calculation result to database."""
    conn = get_conn()

    calc_id = conn.execute(
        "INSERT INTO investment_calculations "
        "(property_id, user_id, property_name, investment_amount, down_payment, loan_amount, "
        "loan_rate, loan_term_years, emi, rental_income_monthly, rental_growth_annual, "
        "property_appreciation_annual, holding_period_years, annual_maintenance, "
        "annual_property_tax, annual_insurance, annual_vacancy_loss, total_rental_income, "
        "total_emi_paid, total_expenses, total_return, roi_percentage, cagr, "
        "cash_on_cash_return, scenario_type, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            None,  # property_id
            user_id,
            calculation_data['property_name'],
            calculation_data['investment_amount'],
            calculation_data['down_payment'],
            calculation_data['loan_amount'],
            calculation_data['loan_rate'],
            calculation_data['loan_term_years'],
            calculation_data['emi'],
            calculation_data['rental_income_monthly'],
            calculation_data['rental_growth_annual'],
            calculation_data['property_appreciation_annual'],
            calculation_data['holding_period_years'],
            calculation_data['annual_maintenance'],
            calculation_data['annual_property_tax'],
            calculation_data['annual_insurance'],
            calculation_data['annual_vacancy_loss'],
            calculation_data['total_rental_income'],
            calculation_data['total_emi_paid'],
            calculation_data['total_expenses'],
            calculation_data['total_return'],
            calculation_data['roi_percentage'],
            calculation_data['cagr'],
            calculation_data['cash_on_cash_return'],
            scenario_type,
            now(),
        )
    ).lastrowid

    conn.commit()
    conn.close()

    return calc_id


def get_calculation_from_db(calc_id):
    """Retrieve calculation from database."""
    conn = get_conn()
    calc = conn.execute("SELECT * FROM investment_calculations WHERE id = ?", (calc_id,)).fetchone()
    conn.close()
    return dict(calc) if calc else None


def get_user_calculations(user_id, limit=50):
    """Get all calculations for a user."""
    conn = get_conn()
    calcs = conn.execute(
        "SELECT * FROM investment_calculations WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit)
    ).fetchall()
    conn.close()
    return [dict(c) for c in calcs]


def create_comparison_set(user_id, title, calculation_ids):
    """Create a named comparison set."""
    import json

    conn = get_conn()

    comp_id = conn.execute(
        "INSERT INTO comparison_sets (user_id, title, calculations_json, created_at) "
        "VALUES (?,?,?,?)",
        (user_id, title, json.dumps(calculation_ids), now())
    ).lastrowid

    conn.commit()
    conn.close()

    return comp_id


def get_comparison_set(comp_id):
    """Get a comparison set with all calculations."""
    import json

    conn = get_conn()
    comp = conn.execute("SELECT * FROM comparison_sets WHERE id = ?", (comp_id,)).fetchone()

    if not comp:
        conn.close()
        return None

    calc_ids = json.loads(comp['calculations_json'])
    calculations = []

    for calc_id in calc_ids:
        calc = conn.execute("SELECT * FROM investment_calculations WHERE id = ?", (calc_id,)).fetchone()
        if calc:
            calculations.append(dict(calc))

    conn.close()

    return {
        'id': comp['id'],
        'title': comp['title'],
        'user_id': comp['user_id'],
        'created_at': comp['created_at'],
        'calculations': calculations,
        'best_roi': max(calculations, key=lambda x: x['roi_percentage']) if calculations else None,
        'best_rental': max(calculations, key=lambda x: x['cash_on_cash_return']) if calculations else None,
    }


# Utility formatting functions

def format_money(amount):
    """Format integer to rupees with comma separators."""
    if amount is None:
        return "—"
    if amount < 0:
        return f"-₹{abs(int(amount)):,}"
    return f"₹{int(amount):,}"


def format_percentage(value):
    """Format float to percentage with 2 decimals."""
    if value is None:
        return "—"
    return f"{value:.2f}%"


def format_emi(emi):
    """Format EMI (monthly payment)."""
    if emi is None or emi == 0:
        return "—"
    return f"₹{int(emi):,}/month"
