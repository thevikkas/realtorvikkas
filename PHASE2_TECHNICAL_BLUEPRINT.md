# 🏗️ PHASE 2: TECHNICAL BLUEPRINT
## Complete 10-System Architecture Design

**Status**: Ready for Implementation
**Timeline**: 12 weeks (3 weeks per system + overlap)
**Dependencies**: None - all systems can integrate incrementally
**Breaking Changes**: ZERO (all additions, no modifications to existing routes)

---

## 🗂️ SYSTEM 1: PROPERTY INTELLIGENCE ENGINE

### **Purpose**
Create a proprietary scoring and analysis framework that helps investors understand property investment potential.

### **Data Model**

```python
# NEW TABLE: property_intelligence
CREATE TABLE IF NOT EXISTS property_intelligence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER NOT NULL UNIQUE,
    
    # LOCATION QUALITY (0-100)
    location_score INTEGER DEFAULT 0,
    connectivity_score INTEGER DEFAULT 0,
    infrastructure_score INTEGER DEFAULT 0,
    
    # INVESTMENT METRICS (0-100)
    price_positioning_score INTEGER DEFAULT 0,
    rental_potential_score INTEGER DEFAULT 0,
    appreciation_potential_score INTEGER DEFAULT 0,
    
    # RISK & LIQUIDITY (0-100)
    risk_score INTEGER DEFAULT 0,
    liquidity_score INTEGER DEFAULT 0,
    
    # ANALYSIS FIELDS
    area_growth_trend TEXT DEFAULT '',  -- "rising" | "stable" | "declining"
    area_growth_pct REAL DEFAULT 0.0,   -- YoY growth percentage
    comparable_price REAL DEFAULT 0,    -- Average price in locality
    price_variance REAL DEFAULT 0.0,    -- % above/below comparable
    
    # INVESTOR PROFILE MATCH (text explanation)
    investor_type TEXT DEFAULT '',      -- "First-time buyer" | "Investor" | "NRI" etc.
    investment_fit_score INTEGER DEFAULT 0,
    match_explanation TEXT DEFAULT '',
    
    # SENTIMENT & NOTES
    analyst_notes TEXT DEFAULT '',
    last_updated TEXT NOT NULL,
    
    FOREIGN KEY (property_id) REFERENCES properties(id)
);

# NEW TABLE: location_data (for area intelligence)
CREATE TABLE IF NOT EXISTS location_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    city TEXT NOT NULL,
    locality TEXT NOT NULL,
    
    # INFRASTRUCTURE
    nearest_metro_km REAL DEFAULT 0,
    nearest_mall_km REAL DEFAULT 0,
    nearest_hospital_km REAL DEFAULT 0,
    nearest_school_km REAL DEFAULT 0,
    
    # CONNECTIVITY
    road_quality TEXT DEFAULT '',       -- "excellent" | "good" | "moderate" | "poor"
    public_transport TEXT DEFAULT '',   -- "excellent" | "good" | "limited"
    airport_km REAL DEFAULT 0,
    
    # GROWTH INDICATORS
    infrastructure_under_development TEXT DEFAULT '',
    metro_planned BOOLEAN DEFAULT 0,
    commercial_development TEXT DEFAULT '',
    
    # MARKET DATA
    avg_price_per_sqft INTEGER DEFAULT 0,
    price_growth_1yr REAL DEFAULT 0.0,
    price_growth_3yr REAL DEFAULT 0.0,
    price_growth_5yr REAL DEFAULT 0.0,
    
    # DEMAND INDICATORS
    avg_rental_yield REAL DEFAULT 0.0,
    demand_level TEXT DEFAULT 'medium',  -- "high" | "medium" | "low"
    
    last_updated TEXT NOT NULL,
    UNIQUE (city, locality)
);
```

### **Route Architecture**

```python
# NEW ROUTES

GET /property/<id>/intelligence
  → Returns: PropertyIntelligence object
  → Shows: All scores, analysis, investor fit

GET /api/property/<id>/scores
  → Returns: JSON with all scores (for API integrations)
  → Example: {"location_score": 85, "rental_potential": 72, ...}

GET /location/<city>/<locality>/data
  → Returns: LocationData for area intelligence
  → Shows: Infrastructure, connectivity, growth, price trends

POST /admin/property/<id>/intelligence (owner only)
  → Update property intelligence scores & analysis
  → Fields: All scores, analyst notes, investor type

POST /admin/location/<city>/<locality>/data (owner only)
  → Update location data for area
  → Fields: Infrastructure, connectivity, growth metrics
```

### **Scoring Formula** (Proprietary)

```
LOCATION_SCORE = (
  connectivity_factor * 40% +
  infrastructure_factor * 35% +
  growth_factor * 25%
)

RENTAL_POTENTIAL = (
  avg_area_rental_yield * 50% +
  property_size_demand_factor * 30% +
  location_accessibility * 20%
)

APPRECIATION_POTENTIAL = (
  historical_growth_rate * 40% +
  infrastructure_under_dev_factor * 35% +
  area_demand_factor * 25%
)

PROPERTY_OPPORTUNITY_SCORE = (
  location_score * 25% +
  rental_potential_score * 20% +
  appreciation_potential_score * 25% +
  price_positioning_score * 15% +
  investor_fit_score * 15%
)

Score Range: 0-100 (displayed as visual gauge)
```

### **Implementation Priority**: HIGH
**Estimated Effort**: 3-4 weeks
**Dependencies**: None (builds on existing property data)

---

## 💰 SYSTEM 2: REAL ESTATE INVESTMENT OS

### **Purpose**
Complete investment calculator suite for scenario modeling, comparison, and ROI analysis.

### **Data Model**

```python
# NEW TABLE: investment_calculations
CREATE TABLE IF NOT EXISTS investment_calculations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER,                        # Optional (for single property)
    user_id INTEGER,                           # Who created this calculation
    
    # BASIC INPUTS
    property_name TEXT NOT NULL,
    investment_amount INTEGER NOT NULL,        # Total investment in INR
    down_payment INTEGER NOT NULL,
    loan_amount INTEGER DEFAULT 0,
    
    # LOAN DETAILS (if applicable)
    loan_rate REAL DEFAULT 0.0,                # Interest rate %
    loan_term_years INTEGER DEFAULT 0,
    emi REAL DEFAULT 0,                        # Monthly EMI
    
    # INCOME ASSUMPTIONS
    rental_income_monthly INTEGER DEFAULT 0,
    rental_growth_annual REAL DEFAULT 0.0,     # Annual growth %
    
    # APPRECIATION ASSUMPTIONS
    property_appreciation_annual REAL DEFAULT 0.0,
    holding_period_years INTEGER DEFAULT 0,
    estimated_resale_value INTEGER DEFAULT 0,
    
    # EXPENSES
    annual_maintenance INTEGER DEFAULT 0,
    annual_property_tax INTEGER DEFAULT 0,
    annual_insurance INTEGER DEFAULT 0,
    annual_vacancy_loss REAL DEFAULT 0.0,      # % of rental income
    
    # CALCULATED RESULTS
    total_rental_income INTEGER DEFAULT 0,     # Over holding period
    total_emi_paid INTEGER DEFAULT 0,
    total_expenses INTEGER DEFAULT 0,
    total_return INTEGER DEFAULT 0,
    roi_percentage REAL DEFAULT 0.0,
    cagr REAL DEFAULT 0.0,
    cash_on_cash_return REAL DEFAULT 0.0,
    
    # SCENARIOS
    scenario_type TEXT NOT NULL,               # "conservative" | "base" | "optimistic"
    
    created_at TEXT NOT NULL,
    FOREIGN KEY (property_id) REFERENCES properties(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

# NEW TABLE: comparison_sets
CREATE TABLE IF NOT EXISTS comparison_sets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    
    # PROPERTIES BEING COMPARED (JSON array of calc IDs)
    calculations_json TEXT NOT NULL,
    
    # COMPARISON INSIGHTS
    best_roi_calc_id INTEGER,
    best_rental_calc_id INTEGER,
    most_liquid_calc_id INTEGER,
    
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

### **Route Architecture**

```python
# NEW ROUTES

GET /calculator
  → Shows: Investment calculator form
  → Inputs: Investment amount, location, property type, assumptions
  → Supports: Residential, Commercial, Land, Plots, Villas, Resort

POST /api/calculate
  → Accepts: Investment parameters
  → Returns: Calculated results (all metrics)
  → Saves: User's calculation for comparison

GET /calculation/<calc_id>
  → Returns: Full calculation with all scenarios
  → Shows: Conservative, Base, Optimistic projections
  → Visual: Charts, gauge indicators, breakdown tables

GET /compare
  → Shows: User's saved calculations
  → Features: Side-by-side comparison
  → Sorting: By ROI, rental yield, CAGR, total return

POST /comparison/create
  → Create named comparison set
  → Add multiple calculations to compare

GET /comparison/<comp_id>
  → Show: Side-by-side analysis
  → Insights: Which is best for what purpose
  → Export: PDF report option

GET /api/scenarios/<property_id>
  → Returns: Pre-calculated scenarios for property
  → Shows: Conservative (2% growth), Base (4%), Optimistic (6%)
