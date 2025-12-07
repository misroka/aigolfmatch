"""Database connection and utility functions."""

import os
from typing import List, Optional, Dict, Any
from contextlib import contextmanager
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()


class DatabaseConnection:
    """Manages database connections and queries."""
    
    def __init__(self):
        self.config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': os.getenv('DB_PORT', '5432'),
            'database': os.getenv('DB_NAME', 'golf_clubs'),
            'user': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASSWORD', '')
        }
        # Add SSL mode if specified (required for Azure PostgreSQL)
        sslmode = os.getenv('DB_SSLMODE')
        if sslmode:
            self.config['sslmode'] = sslmode
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = psycopg2.connect(**self.config)
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    @contextmanager
    def get_cursor(self, cursor_factory=RealDictCursor):
        """Context manager for database cursors."""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=cursor_factory)
            try:
                yield cursor
            finally:
                cursor.close()


db = DatabaseConnection()


def get_clubs(
    brand: Optional[str] = None,
    club_type: Optional[str] = None,
    year: Optional[int] = None,
    year_min: Optional[int] = None,
    year_max: Optional[int] = None,
    skill_level: Optional[str] = None,
    is_current: Optional[bool] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Query golf clubs with various filters.
    
    Args:
        brand: Brand name
        club_type: Type of club (Driver, Iron, etc.)
        year: Specific release year
        year_min: Minimum release year
        year_max: Maximum release year
        skill_level: Skill level (Beginner, Intermediate, Advanced, Professional)
        is_current: Whether club is currently in production
        limit: Maximum number of results
    
    Returns:
        List of club dictionaries
    """
    query = """
        SELECT 
            gc.*,
            b.name as brand_name,
            ct.name as club_type_name
        FROM golf_clubs gc
        JOIN brands b ON gc.brand_id = b.id
        JOIN club_types ct ON gc.club_type_id = ct.id
        WHERE 1=1
    """
    params = []
    
    if brand:
        query += " AND b.name ILIKE %s"
        params.append(f"%{brand}%")
    
    if club_type:
        query += " AND ct.name ILIKE %s"
        params.append(f"%{club_type}%")
    
    if year:
        query += " AND gc.year_released = %s"
        params.append(year)
    
    if year_min:
        query += " AND gc.year_released >= %s"
        params.append(year_min)
    
    if year_max:
        query += " AND gc.year_released <= %s"
        params.append(year_max)
    
    if skill_level:
        query += " AND gc.skill_level = %s"
        params.append(skill_level)
    
    if is_current is not None:
        query += " AND gc.is_current = %s"
        params.append(is_current)
    
    query += " ORDER BY gc.year_released DESC, b.name, gc.model_name LIMIT %s"
    params.append(limit)
    
    with db.get_cursor() as cursor:
        cursor.execute(query, params)
        return cursor.fetchall()


def get_club_by_id(club_id: int) -> Optional[Dict[str, Any]]:
    """Get a specific club by ID with all related data."""
    query = """
        SELECT 
            gc.*,
            b.name as brand_name,
            ct.name as club_type_name,
            cs.*
        FROM golf_clubs gc
        JOIN brands b ON gc.brand_id = b.id
        JOIN club_types ct ON gc.club_type_id = ct.id
        LEFT JOIN club_specifications cs ON gc.id = cs.golf_club_id
        WHERE gc.id = %s
    """
    
    with db.get_cursor() as cursor:
        cursor.execute(query, (club_id,))
        return cursor.fetchone()


def get_brands() -> List[Dict[str, Any]]:
    """Get all brands."""
    query = "SELECT * FROM brands ORDER BY name"
    
    with db.get_cursor() as cursor:
        cursor.execute(query)
        return cursor.fetchall()


def get_club_types() -> List[Dict[str, Any]]:
    """Get all club types."""
    query = "SELECT * FROM club_types ORDER BY name"
    
    with db.get_cursor() as cursor:
        cursor.execute(query)
        return cursor.fetchall()


def insert_club(club_data: Dict[str, Any]) -> int:
    """
    Insert a new golf club.
    
    Args:
        club_data: Dictionary with club information
    
    Returns:
        ID of the newly inserted club
    """
    query = """
        INSERT INTO golf_clubs (
            brand_id, club_type_id, model_name, year_released,
            year_discontinued, msrp, current_price, is_current,
            description, target_handicap_range, skill_level,
            gender, hand
        ) VALUES (
            %(brand_id)s, %(club_type_id)s, %(model_name)s, %(year_released)s,
            %(year_discontinued)s, %(msrp)s, %(current_price)s, %(is_current)s,
            %(description)s, %(target_handicap_range)s, %(skill_level)s,
            %(gender)s, %(hand)s
        )
        RETURNING id
    """
    
    with db.get_cursor() as cursor:
        cursor.execute(query, club_data)
        return cursor.fetchone()['id']


def update_club_price(club_id: int, price: float, source: str):
    """Update the current price of a club."""
    query = """
        UPDATE golf_clubs 
        SET current_price = %s, updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
    """
    
    with db.get_cursor() as cursor:
        cursor.execute(query, (price, club_id))
    
    # Also log in product_sources
    source_query = """
        INSERT INTO product_sources (golf_club_id, source_name, price, last_checked)
        VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (golf_club_id, source_name) 
        DO UPDATE SET price = EXCLUDED.price, last_checked = CURRENT_TIMESTAMP
    """
    
    with db.get_cursor() as cursor:
        cursor.execute(source_query, (club_id, source, price))


def log_scrape(source_name: str, scrape_type: str, status: str, 
               records_added: int = 0, records_updated: int = 0,
               error_message: Optional[str] = None):
    """Log scraping activity."""
    query = """
        INSERT INTO scraping_logs (
            source_name, scrape_type, status, records_added,
            records_updated, error_message, completed_at
        ) VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
    """
    
    with db.get_cursor() as cursor:
        cursor.execute(query, (
            source_name, scrape_type, status, records_added,
            records_updated, error_message
        ))


def get_or_create_reviewer_profile(profile_data: Dict[str, Any]) -> int:
    """
    Get or create a reviewer profile.
    
    Args:
        profile_data: Dictionary with reviewer profile information
    
    Returns:
        ID of the reviewer profile
    """
    # Check if profile exists
    if profile_data.get('external_id') and profile_data.get('source_name'):
        with db.get_cursor() as cursor:
            cursor.execute(
                """
                SELECT id FROM reviewer_profiles 
                WHERE external_id = %s AND source_name = %s
                """,
                (profile_data['external_id'], profile_data['source_name'])
            )
            result = cursor.fetchone()
            
            if result:
                # Update existing profile
                update_query = """
                    UPDATE reviewer_profiles 
                    SET age = COALESCE(%(age)s, age),
                        weight_lbs = COALESCE(%(weight_lbs)s, weight_lbs),
                        height_inches = COALESCE(%(height_inches)s, height_inches),
                        gender = COALESCE(%(gender)s, gender),
                        handicap = COALESCE(%(handicap)s, handicap),
                        average_drive_distance_yards = COALESCE(%(average_drive_distance_yards)s, average_drive_distance_yards),
                        swing_speed_mph = COALESCE(%(swing_speed_mph)s, swing_speed_mph),
                        swing_tempo = COALESCE(%(swing_tempo)s, swing_tempo),
                        ball_flight = COALESCE(%(ball_flight)s, ball_flight),
                        skill_level = COALESCE(%(skill_level)s, skill_level),
                        years_playing = COALESCE(%(years_playing)s, years_playing),
                        rounds_per_year = COALESCE(%(rounds_per_year)s, rounds_per_year),
                        primary_miss = COALESCE(%(primary_miss)s, primary_miss),
                        launch_angle_preference = COALESCE(%(launch_angle_preference)s, launch_angle_preference),
                        spin_preference = COALESCE(%(spin_preference)s, spin_preference),
                        feel_preference = COALESCE(%(feel_preference)s, feel_preference),
                        game_improvement_priority = COALESCE(%(game_improvement_priority)s, game_improvement_priority),
                        budget_range = COALESCE(%(budget_range)s, budget_range),
                        notes = COALESCE(%(notes)s, notes),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %(id)s
                """
                profile_data['id'] = result['id']
                cursor.execute(update_query, profile_data)
                return result['id']
    
    # Create new profile
    insert_query = """
        INSERT INTO reviewer_profiles (
            external_id, source_name, age, weight_lbs, height_inches,
            gender, handicap, average_drive_distance_yards, swing_speed_mph,
            swing_tempo, ball_flight, skill_level, years_playing,
            rounds_per_year, primary_miss, launch_angle_preference,
            spin_preference, feel_preference, game_improvement_priority,
            budget_range, notes
        ) VALUES (
            %(external_id)s, %(source_name)s, %(age)s, %(weight_lbs)s, %(height_inches)s,
            %(gender)s, %(handicap)s, %(average_drive_distance_yards)s, %(swing_speed_mph)s,
            %(swing_tempo)s, %(ball_flight)s, %(skill_level)s, %(years_playing)s,
            %(rounds_per_year)s, %(primary_miss)s, %(launch_angle_preference)s,
            %(spin_preference)s, %(feel_preference)s, %(game_improvement_priority)s,
            %(budget_range)s, %(notes)s
        )
        RETURNING id
    """
    
    with db.get_cursor() as cursor:
        cursor.execute(insert_query, profile_data)
        return cursor.fetchone()['id']


def get_reviewer_profiles(
    handicap_min: Optional[float] = None,
    handicap_max: Optional[float] = None,
    skill_level: Optional[str] = None,
    swing_speed_min: Optional[int] = None,
    swing_speed_max: Optional[int] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Query reviewer profiles with filters.
    
    Args:
        handicap_min: Minimum handicap
        handicap_max: Maximum handicap
        skill_level: Skill level filter
        swing_speed_min: Minimum swing speed (mph)
        swing_speed_max: Maximum swing speed (mph)
        limit: Maximum number of results
    
    Returns:
        List of reviewer profile dictionaries
    """
    query = "SELECT * FROM reviewer_profiles WHERE 1=1"
    params = []
    
    if handicap_min is not None:
        query += " AND handicap >= %s"
        params.append(handicap_min)
    
    if handicap_max is not None:
        query += " AND handicap <= %s"
        params.append(handicap_max)
    
    if skill_level:
        query += " AND skill_level = %s"
        params.append(skill_level)
    
    if swing_speed_min is not None:
        query += " AND swing_speed_mph >= %s"
        params.append(swing_speed_min)
    
    if swing_speed_max is not None:
        query += " AND swing_speed_mph <= %s"
        params.append(swing_speed_max)
    
    query += " ORDER BY created_at DESC LIMIT %s"
    params.append(limit)
    
    with db.get_cursor() as cursor:
        cursor.execute(query, params)
        return cursor.fetchall()


def get_reviews_with_profiles(club_id: int) -> List[Dict[str, Any]]:
    """
    Get all reviews for a club with reviewer profile information.
    
    Args:
        club_id: Golf club ID
    
    Returns:
        List of review dictionaries with profile data
    """
    query = """
        SELECT 
            cr.*,
            rp.handicap as reviewer_handicap,
            rp.swing_speed_mph as reviewer_swing_speed,
            rp.skill_level as reviewer_skill_level,
            rp.ball_flight as reviewer_ball_flight,
            rp.average_drive_distance_yards as reviewer_avg_distance,
            rp.age as reviewer_age,
            rp.gender as reviewer_gender
        FROM club_reviews cr
        LEFT JOIN reviewer_profiles rp ON cr.reviewer_profile_id = rp.id
        WHERE cr.golf_club_id = %s
        ORDER BY cr.review_date DESC
    """
    
    with db.get_cursor() as cursor:
        cursor.execute(query, (club_id,))
        return cursor.fetchall()
