# 🗄️ DATABASE MIGRATION STRATEGY
## Safe, Incremental Schema Evolution (Zero Breaking Changes)

**Principle**: Add new tables and columns only. Never modify existing tables that existing code depends on.

---

## 🎯 MIGRATION PHILOSOPHY

```
EXISTING SCHEMA (Untouchable)
├─ users
├─ properties
├─ enquiries
├─ callbacks
├─ favorites
├─ sessions
├─ leads
├─ investments
└─ insights

NEW TABLES (Add Only - Weeks 1-12)
├─ Week 1: property_intelligence, location_data
├─ Week 2: investment_calculations, comparison_sets
├─ Week 3: buyer_requirements, property_matches
├─ Week 4: market_insights, infrastructure_projects, growth_indicators
├─ Week 5: deal_rooms, deal_room_participants, deal_documents, deal_communications, deal_milestones, deal_payments
├─ Week 6: premium_investments, mega_project_developers, mega_project_inquiries
├─ Week 7: concierge_sessions, concierge_recommendations
├─ Week 8: property_opportunity_scores, score_methodology_v1
├─ Week 9: agent_performance_metrics, lead_scoring_model, recommended_actions
└─ Week 10: activity_stream, dashboard_widgets, system_metrics

OPTIONAL DENORMALIZATION COLUMNS (Add if needed - Week 9+)
└─ enquiries: ADD lead_temperature, lead_score, predicted_close_probability
```

**Golden Rule**: If it doesn't break existing queries, add it. If it requires modifying existing queries, don't do it.

---

## 📋 MIGRATION PHASES

### **PHASE 0: BACKUP & SNAPSHOT (Before Any Changes)**

```python
# backup_database.py
import sqlite3
import shutil
from datetime import datetime

def backup_database():
    """Create backup before any schema changes"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"database_backup_{timestamp}.db"
    shutil.copy("realtor.db", backup_path)
    print(f"✅ Backup created: {backup_path}")
    return backup_path

def verify_existing_schema():
    """Verify existing schema is intact"""
    conn = sqlite3.connect("realtor.db")
    cursor = conn.cursor()
    
    existing_tables = [
        'users', 'properties', 'enquiries', 'callbacks', 
        'favorites', 'sessions', 'leads', 'investments', 'insights'
    ]
    
    for table in existing_tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"✅ {table}: {count} rows")
    
    conn.close()

# RUN BEFORE MIGRATIONS
backup_database()
verify_existing_schema()
```

---

## 🔄 MIGRATION STRATEGY (By Week)

### **WEEK 1: PROPERTY INTELLIGENCE SCHEMA**

**Files to Modify**:
- `database.py` - Add new table definitions

**Migration**:

```python
# database.py - ADD (no modifications to existing code)

def init_intelligence_tables():
    """Create intelligence tracking tables - Week 1"""
    cursor = db.cursor()
    
    # NEW TABLE: property_intelligence
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS property_intelligence (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        property_id INTEGER NOT NULL UNIQUE,
        
        location_score INTEGER DEFAULT 0,
        connectivity_score INTEGER DEFAULT 0,
        infrastructure_score INTEGER DEFAULT 0,
        
        price_positioning_score INTEGER DEFAULT 0,
        rental_potential_score INTEGER DEFAULT 0,
        appreciation_potential_score INTEGER DEFAULT 0,
        
        risk_score INTEGER DEFAULT 0,
        liquidity_score INTEGER DEFAULT 0,
        
        area_growth_trend TEXT DEFAULT '',
        area_growth_pct REAL DEFAULT 0.0,
        comparable_price REAL DEFAULT 0,
        price_variance REAL DEFAULT 0.0,
        
        investor_type TEXT DEFAULT '',
        investment_fit_score INTEGER DEFAULT 0,
        match_explanation TEXT DEFAULT '',
        
        analyst_notes TEXT DEFAULT '',
        last_updated TEXT NOT NULL,
        
        FOREIGN KEY (property_id) REFERENCES properties(id)
    )
    ''')
    
    # NEW TABLE: location_data
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS location_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        city TEXT NOT NULL,
        locality TEXT NOT NULL,
        
        nearest_metro_km REAL DEFAULT 0,
        nearest_mall_km REAL DEFAULT 0,
        nearest_hospital_km REAL DEFAULT 0,
        nearest_school_km REAL DEFAULT 0,
        
        road_quality TEXT DEFAULT '',
        public_transport TEXT DEFAULT '',
        airport_km REAL DEFAULT 0,
        
        infrastructure_under_development TEXT DEFAULT '',
        metro_planned BOOLEAN DEFAULT 0,
        commercial_development TEXT DEFAULT '',
        
        avg_price_per_sqft INTEGER DEFAULT 0,
        price_growth_1yr REAL DEFAULT 0.0,
        price_growth_3yr REAL DEFAULT 0.0,
        price_growth_5yr REAL DEFAULT 0.0,
        
        avg_rental_yield REAL DEFAULT 0.0,
        demand_level TEXT DEFAULT 'medium',
        
        last_updated TEXT NOT NULL,
        UNIQUE (city, locality)
    )
    ''')
    
    db.commit()
    print("✅ Week 1 tables created: property_intelligence, location_data")

# CALL IN init_db():
def init_db():
    """Initialize database with all tables"""
    # ... existing code ...
    init_intelligence_tables()  # ← ADD THIS LINE
    # ... rest of existing code ...
```