```

### **Calculation Engine** (Core Logic)

```python
def calculate_investment(inputs):
    """Core calculation engine"""
    
    # Monthly EMI
    if inputs['loan_amount'] > 0:
        emi = calculate_emi(
            principal=inputs['loan_amount'],
            rate=inputs['loan_rate'],
            years=inputs['loan_term_years']
        )
    else:
        emi = 0
    
    # Rental income projection
    rental_income = []
    rental = inputs['rental_income_monthly']
    for year in range(inputs['holding_period_years']):
        annual_rental = rental * 12 * (1 + inputs['rental_growth_annual']) ** year
        rental_income.append(annual_rental)
    
    # Expense projection
    total_expenses = sum([
        inputs['annual_maintenance'],
        inputs['annual_property_tax'],
        inputs['annual_insurance']
    ]) * inputs['holding_period_years']
    
    # Resale value
    resale = inputs['investment_amount'] * (
        1 + inputs['property_appreciation_annual']
    ) ** inputs['holding_period_years']
    
    # Total return
    total_rental = sum(rental_income)
    total_emi = emi * 12 * inputs['loan_term_years']
    net_profit = (
        total_rental + 
        resale - 
        inputs['down_payment'] - 
        total_emi - 
        total_expenses
    )
    
    # ROI & CAGR
    roi = (net_profit / inputs['down_payment']) * 100
    cagr = (
        ((resale + total_rental - total_expenses) / inputs['down_payment']) 
        ** (1 / inputs['holding_period_years']) - 1
    ) * 100
    
    cash_on_cash = (
        (total_rental - total_expenses) / inputs['down_payment']
    ) * 100
    
    return {
        'emi': emi,
        'total_rental_income': total_rental,
        'total_emi_paid': total_emi,
        'total_expenses': total_expenses,
        'estimated_resale': resale,
        'net_profit': net_profit,
        'roi_percentage': roi,
        'cagr': cagr,
        'cash_on_cash': cash_on_cash
    }
```

### **UI Components**

```html
<!-- Investment Calculator Form -->
Investment Type: Residential | Commercial | Land | Plots | Villas | Resort
Property Value: ₹ [input]
Down Payment: ₹ [input] ([%])
Loan Amount: ₹ [auto-calculated]
Loan Rate: [%] [input]
Loan Tenure: [years] [input]

Monthly Rental Income: ₹ [input]
Annual Rental Growth: [%] [input]
Property Appreciation: [%] [input]
Holding Period: [years] [input]

Annual Maintenance: ₹ [input]
Annual Property Tax: ₹ [input]
Annual Insurance: ₹ [input]

[CALCULATE] [ADD TO COMPARISON]

<!-- Results Display -->
Total Investment: ₹ [value]
Total Rental Income: ₹ [value]
Estimated Resale Value: ₹ [value]
Total Return: ₹ [value]
ROI: [gauge display] [%]
CAGR: [%]
Cash-on-Cash Return: [%]

Scenario: [Conservative] [Base] [Optimistic]
```

### **Implementation Priority**: HIGH
**Estimated Effort**: 3-4 weeks
**Dependencies**: None (independent module)

---

## 👥 SYSTEM 3: AI PROPERTY MATCHMAKER

### **Purpose**
Intelligent matching algorithm that suggests properties based on buyer requirements and investor preferences.

### **Data Model**

```python
# NEW TABLE: buyer_requirements
CREATE TABLE IF NOT EXISTS buyer_requirements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    
    # BASIC REQUIREMENTS
    budget_min INTEGER NOT NULL,
    budget_max INTEGER NOT NULL,
    location_preferences TEXT NOT NULL,         # JSON array ["Jaipur", "Udaipur", ...]
    property_types TEXT NOT NULL,               # JSON array ["Flat", "Villa", ...]
    listing_type TEXT NOT NULL,                 # "buy" | "rent" | "either"
    
    # PROPERTY PREFERENCES
    min_bedrooms INTEGER DEFAULT 0,
    min_bathrooms INTEGER DEFAULT 0,
    min_area_sqft INTEGER DEFAULT 0,
    max_area_sqft INTEGER DEFAULT 0,
    
    # INVESTMENT PREFERENCES (if applicable)
    investment_purpose TEXT DEFAULT '',         # "personal" | "investment" | "both"
    expected_holding_years INTEGER DEFAULT 0,
    expected_roi_min REAL DEFAULT 0,
    expected_rental_yield REAL DEFAULT 0,
    
    # LIFESTYLE PREFERENCES
    amenities_wanted TEXT DEFAULT '',           # JSON array ["Pool", "Gym", ...]
    walkability_important BOOLEAN DEFAULT 0,
    public_transit_important BOOLEAN DEFAULT 0,
    
    # PROFILE PREFERENCE
    investor_profile TEXT DEFAULT '',           # "first-time buyer" | "investor" | "nri" | "hni"
    
    created_at TEXT NOT NULL,
    last_updated TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

# NEW TABLE: property_matches
CREATE TABLE IF NOT EXISTS property_matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    requirement_id INTEGER NOT NULL,
    property_id INTEGER NOT NULL,
    
    # MATCH SCORE & FACTORS
    match_score INTEGER DEFAULT 0,              # 0-100
    
    # INDIVIDUAL FACTORS
    price_fit_score INTEGER DEFAULT 0,
    location_fit_score INTEGER DEFAULT 0,
    property_type_fit INTEGER DEFAULT 0,
    amenity_fit_score INTEGER DEFAULT 0,
    investment_fit_score INTEGER DEFAULT 0,
    lifestyle_fit_score INTEGER DEFAULT 0,
    
    # MATCH EXPLANATION
    match_explanation TEXT DEFAULT '',
    match_reasons TEXT DEFAULT '',              # JSON array of reasons
    potential_concerns TEXT DEFAULT '',         # JSON array of concerns
    
    rank INTEGER DEFAULT 0,                     # Ranking (1 = best match)
    
    created_at TEXT NOT NULL,
    FOREIGN KEY (requirement_id) REFERENCES buyer_requirements(id),
    FOREIGN KEY (property_id) REFERENCES properties(id),
    UNIQUE (requirement_id, property_id)
);
```

### **Route Architecture**

```python
# NEW ROUTES

GET /requirements/new
  → Shows: Multi-step requirement collection form
  → Step 1: Budget & Location
  → Step 2: Property Type & Features
  → Step 3: Investment Goals (optional)
  → Step 4: Lifestyle Preferences (optional)

POST /requirements
  → Save buyer requirements
  → Trigger matching algorithm
  → Redirect to matches

GET /requirements/<req_id>/matches
  → Show: Ranked property matches
  → Display: Match score, reasons, concerns
  → Features: Filter by score, sort by type/price

GET /api/match/<property_id>
  → Returns: Matching profiles that fit this property
  → Shows: Which buyer types would like this

POST /admin/matching/recalculate
  → Admin: Recalculate all matches
  → Useful: After property data updates
  → Runs: Background matching algorithm
```

### **Matching Algorithm** (Scoring Logic)

```python
def calculate_match_score(requirement, property):
    """Intelligent matching algorithm"""
    
    scores = {}
    weights = {
        'price': 0.25,
        'location': 0.25,
        'property_type': 0.15,
        'amenities': 0.15,
        'investment': 0.15,
        'lifestyle': 0.05
    }
    
    # PRICE FIT (0-100)
    price_fit = 100 if (requirement['budget_min'] <= property['price'] <= requirement['budget_max']) else max(0, 100 - abs(property['price'] - requirement['budget_avg']) / 100000)
    
    # LOCATION FIT (0-100)
    location_fit = 100 if property['city'] in requirement['locations'] else 30
    
    # PROPERTY TYPE FIT (0-100)
    property_type_fit = 100 if property['ptype'] in requirement['types'] else 0
    
    # AMENITY FIT (0-100)
    if requirement['amenities']:
        property_amenities = set(property['amenities'].split(','))
        desired_amenities = set(requirement['amenities_wanted'])
        amenity_fit = (len(property_amenities & desired_amenities) / len(desired_amenities)) * 100
    else:
        amenity_fit = 50
    
    # INVESTMENT FIT (0-100)
    if requirement['investment_purpose'] == 'investment':
        # Use property intelligence score if available
        investment_fit = get_property_opportunity_score(property['id'])
    else:
        investment_fit = 50
    
    # LIFESTYLE FIT (0-100)
    lifestyle_fit = 50  # Placeholder
    if requirement['walkability_important']:
        lifestyle_fit += 20 if property['walkability_score'] > 70 else -10
    if requirement['public_transit_important']:
        lifestyle_fit += 20 if property['transit_score'] > 70 else -10
    lifestyle_fit = max(0, min(100, lifestyle_fit))
    
    scores = {
        'price': price_fit,
        'location': location_fit,
        'property_type': property_type_fit,
        'amenities': amenity_fit,
        'investment': investment_fit,
        'lifestyle': lifestyle_fit
    }
    
    # WEIGHTED SCORE
    overall = sum(scores[k] * weights[k] for k in weights)
    
    # GENERATE REASONS & CONCERNS
    reasons = []
    if scores['price'] > 80: reasons.append("Excellent price fit")
    if scores['location'] == 100: reasons.append("Matches your location preference")
    if scores['property_type'] == 100: reasons.append("Exact property type you want")
    if scores['investment'] > 80: reasons.append("Strong investment potential")
    
    concerns = []
    if scores['price'] < 50: concerns.append("Price is outside your budget range")
    if scores['location'] < 50: concerns.append("Not in your preferred locations")
    if scores['amenities'] < 40: concerns.append("Missing several desired amenities")
    
    return {
        'overall_score': round(overall),
        'individual_scores': scores,
        'reasons': reasons,
        'concerns': concerns,
        'rank': 0  # Will be set after all matches calculated
    }
