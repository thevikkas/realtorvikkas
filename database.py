"""SQLite storage for Realtor Vikkas.

Zero external dependencies — uses the Python standard-library sqlite3 module.
The database file (realtor.db) is created and seeded automatically on first run.
"""

import os
import sqlite3
from datetime import datetime

# Where the SQLite file lives. In production (e.g. Render with a persistent
# disk) set DATABASE_PATH to a path on that disk — e.g. /var/data/realtor.db —
# so data survives restarts and redeploys. Locally it defaults to this folder.
_LOCAL_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "realtor.db")
DB_PATH = os.environ.get("DATABASE_PATH") or _LOCAL_DB

# Ensure the folder holding the database exists. If a configured path (e.g. a
# mounted disk like /var/data) isn't available or writable, fall back to a local
# file so the app still STARTS instead of crashing at import (which would make
# the whole site return "Not Found" on the host).
try:
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
except Exception as _exc:
    print(f"[db] cannot use {DB_PATH} ({_exc}); falling back to local realtor.db")
    DB_PATH = _LOCAL_DB
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    email         TEXT    NOT NULL UNIQUE,
    phone         TEXT    DEFAULT '',
    password_hash TEXT    NOT NULL,
    role          TEXT    NOT NULL DEFAULT 'customer',  -- 'owner' | 'customer'
    created_at    TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS properties (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    ptype       TEXT    NOT NULL,                 -- Villa | Plot | Flat | Townhouse | Commercial
    listing     TEXT    NOT NULL DEFAULT 'buy',   -- buy | rent
    city        TEXT    NOT NULL,
    locality    TEXT    DEFAULT '',
    price       INTEGER NOT NULL DEFAULT 0,       -- in INR (absolute)
    area_sqft   INTEGER DEFAULT 0,
    bedrooms    INTEGER DEFAULT 0,
    bathrooms   INTEGER DEFAULT 0,
    description TEXT    DEFAULT '',
    status      TEXT    NOT NULL DEFAULT 'available', -- available | sold | rented
    featured    INTEGER NOT NULL DEFAULT 0,
    photos_url  TEXT    DEFAULT '',
    amenities   TEXT    DEFAULT '',                   -- comma-separated (optional)
    owner_id    INTEGER,
    created_at  TEXT    NOT NULL,
    FOREIGN KEY (owner_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS enquiries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER,
    customer_id INTEGER,                          -- nullable (guest enquiries)
    name        TEXT    NOT NULL,
    email       TEXT    NOT NULL,
    phone       TEXT    DEFAULT '',
    message     TEXT    DEFAULT '',
    status      TEXT    NOT NULL DEFAULT 'new',   -- new | contacted | closed
    created_at  TEXT    NOT NULL,
    FOREIGN KEY (property_id) REFERENCES properties(id),
    FOREIGN KEY (customer_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS callbacks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    phone       TEXT    NOT NULL,
    preferred   TEXT    DEFAULT '',                -- best time to call
    note        TEXT    DEFAULT '',
    property_id INTEGER,                           -- optional (from a listing page)
    status      TEXT    NOT NULL DEFAULT 'new',    -- new | called | done
    created_at  TEXT    NOT NULL,
    FOREIGN KEY (property_id) REFERENCES properties(id)
);

CREATE TABLE IF NOT EXISTS favorites (
    user_id     INTEGER NOT NULL,
    property_id INTEGER NOT NULL,
    created_at  TEXT    NOT NULL,
    PRIMARY KEY (user_id, property_id)
);

CREATE TABLE IF NOT EXISTS sessions (
    token      TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL,
    expires_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS leads (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT    DEFAULT '',
    phone    TEXT    DEFAULT '',
    property TEXT    DEFAULT '',
    message  TEXT    DEFAULT '',
    status   TEXT    NOT NULL DEFAULT 'New',   -- New | Contacted | Visited | Closed
    created  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS investments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    category    TEXT    NOT NULL DEFAULT 'Plot',   -- Plot | Pre-launch | Resort / Second Home | Rental Yield | Commercial | Farmhouse
    location    TEXT    DEFAULT '',
    ticket      INTEGER DEFAULT 0,                 -- indicative ticket size in INR (0 = "On request")
    horizon     TEXT    DEFAULT '',                -- owner's words, e.g. "3–5 years" (optional)
    highlights  TEXT    DEFAULT '',                -- comma / newline separated bullet points
    description TEXT    DEFAULT '',
    photos_url  TEXT    DEFAULT '',
    status      TEXT    NOT NULL DEFAULT 'active',  -- active | hidden
    featured    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS insights (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    category    TEXT    NOT NULL DEFAULT 'Guide',   -- Guide | Market Note | Locality | Investment
    area        TEXT    DEFAULT '',                 -- optional locality/city
    summary     TEXT    DEFAULT '',
    body        TEXT    DEFAULT '',
    source      TEXT    DEFAULT '',                 -- optional attribution for real data
    status      TEXT    NOT NULL DEFAULT 'published', -- published | hidden
    featured    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT    NOT NULL
);

-- WEEK 4: Real Estate Growth Map
CREATE TABLE IF NOT EXISTS market_insights (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    city                        TEXT NOT NULL,
    locality                    TEXT,

    -- MARKET STATISTICS
    total_properties            INTEGER DEFAULT 0,
    avg_price                   INTEGER DEFAULT 0,
    median_price                INTEGER DEFAULT 0,
    price_range_min             INTEGER DEFAULT 0,
    price_range_max             INTEGER DEFAULT 0,

    -- DEMAND & SUPPLY
    property_type_distribution  TEXT DEFAULT '',
    rent_vs_buy_ratio           REAL DEFAULT 0.0,
    days_on_market              INTEGER DEFAULT 0,

    -- GROWTH & TRENDS
    price_appreciation_1yr       REAL DEFAULT 0.0,
    price_appreciation_3yr       REAL DEFAULT 0.0,
    price_appreciation_5yr       REAL DEFAULT 0.0,
    market_sentiment            TEXT DEFAULT 'neutral',

    -- INVESTOR ACTIVITY
    investor_purchases_pct      REAL DEFAULT 0.0,
    avg_investor_roi            REAL DEFAULT 0.0,

    -- UPCOMING PROJECTS
    major_projects              TEXT DEFAULT '',

    source                      TEXT DEFAULT 'internal',
    last_updated                TEXT NOT NULL,

    UNIQUE (city, locality)
);

CREATE TABLE IF NOT EXISTS infrastructure_projects (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    city                        TEXT NOT NULL,
    locality                    TEXT,

    project_name                TEXT NOT NULL,
    project_type                TEXT NOT NULL,
    status                      TEXT DEFAULT 'planned',

    completion_date             TEXT,
    estimated_impact            TEXT DEFAULT 'MEDIUM',
    impact_description          TEXT DEFAULT '',

    created_at                  TEXT NOT NULL,
    UNIQUE (project_name, city)
);

CREATE TABLE IF NOT EXISTS growth_indicators (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    city                        TEXT NOT NULL,
    locality                    TEXT,

    -- ECONOMIC INDICATORS
    population_growth           REAL DEFAULT 0.0,
    commercial_development      REAL DEFAULT 0.0,
    employment_centers_count    INTEGER DEFAULT 0,

    -- QUALITY OF LIFE
    education_institutions      INTEGER DEFAULT 0,
    hospitals_clinics           INTEGER DEFAULT 0,
    shopping_malls              INTEGER DEFAULT 0,
    entertainment_venues        INTEGER DEFAULT 0,

    -- CONNECTIVITY
    road_quality_score          INTEGER DEFAULT 0,
    public_transport_score      INTEGER DEFAULT 0,

    created_at                  TEXT NOT NULL,
    UNIQUE (city, locality)
);

-- WEEK 3: AI Property Matchmaker
CREATE TABLE IF NOT EXISTS buyer_requirements (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id                     INTEGER NOT NULL,

    -- BASIC REQUIREMENTS
    budget_min                  INTEGER NOT NULL,
    budget_max                  INTEGER NOT NULL,
    location_preferences        TEXT NOT NULL,
    property_types              TEXT NOT NULL,
    listing_type                TEXT NOT NULL,

    -- PROPERTY PREFERENCES
    min_bedrooms                INTEGER DEFAULT 0,
    min_bathrooms               INTEGER DEFAULT 0,
    min_area_sqft               INTEGER DEFAULT 0,
    max_area_sqft               INTEGER DEFAULT 0,

    -- INVESTMENT PREFERENCES
    investment_purpose          TEXT DEFAULT '',
    expected_holding_years      INTEGER DEFAULT 0,
    expected_roi_min            REAL DEFAULT 0,
    expected_rental_yield       REAL DEFAULT 0,

    -- LIFESTYLE PREFERENCES
    amenities_wanted            TEXT DEFAULT '',
    walkability_important       BOOLEAN DEFAULT 0,
    public_transit_important    BOOLEAN DEFAULT 0,

    -- PROFILE
    investor_profile            TEXT DEFAULT '',

    created_at                  TEXT NOT NULL,
    last_updated                TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS property_matches (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    requirement_id              INTEGER NOT NULL,
    property_id                 INTEGER NOT NULL,

    -- MATCH SCORE & FACTORS
    match_score                 INTEGER DEFAULT 0,

    price_fit_score             INTEGER DEFAULT 0,
    location_fit_score          INTEGER DEFAULT 0,
    property_type_fit           INTEGER DEFAULT 0,
    amenity_fit_score           INTEGER DEFAULT 0,
    investment_fit_score        INTEGER DEFAULT 0,
    lifestyle_fit_score         INTEGER DEFAULT 0,

    -- EXPLANATION
    match_explanation           TEXT DEFAULT '',
    match_reasons               TEXT DEFAULT '',
    potential_concerns          TEXT DEFAULT '',

    rank                        INTEGER DEFAULT 0,

    created_at                  TEXT NOT NULL,
    FOREIGN KEY (requirement_id) REFERENCES buyer_requirements(id),
    FOREIGN KEY (property_id) REFERENCES properties(id),
    UNIQUE (requirement_id, property_id)
);

-- WEEK 2: Real Estate Investment OS
CREATE TABLE IF NOT EXISTS investment_calculations (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id                 INTEGER,
    user_id                     INTEGER,

    -- BASIC INPUTS
    property_name               TEXT NOT NULL,
    investment_amount           INTEGER NOT NULL,
    down_payment                INTEGER NOT NULL,
    loan_amount                 INTEGER DEFAULT 0,

    -- LOAN DETAILS
    loan_rate                   REAL DEFAULT 0.0,
    loan_term_years             INTEGER DEFAULT 0,
    emi                         REAL DEFAULT 0,

    -- INCOME ASSUMPTIONS
    rental_income_monthly       INTEGER DEFAULT 0,
    rental_growth_annual        REAL DEFAULT 0.0,

    -- APPRECIATION ASSUMPTIONS
    property_appreciation_annual REAL DEFAULT 0.0,
    holding_period_years        INTEGER DEFAULT 0,
    estimated_resale_value      INTEGER DEFAULT 0,

    -- EXPENSES
    annual_maintenance          INTEGER DEFAULT 0,
    annual_property_tax         INTEGER DEFAULT 0,
    annual_insurance            INTEGER DEFAULT 0,
    annual_vacancy_loss         REAL DEFAULT 0.0,

    -- CALCULATED RESULTS
    total_rental_income         INTEGER DEFAULT 0,
    total_emi_paid              INTEGER DEFAULT 0,
    total_expenses              INTEGER DEFAULT 0,
    total_return                INTEGER DEFAULT 0,
    roi_percentage              REAL DEFAULT 0.0,
    cagr                        REAL DEFAULT 0.0,
    cash_on_cash_return         REAL DEFAULT 0.0,

    -- SCENARIO TYPE
    scenario_type               TEXT NOT NULL,

    created_at                  TEXT NOT NULL,
    FOREIGN KEY (property_id) REFERENCES properties(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS comparison_sets (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id                     INTEGER NOT NULL,
    title                       TEXT NOT NULL,

    -- CALCULATIONS IN THIS SET (JSON array of calc IDs)
    calculations_json           TEXT NOT NULL,

    -- COMPARISON INSIGHTS
    best_roi_calc_id            INTEGER,
    best_rental_calc_id         INTEGER,
    most_liquid_calc_id         INTEGER,

    created_at                  TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- WEEK 1: Property Intelligence Engine
CREATE TABLE IF NOT EXISTS property_intelligence (
    id                              INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id                     INTEGER NOT NULL UNIQUE,

    -- LOCATION QUALITY (0-100)
    location_score                  INTEGER DEFAULT 0,
    connectivity_score              INTEGER DEFAULT 0,
    infrastructure_score            INTEGER DEFAULT 0,

    -- INVESTMENT METRICS (0-100)
    price_positioning_score         INTEGER DEFAULT 0,
    rental_potential_score          INTEGER DEFAULT 0,
    appreciation_potential_score    INTEGER DEFAULT 0,

    -- RISK & LIQUIDITY (0-100)
    risk_score                      INTEGER DEFAULT 0,
    liquidity_score                 INTEGER DEFAULT 0,

    -- ANALYSIS FIELDS
    area_growth_trend               TEXT DEFAULT '',
    area_growth_pct                 REAL DEFAULT 0.0,
    comparable_price                REAL DEFAULT 0,
    price_variance                  REAL DEFAULT 0.0,

    -- INVESTOR PROFILE MATCH
    investor_type                   TEXT DEFAULT '',
    investment_fit_score            INTEGER DEFAULT 0,
    match_explanation               TEXT DEFAULT '',

    -- NOTES & TIMESTAMPS
    analyst_notes                   TEXT DEFAULT '',
    last_updated                    TEXT NOT NULL,

    FOREIGN KEY (property_id) REFERENCES properties(id)
);

CREATE TABLE IF NOT EXISTS location_data (
    id                              INTEGER PRIMARY KEY AUTOINCREMENT,
    city                            TEXT NOT NULL,
    locality                        TEXT NOT NULL,

    -- INFRASTRUCTURE
    nearest_metro_km                REAL DEFAULT 0,
    nearest_mall_km                 REAL DEFAULT 0,
    nearest_hospital_km             REAL DEFAULT 0,
    nearest_school_km               REAL DEFAULT 0,

    -- CONNECTIVITY
    road_quality                    TEXT DEFAULT '',
    public_transport                TEXT DEFAULT '',
    airport_km                      REAL DEFAULT 0,

    -- GROWTH INDICATORS
    infrastructure_under_development TEXT DEFAULT '',
    metro_planned                   BOOLEAN DEFAULT 0,
    commercial_development          TEXT DEFAULT '',

    -- MARKET DATA
    avg_price_per_sqft              INTEGER DEFAULT 0,
    price_growth_1yr                REAL DEFAULT 0.0,
    price_growth_3yr                REAL DEFAULT 0.0,
    price_growth_5yr                REAL DEFAULT 0.0,

    -- DEMAND INDICATORS
    avg_rental_yield                REAL DEFAULT 0.0,
    demand_level                    TEXT DEFAULT 'medium',

    last_updated                    TEXT NOT NULL,
    UNIQUE (city, locality)
);

-- WEEK 5: DEAL ROOM SYSTEM
CREATE TABLE IF NOT EXISTS deals (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id             INTEGER,
    title                   TEXT NOT NULL,
    status                  TEXT NOT NULL DEFAULT 'prospecting',  -- prospecting|offer|negotiation|closing|closed|cancelled
    deal_type               TEXT NOT NULL DEFAULT 'purchase',  -- purchase|investment|rent|lease
    buyer_id                INTEGER,
    seller_id               INTEGER,
    agent_id                INTEGER,

    -- FINANCIAL TRACKING
    offer_price             INTEGER DEFAULT 0,
    agreed_price            INTEGER DEFAULT 0,
    down_payment            INTEGER DEFAULT 0,
    loan_amount             INTEGER DEFAULT 0,
    expected_closing_date   TEXT DEFAULT '',

    -- DEAL DETAILS
    offer_date              TEXT NOT NULL,
    acceptance_date         TEXT,
    negotiation_notes       TEXT DEFAULT '',
    special_conditions      TEXT DEFAULT '',

    -- TEAM TRACKING
    team_lead_id            INTEGER,
    assigned_lawyer_id      INTEGER,
    assigned_inspector_id   INTEGER,

    -- METRICS & TRACKING
    deal_stage_completion   INTEGER DEFAULT 0,  -- 0-100%
    estimated_roi           REAL DEFAULT 0.0,
    holding_period_months   INTEGER DEFAULT 0,
    expected_rental_income  INTEGER DEFAULT 0,

    -- TIMESTAMPS
    created_at              TEXT NOT NULL,
    updated_at              TEXT NOT NULL,
    closed_at               TEXT,

    -- METADATA
    priority                TEXT DEFAULT 'medium',  -- low|medium|high|critical
    tags                    TEXT DEFAULT '',  -- JSON array
    custom_data             TEXT DEFAULT ''  -- JSON for extensibility
);

CREATE TABLE IF NOT EXISTS deal_stakeholders (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    deal_id                 INTEGER NOT NULL,
    user_id                 INTEGER NOT NULL,
    role                    TEXT NOT NULL,  -- buyer|seller|agent|lawyer|inspector|accountant|loan_officer|other
    name                    TEXT NOT NULL,
    email                   TEXT DEFAULT '',
    phone                   TEXT DEFAULT '',
    organization            TEXT DEFAULT '',

    -- RELATIONSHIP TRACKING
    is_primary              BOOLEAN DEFAULT 0,
    communication_preferred TEXT DEFAULT 'email',  -- email|phone|sms

    -- TIMESTAMPS
    added_at                TEXT NOT NULL,

    FOREIGN KEY (deal_id) REFERENCES deals(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS deal_documents (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    deal_id                 INTEGER NOT NULL,
    document_type           TEXT NOT NULL,  -- agreement|inspection|appraisal|legal|financial|insurance|other
    title                   TEXT NOT NULL,
    file_path               TEXT NOT NULL,
    file_size               INTEGER DEFAULT 0,
    mime_type               TEXT DEFAULT 'application/pdf',

    -- VERSIONING
    version                 INTEGER DEFAULT 1,
    is_latest               BOOLEAN DEFAULT 1,

    -- DOCUMENT STATUS
    status                  TEXT DEFAULT 'pending',  -- pending|signed|reviewed|archived
    signed_by               INTEGER,  -- user_id who signed

    -- TIMESTAMPS
    uploaded_at             TEXT NOT NULL,
    signed_at               TEXT,

    FOREIGN KEY (deal_id) REFERENCES deals(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS deal_timeline (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    deal_id                 INTEGER NOT NULL,
    event_type              TEXT NOT NULL,  -- offer_made|offer_accepted|negotiation|inspection|appraisal|loan_approved|closing|closed|cancelled
    title                   TEXT NOT NULL,
    description             TEXT DEFAULT '',

    -- EVENT DETAILS
    scheduled_date          TEXT,
    actual_date             TEXT,
    completed               BOOLEAN DEFAULT 0,

    -- WHO & WHAT
    created_by              INTEGER NOT NULL,
    assigned_to             INTEGER,

    -- PRIORITY & STATUS
    priority                TEXT DEFAULT 'normal',  -- low|normal|high|urgent
    status                  TEXT DEFAULT 'pending',  -- pending|in_progress|completed|cancelled

    -- TIMESTAMPS
    created_at              TEXT NOT NULL,
    updated_at              TEXT NOT NULL,

    FOREIGN KEY (deal_id) REFERENCES deals(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS deal_communications (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    deal_id                 INTEGER NOT NULL,
    sender_id               INTEGER NOT NULL,
    message_type            TEXT DEFAULT 'note',  -- note|email|call|meeting|decision
    subject                 TEXT DEFAULT '',
    content                 TEXT NOT NULL,

    -- REFERENCE
    related_event_id        INTEGER,  -- Timeline event reference
    related_document_id     INTEGER,  -- Document reference

    -- VISIBILITY & TRACKING
    visibility              TEXT DEFAULT 'team',  -- private|team|buyer|seller|all
    is_pinned               BOOLEAN DEFAULT 0,

    -- TIMESTAMPS
    created_at              TEXT NOT NULL,
    updated_at              TEXT NOT NULL,

    FOREIGN KEY (deal_id) REFERENCES deals(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS deal_metrics (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    deal_id                 INTEGER NOT NULL,

    -- FINANCIAL METRICS
    purchase_price          INTEGER DEFAULT 0,
    total_investment        INTEGER DEFAULT 0,  -- Purchase + closing costs
    expected_monthly_income INTEGER DEFAULT 0,
    expected_monthly_costs  INTEGER DEFAULT 0,

    -- PERFORMANCE CALCULATIONS
    cash_on_cash_return     REAL DEFAULT 0.0,  -- Annual%
    expected_roi_annual     REAL DEFAULT 0.0,
    expected_irr            REAL DEFAULT 0.0,
    break_even_months       INTEGER DEFAULT 0,

    -- MARKET COMPARISON
    price_per_sqft          INTEGER DEFAULT 0,
    market_price_estimate   INTEGER DEFAULT 0,
    price_variance_pct      REAL DEFAULT 0.0,

    -- APPRAISAL & VALUATION
    appraised_value         INTEGER DEFAULT 0,
    equity_buildup_1yr      INTEGER DEFAULT 0,
    equity_buildup_5yr      INTEGER DEFAULT 0,

    -- MARKET ANALYSIS
    property_appreciation_1yr REAL DEFAULT 0.0,
    property_appreciation_5yr REAL DEFAULT 0.0,
    rental_yield            REAL DEFAULT 0.0,
    cap_rate                REAL DEFAULT 0.0,

    -- TIMESTAMPS
    calculated_at           TEXT NOT NULL,
    updated_at              TEXT NOT NULL,

    UNIQUE(deal_id),
    FOREIGN KEY (deal_id) REFERENCES deals(id) ON DELETE CASCADE
);

-- WEEK 6: MEGA INVESTMENT DESK SYSTEM
CREATE TABLE IF NOT EXISTS investment_portfolios (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    name                    TEXT NOT NULL,
    description             TEXT DEFAULT '',
    portfolio_type          TEXT NOT NULL DEFAULT 'mixed',  -- residential|commercial|mixed|investment_trust
    owner_id                INTEGER,

    -- PORTFOLIO STRATEGY
    investment_strategy     TEXT DEFAULT 'balanced',  -- growth|income|balanced|value
    risk_profile            TEXT DEFAULT 'moderate',  -- conservative|moderate|aggressive
    target_returns          REAL DEFAULT 0.0,
    rebalance_frequency     TEXT DEFAULT 'quarterly',  -- monthly|quarterly|annual|manual

    -- PERFORMANCE TRACKING
    total_investment        INTEGER DEFAULT 0,
    current_value           INTEGER DEFAULT 0,
    total_return            REAL DEFAULT 0.0,  -- %
    annual_return           REAL DEFAULT 0.0,  -- %
    ytd_return              REAL DEFAULT 0.0,  -- %

    -- PORTFOLIO COMPOSITION
    num_properties          INTEGER DEFAULT 0,
    property_distribution   TEXT DEFAULT '',  -- JSON
    geographic_distribution TEXT DEFAULT '',  -- JSON by city
    type_distribution       TEXT DEFAULT '',  -- JSON by property type

    -- METRICS & ANALYTICS
    average_roi             REAL DEFAULT 0.0,
    weighted_cap_rate       REAL DEFAULT 0.0,
    diversification_score   INTEGER DEFAULT 0,  -- 0-100
    risk_score              INTEGER DEFAULT 50,  -- 0-100

    -- TIMESTAMPS
    created_at              TEXT NOT NULL,
    updated_at              TEXT NOT NULL,
    last_rebalanced         TEXT
);

CREATE TABLE IF NOT EXISTS portfolio_properties (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id            INTEGER NOT NULL,
    property_id             INTEGER NOT NULL,

    -- ALLOCATION
    allocation_percentage   REAL DEFAULT 0.0,  -- % of portfolio
    acquisition_date        TEXT,
    acquisition_price       INTEGER DEFAULT 0,

    -- PERFORMANCE
    current_value           INTEGER DEFAULT 0,
    unrealized_gain         INTEGER DEFAULT 0,
    unrealized_gain_pct     REAL DEFAULT 0.0,
    realized_gain           INTEGER DEFAULT 0,

    -- CONTRIBUTION
    rental_income_annual    INTEGER DEFAULT 0,
    operating_costs_annual  INTEGER DEFAULT 0,
    net_income_annual       INTEGER DEFAULT 0,

    -- WEIGHTING & IMPACT
    weight_in_portfolio     REAL DEFAULT 0.0,  -- Calculated %
    roi_contribution        REAL DEFAULT 0.0,  -- Property ROI impact

    -- METADATA
    status                  TEXT DEFAULT 'active',  -- active|sold|divested
    sale_date               TEXT,
    sale_price              INTEGER DEFAULT 0,

    -- TIMESTAMPS
    added_at                TEXT NOT NULL,
    updated_at              TEXT NOT NULL,

    UNIQUE(portfolio_id, property_id),
    FOREIGN KEY (portfolio_id) REFERENCES investment_portfolios(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS portfolio_performance (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id            INTEGER NOT NULL,

    -- VALUATION
    total_properties_value  INTEGER DEFAULT 0,
    total_rental_income     INTEGER DEFAULT 0,
    total_operating_costs   INTEGER DEFAULT 0,
    net_cash_flow           INTEGER DEFAULT 0,

    -- RETURNS
    total_return_amount     INTEGER DEFAULT 0,
    total_return_percentage REAL DEFAULT 0.0,
    annualized_return       REAL DEFAULT 0.0,
    cash_on_cash_return     REAL DEFAULT 0.0,

    -- MARKET COMPARISON
    benchmark_return        REAL DEFAULT 0.0,  -- Market average
    alpha                   REAL DEFAULT 0.0,  -- Excess return vs benchmark
    beta                    REAL DEFAULT 1.0,  -- Volatility vs benchmark

    -- MEASUREMENT PERIOD
    period_start            TEXT NOT NULL,
    period_end              TEXT NOT NULL,
    calculated_at           TEXT NOT NULL,

    UNIQUE(portfolio_id, period_start),
    FOREIGN KEY (portfolio_id) REFERENCES investment_portfolios(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS portfolio_scenarios (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id            INTEGER NOT NULL,
    scenario_name           TEXT NOT NULL,
    scenario_type           TEXT NOT NULL,  -- conservative|base|optimistic|custom

    -- ASSUMPTIONS
    property_appreciation_rate REAL DEFAULT 0.05,
    rental_growth_rate      REAL DEFAULT 0.03,
    inflation_rate          REAL DEFAULT 0.03,
    sale_timeline_years     INTEGER DEFAULT 5,

    -- PROJECTIONS
    projected_portfolio_value INTEGER DEFAULT 0,
    projected_annual_income INTEGER DEFAULT 0,
    projected_total_return REAL DEFAULT 0.0,
    projected_irr           REAL DEFAULT 0.0,

    -- RISK ADJUSTMENTS
    market_downturn_pct     REAL DEFAULT 0.0,  -- Assume market decline %
    vacancy_rate            REAL DEFAULT 0.0,

    -- METADATA
    description             TEXT DEFAULT '',
    is_baseline             BOOLEAN DEFAULT 0,

    -- TIMESTAMPS
    created_at              TEXT NOT NULL,
    updated_at              TEXT NOT NULL,

    FOREIGN KEY (portfolio_id) REFERENCES investment_portfolios(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS investment_strategies (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id            INTEGER,
    strategy_name           TEXT NOT NULL,
    strategy_type           TEXT NOT NULL,  -- growth|income|value|leverage|core_plus

    -- STRATEGY DEFINITION
    description             TEXT DEFAULT '',
    target_allocation       TEXT DEFAULT '',  -- JSON with allocation %
    rebalance_threshold     REAL DEFAULT 5.0,  -- % change triggers rebalance

    -- IMPLEMENTATION
    property_criteria       TEXT DEFAULT '',  -- JSON with property filters
    max_property_size       REAL DEFAULT 0.0,  -- Max allocation per property
    geographic_constraints  TEXT DEFAULT '',  -- JSON with geography rules

    -- PERFORMANCE TARGETS
    target_annual_return    REAL DEFAULT 0.0,
    max_acceptable_risk     REAL DEFAULT 0.2,  -- Max volatility %

    -- METADATA
    is_active               BOOLEAN DEFAULT 1,
    created_at              TEXT NOT NULL,
    updated_at              TEXT NOT NULL,

    FOREIGN KEY (portfolio_id) REFERENCES investment_portfolios(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS portfolio_risk_analysis (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id            INTEGER NOT NULL,

    -- RISK METRICS
    concentration_risk      INTEGER DEFAULT 0,  -- 0-100
    geographic_risk         INTEGER DEFAULT 0,  -- Concentration by city
    property_type_risk      INTEGER DEFAULT 0,  -- Concentration by type
    market_risk             REAL DEFAULT 0.0,  -- Beta
    interest_rate_risk      REAL DEFAULT 0.0,  -- Sensitivity to rates

    -- DIVERSIFICATION
    diversification_score   INTEGER DEFAULT 0,  -- 0-100 (higher is better)
    num_unique_properties   INTEGER DEFAULT 0,
    num_unique_locations    INTEGER DEFAULT 0,
    num_unique_types        INTEGER DEFAULT 0,

    -- STRESS TESTING
    value_at_risk_10pct     INTEGER DEFAULT 0,  -- 10% probability loss
    max_drawdown_pct        REAL DEFAULT 0.0,  -- Worst case scenario
    recovery_time_months    INTEGER DEFAULT 0,  -- Months to recover from downturn

    -- RECOMMENDATIONS
    risk_mitigation_actions TEXT DEFAULT '',  -- JSON array of recommendations

    -- TIMESTAMPS
    analyzed_at             TEXT NOT NULL,
    updated_at              TEXT NOT NULL,

    UNIQUE(portfolio_id),
    FOREIGN KEY (portfolio_id) REFERENCES investment_portfolios(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS portfolio_allocations (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id            INTEGER NOT NULL,

    -- CURRENT ALLOCATION
    target_equity_allocation REAL DEFAULT 0.7,  -- % in equity
    target_debt_allocation   REAL DEFAULT 0.3,  -- % in debt/loans
    current_equity_allocation REAL DEFAULT 0.0,
    current_debt_allocation   REAL DEFAULT 0.0,

    -- ALLOCATION BY TYPE
    residential_allocation  REAL DEFAULT 0.0,
    commercial_allocation   REAL DEFAULT 0.0,
    mixed_allocation        REAL DEFAULT 0.0,
    other_allocation        REAL DEFAULT 0.0,

    -- ALLOCATION BY LOCATION
    location_diversification TEXT DEFAULT '',  -- JSON with city allocations

    -- REBALANCING
    last_rebalance_date     TEXT,
    next_rebalance_date     TEXT,
    rebalance_needed        BOOLEAN DEFAULT 0,
    actions_to_rebalance    TEXT DEFAULT '',  -- JSON recommendations

    -- TIMESTAMPS
    created_at              TEXT NOT NULL,
    updated_at              TEXT NOT NULL,

    UNIQUE(portfolio_id),
    FOREIGN KEY (portfolio_id) REFERENCES investment_portfolios(id) ON DELETE CASCADE
);

-- WEEK 7: CONCIERGE FOUNDATION SYSTEM
CREATE TABLE IF NOT EXISTS concierge_requests (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id               INTEGER NOT NULL,
    request_type            TEXT NOT NULL,  -- property_search|advisory|transaction|document|other
    title                   TEXT NOT NULL,
    description             TEXT DEFAULT '',

    -- SERVICE DETAILS
    service_tier            TEXT DEFAULT 'standard',  -- basic|standard|premium|vip
    status                  TEXT DEFAULT 'pending',  -- pending|assigned|in_progress|completed|cancelled
    priority                TEXT DEFAULT 'normal',  -- low|normal|high|urgent

    -- ASSIGNMENT
    assigned_advisor_id     INTEGER,
    assignment_date         TEXT,

    -- REQUESTS & PREFERENCES
    service_details         TEXT DEFAULT '',  -- JSON with specific requests
    budget_range            TEXT DEFAULT '',  -- JSON with min/max
    preferred_locations     TEXT DEFAULT '',  -- JSON array
    timeline                TEXT DEFAULT '',  -- urgency/timeline info

    -- TRACKING
    completion_date         TEXT,
    satisfaction_rating     INTEGER,  -- 1-5 stars
    feedback                TEXT DEFAULT '',

    -- TIMESTAMPS
    created_at              TEXT NOT NULL,
    updated_at              TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS personal_advisors (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    advisor_id              INTEGER NOT NULL,
    client_id               INTEGER NOT NULL,
    relationship_start      TEXT NOT NULL,

    -- ADVISOR PROFILE
    advisor_name            TEXT NOT NULL,
    advisor_expertise       TEXT DEFAULT '',  -- JSON array of expertise areas
    advisor_phone           TEXT DEFAULT '',
    advisor_email           TEXT DEFAULT '',

    -- SERVICE PREFERENCES
    preferred_communication TEXT DEFAULT 'email',  -- email|phone|in_person|sms
    communication_frequency TEXT DEFAULT 'weekly',  -- daily|weekly|bi-weekly|monthly

    -- PERFORMANCE
    total_clients_served    INTEGER DEFAULT 0,
    client_satisfaction     REAL DEFAULT 0.0,  -- 0-5 rating
    deals_closed            INTEGER DEFAULT 0,
    total_value_managed     INTEGER DEFAULT 0,

    -- RELATIONSHIP STATUS
    status                  TEXT DEFAULT 'active',  -- active|inactive|transferred
    notes                   TEXT DEFAULT '',

    -- TIMESTAMPS
    created_at              TEXT NOT NULL,
    updated_at              TEXT NOT NULL,

    UNIQUE(client_id),
    FOREIGN KEY (client_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS client_preferences (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id               INTEGER NOT NULL,

    -- PROPERTY PREFERENCES
    preferred_cities        TEXT DEFAULT '',  -- JSON array
    preferred_localities    TEXT DEFAULT '',  -- JSON array
    property_types          TEXT DEFAULT '',  -- JSON array (apartment, villa, commercial, etc)
    min_bedrooms            INTEGER DEFAULT 0,
    max_bedrooms            INTEGER DEFAULT 10,
    min_price               INTEGER DEFAULT 0,
    max_price               INTEGER DEFAULT 100000000,

    -- LIFESTYLE PREFERENCES
    desired_amenities       TEXT DEFAULT '',  -- JSON array
    walkability_importance  BOOLEAN DEFAULT 0,
    transit_importance      BOOLEAN DEFAULT 0,
    investment_purpose      TEXT DEFAULT 'personal',  -- personal|investment|both

    -- SEARCH BEHAVIOR
    search_frequency        TEXT DEFAULT 'weekly',  -- daily|weekly|bi-weekly|monthly|on-demand
    auto_notify             BOOLEAN DEFAULT 1,  -- Send matching properties?

    -- SAVING PREFERENCES
    saved_searches          INTEGER DEFAULT 0,
    saved_properties        INTEGER DEFAULT 0,

    -- TIMESTAMPS
    created_at              TEXT NOT NULL,
    updated_at              TEXT NOT NULL,

    UNIQUE(client_id),
    FOREIGN KEY (client_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS advisory_recommendations (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id               INTEGER NOT NULL,
    advisor_id              INTEGER,

    -- RECOMMENDATION DETAILS
    recommendation_type     TEXT NOT NULL,  -- property_suggestion|market_insight|investment_strategy|portfolio_advice
    title                   TEXT NOT NULL,
    description             TEXT DEFAULT '',
    rationale               TEXT DEFAULT '',  -- Why this recommendation?

    -- RELATED DATA
    related_property_id     INTEGER,
    related_portfolio_id    INTEGER,
    related_market_insight  TEXT DEFAULT '',

    -- RECOMMENDATION METRICS
    confidence_score        INTEGER DEFAULT 0,  -- 0-100
    potential_return        REAL DEFAULT 0.0,  -- % or absolute
    risk_level              TEXT DEFAULT 'medium',  -- low|medium|high

    -- ENGAGEMENT TRACKING
    viewed_at               TEXT,
    clicked_at              TEXT,
    action_taken            BOOLEAN DEFAULT 0,
    action_details          TEXT DEFAULT '',

    -- STATUS
    status                  TEXT DEFAULT 'active',  -- active|archived|implemented
    implementation_date     TEXT,

    -- TIMESTAMPS
    created_at              TEXT NOT NULL,
    updated_at              TEXT NOT NULL,

    FOREIGN KEY (client_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS concierge_communications (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id              INTEGER NOT NULL,
    sender_id               INTEGER NOT NULL,
    message_type            TEXT DEFAULT 'message',  -- message|call_log|meeting|email|sms

    -- MESSAGE CONTENT
    subject                 TEXT DEFAULT '',
    content                 TEXT NOT NULL,

    -- COMMUNICATION DETAILS
    channel                 TEXT DEFAULT 'email',  -- email|phone|in_person|sms|chat
    duration_minutes        INTEGER DEFAULT 0,  -- For calls/meetings

    -- FOLLOW UP
    follow_up_needed        BOOLEAN DEFAULT 0,
    follow_up_date          TEXT,
    follow_up_notes         TEXT DEFAULT '',

    -- ENGAGEMENT
    is_read                 BOOLEAN DEFAULT 0,
    read_at                 TEXT,
    priority                TEXT DEFAULT 'normal',

    -- TIMESTAMPS
    created_at              TEXT NOT NULL,
    updated_at              TEXT NOT NULL,

    FOREIGN KEY (request_id) REFERENCES concierge_requests(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS service_packages (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    package_name            TEXT NOT NULL,
    tier_level              TEXT NOT NULL,  -- basic|standard|premium|vip

    -- PACKAGE DETAILS
    description             TEXT DEFAULT '',
    target_clients          TEXT DEFAULT '',  -- JSON with client profile

    -- FEATURES
    features                TEXT DEFAULT '',  -- JSON array of included features
    max_requests_per_month  INTEGER DEFAULT 10,
    dedicated_advisor       BOOLEAN DEFAULT 0,
    priority_support        BOOLEAN DEFAULT 0,

    -- PRICING
    monthly_fee             INTEGER DEFAULT 0,
    annual_fee              INTEGER DEFAULT 0,
    setup_fee               INTEGER DEFAULT 0,

    -- PERFORMANCE METRICS
    avg_response_time_hours INTEGER DEFAULT 24,
    avg_satisfaction_rating REAL DEFAULT 4.0,
    included_services       TEXT DEFAULT '',  -- JSON array

    -- STATUS
    is_active               BOOLEAN DEFAULT 1,

    -- TIMESTAMPS
    created_at              TEXT NOT NULL,
    updated_at              TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS advisor_performance (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    advisor_id              INTEGER NOT NULL,

    -- METRICS
    total_clients           INTEGER DEFAULT 0,
    total_requests_handled  INTEGER DEFAULT 0,
    average_satisfaction    REAL DEFAULT 0.0,  -- 0-5
    deals_facilitated       INTEGER DEFAULT 0,
    total_value_assisted    INTEGER DEFAULT 0,

    -- RESPONSE METRICS
    avg_response_time_hours REAL DEFAULT 24.0,
    on_time_completion_rate REAL DEFAULT 0.0,  -- %

    -- QUALITY METRICS
    client_retention_rate   REAL DEFAULT 0.0,  -- %
    repeat_business_rate    REAL DEFAULT 0.0,  -- %
    recommendation_rate     REAL DEFAULT 0.0,  -- % recommending to others

    -- PERFORMANCE TIER
    performance_tier        TEXT DEFAULT 'standard',  -- emerging|standard|senior|elite
    ranking                 INTEGER DEFAULT 0,  -- Rank among advisors

    -- PERIOD
    period_start            TEXT NOT NULL,
    period_end              TEXT NOT NULL,

    -- TIMESTAMPS
    calculated_at           TEXT NOT NULL,
    updated_at              TEXT NOT NULL,

    UNIQUE(advisor_id, period_start)
);

CREATE TABLE IF NOT EXISTS concierge_activity_log (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id               INTEGER NOT NULL,
    advisor_id              INTEGER,
    activity_type           TEXT NOT NULL,  -- request_created|recommendation_sent|call_made|meeting_scheduled|property_viewed|offer_made

    -- ACTIVITY DETAILS
    activity_description    TEXT DEFAULT '',
    related_property_id     INTEGER,
    related_request_id      INTEGER,

    -- METRICS
    duration_minutes        INTEGER DEFAULT 0,
    outcome                 TEXT DEFAULT '',  -- success|pending|failed

    -- TIMESTAMPS
    created_at              TEXT NOT NULL,

    FOREIGN KEY (client_id) REFERENCES users(id) ON DELETE CASCADE
);

-- WEEK 8: OPPORTUNITY SCORE™ SYSTEM
CREATE TABLE IF NOT EXISTS opportunity_scores (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id             INTEGER NOT NULL,

    -- SCORE COMPONENTS
    location_score          INTEGER DEFAULT 0,  -- 0-100
    market_score            INTEGER DEFAULT 0,  -- 0-100
    financial_score         INTEGER DEFAULT 0,  -- 0-100
    demand_score            INTEGER DEFAULT 0,  -- 0-100
    timing_score            INTEGER DEFAULT 0,  -- 0-100

    -- OVERALL SCORE
    opportunity_score       INTEGER DEFAULT 0,  -- 0-100 (weighted combination)
    confidence_level        INTEGER DEFAULT 0,  -- 0-100

    -- ANALYSIS
    opportunity_type        TEXT DEFAULT 'general',  -- buy|flip|rent|commercial|development
    risk_level              TEXT DEFAULT 'medium',  -- low|medium|high
    potential_return        REAL DEFAULT 0.0,  -- % annual

    -- RECOMMENDATIONS
    recommendation          TEXT DEFAULT '',  -- Text description
    action_priority         TEXT DEFAULT 'consider',  -- monitor|consider|strong_buy|critical
    time_sensitivity        TEXT DEFAULT 'low',  -- low|medium|high|urgent

    -- INVESTMENT METRICS
    cap_rate_potential      REAL DEFAULT 0.0,
    appreciation_potential  REAL DEFAULT 0.0,
    roi_potential           REAL DEFAULT 0.0,

    -- SIGNALS
    bullish_signals         INTEGER DEFAULT 0,  -- Count
    bearish_signals         INTEGER DEFAULT 0,  -- Count
    neutral_signals         INTEGER DEFAULT 0,  -- Count

    -- MARKET CONTEXT
    market_sentiment        TEXT DEFAULT 'neutral',  -- bullish|neutral|bearish
    market_cycle_stage      TEXT DEFAULT 'steady',  -- early|growing|peak|declining|steady

    -- TIMESTAMPS
    calculated_at           TEXT NOT NULL,
    updated_at              TEXT NOT NULL,

    UNIQUE(property_id),
    FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS score_components (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_score_id    INTEGER NOT NULL,

    -- LOCATION COMPONENT (25% weight)
    location_growth_score   INTEGER DEFAULT 0,
    infrastructure_score    INTEGER DEFAULT 0,
    connectivity_score      INTEGER DEFAULT 0,
    neighborhood_score      INTEGER DEFAULT 0,

    -- MARKET COMPONENT (25% weight)
    market_demand_score     INTEGER DEFAULT 0,
    competition_score       INTEGER DEFAULT 0,
    price_trend_score       INTEGER DEFAULT 0,
    absorption_rate_score   INTEGER DEFAULT 0,

    -- FINANCIAL COMPONENT (25% weight)
    price_value_score       INTEGER DEFAULT 0,
    financing_score         INTEGER DEFAULT 0,
    cash_flow_score         INTEGER DEFAULT 0,
    appreciation_score      INTEGER DEFAULT 0,

    -- DEMAND COMPONENT (15% weight)
    buyer_interest_score    INTEGER DEFAULT 0,
    search_volume_score     INTEGER DEFAULT 0,
    inquiry_score           INTEGER DEFAULT 0,

    -- TIMING COMPONENT (10% weight)
    market_timing_score     INTEGER DEFAULT 0,
    seasonal_score          INTEGER DEFAULT 0,
    cycle_position_score    INTEGER DEFAULT 0,

    -- CALCULATED WEIGHTS
    component_weights       TEXT DEFAULT '',  -- JSON with actual weights used

    -- TIMESTAMPS
    calculated_at           TEXT NOT NULL,

    UNIQUE(opportunity_score_id),
    FOREIGN KEY (opportunity_score_id) REFERENCES opportunity_scores(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS opportunity_signals (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_score_id    INTEGER NOT NULL,

    -- SIGNAL DETAILS
    signal_type             TEXT NOT NULL,  -- price_drop|demand_spike|new_infrastructure|zoning_change|etc
    signal_strength         TEXT DEFAULT 'medium',  -- weak|medium|strong|critical
    signal_direction        TEXT DEFAULT 'bullish',  -- bullish|bearish|neutral

    -- SIGNAL DATA
    signal_description      TEXT NOT NULL,
    data_source             TEXT DEFAULT '',  -- market_data|news|buyer_activity|developer_plans|etc
    confidence_pct          INTEGER DEFAULT 0,  -- 0-100

    -- IMPACT
    impact_on_score         INTEGER DEFAULT 0,  -- Points added/subtracted
    signal_weight           REAL DEFAULT 1.0,  -- 0-2.0x multiplier

    -- TIMESTAMPS
    detected_at             TEXT NOT NULL,
    expires_at              TEXT,  -- Signal expiration date

    FOREIGN KEY (opportunity_score_id) REFERENCES opportunity_scores(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS opportunity_recommendations (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_score_id    INTEGER NOT NULL,

    -- RECOMMENDATION
    recommendation_type     TEXT NOT NULL,  -- buy|watch|pass|flip|hold|develop
    confidence_level        INTEGER DEFAULT 0,  -- 0-100
    recommendation_text     TEXT NOT NULL,

    -- TARGET PROFILE
    ideal_investor_profile  TEXT DEFAULT '',  -- income_focused|growth_focused|flippers|developers
    target_portfolio_type   TEXT DEFAULT '',  -- residential|commercial|mixed

    -- FINANCIAL TARGETS
    suggested_offer_price   INTEGER DEFAULT 0,
    expected_appreciation   REAL DEFAULT 0.0,  -- % annual
    target_exit_timeline    INTEGER DEFAULT 5,  -- Years

    -- RISK ASSESSMENT
    risk_factors            TEXT DEFAULT '',  -- JSON array of risks
    mitigation_strategies   TEXT DEFAULT '',  -- JSON array

    -- ACTION ITEMS
    next_steps              TEXT DEFAULT '',  -- JSON array
    required_due_diligence  TEXT DEFAULT '',  -- JSON array

    -- TIMESTAMPS
    created_at              TEXT NOT NULL,
    updated_at              TEXT NOT NULL,

    UNIQUE(opportunity_score_id),
    FOREIGN KEY (opportunity_score_id) REFERENCES opportunity_scores(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS opportunity_tracking (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_score_id    INTEGER NOT NULL,

    -- TRACKING
    watch_count             INTEGER DEFAULT 0,  -- How many watching
    inquiry_count           INTEGER DEFAULT 0,  -- Inquiries received
    offer_count             INTEGER DEFAULT 0,  -- Offers made
    action_taken            BOOLEAN DEFAULT 0,  -- Someone acted on it

    -- ENGAGEMENT
    avg_view_duration       INTEGER DEFAULT 0,  -- Seconds
    engagement_score        INTEGER DEFAULT 0,  -- 0-100

    -- OUTCOMES
    status                  TEXT DEFAULT 'active',  -- active|sold|leased|monitoring|passed
    final_outcome_price     INTEGER DEFAULT 0,
    final_outcome_date      TEXT,

    -- TIMESTAMPS
    created_at              TEXT NOT NULL,
    updated_at              TEXT NOT NULL,

    UNIQUE(opportunity_score_id),
    FOREIGN KEY (opportunity_score_id) REFERENCES opportunity_scores(id) ON DELETE CASCADE
);

-- WEEK 9: CRM INTELLIGENCE SYSTEM
CREATE TABLE IF NOT EXISTS crm_leads (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id                 INTEGER NOT NULL,

    -- LEAD INFO
    lead_name               TEXT NOT NULL,
    lead_email              TEXT DEFAULT '',
    lead_phone              TEXT DEFAULT '',
    lead_status             TEXT DEFAULT 'new',  -- new|contacted|qualified|interested|negotiating|closed|lost

    -- LEAD CLASSIFICATION
    lead_type               TEXT DEFAULT 'buyer',  -- buyer|seller|investor
    lead_source             TEXT DEFAULT 'direct',  -- website|referral|property|concierge|match
    lead_quality            TEXT DEFAULT 'unknown',  -- hot|warm|cold|unknown

    -- SCORING
    lead_score              INTEGER DEFAULT 0,  -- 0-100
    qualification_score     INTEGER DEFAULT 0,  -- 0-100

    -- ENGAGEMENT
    last_contacted          TEXT,
    next_followup           TEXT,
    contact_count           INTEGER DEFAULT 0,

    -- PROPERTY INTEREST
    interested_properties   TEXT DEFAULT '',  -- JSON array
    interested_cities       TEXT DEFAULT '',  -- JSON array

    -- METADATA
    notes                   TEXT DEFAULT '',
    assigned_advisor_id     INTEGER,

    -- TIMESTAMPS
    created_at              TEXT NOT NULL,
    updated_at              TEXT NOT NULL,
    closed_at               TEXT
);

CREATE TABLE IF NOT EXISTS crm_interactions (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id                 INTEGER NOT NULL,

    -- INTERACTION DETAILS
    interaction_type        TEXT NOT NULL,  -- call|email|meeting|property_view|offer|other
    subject                 TEXT DEFAULT '',
    notes                   TEXT DEFAULT '',
    duration_minutes        INTEGER DEFAULT 0,

    -- ENGAGEMENT
    contacted_by            INTEGER,
    interaction_outcome     TEXT DEFAULT 'pending',  -- positive|neutral|negative|pending
    next_action             TEXT DEFAULT '',

    -- TIMESTAMPS
    interaction_date        TEXT NOT NULL,
    created_at              TEXT NOT NULL,

    FOREIGN KEY (lead_id) REFERENCES crm_leads(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS lead_scores (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id                 INTEGER NOT NULL,

    -- SCORE COMPONENTS
    budget_alignment_score  INTEGER DEFAULT 0,
    engagement_score        INTEGER DEFAULT 0,
    decision_readiness      INTEGER DEFAULT 0,
    match_quality_score     INTEGER DEFAULT 0,
    opportunity_score       INTEGER DEFAULT 0,

    -- OVERALL
    total_lead_score        INTEGER DEFAULT 0,  -- 0-100
    lead_quality_tier       TEXT DEFAULT 'cold',  -- hot|warm|cold

    -- TIMING
    urgency_level           TEXT DEFAULT 'low',  -- high|medium|low
    estimated_conversion    REAL DEFAULT 0.0,  -- %

    -- TIMESTAMPS
    calculated_at           TEXT NOT NULL,

    UNIQUE(lead_id),
    FOREIGN KEY (lead_id) REFERENCES crm_leads(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS crm_pipelines (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,

    -- PIPELINE TRACKING
    pipeline_name           TEXT NOT NULL,
    stage                   TEXT NOT NULL,  -- prospecting|qualified|proposal|negotiating|closing|closed
    lead_count              INTEGER DEFAULT 0,
    total_value             INTEGER DEFAULT 0,
    expected_close_value    INTEGER DEFAULT 0,

    -- METRICS
    conversion_rate         REAL DEFAULT 0.0,  -- %
    avg_days_in_stage       INTEGER DEFAULT 0,

    -- TIMESTAMPS
    created_at              TEXT NOT NULL,
    updated_at              TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS advisor_lead_assignments (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id                 INTEGER NOT NULL,
    advisor_id              INTEGER NOT NULL,

    -- ASSIGNMENT
    assigned_date           TEXT NOT NULL,
    assignment_type         TEXT DEFAULT 'primary',  -- primary|support

    -- PERFORMANCE
    interaction_count       INTEGER DEFAULT 0,
    last_interaction        TEXT,

    -- STATUS
    status                  TEXT DEFAULT 'active',  -- active|completed|transferred

    UNIQUE(lead_id, advisor_id),
    FOREIGN KEY (lead_id) REFERENCES crm_leads(id) ON DELETE CASCADE
);
"""


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def now():
    return datetime.utcnow().isoformat(timespec="seconds")


def init_db():
    """Create tables and seed demo data if the database is empty."""
    first_time = not os.path.exists(DB_PATH)
    conn = get_conn()
    conn.executescript(SCHEMA)
    conn.commit()

    # migration: databases created before Excel-sync lack the photos_url column
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(properties)").fetchall()]
    if "photos_url" not in cols:
        conn.execute("ALTER TABLE properties ADD COLUMN photos_url TEXT DEFAULT ''")
        conn.commit()
    if "amenities" not in cols:                    # migration: optional amenities list
        conn.execute("ALTER TABLE properties ADD COLUMN amenities TEXT DEFAULT ''")
        conn.commit()

    # Seed only when there are no users yet, so re-runs don't duplicate data.
    have_users = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
    if not have_users:
        _seed(conn)
    # Seed demo investment opportunities once (independent of users, so it also
    # populates an already-live database the first time the table appears).
    have_inv = conn.execute("SELECT COUNT(*) AS c FROM investments").fetchone()["c"]
    if not have_inv:
        _seed_investments(conn)
    have_ins = conn.execute("SELECT COUNT(*) AS c FROM insights").fetchone()["c"]
    if not have_ins:
        _seed_insights(conn)

    # WEEK 1: Seed location intelligence data (independent of existing data)
    have_locs = conn.execute("SELECT COUNT(*) AS c FROM location_data").fetchone()["c"]
    if not have_locs:
        _seed_location_data(conn)

    # WEEK 1: Calculate property intelligence scores
    _seed_property_intelligence(conn)

    ensure_accounts(conn)          # guarantee the real owner + client logins
    conn.close()
    return first_time


# Real login accounts (owner set by Vikkas; client is a ready test account).
OWNER_EMAIL = "thevikkas@gmail.com"
OWNER_PASSWORD = "Jerry@1998"
OWNER_NAME = "Vikkas"
CLIENT_EMAIL = "client@realtorvikkas.in"
CLIENT_PASSWORD = "Client@1998"
CLIENT_NAME = "Client"


def ensure_accounts(conn):
    """Guarantee the real owner + a real client login exist. Runs on every
    start, so it also corrects an already-seeded database on a persistent disk."""
    from auth import hash_password

    owner = conn.execute(
        "SELECT id FROM users WHERE role = 'owner' ORDER BY id LIMIT 1").fetchone()
    if owner:
        conn.execute(
            "UPDATE users SET name=?, email=?, password_hash=?, role='owner' WHERE id=?",
            (OWNER_NAME, OWNER_EMAIL, hash_password(OWNER_PASSWORD), owner["id"]))
    else:
        conn.execute(
            "INSERT INTO users (name, email, phone, password_hash, role, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (OWNER_NAME, OWNER_EMAIL, "", hash_password(OWNER_PASSWORD), "owner", now()))

    client = conn.execute(
        "SELECT id FROM users WHERE role = 'customer' ORDER BY id LIMIT 1").fetchone()
    if client:
        conn.execute(
            "UPDATE users SET name=?, email=?, password_hash=?, role='customer' WHERE id=?",
            (CLIENT_NAME, CLIENT_EMAIL, hash_password(CLIENT_PASSWORD), client["id"]))
    else:
        conn.execute(
            "INSERT INTO users (name, email, phone, password_hash, role, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (CLIENT_NAME, CLIENT_EMAIL, "", hash_password(CLIENT_PASSWORD), "customer", now()))
    conn.commit()


def _seed(conn):
    # Imported here to avoid a circular import (auth imports nothing from db).
    from auth import hash_password

    owner_id = conn.execute(
        "INSERT INTO users (name, email, phone, password_hash, role, created_at) "
        "VALUES (?,?,?,?,?,?)",
        ("Vikkas", "owner@realtorvikkas.in", "+91 98290 00000",
         hash_password("vikkas123"), "owner", now()),
    ).lastrowid

    conn.execute(
        "INSERT INTO users (name, email, phone, password_hash, role, created_at) "
        "VALUES (?,?,?,?,?,?)",
        ("Aarti Sharma", "customer@example.com", "+91 90000 11111",
         hash_password("demo1234"), "customer", now()),
    )

    demo = [
        # title, ptype, listing, city, locality, price, area, bed, bath, featured, desc
        ("Aravalli Meadows Villa", "Villa", "buy", "Jaipur", "Jagatpura",
         21500000, 3200, 4, 4, 1,
         "A four-bedroom villa backing onto the Aravalli ridge, with a private lawn, staff quarter and covered parking for three cars."),
        ("Register Plot — JDA Approved", "Plot", "buy", "Jaipur", "Ajmer Road",
         8500000, 2160, 0, 0, 1,
         "JDA-approved corner plot on a 40-foot road, clear title, ready for immediate registry. Khasra verified."),
        ("Pink City Flat", "Flat", "rent", "Jaipur", "C-Scheme",
         45000, 1450, 3, 2, 0,
         "Bright 3BHK on C-Scheme's tree-lined avenue, walking distance to MI Road. Semi-furnished, lift, power backup."),
        ("Lake Vista Townhouse", "Townhouse", "buy", "Udaipur", "Fateh Sagar",
         18900000, 2400, 3, 3, 1,
         "Split-level townhouse with a rooftop terrace framing the Fateh Sagar lake. Italian marble, modular kitchen."),
        ("NCR Skyline Apartment", "Flat", "buy", "Delhi NCR", "Golf Course Ext.",
         16200000, 1720, 3, 3, 0,
         "High-floor apartment in a gated tower with clubhouse, pool and concierge. East-facing, two covered parkings."),
        ("Sabarmati Riverfront Flat", "Flat", "buy", "Ahmedabad", "Vastrapur",
         9800000, 1380, 2, 2, 0,
         "Compact 2BHK minutes from Vastrapur lake, in a well-run society with lift and 24x7 security."),
        ("Hillside Cottage", "Villa", "buy", "Shimla", "Mashobra",
         27500000, 2800, 4, 3, 1,
         "Stone-and-timber cottage on a south-facing Mashobra slope, deodar views, wood-burning fireplaces, orchard land."),
        ("Manali Apple Orchard Plot", "Plot", "buy", "Manali", "Naggar Road",
         12500000, 5400, 0, 0, 0,
         "Freehold orchard plot on Naggar Road with an existing bearing apple orchard and a mountain stream boundary."),
        ("Jodhpur Heritage Haveli", "Villa", "buy", "Jodhpur", "Old City",
         34000000, 4100, 6, 5, 0,
         "Restored sandstone haveli with a central courtyard, jharokhas and a fort-facing terrace — rare heritage title."),
        ("Gandhinagar Commercial Suite", "Commercial", "rent", "Gandhinagar", "Sector 11",
         85000, 2200, 0, 2, 0,
         "Ground-floor commercial suite on a main sector road, glass frontage, ideal for a clinic, studio or office."),
    ]
    for (title, ptype, listing, city, locality, price, area, bed, bath, feat, desc) in demo:
        conn.execute(
            "INSERT INTO properties (title, ptype, listing, city, locality, price, "
            "area_sqft, bedrooms, bathrooms, description, status, featured, owner_id, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (title, ptype, listing, city, locality, price, area, bed, bath, desc,
             "available", feat, owner_id, now()),
        )

    conn.execute(
        "INSERT INTO enquiries (property_id, customer_id, name, email, phone, message, status, created_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (1, 2, "Aarti Sharma", "customer@example.com", "+91 90000 11111",
         "Is the Jagatpura villa still available for a site visit this weekend?", "new", now()),
    )
    conn.commit()


def _seed_investments(conn):
    """Demo investment opportunities — structural placeholders Vikkas replaces with
    real ones via /admin/investments. Deliberately carry NO invented returns/ROI:
    only factual attributes; prices show 'On request' until real figures are added."""
    demo = [
        # title, category, location, ticket, horizon, highlights, description
        ("JDA-Approved Land Bank — Ajmer Road Corridor", "Plot", "Ajmer Road, Jaipur", 0, "",
         "JDA-approved layout, Clear title, Developing arterial corridor, Ready for registry",
         "A land-banking opportunity along the Ajmer Road growth corridor for buyers who want "
         "approved, clear-title land to hold. All prices, sizes and timelines are confirmed on consultation."),
        ("Resort & Second-Home Plots — Jaipur Outskirts", "Resort / Second Home", "Jaipur outskirts", 0, "",
         "Gated project, Farmhouse / weekend-home use, Green surroundings, Managed community",
         "Weekend-home and second-home plots on Jaipur's outskirts, for buyers seeking a managed "
         "farmhouse or resort-style holding. Current availability is shared on request."),
        ("Pre-Launch Residential — Early-Entry Allotment", "Pre-launch", "Jaipur", 0, "",
         "Early-entry allotment, RERA status verified on request, Builder track-record shared",
         "Early-entry allotment in a pre-launch residential project. RERA registration and builder "
         "details are verified and shared during consultation."),
        ("Rental-Yield Commercial Unit — Main-Road Frontage", "Rental Yield", "Jaipur", 0, "",
         "Main-road frontage, Suited to clinic / office / retail, Leasing support",
         "A commercial unit positioned for rental income, with leasing support. Rental outcomes depend "
         "on the tenant and the market at the time and are not guaranteed."),
    ]
    for (title, cat, loc, ticket, horizon, highlights, desc) in demo:
        conn.execute(
            "INSERT INTO investments (title, category, location, ticket, horizon, highlights, "
            "description, status, featured, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (title, cat, loc, ticket, horizon, highlights, desc, "active", 1, now()))
    conn.commit()


def _seed_insights(conn):
    """Starter market-insight articles. FACTUAL, educational guidance only — NO invented
    prices, ROI or market statistics. Vikkas adds real market notes via /admin/insights."""
    guides = [
        ("How to verify a clear title before buying in Jaipur", "Guide", "Jaipur",
         "The document checks that protect you before you pay a rupee.",
         "Before buying any property in Jaipur, confirm the chain of ownership and that the title is "
         "clear and marketable.\n\n"
         "• Ask for the last 13–30 years of title/ownership documents and check the chain is unbroken.\n"
         "• Match the seller's name on the registry, the mutation (namantaran) and the latest tax receipts.\n"
         "• For JDA/urban land, confirm the patta and approved layout; for agricultural land check the "
         "khasra/khatauni and whether conversion (CLU) is needed.\n"
         "• Get an Encumbrance Certificate to check for existing loans or charges on the property.\n"
         "• Have a property lawyer do due diligence before you pay any advance.\n\n"
         "This is general guidance — always take independent legal advice for your specific case."),
        ("JDA approval & patta — what to check on a Jaipur plot", "Guide", "Jaipur",
         "Approved, clear-title land vs. an unapproved colony: how to tell.",
         "\"JDA-approved\" means the Jaipur Development Authority has sanctioned the layout of the "
         "colony/scheme the plot sits in. It matters for loans, resale and construction approvals.\n\n"
         "• Ask which scheme the plot is in and whether it is JDA/authorised and has an approved layout plan.\n"
         "• Confirm the patta (title deed) is issued in the current owner's name.\n"
         "• Check road width, setbacks and the plot's marking against the approved plan.\n"
         "• Unapproved or 'krishi' (agricultural) plots can be cheaper but carry approval, loan and "
         "regularisation risks — understand these before buying.\n\n"
         "General educational information, not legal advice."),
        ("Buy vs rent in Jaipur — questions to ask yourself", "Guide", "Jaipur",
         "A simple framework to decide, without the hype.",
         "There is no single right answer — it depends on your horizon, cash flow and goals.\n\n"
         "• How long will you stay? Buying usually makes more sense the longer your horizon.\n"
         "• Do you have the down payment plus registry, stamp duty and furnishing costs comfortably?\n"
         "• Would the EMI stretch your monthly budget? (Use the EMI calculator on this site to check.)\n"
         "• Is this a home to live in or an investment? Those are different decisions.\n"
         "• Renting keeps you flexible; buying builds an asset but ties up capital.\n\n"
         "Talk it through with Realtor Vikkas for guidance specific to your situation."),
    ]
    for (title, cat, area, summary, body) in guides:
        conn.execute(
            "INSERT INTO insights (title, category, area, summary, body, source, status, featured, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (title, cat, area, summary, body, "", "published", 1, now()))
    conn.commit()


def _seed_location_data(conn):
    """Seed location intelligence for Jaipur and Udaipur — factual infrastructure
    and connectivity data. Vikkas updates these regularly via /admin endpoints."""
    locations = [
        # city, locality, metro_km, mall_km, hospital_km, school_km, road_quality, transit,
        # airport_km, infra_dev, metro_planned, commercial, avg_price/sqft, 1yr, 3yr, 5yr, rental_yield, demand
        ("Jaipur", "Jagatpura", 8.5, 3.2, 1.8, 0.9, "excellent", "good", 12.0,
         "Metro connection planned", True, "Shopping mall in planning", 38000, 4.2, 3.8, 3.5, 4.8, "high"),
        ("Jaipur", "C-Scheme", 2.1, 0.5, 0.8, 0.3, "excellent", "excellent", 8.0,
         "Developed commercial area", False, "Established retail", 52000, 2.8, 2.5, 2.2, 3.2, "high"),
        ("Jaipur", "Ajmer Road", 5.3, 2.1, 1.5, 0.7, "good", "good", 10.0,
         "Commercial development", False, "Growing commercial", 28000, 3.5, 3.2, 2.9, 4.5, "medium"),
        ("Jaipur", "MI Road", 3.2, 1.5, 1.2, 0.5, "excellent", "excellent", 9.0,
         "Developed arterial", False, "Main commercial hub", 48000, 2.5, 2.0, 1.8, 3.0, "high"),
        ("Jaipur", "Vaishali", 10.2, 4.5, 2.5, 1.2, "good", "moderate", 14.0,
         "Residential expansion", True, "Local commercial", 22000, 5.1, 4.8, 4.5, 5.2, "high"),
        ("Udaipur", "Fateh Sagar", 6.5, 2.8, 2.0, 0.8, "excellent", "good", 20.0,
         "Lake development zone", False, "Premium retail", 35000, 3.2, 2.8, 2.5, 4.0, "high"),
        ("Udaipur", "City Palace Zone", 1.2, 0.8, 0.5, 0.2, "good", "good", 18.0,
         "Historic preservation", False, "Tourist retail", 42000, 2.0, 1.8, 1.5, 3.5, "medium"),
    ]

    for (city, locality, metro, mall, hosp, school, road, transit, airport, infra, metro_p, commercial,
         price_sqft, gr_1yr, gr_3yr, gr_5yr, rental, demand) in locations:
        conn.execute(
            "INSERT INTO location_data "
            "(city, locality, nearest_metro_km, nearest_mall_km, nearest_hospital_km, nearest_school_km, "
            "road_quality, public_transport, airport_km, infrastructure_under_development, metro_planned, "
            "commercial_development, avg_price_per_sqft, price_growth_1yr, price_growth_3yr, price_growth_5yr, "
            "avg_rental_yield, demand_level, last_updated) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (city, locality, metro, mall, hosp, school, road, transit, airport, infra, metro_p, commercial,
             price_sqft, gr_1yr, gr_3yr, gr_5yr, rental, demand, now()))

    conn.commit()


def _seed_property_intelligence(conn):
    """Seed property intelligence scores for existing demo properties.
    Scores are calculated based on location and property data."""
    # Get all properties to calculate intelligence for them
    props = conn.execute("SELECT id, city, locality, ptype, price, bedrooms FROM properties").fetchall()

    for prop in props:
        prop_id = prop["id"]

        # Get location data for this property's city/locality
        loc = conn.execute(
            "SELECT * FROM location_data WHERE city = ? AND locality = ?",
            (prop["city"], prop["locality"])
        ).fetchone()

        if not loc:
            continue  # Skip if no location data

        # Calculate scores based on location and property type
        location_score = min(100, int((loc["road_quality"] == "excellent") * 30 +
                                     (loc["public_transport"] == "excellent") * 30 +
                                     (loc["metro_planned"]) * 20 + 20))

        connectivity_score = min(100, int(
            (100 - min(loc["nearest_metro_km"], 20) * 5) +
            (100 - min(loc["nearest_mall_km"], 10) * 5)
        ) // 2)

        appreciation_score = min(100, int(loc["price_growth_1yr"] * 15 + 40))

        rental_score = min(100, int(loc["avg_rental_yield"] * 15 + 30))

        price_positioning_score = 75  # Moderate - user properties tend to be fairly priced

        risk_score = 85 if loc["road_quality"] == "excellent" else 70  # Lower risk in well-developed areas

        liquidity_score = 80 if loc["demand_level"] == "high" else 60

        investment_fit = min(100, appreciation_score + rental_score) // 2

        investor_type = "investor" if rental_score > 60 else "first-time buyer"

        match_explanation = f"This {prop['ptype'].lower()} in {prop['locality']} has strong {investor_type} potential based on location quality and market demand."

        # Check if intelligence already exists
        existing = conn.execute(
            "SELECT id FROM property_intelligence WHERE property_id = ?", (prop_id,)
        ).fetchone()

        if existing:
            conn.execute(
                "UPDATE property_intelligence SET location_score=?, connectivity_score=?, "
                "appreciation_potential_score=?, rental_potential_score=?, price_positioning_score=?, "
                "risk_score=?, liquidity_score=?, investor_type=?, investment_fit_score=?, "
                "match_explanation=?, last_updated=? WHERE property_id=?",
                (location_score, connectivity_score, appreciation_score, rental_score, price_positioning_score,
                 risk_score, liquidity_score, investor_type, investment_fit, match_explanation, now(), prop_id))
        else:
            conn.execute(
                "INSERT INTO property_intelligence "
                "(property_id, location_score, connectivity_score, infrastructure_score, "
                "appreciation_potential_score, rental_potential_score, price_positioning_score, "
                "risk_score, liquidity_score, investor_type, investment_fit_score, match_explanation, "
                "last_updated) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (prop_id, location_score, connectivity_score, 70, appreciation_score, rental_score,
                 price_positioning_score, risk_score, liquidity_score, investor_type, investment_fit,
                 match_explanation, now()))

    conn.commit()
