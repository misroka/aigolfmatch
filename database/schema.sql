-- Golf Club Database Schema
-- Comprehensive database for tracking golf clubs from all major brands

-- Brands table
CREATE TABLE brands (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    country VARCHAR(50),
    website VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Club types/categories
CREATE TABLE club_types (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,  -- Driver, Fairway Wood, Hybrid, Iron, Wedge, Putter
    description TEXT
);

-- Main golf clubs table
CREATE TABLE golf_clubs (
    id SERIAL PRIMARY KEY,
    brand_id INTEGER REFERENCES brands(id),
    club_type_id INTEGER REFERENCES club_types(id),
    model_name VARCHAR(200) NOT NULL,
    year_released INTEGER NOT NULL,
    year_discontinued INTEGER,
    msrp DECIMAL(10, 2),
    current_price DECIMAL(10, 2),
    is_current BOOLEAN DEFAULT TRUE,
    description TEXT,
    target_handicap_range VARCHAR(50),  -- e.g., "0-10", "10-20", "20+"
    skill_level VARCHAR(50),  -- Beginner, Intermediate, Advanced, Professional
    gender VARCHAR(20),  -- Men's, Women's, Junior's, Unisex
    hand VARCHAR(10),  -- Right, Left, Both
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(brand_id, model_name, year_released)
);

-- Club specifications
CREATE TABLE club_specifications (
    id SERIAL PRIMARY KEY,
    golf_club_id INTEGER REFERENCES golf_clubs(id) ON DELETE CASCADE,
    loft_degrees DECIMAL(4, 1),
    lie_angle_degrees DECIMAL(4, 1),
    club_length_inches DECIMAL(4, 2),
    swing_weight VARCHAR(10),
    shaft_material VARCHAR(50),  -- Steel, Graphite, Carbon Fiber
    shaft_flex VARCHAR(20),  -- Extra Stiff, Stiff, Regular, Senior, Ladies
    shaft_model VARCHAR(100),
    grip_model VARCHAR(100),
    club_head_material VARCHAR(100),
    club_head_volume_cc INTEGER,  -- For woods/drivers
    offset_mm DECIMAL(4, 1),
    bounce_degrees DECIMAL(4, 1),  -- For wedges
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Product URLs and sources
CREATE TABLE product_sources (
    id SERIAL PRIMARY KEY,
    golf_club_id INTEGER REFERENCES golf_clubs(id) ON DELETE CASCADE,
    source_name VARCHAR(100) NOT NULL,  -- Golf Galaxy, PGA Tour Superstore, etc.
    product_url VARCHAR(500),
    price DECIMAL(10, 2),
    in_stock BOOLEAN,
    last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Reviewer profiles for personalized recommendations
CREATE TABLE reviewer_profiles (
    id SERIAL PRIMARY KEY,
    external_id VARCHAR(100),  -- ID from review source (e.g., user123 from GlobalGolf)
    source_name VARCHAR(100),  -- Where the reviewer profile came from
    age INTEGER,
    weight_lbs INTEGER,
    height_inches INTEGER,
    gender VARCHAR(20),  -- Male, Female, Other
    handicap DECIMAL(4, 1),  -- Golf handicap index
    average_drive_distance_yards INTEGER,
    swing_speed_mph INTEGER,  -- Driver swing speed
    swing_tempo VARCHAR(20),  -- Slow, Moderate, Fast
    ball_flight VARCHAR(30),  -- Draw, Fade, Straight, Hook, Slice
    skill_level VARCHAR(50),  -- Beginner, Intermediate, Advanced, Professional
    years_playing INTEGER,
    rounds_per_year INTEGER,
    primary_miss VARCHAR(30),  -- Left, Right, Short, Long
    launch_angle_preference VARCHAR(20),  -- Low, Mid, High
    spin_preference VARCHAR(20),  -- Low, Mid, High
    feel_preference VARCHAR(20),  -- Soft, Medium, Firm
    game_improvement_priority VARCHAR(100),  -- Distance, Accuracy, Forgiveness, etc.
    budget_range VARCHAR(50),  -- e.g., "$0-500", "$500-1000", "$1000+"
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(external_id, source_name)
);

-- Reviews and ratings aggregation
CREATE TABLE club_reviews (
    id SERIAL PRIMARY KEY,
    golf_club_id INTEGER REFERENCES golf_clubs(id) ON DELETE CASCADE,
    reviewer_profile_id INTEGER REFERENCES reviewer_profiles(id) ON DELETE SET NULL,
    source_name VARCHAR(100),
    rating DECIMAL(3, 2),  -- 0.00 to 5.00
    num_reviews INTEGER,
    pros TEXT[],
    cons TEXT[],
    review_text TEXT,
    review_title VARCHAR(255),
    verified_purchase BOOLEAN,
    helpful_count INTEGER,  -- Number of users who found review helpful
    review_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Technologies/Features
CREATE TABLE technologies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT
);

CREATE TABLE club_technologies (
    golf_club_id INTEGER REFERENCES golf_clubs(id) ON DELETE CASCADE,
    technology_id INTEGER REFERENCES technologies(id),
    PRIMARY KEY (golf_club_id, technology_id)
);

-- Data collection tracking
CREATE TABLE scraping_logs (
    id SERIAL PRIMARY KEY,
    source_name VARCHAR(100) NOT NULL,
    scrape_type VARCHAR(50),  -- full, incremental, update_prices
    status VARCHAR(20),  -- success, failed, partial
    records_added INTEGER DEFAULT 0,
    records_updated INTEGER DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_golf_clubs_brand ON golf_clubs(brand_id);
CREATE INDEX idx_golf_clubs_type ON golf_clubs(club_type_id);
CREATE INDEX idx_golf_clubs_year ON golf_clubs(year_released);
CREATE INDEX idx_golf_clubs_current ON golf_clubs(is_current);
CREATE INDEX idx_product_sources_club ON product_sources(golf_club_id);
CREATE INDEX idx_club_specs_club ON club_specifications(golf_club_id);
CREATE INDEX idx_club_reviews_club ON club_reviews(golf_club_id);
CREATE INDEX idx_club_reviews_profile ON club_reviews(reviewer_profile_id);
CREATE INDEX idx_reviewer_profiles_handicap ON reviewer_profiles(handicap);
CREATE INDEX idx_reviewer_profiles_skill ON reviewer_profiles(skill_level);
CREATE INDEX idx_scraping_logs_source_date ON scraping_logs(source_name, started_at);