```

### **Implementation Priority**: MEDIUM
**Estimated Effort**: 2-3 weeks
**Dependencies**: System 1 (Property Intelligence, for scoring)

---

## 🗺️ SYSTEM 4: REAL ESTATE GROWTH MAP

### **Purpose**
Interactive market intelligence system showing growth trends, infrastructure development, and investment opportunities by geography.

### **Data Model**

```python
# EXTEND: location_data table (from System 1)
# Already includes: infrastructure, connectivity, growth metrics

# NEW TABLE: market_insights (different from insights articles)
CREATE TABLE IF NOT EXISTS market_insights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    city TEXT NOT NULL,
    locality TEXT NOT NULL,
    
    # MARKET STATISTICS
    total_properties INTEGER DEFAULT 0,
    avg_price INTEGER DEFAULT 0,
    median_price INTEGER DEFAULT 0,
    price_range_min INTEGER DEFAULT 0,
    price_range_max INTEGER DEFAULT 0,
    
    # DEMAND & SUPPLY
    property_type_distribution TEXT DEFAULT '',    # JSON {"Flat": 40%, "Villa": 30%, ...}
    rent_vs_buy_ratio REAL DEFAULT 0.0,
    days_on_market INTEGER DEFAULT 0,              # Average
    
    # GROWTH & TRENDS
    price_appreciation_1yr REAL DEFAULT 0.0,
    price_appreciation_3yr REAL DEFAULT 0.0,
    price_appreciation_5yr REAL DEFAULT 0.0,
    market_sentiment TEXT DEFAULT 'neutral',       # "bullish" | "neutral" | "bearish"
    
    # INVESTOR ACTIVITY
    investor_purchases_pct REAL DEFAULT 0.0,
    avg_investor_ROI REAL DEFAULT 0.0,
    
    # UPCOMING PROJECTS
    major_projects TEXT DEFAULT '',                # JSON array
    
    # DATA SOURCE
    source TEXT DEFAULT 'internal',
    last_updated TEXT NOT NULL,
    
    UNIQUE (city, locality)
);

# NEW TABLE: infrastructure_projects
CREATE TABLE IF NOT EXISTS infrastructure_projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    city TEXT NOT NULL,
    locality TEXT,                                 # Null if city-wide
    
    project_name TEXT NOT NULL,
    project_type TEXT NOT NULL,                    # "metro" | "highway" | "commercial" | "residential"
    status TEXT DEFAULT 'planned',                 # "planned" | "under-construction" | "completed"
    
    completion_date TEXT,                          # YYYY-MM-DD
    estimated_impact TEXT DEFAULT '',              # "HIGH" | "MEDIUM" | "LOW"
    impact_description TEXT DEFAULT '',
    
    created_at TEXT NOT NULL,
    UNIQUE (project_name, city)
);

# NEW TABLE: growth_indicators
CREATE TABLE IF NOT EXISTS growth_indicators (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    city TEXT NOT NULL,
    locality TEXT,
    
    # ECONOMIC INDICATORS
    population_growth REAL DEFAULT 0.0,
    commercial_development REAL DEFAULT 0.0,      # % change
    employment_centers_count INTEGER DEFAULT 0,
    
    # QUALITY OF LIFE
    education_institutions INTEGER DEFAULT 0,
    hospitals_clinics INTEGER DEFAULT 0,
    shopping_malls INTEGER DEFAULT 0,
    entertainment_venues INTEGER DEFAULT 0,
    
    # CONNECTIVITY
    road_quality_score INTEGER DEFAULT 0,         # 0-100
    public_transport_score INTEGER DEFAULT 0,     # 0-100
    
    created_at TEXT NOT NULL,
    UNIQUE (city, locality)
);
```

### **Route Architecture**

```python
# NEW ROUTES

GET /growth-map
  → Show: Interactive map of all cities/markets
  → Features: Filter by growth rate, investment potential
  → Visual: Heat map showing hot markets

GET /growth-map/<city>
  → Show: City-level analysis
  → Sections: Overview, Localities, Infrastructure, Growth Trends
  → Charts: Price appreciation, demand, investor activity

GET /growth-map/<city>/<locality>
  → Show: Locality deep-dive
  → Stats: Price, demand, growth rate
  → Infrastructure: Upcoming projects, connectivity
  → Properties: Available properties in this locality
  → Investment: Avg ROI, rental yield for this area

GET /api/market-data/<city>/<locality>
  → Returns: Complete market intelligence JSON
  → For: Building custom dashboards

GET /infrastructure-projects/<city>
  → Show: Upcoming projects in city
  → Filter: By project type, status, completion date
  → Impact: How projects affect neighborhood

POST /admin/market-insight/<city>/<locality>
  → Admin: Update market data
  → Admin: Add/update growth statistics

GET /growth-map/api/heat-map
  → Returns: Heat map data (GeoJSON)
  → Shows: Growth opportunities by region
```

### **Visual Components**

```
GROWTH MAP VIEW:
├─ Heat Map (Growth Opportunities by Color)
├─ City List with Quick Stats
│  └─ Jaipur: 4.2% YoY, ₹55L avg, 340 properties
│  └─ Udaipur: 3.8% YoY, ₹42L avg, 120 properties
├─ Infrastructure Projects Timeline
└─ Top Performing Localities (Table)

CITY DETAIL:
├─ Key Metrics (Cards)
│  ├─ Avg Price: ₹55L
│  ├─ YoY Growth: 4.2%
│  ├─ Rental Yield: 3.8%
│  └─ Properties: 340
├─ Growth Trends (Charts)
│  ├─ 5-Year Price Appreciation
│  └─ Demand vs Supply
├─ Localities Grid (Sorted by Growth)
└─ Infrastructure Projects

LOCALITY DETAIL:
├─ Overview Stats
├─ Property Distribution (by type)
├─ Price Range & Trends
├─ Upcoming Infrastructure
├─ Available Properties (Quick Cards)
└─ Investment Recommendations
```

### **Implementation Priority**: MEDIUM
**Estimated Effort**: 4 weeks
**Dependencies**: System 1 (Intelligence data)

---

## 🤝 SYSTEM 5: AI DEAL ROOM

### **Purpose**
Private collaborative workspace where buyers, sellers, agents, and investors can securely share documents, communicate, and track deal progress.

### **Data Model**

```python
# NEW TABLE: deal_rooms
CREATE TABLE IF NOT EXISTS deal_rooms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    # BASICS
    title TEXT NOT NULL,
    deal_type TEXT NOT NULL,                      # "buy" | "sell" | "invest" | "development"
    status TEXT DEFAULT 'active',                 # "active" | "in-negotiation" | "closed" | "failed"
    
    # PARTICIPANTS
    initiator_id INTEGER NOT NULL,                # Who created it
    property_id INTEGER,                          # Property involved (optional)
    investment_id INTEGER,                        # Investment involved (optional)
    
    # DEAL INFO
    estimated_value INTEGER DEFAULT 0,
    expected_close_date TEXT,
    
    # PRIVACY & PERMISSIONS
    is_private BOOLEAN DEFAULT 1,
    access_level TEXT DEFAULT 'private',          # "private" | "shared-team" | "public"
    
    created_at TEXT NOT NULL,
    FOREIGN KEY (initiator_id) REFERENCES users(id),
    FOREIGN KEY (property_id) REFERENCES properties(id),
    FOREIGN KEY (investment_id) REFERENCES investments(id)
);

# NEW TABLE: deal_room_participants
CREATE TABLE IF NOT EXISTS deal_room_participants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deal_room_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    
    role TEXT DEFAULT 'participant',              # "owner" | "agent" | "buyer" | "investor" | "participant"
    can_upload BOOLEAN DEFAULT 1,
    can_comment BOOLEAN DEFAULT 1,
    can_edit_deal BOOLEAN DEFAULT 0,
    
    joined_at TEXT NOT NULL,
    FOREIGN KEY (deal_room_id) REFERENCES deal_rooms(id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE (deal_room_id, user_id)
);

# NEW TABLE: deal_documents
CREATE TABLE IF NOT EXISTS deal_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deal_room_id INTEGER NOT NULL,
    uploaded_by INTEGER NOT NULL,
    
    filename TEXT NOT NULL,
    file_type TEXT NOT NULL,                      # "pdf" | "image" | "document" | "spreadsheet"
    file_url TEXT NOT NULL,                       # S3 URL or local path
    file_size INTEGER DEFAULT 0,
    
    doc_category TEXT DEFAULT '',                 # "property-details" | "legal" | "financial" | "inspection" | "other"
    
    # METADATA
    document_description TEXT DEFAULT '',
    extracted_text TEXT DEFAULT '',               # OCR or extracted text for search
    
    created_at TEXT NOT NULL,
    FOREIGN KEY (deal_room_id) REFERENCES deal_rooms(id),
    FOREIGN KEY (uploaded_by) REFERENCES users(id)
);