**Deployment**:
```bash
# 1. Backup
python3 -c "from database import backup_database; backup_database()"

# 2. Verify existing tables
python3 -c "from database import verify_existing_schema; verify_existing_schema()"

# 3. Create new tables
python3 -c "from database import init_db; init_db()"

# 4. Verify new tables created
sqlite3 realtor.db ".tables"
# Should show: ... property_intelligence location_data
```

**Testing**:
```python
# test_week1_migration.py
import sqlite3

def test_existing_tables_untouched():
    """Verify existing tables are not modified"""
    conn = sqlite3.connect("realtor.db")
    cursor = conn.cursor()
    
    # Check users table still has original columns
    cursor.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in cursor.fetchall()]
    assert 'id' in columns
    assert 'name' in columns
    assert 'email' in columns
    
    conn.close()
    print("✅ Existing tables untouched")

def test_new_tables_created():
    """Verify new tables exist"""
    conn = sqlite3.connect("realtor.db")
    cursor = conn.cursor()
    
    # Check new tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    assert 'property_intelligence' in tables
    assert 'location_data' in tables
    
    conn.close()
    print("✅ New tables created successfully")

# RUN TESTS
test_existing_tables_untouched()
test_new_tables_created()
```

---

### **WEEK 2: INVESTMENT OS SCHEMA**

```python
# database.py - ADD

def init_investment_tables():
    """Create investment calculation tables - Week 2"""
    cursor = db.cursor()
    
    # NEW TABLE: investment_calculations
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS investment_calculations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        property_id INTEGER,
        user_id INTEGER,
        
        property_name TEXT NOT NULL,
        investment_amount INTEGER NOT NULL,
        down_payment INTEGER NOT NULL,
        loan_amount INTEGER DEFAULT 0,
        
        loan_rate REAL DEFAULT 0.0,
        loan_term_years INTEGER DEFAULT 0,
        emi REAL DEFAULT 0,
        
        rental_income_monthly INTEGER DEFAULT 0,
        rental_growth_annual REAL DEFAULT 0.0,
        
        property_appreciation_annual REAL DEFAULT 0.0,
        holding_period_years INTEGER DEFAULT 0,
        estimated_resale_value INTEGER DEFAULT 0,
        
        annual_maintenance INTEGER DEFAULT 0,
        annual_property_tax INTEGER DEFAULT 0,
        annual_insurance INTEGER DEFAULT 0,
        annual_vacancy_loss REAL DEFAULT 0.0,
        
        total_rental_income INTEGER DEFAULT 0,
        total_emi_paid INTEGER DEFAULT 0,
        total_expenses INTEGER DEFAULT 0,
        total_return INTEGER DEFAULT 0,
        roi_percentage REAL DEFAULT 0.0,
        cagr REAL DEFAULT 0.0,
        cash_on_cash_return REAL DEFAULT 0.0,
        
        scenario_type TEXT NOT NULL,
        
        created_at TEXT NOT NULL,
        FOREIGN KEY (property_id) REFERENCES properties(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    ''')
    
    # NEW TABLE: comparison_sets
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS comparison_sets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        
        calculations_json TEXT NOT NULL,
        
        best_roi_calc_id INTEGER,
        best_rental_calc_id INTEGER,
        most_liquid_calc_id INTEGER,
        
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    ''')
    
    db.commit()
    print("✅ Week 2 tables created: investment_calculations, comparison_sets")

# UPDATE init_db():
def init_db():
    # ... existing code ...
    init_intelligence_tables()  # Week 1
    init_investment_tables()     # ← ADD THIS LINE
```

