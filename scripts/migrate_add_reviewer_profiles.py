"""Migration script to add reviewer profiles to existing database."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.db import db


def run_migration():
    """Add reviewer_profiles table and update club_reviews table."""
    
    print("Starting migration: Adding reviewer profiles...")
    
    migrations = [
        # Step 1: Create reviewer_profiles table
        """
        CREATE TABLE IF NOT EXISTS reviewer_profiles (
            id SERIAL PRIMARY KEY,
            external_id VARCHAR(100),
            source_name VARCHAR(100),
            age INTEGER,
            weight_lbs INTEGER,
            height_inches INTEGER,
            gender VARCHAR(20),
            handicap DECIMAL(4, 1),
            average_drive_distance_yards INTEGER,
            swing_speed_mph INTEGER,
            swing_tempo VARCHAR(20),
            ball_flight VARCHAR(30),
            skill_level VARCHAR(50),
            years_playing INTEGER,
            rounds_per_year INTEGER,
            primary_miss VARCHAR(30),
            launch_angle_preference VARCHAR(20),
            spin_preference VARCHAR(20),
            feel_preference VARCHAR(20),
            game_improvement_priority VARCHAR(100),
            budget_range VARCHAR(50),
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(external_id, source_name)
        )
        """,
        
        # Step 2: Add reviewer_profile_id to club_reviews if not exists
        """
        DO $$ 
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'club_reviews' 
                AND column_name = 'reviewer_profile_id'
            ) THEN
                ALTER TABLE club_reviews 
                ADD COLUMN reviewer_profile_id INTEGER REFERENCES reviewer_profiles(id) ON DELETE SET NULL;
            END IF;
        END $$
        """,
        
        # Step 3: Add new columns to club_reviews if not exists
        """
        DO $$ 
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'club_reviews' 
                AND column_name = 'review_text'
            ) THEN
                ALTER TABLE club_reviews ADD COLUMN review_text TEXT;
            END IF;
            
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'club_reviews' 
                AND column_name = 'review_title'
            ) THEN
                ALTER TABLE club_reviews ADD COLUMN review_title VARCHAR(255);
            END IF;
            
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'club_reviews' 
                AND column_name = 'verified_purchase'
            ) THEN
                ALTER TABLE club_reviews ADD COLUMN verified_purchase BOOLEAN;
            END IF;
            
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'club_reviews' 
                AND column_name = 'helpful_count'
            ) THEN
                ALTER TABLE club_reviews ADD COLUMN helpful_count INTEGER;
            END IF;
        END $$
        """,
        
        # Step 4: Create indexes
        """
        CREATE INDEX IF NOT EXISTS idx_club_reviews_club ON club_reviews(golf_club_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_club_reviews_profile ON club_reviews(reviewer_profile_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_reviewer_profiles_handicap ON reviewer_profiles(handicap)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_reviewer_profiles_skill ON reviewer_profiles(skill_level)
        """
    ]
    
    try:
        with db.get_cursor() as cursor:
            for i, migration in enumerate(migrations, 1):
                print(f"Running migration step {i}/{len(migrations)}...")
                cursor.execute(migration)
        
        print("\n✓ Migration completed successfully!")
        print("\nNew features:")
        print("  - reviewer_profiles table created")
        print("  - club_reviews.reviewer_profile_id added")
        print("  - Additional review fields (review_text, review_title, etc.)")
        print("  - Indexes created for better performance")
        print("\nYou can now:")
        print("  - Store detailed reviewer information")
        print("  - Link reviews to reviewer profiles")
        print("  - Make more personalized recommendations")
        
    except Exception as e:
        print(f"\n✗ Migration failed: {str(e)}")
        sys.exit(1)


def main():
    """Run the migration."""
    print("=" * 60)
    print("Golf Club Database Migration")
    print("Adding Reviewer Profiles Support")
    print("=" * 60)
    print()
    
    response = input("This will modify your database. Continue? (yes/no): ")
    
    if response.lower() in ['yes', 'y']:
        run_migration()
    else:
        print("Migration cancelled.")


if __name__ == "__main__":
    main()