# NEW TABLE: deal_communications
CREATE TABLE IF NOT EXISTS deal_communications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deal_room_id INTEGER NOT NULL,
    sender_id INTEGER NOT NULL,
    
    message_type TEXT DEFAULT 'comment',          # "comment" | "update" | "milestone"
    message_text TEXT NOT NULL,
    
    # THREADING
    parent_message_id INTEGER,                    # For replies
    
    # DEAL TRACKING
    relates_to TEXT DEFAULT '',                   # "price-negotiation" | "inspection" | "documents" | "payment"
    priority TEXT DEFAULT 'normal',               # "low" | "normal" | "high"
    
    created_at TEXT NOT NULL,
    FOREIGN KEY (deal_room_id) REFERENCES deal_rooms(id),
    FOREIGN KEY (sender_id) REFERENCES users(id)
);

# NEW TABLE: deal_milestones
CREATE TABLE IF NOT EXISTS deal_milestones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deal_room_id INTEGER NOT NULL,
    
    milestone_name TEXT NOT NULL,                 # "Agreement Signed" | "Inspection Done" | "Payment 1" | "Registry"
    status TEXT DEFAULT 'pending',                # "pending" | "completed" | "missed"
    
    scheduled_date TEXT,
    completed_date TEXT,
    
    # DETAILS
    assigned_to INTEGER,                          # User responsible (optional)
    description TEXT DEFAULT '',
    
    created_at TEXT NOT NULL,
    FOREIGN KEY (deal_room_id) REFERENCES deal_rooms(id),
    FOREIGN KEY (assigned_to) REFERENCES users(id)
);

# NEW TABLE: deal_payments
CREATE TABLE IF NOT EXISTS deal_payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deal_room_id INTEGER NOT NULL,
    
    payment_description TEXT NOT NULL,            # "Advance" | "Registration" | "Possession" etc
    scheduled_amount INTEGER DEFAULT 0,
    scheduled_date TEXT,
    
    actual_amount INTEGER DEFAULT 0,
    actual_date TEXT,
    status TEXT DEFAULT 'pending',                # "pending" | "completed" | "delayed"
    
    created_at TEXT NOT NULL,
    FOREIGN KEY (deal_room_id) REFERENCES deal_rooms(id)
);
```

### **Route Architecture**

```python
# NEW ROUTES

GET /deal-room/new
  → Show: Create new deal room form
  → Inputs: Deal type, participants, property/investment

POST /deal-rooms
  → Create deal room
  → Add initial participants
  → Generate unique deal room link

GET /deal-room/<room_id>
  → Show: Deal room interface
  → Sections:
    ├─ Property/Investment Overview
    ├─ Document Center (upload, view, organize)
    ├─ Communication Thread
    ├─ Deal Milestones Tracker
    ├─ Payment Schedule
    └─ Participants List

POST /deal-room/<room_id>/documents
  → Upload document to deal room
  → OCR for searchability (optional)

POST /deal-room/<room_id>/message
  → Add comment/update to deal
  → Notifies all participants

GET /deal-room/<room_id>/timeline
  → Visual timeline of:
    ├─ Milestones
    ├─ Payments
    ├─ Key communications
    └─ Document uploads

POST /deal-room/<room_id>/milestone
  → Add or complete milestone
  → Triggers notifications

POST /deal-room/<room_id>/invite
  → Add new participant to deal room
  → Sends invite link

GET /api/deal-room/<room_id>/summary
  → Returns: Deal status, key dates, next actions
  → For: Integration with dashboards
```

### **Deal Room Interface**

```
DEAL ROOM: ₹75L Dwarka Flat - Sharma Family
Status: In Negotiation ⏱️

┌─ PROPERTY SNAPSHOT ──────────────────────┐
│ 3BHK Flat, Dwarka | ₹75L | 1450 sqft     │
│ Price Negotiation: ₹73L - ₹77L           │
│ Expected Closing: Dec 15, 2026            │
└──────────────────────────────────────────┘

DOCUMENTS [4 files]
├─ Property Details (PDF)
├─ Site Photo (JPG)
├─ Legal Opinion (PDF)
└─ Inspection Report (PDF)
[+ Upload New]

MILESTONES
✓ Agreement Signed (Oct 1, 2026)
⏳ Inspection Due (Oct 10, 2026)
☐ Payment 1 (Oct 15, 2026)
☐ Registry (Nov 15, 2026)
☐ Possession (Dec 15, 2026)

COMMUNICATIONS
"Mr. Sharma offered ₹73.5L" - Agent (Today)
"Waiting for inspection report" - Buyer (Yesterday)
```

### **Implementation Priority**: MEDIUM-HIGH
**Estimated Effort**: 3-4 weeks
**Dependencies**: None (can work independently)

---

## 🏛️ SYSTEM 6: PREMIUM RESORT & MEGA INVESTMENT DESK

### **Purpose**
High-end investment opportunity showcase for large-scale projects (₹100Cr+) with institutional-grade financial analysis.

### **Data Model**

```python
# EXTEND: investments table with premium fields
CREATE TABLE IF NOT EXISTS premium_investments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    investment_id INTEGER NOT NULL UNIQUE,
    
    # PROJECT CLASSIFICATION
    project_scale TEXT NOT NULL,                  # "mega" (₹500Cr+) | "major" (₹100Cr+) | "premium" (₹50Cr+)
    project_stage TEXT DEFAULT 'pre-launch',      # "pre-launch" | "soft-launch" | "active" | "construction" | "ready"
    
    # FINANCIAL STRUCTURE
    total_project_cost INTEGER DEFAULT 0,         # Total development cost
    total_units INTEGER DEFAULT 0,                # Total units/plots
    units_sold INTEGER DEFAULT 0,
    
    # INVESTMENT OPTIONS
    investment_options TEXT DEFAULT '',           # JSON array of options
    # Example: [
    #   {"name": "Pre-Launch", "pricing": "₹25L", "units": 50},
    #   {"name": "Phase 2", "pricing": "₹28L", "units": 50}
    # ]
    
    # REVENUE MODEL
    revenue_model TEXT DEFAULT '',                # Description
    estimated_monthly_occupancy REAL DEFAULT 0,  # %
    estimated_monthly_revenue INTEGER DEFAULT 0, # INR
    
    # EXPENSE MODEL
    operating_expense_monthly INTEGER DEFAULT 0,
    maintenance_reserve REAL DEFAULT 0,          # % of revenue
    management_fee REAL DEFAULT 0,                # % of revenue
    
    # SCENARIO ANALYSIS
    scenario_conservative TEXT DEFAULT '',        # JSON conservative case
    scenario_base TEXT DEFAULT '',                # JSON base case
    scenario_optimistic TEXT DEFAULT '',          # JSON optimistic case
    
    # INVESTOR BENEFITS
    investor_benefits TEXT DEFAULT '',            # JSON array ["Capital appreciation", "Rental yield", ...]
    
    # EXIT POSSIBILITIES
    exit_options TEXT DEFAULT '',                 # JSON array
    historical_exit_data TEXT DEFAULT '',         # Similar projects' exit data
    
    # RISK FACTORS
    risk_factors TEXT DEFAULT '',                 # JSON array of identified risks
    risk_mitigation TEXT DEFAULT '',              # How risks are managed
    
    # DOCUMENTATION
    brochure_url TEXT DEFAULT '',
    financial_model_url TEXT DEFAULT '',
    legal_review_status TEXT DEFAULT 'pending',   # "pending" | "approved" | "flagged"
    
    created_at TEXT NOT NULL,
    FOREIGN KEY (investment_id) REFERENCES investments(id)
);

# NEW TABLE: mega_project_developers
CREATE TABLE IF NOT EXISTS mega_project_developers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    premium_investment_id INTEGER NOT NULL,
    
    developer_name TEXT NOT NULL,
    developer_email TEXT,
    developer_phone TEXT,
    
    track_record TEXT DEFAULT '',                 # Previous projects
    financial_stability TEXT DEFAULT 'verified',  # "verified" | "pending" | "flagged"
    
    FOREIGN KEY (premium_investment_id) REFERENCES premium_investments(id)
);

# NEW TABLE: mega_project_inquiries
CREATE TABLE IF NOT EXISTS mega_project_inquiries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    premium_investment_id INTEGER NOT NULL,
    
    investor_name TEXT NOT NULL,
    investor_email TEXT,
    investor_phone TEXT,
    
    # INVESTOR PROFILE
    investment_capacity_min INTEGER,
    investment_capacity_max INTEGER,
    investor_type TEXT DEFAULT '',                # "hni" | "institution" | "nri" | "corporate"
    
    # INQUIRY DETAILS
    inquiry_date TEXT NOT NULL,
    inquiry_text TEXT DEFAULT '',
    interest_level TEXT DEFAULT 'inquiry',        # "inquiry" | "serious" | "ready-to-invest"
    
    # FOLLOW-UP
    follow_up_date TEXT,
    assigned_to INTEGER,                          # Agent assigned
    status TEXT DEFAULT 'new',                    # "new" | "contacted" | "sent-info" | "negotiating" | "invested"
    
    FOREIGN KEY (premium_investment_id) REFERENCES premium_investments(id),
    FOREIGN KEY (assigned_to) REFERENCES users(id)
);
```

### **Route Architecture**

```python
# NEW ROUTES

GET /mega-investments
  → Show: Curated list of major investment opportunities
  → Filter: By project stage, minimum ticket size, expected ROI
  → Sort: By project size, timeline, investor preference