---

### **WEEK 3: PROPERTY MATCHMAKER SCHEMA**

```python
# database.py - ADD

def init_matching_tables():
    """Create matching tables - Week 3"""
    cursor = db.cursor()
    
    # NEW TABLE: buyer_requirements
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS buyer_requirements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        
        budget_min INTEGER NOT NULL,
        budget_max INTEGER NOT NULL,
        location_preferences TEXT NOT NULL,
        property_types TEXT NOT NULL,
        listing_type TEXT NOT NULL,
        
        min_bedrooms INTEGER DEFAULT 0,
        min_bathrooms INTEGER DEFAULT 0,
        min_area_sqft INTEGER DEFAULT 0,
        max_area_sqft INTEGER DEFAULT 0,
        
        investment_purpose TEXT DEFAULT '',
        expected_holding_years INTEGER DEFAULT 0,
        expected_roi_min REAL DEFAULT 0,
        expected_rental_yield REAL DEFAULT 0,
        
        amenities_wanted TEXT DEFAULT '',
        walkability_important BOOLEAN DEFAULT 0,
        public_transit_important BOOLEAN DEFAULT 0,
        
        investor_profile TEXT DEFAULT '',
        
        created_at TEXT NOT NULL,
        last_updated TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    ''')
    
    # NEW TABLE: property_matches
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS property_matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        requirement_id INTEGER NOT NULL,
        property_id INTEGER NOT NULL,
        
        match_score INTEGER DEFAULT 0,
        
        price_fit_score INTEGER DEFAULT 0,
        location_fit_score INTEGER DEFAULT 0,
        property_type_fit INTEGER DEFAULT 0,
        amenity_fit_score INTEGER DEFAULT 0,
        investment_fit_score INTEGER DEFAULT 0,
        lifestyle_fit_score INTEGER DEFAULT 0,
        
        match_explanation TEXT DEFAULT '',
        match_reasons TEXT DEFAULT '',
        potential_concerns TEXT DEFAULT '',
        
        rank INTEGER DEFAULT 0,
        
        created_at TEXT NOT NULL,
        FOREIGN KEY (requirement_id) REFERENCES buyer_requirements(id),
        FOREIGN KEY (property_id) REFERENCES properties(id),
        UNIQUE (requirement_id, property_id)
    )
    ''')
    
    db.commit()
    print("✅ Week 3 tables created: buyer_requirements, property_matches")

# UPDATE init_db():
def init_db():
    # ... existing code ...
    init_intelligence_tables()  # Week 1
    init_investment_tables()    # Week 2
    init_matching_tables()      # ← ADD THIS LINE
```

---

### **WEEKS 4-12: CONTINUE SAME PATTERN**

Each week:
1. Create new migration function in `database.py`
2. Add all new tables for that week
3. Call function in `init_db()`
4. Backup database before deployment
5. Run migration
6. Test existing functionality still works

**Template for Each Week**:

```python
# database.py

def init_week_X_tables():
    """Create tables for Week X - [System Name]"""
    cursor = db.cursor()
    
    # NEW TABLE 1: ...
    cursor.execute('''CREATE TABLE IF NOT EXISTS ... ''')
    
    # NEW TABLE 2: ...
    cursor.execute('''CREATE TABLE IF NOT EXISTS ... ''')
    
    db.commit()
    print("✅ Week X tables created: ...")

# UPDATE init_db():
def init_db():
    # ... existing code unchanged ...
    
    # Week-by-week additions
    init_intelligence_tables()      # Week 1
    init_investment_tables()        # Week 2
    init_matching_tables()          # Week 3
    init_growth_map_tables()        # Week 4
    init_deal_room_tables()         # Week 5
    init_premium_investment_tables() # Week 6
    init_concierge_tables()         # Week 7
    init_scoring_tables()           # Week 8
    init_crm_tables()               # Week 9
    init_command_center_tables()    # Week 10
```