GET /mega-investment/<inv_id>
  → Show: Premium project detail page
  → Sections:
    ├─ Executive Summary
    ├─ Project Overview & Photos
    ├─ Investment Structure & Options
    ├─ Financial Model (Conservative/Base/Optimistic)
    ├─ Revenue & Expense Breakdown
    ├─ Risk Analysis & Mitigation
    ├─ Developer Profile & Track Record
    ├─ Similar Projects' Exit Data
    ├─ Timeline & Milestones
    └─ Investment Enquiry Form

GET /mega-investment/<inv_id>/financial-model
  → Show: Detailed financial analysis
  → Download: PDF report with full calculations

GET /mega-investment/<inv_id>/comparison
  → Compare: Against similar projects
  → Metrics: ROI, timeline, risk profile

POST /mega-investment/<inv_id>/enquiry
  → Submit: High-touch inquiry
  → Triggers: Direct agent assignment

POST /admin/mega-investment/create
  → Admin: Create new mega investment opportunity
  → Fields: All premium investment data

GET /api/mega-investment/<inv_id>/summary
  → Returns: JSON summary for API access
```

### **Premium Project Page Example**

```
🏆 LUXURY RESORT DEVELOPMENT — MALDIVES RESORT GROUP

Investment Size: ₹500 Crore
Expected Return: 15-18% CAGR
Timeline: 5 years

INVESTMENT OPTIONS:
├─ Pre-Launch: ₹25L per unit (50 units available)
├─ Phase 2: ₹28L per unit (60 units available) 
└─ Phase 3: ₹32L per unit (50 units available)

FINANCIAL MODEL:
Conservative Case: 12% CAGR, ₹55L average unit return
Base Case: 15% CAGR, ₹68L average unit return
Optimistic Case: 18% CAGR, ₹82L average unit return

REVENUE MODEL:
- 200 luxury villas (₹3.5Cr - ₹5.5Cr each)
- 400 villa rentals (₹20-40L annually)
- 100 commercial plots (₹1.5Cr - ₹3Cr each)
- Resort amenities (₹5-10Cr annually)

RISK FACTORS:
- Regulatory: Maldives environmental compliance (MITIGATED: Legal team approved)
- Market: Currency fluctuations (MITIGATED: INR-pricing options available)
- Delivery: Project timeline slippage (MITIGATED: ₹50Cr performance bond)

DEVELOPER:
Maldives Resort Group (Est. 1995)
Track Record: 12 successful projects, ₹2000Cr+ completed
Financial: AAA rated, ICRA verified
```

### **Implementation Priority**: MEDIUM
**Estimated Effort**: 3 weeks
**Dependencies**: System 2 (Investment Calculations)

---

## 🤖 SYSTEM 7: AI REAL ESTATE CONCIERGE (Foundation)

### **Purpose**
NLP-powered AI assistant that understands natural language requirements and guides users through the entire real estate journey.

### **Architecture** (Foundation Only - Phase 2)

```python
# NEW TABLE: concierge_sessions
CREATE TABLE IF NOT EXISTS concierge_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,                              # Null for anonymous
    
    # CONVERSATION
    conversation_history TEXT DEFAULT '',         # JSON array of messages
    session_state TEXT DEFAULT 'greeting',        # "greeting" | "collecting-requirements" | "showing-properties" | "negotiating" | "closing"
    
    # UNDERSTOOD PROFILE
    understood_budget_min INTEGER DEFAULT 0,
    understood_budget_max INTEGER DEFAULT 0,
    understood_locations TEXT DEFAULT '',
    understood_property_types TEXT DEFAULT '',
    understood_purpose TEXT DEFAULT '',           # "buy" | "rent" | "invest" | "explore"
    
    # CONFIDENCE SCORES
    requirement_confidence REAL DEFAULT 0.0,      # How confident AI is about understanding needs
    
    created_at TEXT NOT NULL,
    last_updated TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

# NEW TABLE: concierge_recommendations
CREATE TABLE IF NOT EXISTS concierge_recommendations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    property_id INTEGER NOT NULL,
    
    recommendation_score REAL DEFAULT 0.0,        # 0-1.0
    reasoning TEXT DEFAULT '',
    mentioned_at TEXT NOT NULL,
    
    FOREIGN KEY (session_id) REFERENCES concierge_sessions(id),
    FOREIGN KEY (property_id) REFERENCES properties(id)
);
```

### **Natural Language Understanding Framework**

```python
class ConciergeMicroservices:
    """Concierge NLP components"""
    
    def understand_requirement(self, user_input):
        """Extract buyer requirements from natural language"""
        # Example:
        # Input: "I have 80 lakh and want to invest in Jaipur"
        # Output: {
        #   'budget_detected': True,
        #   'budget_value': 8000000,
        #   'location_detected': True,
        #   'location_value': 'Jaipur',
        #   'purpose_detected': True,
        #   'purpose_value': 'invest',
        #   'confidence': 0.95
        # }
        pass
    
    def suggest_next_question(self, current_profile):
        """Suggest intelligent follow-up questions"""
        # Example:
        # Input: {"budget": "80L", "location": "Jaipur", "purpose": "invest"}
        # Output: "What's your expected investment timeline? 3-5 years or longer?"
        pass
    
    def rank_matching_properties(self, profile, properties):
        """Rank properties based on NLP-understood profile"""
        pass
    
    def generate_investment_summary(self, profile):
        """Create personalized investment summary"""
        pass
    
    def respond_to_query(self, query, profile, context):
        """Respond to user queries in natural language"""
        pass
```

### **Conversational Flows**

```
GREETING:
Concierge: "Hi! I'm JARVIS, your AI real estate guide. Are you looking to buy, rent, or invest in property?"
User: "I want to invest in Jaipur"
Concierge: "Great! Real estate investment in Jaipur is exciting. What's your budget range?"

REQUIREMENT COLLECTION:
Concierge: [Asks 5-7 targeted questions]
- "How long are you planning to hold the investment?"
- "Are you looking for rental income or appreciation?"
- "Any preferred neighborhoods?"

PROPERTY MATCHING:
Concierge: "Based on your requirements, here are my top 3 recommendations..."
[Shows properties with reasons]

INVESTMENT GUIDANCE:
Concierge: "Let me calculate ROI scenarios for this property."
[Links to investment calculator]

DEAL SUPPORT:
Concierge: "I can set up a deal room to manage this transaction."
[Creates deal room]
```

### **Route Architecture** (Foundation)

```python
# NEW ROUTES

GET /concierge
  → Show: Concierge chat interface
  → Features: Real-time messaging, context awareness

POST /api/concierge/chat
  → Send: Message to concierge
  → Returns: AI response + action suggestions

GET /api/concierge/session/<session_id>
  → Get: Conversation history
  → Returns: Profile, recommendations, context

GET /concierge/recommendations
  → Show: Concierge's recommended properties for user
  → Reasoning: Why each is recommended

POST /admin/concierge/train
  → Admin: Train/improve concierge understanding
  → Feedback loop for continuous improvement
```

### **Implementation Priority**: LOW (Foundation Phase 2)
**Estimated Effort**: 4 weeks (foundation)
**Dependencies**: System 3 (Matching), System 2 (Calculations)
**Note**: Full NLP integration comes in Phase 3

---

## 📊 SYSTEM 8: PROPERTY OPPORTUNITY SCORE™

### **Purpose**
Proprietary scoring framework that creates a standardized, explainable investment suitability score for every property.

### **Data Model**

```python
# NEW TABLE: property_opportunity_scores
CREATE TABLE IF NOT EXISTS property_opportunity_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER NOT NULL UNIQUE,
    
    # MAIN SCORE (0-100)
    opportunity_score INTEGER DEFAULT 0,
    score_percentile INTEGER DEFAULT 0,           # 0-100 (how it ranks vs similar)
    
    # COMPONENT SCORES (0-100 each)
    location_score INTEGER DEFAULT 0,
    connectivity_score INTEGER DEFAULT 0,
    appreciation_score INTEGER DEFAULT 0,
    rental_yield_score INTEGER DEFAULT 0,
    price_positioning_score INTEGER DEFAULT 0,
    liquidity_score INTEGER DEFAULT 0,
    risk_score INTEGER DEFAULT 0,                 # Inverted (high = low risk)
    
    # INVESTOR PROFILE MATCH (0-100)
    first_time_buyer_match INTEGER DEFAULT 0,
    investor_match INTEGER DEFAULT 0,
    nri_match INTEGER DEFAULT 0,
    hni_match INTEGER DEFAULT 0,
    
    # DETAILED BREAKDOWN
    scoring_formula_used TEXT DEFAULT 'v1',       # Version of formula
    weight_allocation TEXT DEFAULT '',            # JSON showing weights
    component_details TEXT DEFAULT '',            # JSON with explanation for each component
    
    # TRENDS
    score_3mo_ago INTEGER DEFAULT 0,              # Historical tracking
    score_6mo_ago INTEGER DEFAULT 0,
    score_trend TEXT DEFAULT 'stable',            # "rising" | "stable" | "declining"
    
    # LAST UPDATED
    last_calculated TEXT NOT NULL,
    last_updated_reason TEXT DEFAULT '',          # "manual-review" | "market-update" | "data-refresh"
    
    FOREIGN KEY (property_id) REFERENCES properties(id)
);

# NEW TABLE: score_methodology_v1
CREATE TABLE IF NOT EXISTS score_methodology_v1 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    # COMPONENT: LOCATION (25 points)
    location_perfect_score INTEGER DEFAULT 25,
    connectivity_weight REAL DEFAULT 0.4,
    infrastructure_weight REAL DEFAULT 0.35,
    growth_trajectory_weight REAL DEFAULT 0.25,
    
    # COMPONENT: APPRECIATION (20 points)
    appreciation_perfect_score INTEGER DEFAULT 20,
    historical_growth_weight REAL DEFAULT 0.35,
    infrastructure_pipeline_weight REAL DEFAULT 0.35,
    area_demand_weight REAL DEFAULT 0.3,
    
    # COMPONENT: RENTAL YIELD (20 points)
    rental_perfect_score INTEGER DEFAULT 20,
    current_rental_rate_weight REAL DEFAULT 0.4,
    area_average_yield_weight REAL DEFAULT 0.35,
    property_type_demand_weight REAL DEFAULT 0.25,
    
    # COMPONENT: PRICE POSITIONING (15 points)
    price_perfect_score INTEGER DEFAULT 15,
    price_vs_comparable_weight REAL DEFAULT 0.6,
    price_trend_weight REAL DEFAULT 0.4,
    
    # COMPONENT: LIQUIDITY (10 points)
    liquidity_perfect_score INTEGER DEFAULT 10,
    property_type_demand_weight_liq REAL DEFAULT 0.5,
    location_desirability_weight_liq REAL DEFAULT 0.5,
    
    # COMPONENT: RISK (10 points - inverted)
    risk_perfect_score INTEGER DEFAULT 10,
    title_risk_weight REAL DEFAULT 0.4,
    market_risk_weight REAL DEFAULT 0.3,
    legal_compliance_weight REAL DEFAULT 0.3,
    
    version_number TEXT DEFAULT 'v1',
    active BOOLEAN DEFAULT 1,
    created_at TEXT NOT NULL
);
```

### **Scoring Formula** (Transparent & Explainable)

```python
def calculate_property_opportunity_score(property_id):
    """
    Proprietary scoring framework
    
    Total Score: 100 points distributed across components
    - Location & Connectivity: 25 points
    - Appreciation Potential: 20 points
    - Rental Yield: 20 points
    - Price Positioning: 15 points
    - Liquidity: 10 points
    - Risk Mitigation: 10 points
    """
    
    methodology = get_methodology_v1()
    
    # LOCATION COMPONENT (25 points)
    location_base = calculate_location_score(property_id)  # 0-100
    location_points = (location_base / 100) * methodology['location_perfect_score']
    
    # APPRECIATION COMPONENT (20 points)
    appreciation_base = calculate_appreciation_potential(property_id)  # 0-100
    appreciation_points = (appreciation_base / 100) * methodology['appreciation_perfect_score']
    
    # RENTAL YIELD COMPONENT (20 points)
    rental_base = calculate_rental_potential(property_id)  # 0-100
    rental_points = (rental_base / 100) * methodology['rental_perfect_score']
    
    # PRICE POSITIONING COMPONENT (15 points)
    price_base = calculate_price_positioning(property_id)  # 0-100
    price_points = (price_base / 100) * methodology['price_perfect_score']
    
    # LIQUIDITY COMPONENT (10 points)
    liquidity_base = calculate_liquidity(property_id)  # 0-100
    liquidity_points = (liquidity_base / 100) * methodology['liquidity_perfect_score']
    
    # RISK COMPONENT (10 points - inverted)
    risk_base = calculate_risk_factors(property_id)  # 0-100 (0 = high risk, 100 = low risk)
    risk_points = (risk_base / 100) * methodology['risk_perfect_score']
    
    # TOTAL SCORE
    total_score = (
        location_points +
        appreciation_points +
        rental_points +
        price_points +
        liquidity_points +
        risk_points
    )
    
    return {
        'opportunity_score': round(total_score),
        'component_scores': {
            'location': round(location_points),
            'appreciation': round(appreciation_points),
            'rental_yield': round(rental_points),
            'price_positioning': round(price_points),
            'liquidity': round(liquidity_points),
            'risk': round(risk_points)
        },
        'breakdown': {
            'location_detail': location_detail,
            'appreciation_detail': appreciation_detail,
            'rental_detail': rental_detail,
            'price_detail': price_detail,
            'liquidity_detail': liquidity_detail,
            'risk_detail': risk_detail
        }
    }
```

### **Route Architecture**

```python
# NEW ROUTES

GET /property/<id>/score
  → Show: Property Opportunity Score™ page
  → Displays:
    ├─ Overall score (0-100 with visual)
    ├─ Component breakdown (6 scores)
    ├─ Investor profile match scores
    ├─ Detailed explanation of each component
    ├─ How it compares to similar properties (percentile)
    └─ Score trend (3-month, 6-month)

GET /api/property/<id>/score
  → Returns: JSON score data (for integrations)

POST /admin/property/<id>/score/recalculate
  → Admin: Force recalculation
  → Updates: All scores based on latest data

GET /score-methodology
  → Show: Explanation of scoring formula
  → Transparency: How we calculate scores
  → Public documentation

POST /admin/score-methodology/update
  → Admin: Update scoring formula
  → Version: New methodology version
  → Triggers: Recalculation of all scores
```

### **Display Example**

```
PROPERTY OPPORTUNITY SCORE™

91/100 ⭐⭐⭐⭐⭐

🏆 EXCELLENT INVESTMENT OPPORTUNITY

Component Breakdown:
├─ Location & Connectivity: 24/25 ⭐⭐⭐⭐⭐
│  └─ Jagatpura is rapidly developing with good metro connectivity
│  └─ Amenities score: 92/100
│
├─ Appreciation Potential: 18/20 ⭐⭐⭐⭐⭐
│  └─ 4.2% historical YoY growth
│  └─ Major infrastructure projects planned
│  └─ Area still appreciating (not saturated)
│
├─ Rental Yield: 19/20 ⭐⭐⭐⭐⭐
│  └─ Current rental yield: 4.8% annually
│  └─ High demand for rentals in this area
│  └─ Strong tenant pool (young professionals)
│
├─ Price Positioning: 14/15 ⭐⭐⭐⭐
│  └─ ₹55L for 1450 sqft
│  └─ ₹38k/sqft vs area average ₹40k/sqft (3% below)
│  └─ Good value for location quality
│
├─ Liquidity: 9/10 ⭐⭐⭐⭐
│  └─ High demand area (easy to sell)
│  └─ Average days to sell: 45 days
│
└─ Risk Mitigation: 10/10 ⭐⭐⭐⭐⭐
   └─ JDA-approved property
   └─ Clear title verified
   └─ Low legal/regulatory risk

INVESTOR MATCH SCORES:
├─ First-Time Buyer: 82/100 ✓ Good fit
├─ Investor: 88/100 ✓ Excellent fit
├─ NRI: 79/100 ✓ Good fit
└─ HNI: 72/100 ✓ Moderate fit

PERCENTILE RANKING:
This property scores better than 91% of properties in this locality.
Ranks #4 out of 42 available properties in Jagatpura.
```

### **Implementation Priority**: HIGH
**Estimated Effort**: 2-3 weeks
**Dependencies**: System 1 (Intelligence data)

---

## 👔 SYSTEM 9: AGENT + CRM INTELLIGENCE

### **Purpose**
Intelligent CRM layer that helps agents prioritize leads, identify upsell opportunities, and track performance metrics.

### **Data Model** (Extend existing)

```python
# EXTEND: enquiries table with intelligence fields
ALTER TABLE enquiries ADD COLUMN (
    lead_temperature TEXT DEFAULT 'cold',         # "hot" | "warm" | "cold"
    lead_score INTEGER DEFAULT 0,                 # 0-100 (likelihood to close)
    predicted_close_probability REAL DEFAULT 0,   # 0-1.0
    estimated_deal_value INTEGER DEFAULT 0,      # INR
    next_action_recommended TEXT DEFAULT '',
    days_since_last_contact INTEGER DEFAULT 0
);

# NEW TABLE: agent_performance_metrics
CREATE TABLE IF NOT EXISTS agent_performance_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id INTEGER NOT NULL,
    
    period TEXT DEFAULT 'monthly',                # "weekly" | "monthly" | "quarterly"
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    
    # LEAD METRICS
    leads_generated INTEGER DEFAULT 0,
    leads_contacted INTEGER DEFAULT 0,
    leads_converted INTEGER DEFAULT 0,
    conversion_rate REAL DEFAULT 0.0,
    
    # DEAL METRICS
    deals_closed INTEGER DEFAULT 0,
    total_deal_value INTEGER DEFAULT 0,           # INR
    avg_deal_value INTEGER DEFAULT 0,
    deal_close_rate REAL DEFAULT 0.0,
    avg_days_to_close INTEGER DEFAULT 0,
    
    # QUALITY METRICS
    customer_satisfaction_score REAL DEFAULT 0,   # 1-5
    repeat_customer_rate REAL DEFAULT 0.0,        # % of returning clients
    referral_rate REAL DEFAULT 0.0,               # % of deals from referrals
    
    # EFFICIENCY METRICS
    properties_listed INTEGER DEFAULT 0,
    properties_sold INTEGER DEFAULT 0,
    avg_time_on_market INTEGER DEFAULT 0,
    
    created_at TEXT NOT NULL,
    FOREIGN KEY (agent_id) REFERENCES users(id)
);