---

## ⚠️ OPTIONAL: DENORMALIZATION (Week 9+)

**Only if needed for performance**. Add optional columns to existing table without breaking changes:

```python
# database.py - ONLY if performance requires it

def add_lead_scoring_columns():
    """Add optional columns to enquiries table - Week 9+
    
    NOTE: Only do this if benchmarking shows it's needed.
    Conservative approach: Keep scoring in separate table instead.
    """
    cursor = db.cursor()
    
    # Get existing columns
    cursor.execute("PRAGMA table_info(enquiries)")
    existing_columns = {row[1] for row in cursor.fetchall()}
    
    # Add column only if it doesn't exist
    if 'lead_temperature' not in existing_columns:
        cursor.execute('''
        ALTER TABLE enquiries ADD COLUMN lead_temperature TEXT DEFAULT 'cold'
        ''')
        print("✅ Added: lead_temperature column")
    
    if 'lead_score' not in existing_columns:
        cursor.execute('''
        ALTER TABLE enquiries ADD COLUMN lead_score INTEGER DEFAULT 0
        ''')
        print("✅ Added: lead_score column")
    
    if 'predicted_close_probability' not in existing_columns:
        cursor.execute('''
        ALTER TABLE enquiries ADD COLUMN predicted_close_probability REAL DEFAULT 0
        ''')
        print("✅ Added: predicted_close_probability column")
    
    db.commit()

# SAFE TO CALL ANYTIME - checks if columns exist first
add_lead_scoring_columns()
```

**Better approach**: Keep scoring in separate table:

```python
# Avoid modifying enquiries, use separate lead_scoring_model table instead
CREATE TABLE IF NOT EXISTS lead_scoring_model (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    enquiry_id INTEGER NOT NULL UNIQUE,
    lead_temperature TEXT DEFAULT 'cold',
    lead_score INTEGER DEFAULT 0,
    predicted_close_probability REAL DEFAULT 0,
    calculated_at TEXT NOT NULL,
    FOREIGN KEY (enquiry_id) REFERENCES enquiries(id)
);
```

---

## 🔄 ROLLBACK STRATEGY

**If something goes wrong**:

```python
# rollback.py
import shutil
from datetime import datetime

def rollback_to_backup(backup_path):
    """Restore from backup"""
    shutil.copy(backup_path, "realtor.db")
    print(f"✅ Rolled back to: {backup_path}")

# Usage:
# 1. Find latest backup
# 2. Run: python3 rollback.py backup_path_here.db
# 3. Verify: python3 -c "from database import verify_existing_schema; verify_existing_schema()"
```

---

## 📊 MIGRATION VERIFICATION CHECKLIST

### **After Each Weekly Migration**:

```
□ Backup created before migration
□ New tables created successfully
□ Existing tables unchanged
□ All existing queries still work
□ New functionality tested
□ Performance benchmarked
□ Data integrity verified
□ Rollback plan documented
```

### **Test Script**:

```python
# test_migration.py
import sqlite3

def test_migration(week_num):
    """Comprehensive migration test"""
    conn = sqlite3.connect("realtor.db")
    cursor = conn.cursor()
    
    print(f"\n🧪 Testing Week {week_num} Migration\n")
    
    # 1. Verify existing tables
    print("1. Verifying existing tables...")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    assert 'users' in tables, "users table missing!"
    assert 'properties' in tables, "properties table missing!"
    print("   ✅ All existing tables intact")
    
    # 2. Verify new tables
    print("2. Verifying new tables...")
    expected_tables = {
        1: ['property_intelligence', 'location_data'],
        2: ['investment_calculations', 'comparison_sets'],
        3: ['buyer_requirements', 'property_matches'],
        # ... etc
    }[week_num]
    
    for table in expected_tables:
        assert table in tables, f"{table} not created!"
    print(f"   ✅ All {len(expected_tables)} new tables created")
    
    # 3. Verify existing data intact
    print("3. Verifying existing data...")
    cursor.execute("SELECT COUNT(*) FROM users")
    user_count = cursor.fetchone()[0]
    assert user_count > 0, "Users data lost!"
    
    cursor.execute("SELECT COUNT(*) FROM properties")
    prop_count = cursor.fetchone()[0]
    assert prop_count > 0, "Properties data lost!"
    print(f"   ✅ Data intact: {user_count} users, {prop_count} properties")
    
    # 4. Test existing queries
    print("4. Testing existing functionality...")
    cursor.execute("SELECT * FROM properties WHERE id = 1")
    result = cursor.fetchone()
    assert result is not None, "Cannot query properties!"
    print("   ✅ Existing queries still work")
    
    # 5. Test new functionality
    print("5. Testing new functionality...")
    cursor.execute("SELECT COUNT(*) FROM property_intelligence")
    intel_count = cursor.fetchone()[0]
    print(f"   ✅ New tables queryable: {intel_count} intelligence records")
    
    # 6. Performance check
    print("6. Checking performance...")
    import time
    start = time.time()
    cursor.execute("SELECT * FROM properties LIMIT 10")
    cursor.fetchall()
    elapsed = time.time() - start
    assert elapsed < 0.1, "Performance degraded!"
    print(f"   ✅ Performance acceptable: {elapsed*1000:.1f}ms")
    
    print(f"\n✅ Week {week_num} migration verified successfully!\n")
    
    conn.close()

# Run after each migration:
# python3 test_migration.py
```

---

## 📈 FINAL SCHEMA (After Week 12)

**Total New Tables**: 20
**Total Existing Tables**: 9 (unchanged)
**Total Database Size**: ~50MB (estimated)

```
Users & Auth (Existing)
├─ users (existing)
├─ sessions (existing)

Properties & Listings (Existing + New)
├─ properties (existing)
├─ property_intelligence (Week 1)
├─ location_data (Week 1)

Client Relationships (Existing + New)
├─ enquiries (existing)
├─ callbacks (existing)
├─ favorites (existing)
├─ buyer_requirements (Week 3)
├─ property_matches (Week 3)
├─ lead_scoring_model (Week 9)
├─ recommended_actions (Week 9)

Investments & Finance (Existing + New)
├─ investments (existing)
├─ investment_calculations (Week 2)
├─ comparison_sets (Week 2)
├─ premium_investments (Week 6)
├─ mega_project_developers (Week 6)
├─ mega_project_inquiries (Week 6)

Market Intelligence (New - Week 4)
├─ market_insights (Week 4)
├─ infrastructure_projects (Week 4)
├─ growth_indicators (Week 4)

Transactions & Collaboration (New - Week 5)
├─ deal_rooms (Week 5)
├─ deal_room_participants (Week 5)
├─ deal_documents (Week 5)
├─ deal_communications (Week 5)
├─ deal_milestones (Week 5)
├─ deal_payments (Week 5)

Conversational AI (New - Week 7)
├─ concierge_sessions (Week 7)
├─ concierge_recommendations (Week 7)

Scoring & Analytics (New - Week 8+)
├─ property_opportunity_scores (Week 8)
├─ score_methodology_v1 (Week 8)
├─ agent_performance_metrics (Week 9)

Operations (New - Week 10)
├─ activity_stream (Week 10)
├─ dashboard_widgets (Week 10)
├─ system_metrics (Week 10)

Content & Insights (Existing)
├─ insights (existing)
└─ leads (existing)
```

---

## ✅ MIGRATION COMPLETE CHECKLIST

By end of Week 12:

- [x] Zero breaking changes to existing tables
- [x] All existing queries still functional
- [x] 20 new tables created successfully
- [x] Data migrations tested and verified
- [x] Rollback procedures documented
- [x] Performance acceptable
- [x] All 10 systems operational
- [x] Zero data loss
- [x] Full audit trail maintained

---

**Status**: ✅ **MIGRATION STRATEGY COMPLETE**

**Next Step**: Execute Week 1 migrations in `database.py`