# NEW TABLE: lead_scoring_model
CREATE TABLE IF NOT EXISTS lead_scoring_model (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    enquiry_id INTEGER NOT NULL,
    
    # BEHAVIORAL SIGNALS
    contacted_within_24h BOOLEAN DEFAULT 0,       # Points +20
    replied_to_inquiry BOOLEAN DEFAULT 0,         # Points +15
    requested_site_visit BOOLEAN DEFAULT 0,       # Points +25
    viewed_multiple_properties BOOLEAN DEFAULT 0, # Points +15
    
    # ENGAGEMENT SIGNALS
    engagement_count INTEGER DEFAULT 0,           # Number of interactions
    engagement_depth TEXT DEFAULT 'low',          # "high" | "medium" | "low"
    
    # INTENT SIGNALS
    timeline_urgent BOOLEAN DEFAULT 0,            # Points +20
    budget_confirmed BOOLEAN DEFAULT 0,           # Points +15
    decided_location BOOLEAN DEFAULT 0,           # Points +10
    
    # PREDICTED CLOSE
    predicted_close_probability REAL DEFAULT 0,   # ML model output
    predicted_close_value INTEGER DEFAULT 0,      # Estimated deal value
    
    lead_temperature TEXT DEFAULT 'cold',         # Derived from score
    
    calculated_at TEXT NOT NULL,
    FOREIGN KEY (enquiry_id) REFERENCES enquiries(id)
);

# NEW TABLE: recommended_actions
CREATE TABLE IF NOT EXISTS recommended_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    enquiry_id INTEGER NOT NULL,
    agent_id INTEGER,                             # Assigned agent (optional)
    
    action TEXT NOT NULL,                         # "call" | "email" | "site-visit" | "follow-up" | "upsell"
    action_priority TEXT DEFAULT 'normal',        # "urgent" | "high" | "normal" | "low"
    reasoning TEXT DEFAULT '',
    recommended_timing TEXT DEFAULT '',           # "today" | "within-24h" | "within-week"
    
    action_completed BOOLEAN DEFAULT 0,
    completed_at TEXT,
    
    created_at TEXT NOT NULL,
    FOREIGN KEY (enquiry_id) REFERENCES enquiries(id),
    FOREIGN KEY (agent_id) REFERENCES users(id)
);
```

### **Lead Scoring Algorithm**

```python
def calculate_lead_score(enquiry_id):
    """
    ML-ready lead scoring
    
    0-100 scale:
    - 80-100: Hot (likely to close)
    - 60-79: Warm (promising)
    - 40-59: Cool (needs nurturing)
    - 0-39: Cold (long-term prospect)
    """
    
    enquiry = get_enquiry(enquiry_id)
    score = 0
    
    # BEHAVIORAL SIGNALS (50 points total)
    if contacted_within_24h(enquiry):
        score += 20  # Quick response matters
    
    if has_replied(enquiry):
        score += 15  # Engagement signal
    
    if requested_site_visit(enquiry):
        score += 25  # Strong intent
    
    if viewed_multiple_properties(enquiry):
        score += 15  # Active browsing
    
    # ENGAGEMENT SIGNALS (20 points total)
    engagement_count = count_interactions(enquiry)
    if engagement_count >= 5:
        score += 20
    elif engagement_count >= 3:
        score += 12
    else:
        score += 5
    
    # INTENT SIGNALS (30 points total)
    if has_urgent_timeline(enquiry):
        score += 20
    
    if budget_confirmed(enquiry):
        score += 15
    
    if location_decided(enquiry):
        score += 10
    
    # PROPERTY MATCH BONUS
    property = get_property(enquiry['property_id'])
    if matches_buyer_profile(enquiry, property):
        score += 10
    
    # MARKET CONDITION ADJUSTMENT
    if high_demand_property(property):
        score += 5
    
    return {
        'lead_score': min(100, score),
        'temperature': 'hot' if score >= 80 else 'warm' if score >= 60 else 'cool' if score >= 40 else 'cold',
        'close_probability': score / 100,
        'estimated_value': estimate_deal_value(enquiry, property)
    }
```

### **Route Architecture**

```python
# NEW ROUTES

GET /agent/dashboard
  → Show: Agent's personalized dashboard
  → Sections:
    ├─ Hot Leads (action required)
    ├─ Upcoming Follow-ups
    ├─ Performance Metrics (this month)
    ├─ Property Recommendations
    └─ Quick Actions

GET /agent/leads
  → Show: All leads for this agent
  → Sort: By temperature, score, close date
  → Filter: Status, property type, value range

GET /agent/leads/<lead_id>
  → Show: Lead detail with recommendations
  → History: All interactions
  → Next Action: Recommended step

POST /agent/leads/<lead_id>/action
  → Log: Completed action (call, email, visit)
  → Auto-update: Lead temperature & timeline

GET /agent/performance
  → Show: Agent's KPIs
  → Charts: Conversions, deal value, close time
  → Comparison: vs team average

GET /admin/crm-analytics
  → Show: Team-wide CRM analytics
  → Insights: Best performing agents, top properties
  → Trends: Conversion funnels, lead sources

POST /admin/lead-scoring/retrain
  → Admin: Trigger model retraining
  → Update: Scoring weights based on new data
```

### **Agent Dashboard Example**

```
MY LEADS & RECOMMENDATIONS

HOT LEADS (Require Action Today)
├─ Mr Sharma - ₹75L Dwarka Flat
│  Score: 88/100 | Probability: 88% | Est Value: ₹75L
│  🔴 Next Action: Call for site visit (within 24h)
│
├─ Mrs Patel - ₹50L Vaishali Flat  
│  Score: 82/100 | Probability: 82% | Est Value: ₹50L
│  🔴 Next Action: Send property details (today)

WARM LEADS (Follow Up)
├─ Mr Jain - ₹1Cr Plot
│  Score: 68/100 | Probability: 68% | Est Value: ₹1Cr
│  🟡 Next Action: Schedule call (within 48h)

MY PERFORMANCE (This Month)
Leads: 12 | Contacted: 10 | Converted: 3 | Rate: 25%
Total Value: ₹2.5Cr | Avg Deal: ₹83L | Days to Close: 18
```

### **Implementation Priority**: MEDIUM
**Estimated Effort**: 3 weeks
**Dependencies**: System 8 (Scoring)

---

## 📊 SYSTEM 10: JARVIS COMMAND CENTER

### **Purpose**
Real-time operational dashboard showing the entire real estate business—leads flowing through the system, agents working, deals progressing, and market opportunities emerging.

### **Data Model**

```python
# NEW TABLE: activity_stream
CREATE TABLE IF NOT EXISTS activity_stream (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    activity_type TEXT NOT NULL,                  # "lead-new" | "deal-created" | "property-listed" | "score-changed" | "agent-action"
    entity_type TEXT NOT NULL,                    # "lead" | "property" | "investment" | "agent" | "deal"
    entity_id INTEGER,
    
    # ACTIVITY DETAILS
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    
    # METADATA
    actor_id INTEGER,                             # Who triggered the activity
    actor_type TEXT DEFAULT 'system',             # "user" | "system" | "automation"
    
    # VISUALIZATION
    icon TEXT DEFAULT '',
    priority TEXT DEFAULT 'normal',               # "urgent" | "high" | "normal" | "low"
    color TEXT DEFAULT 'blue',                    # For UI visualization
    
    created_at TEXT NOT NULL,
    FOREIGN KEY (actor_id) REFERENCES users(id)
);

# NEW TABLE: dashboard_widgets
CREATE TABLE IF NOT EXISTS dashboard_widgets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    widget_type TEXT NOT NULL,                    # "metrics" | "chart" | "list" | "map" | "funnel"
    widget_name TEXT NOT NULL,
    
    # CONFIGURATION
    refresh_interval INTEGER DEFAULT 60,          # Seconds
    data_source TEXT DEFAULT '',                  # API endpoint or query
    
    created_at TEXT NOT NULL
);

# NEW TABLE: system_metrics
CREATE TABLE IF NOT EXISTS system_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    # LEAD METRICS
    total_leads INTEGER DEFAULT 0,
    new_leads_today INTEGER DEFAULT 0,
    hot_leads INTEGER DEFAULT 0,
    warm_leads INTEGER DEFAULT 0,
    
    # DEAL METRICS
    active_deals INTEGER DEFAULT 0,
    deals_in_negotiation INTEGER DEFAULT 0,
    total_pipeline_value INTEGER DEFAULT 0,      # INR
    
    # PROPERTY METRICS
    total_properties INTEGER DEFAULT 0,
    properties_live INTEGER DEFAULT 0,
    properties_sold_this_month INTEGER DEFAULT 0,
    avg_days_to_sell INTEGER DEFAULT 0,
    
    # AGENT METRICS
    total_agents INTEGER DEFAULT 0,
    agents_active INTEGER DEFAULT 0,
    avg_conversion_rate REAL DEFAULT 0,          # %
    
    # BUSINESS METRICS
    monthly_revenue INTEGER DEFAULT 0,           # INR
    avg_deal_value INTEGER DEFAULT 0,
    customer_satisfaction_avg REAL DEFAULT 0,
    
    # CALCULATED AT
    calculated_at TEXT NOT NULL
);
```

### **Route Architecture**

```python
# NEW ROUTES

GET /command-center
  → Show: JARVIS Command Center Dashboard
  → Real-time visualization of:
    ├─ Key Metrics (cards)
    │  ├─ Total Leads: 247
    │  ├─ Hot Leads: 12
    │  ├─ Active Deals: 8
    │  ├─ Pipeline Value: ₹50Cr
    │  └─ Properties Live: 127
    │
    ├─ Activity Stream
    │  ├─ "New lead: Mr Sharma, ₹75L, Dwarka" (2 min ago)
    │  ├─ "Deal created: 3BHK Flat - Mrs Patel" (15 min ago)
    │  ├─ "Property listed: Villa in Jagatpura" (30 min ago)
    │  └─ "Opportunity Score updated: Flat +3 points" (1 hr ago)
    │
    ├─ Lead Funnel Chart
    │  ├─ New Leads: 247
    │  ├─ Contacted: 189
    │  ├─ Site Visits: 67
    │  ├─ Offers: 23
    │  └─ Closed: 8
    │
    ├─ Agent Leaderboard
    │  ├─ 1. Agent A: 3 deals, ₹2.5Cr, 25% conversion
    │  ├─ 2. Agent B: 2 deals, ₹1.8Cr, 20% conversion
    │  └─ 3. Agent C: 2 deals, ₹1.2Cr, 18% conversion
    │
    ├─ Deal Progress Timeline
    │  └─ Visual: Deals at each stage (Negotiation, Inspection, Registry, etc)
    │
    ├─ Top Opportunities
    │  ├─ Property A: Score 95/100, Hot Leads
    │  ├─ Property B: Score 92/100, Warm Leads
    │  └─ Property C: Score 88/100, Awaiting Feedback
    │
    └─ Market Watch
       ├─ Rising Areas (Green)
       ├─ Stable Areas (Blue)
       └─ Declining Areas (Red)

GET /command-center/metrics
  → Returns: All metrics JSON for integrations

GET /api/activity-stream
  → Returns: Live activity feed (WebSocket ready)
  → Real-time lead/deal/property updates

GET /command-center/forecast
  → Show: Business forecast
  → Projected: Revenue, deals closing, lead conversion
  → Timeline: Next 30/60/90 days

POST /command-center/alert-settings
  → Configure: Alert thresholds
  → Alerts: Hot leads generated, deals closing soon, etc
```

### **Command Center Visualizations**

```
╔═══════════════════════════════════════════════════════════╗
║         🎯 JARVIS COMMAND CENTER — REAL-TIME              ║
╚═══════════════════════════════════════════════════════════╝

📊 KEY METRICS (Live)
┌─────────────┬──────────┬──────────┬─────────────┐
│ Leads Today │ Hot      │ Deals    │ Pipeline    │
│     47      │   12 🔥  │    8     │   ₹50Cr ⬆️  │
└─────────────┴──────────┴──────────┴─────────────┘

📈 LEAD FUNNEL
New (247) → Contacted (189, 77%) → Site Visit (67, 35%) → Offer (23, 34%) → Closed (8, 35%)

👥 TOP AGENTS THIS MONTH
#1 Vikram: 3 deals | ₹2.5Cr | 25% conversion
#2 Priya: 2 deals | ₹1.8Cr | 22% conversion
#3 Arjun: 2 deals | ₹1.2Cr | 18% conversion

🎯 HIGHEST OPPORTUNITY PROPERTIES
1. 4BHK Villa, Jagatpura — Score: 95/100 | Hot leads: 5
2. 3BHK Flat, C-Scheme — Score: 92/100 | Warm leads: 8
3. Plot, Ajmer Road — Score: 88/100 | Awaiting feedback

📍 MARKET OPPORTUNITIES
Rising: Jagatpura, Vaishali ⬆️ (4.2% growth)
Stable: C-Scheme, MI Road ➡️ (2.1% growth)
Watch: Mansarovar ⬇️ (1.3% growth)

🔔 ACTIVE ALERTS
- 3 hot leads need immediate follow-up
- Deal closing in 5 days: Registry pending
- Property approaching 60 days on market
```

### **Implementation Priority**: MEDIUM-LOW
**Estimated Effort**: 3-4 weeks
**Dependencies**: Systems 1-9 (All data sources)

---

## 📋 IMPLEMENTATION ROADMAP

### **Phase 2A: Foundation (Weeks 1-3)**
```
Week 1: Property Intelligence Engine (System 1)
├─ Database schema (property_intelligence, location_data)
├─ Scoring formulas implementation
└─ Routes: /property/<id>/intelligence, /api/property/<id>/scores

Week 2: Investment OS (System 2)  
├─ Database schema (investment_calculations, comparison_sets)
├─ Calculation engine (EMI, ROI, CAGR, scenarios)
└─ Routes: /calculator, /calculate, /calculation/<id>, /compare

Week 3: Property Matchmaker (System 3)
├─ Database schema (buyer_requirements, property_matches)
├─ Matching algorithm
└─ Routes: /requirements/new, /requirements/<id>/matches
```

### **Phase 2B: Growth Systems (Weeks 4-7)**
```
Week 4: Growth Map (System 4)
├─ Market insights schema
├─ Infrastructure projects tracking
└─ Routes: /growth-map, /growth-map/<city>, /growth-map/<city>/<locality>

Week 5: Deal Room (System 5)
├─ Database schema (deal_rooms, participants, documents, communications)
├─ File upload handling
└─ Routes: /deal-room/new, /deal-room/<id>, /deal-room/<id>/documents

Week 6: Premium Resort Desk (System 6)
├─ Extend investments schema
├─ Premium project pages
└─ Routes: /mega-investments, /mega-investment/<id>
```

### **Phase 2C: Intelligence Systems (Weeks 8-12)**
```
Week 7: AI Concierge Foundation (System 7)
├─ Database schema (concierge_sessions, recommendations)
├─ NLP framework setup
└─ Routes: /concierge, /api/concierge/chat

Week 8: Opportunity Score™ (System 8)
├─ Database schema (property_opportunity_scores, methodology)
├─ Scoring formula & versioning
└─ Routes: /property/<id>/score, /score-methodology

Week 9: CRM Intelligence (System 9)
├─ Extend enquiries schema (lead scoring)
├─ Agent performance metrics
└─ Routes: /agent/dashboard, /agent/leads, /admin/crm-analytics

Week 10-12: Command Center (System 10)
├─ Dashboard schema (activity_stream, system_metrics)
├─ Real-time visualization
└─ Routes: /command-center, /command-center/metrics, /api/activity-stream
```

---

## 🔗 INTEGRATION MATRIX

```
                    ┌─────────┬─────────┬─────────┬─────────┬─────────┬─────────┬─────────┬─────────┬─────────┬─────────┐
                    │ System  │ System  │ System  │ System  │ System  │ System  │ System  │ System  │ System  │ System  │
                    │    1    │    2    │    3    │    4    │    5    │    6    │    7    │    8    │    9    │   10    │
                    │Intel    │Invest   │ Match   │ Growth  │ Deal    │ Resort  │Concierge│ Score  │  CRM    │ Command │
├─────────────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┤
│ System 1: Intel │    ─    │   ←     │   →     │   →     │    ←    │    ←    │   ←     │   →     │    ←    │    ←    │
│ System 2: Invest│   →     │    ─    │   ←     │    ─    │    ←    │   ←     │   ←     │    ─    │    ←    │    ←    │
│ System 3: Match │   ←     │   ←     │    ─    │   ←     │   ←     │    ←    │   ←     │   ←     │    ←    │    ←    │
│ System 4: Growth│   ←     │    ─    │   ←     │    ─    │    ←    │   ←     │   ←     │    ─    │    ←    │    ←    │
│ System 5: Deal  │    ─    │   →     │    ─    │    ─    │    ─    │   →     │    ←    │    ─    │    ←    │    ←    │
│ System 6: Resort│   →     │   →     │    ─    │   →     │   ←     │    ─    │   ←     │    ─    │    ←    │    ←    │
│ System 7:Concierge│  ←     │   ←     │   →     │   ←     │    ←    │   ←     │    ─    │   ←     │    ←    │    ←    │
│ System 8: Score │   ←     │    ─    │   ←     │    ─    │    ─    │    ─    │   ←     │    ─    │    ←    │    ←    │
│ System 9: CRM   │   →     │   →     │   →     │   →     │    ←    │   →     │   ←     │    ←    │    ─    │    ←    │
│ System 10: Center│  ←     │   ←     │   ←     │   ←     │    ←    │   ←     │   ←     │    ←    │    ←    │    ─    │
└─────────────────┴─────────┴─────────┴─────────┴─────────┴─────────┴─────────┴─────────┴─────────┴─────────┴─────────┘

Legend: → = provides data to | ← = receives data from | ─ = self-contained
```

---

## 🎯 SUCCESS CRITERIA (Phase 2)

By end of Phase 2, the platform will have:

✅ **System 1**: Every property has intelligence scores & location analysis
✅ **System 2**: Users can calculate full investment scenarios & compare
✅ **System 3**: Intelligent matching recommends properties to profiles
✅ **System 4**: Market map shows growth trends & opportunities
✅ **System 5**: Private deal rooms support full transaction lifecycle
✅ **System 6**: Premium project pages attract institutional investors
✅ **System 7**: Concierge foundation ready for NLP (Phase 3)
✅ **System 8**: Proprietary scoring differentiates the platform
✅ **System 9**: Agents have CRM intelligence & lead prioritization
✅ **System 10**: Command center shows real-time business intelligence

**Zero breaking changes** to existing functionality—all additions to existing tables and new routes.

