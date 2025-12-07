"""Example usage of reviewer profiles for personalized recommendations."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.db import (
    get_or_create_reviewer_profile,
    get_reviewer_profiles,
    get_reviews_with_profiles,
    db
)


def create_sample_reviewer():
    """Create a sample reviewer profile."""
    
    reviewer_data = {
        'external_id': 'john_doe_123',
        'source_name': 'Global Golf',
        'age': 35,
        'weight_lbs': 180,
        'height_inches': 72,  # 6 feet
        'gender': 'Male',
        'handicap': 12.5,
        'average_drive_distance_yards': 260,
        'swing_speed_mph': 95,
        'swing_tempo': 'Moderate',
        'ball_flight': 'Slight Fade',
        'skill_level': 'Intermediate',
        'years_playing': 10,
        'rounds_per_year': 30,
        'primary_miss': 'Right',
        'launch_angle_preference': 'Mid',
        'spin_preference': 'Mid',
        'feel_preference': 'Medium',
        'game_improvement_priority': 'Accuracy and Forgiveness',
        'budget_range': '$500-1000',
        'notes': 'Looking to improve consistency with irons'
    }
    
    profile_id = get_or_create_reviewer_profile(reviewer_data)
    print(f"✓ Created reviewer profile with ID: {profile_id}")
    return profile_id


def add_review_with_profile(profile_id: int, club_id: int):
    """Add a review linked to a reviewer profile."""
    
    review_data = {
        'golf_club_id': club_id,
        'reviewer_profile_id': profile_id,
        'source_name': 'Global Golf',
        'rating': 4.5,
        'review_title': 'Great forgiveness, improved my game',
        'review_text': 'These irons have really helped me hit more greens. The forgiveness on mis-hits is excellent, and I gained about 10 yards compared to my old set. Highly recommend for mid-handicappers.',
        'pros': ['Forgiving', 'Good distance', 'Nice feel'],
        'cons': ['A bit pricey', 'Stock shaft could be better'],
        'verified_purchase': True,
        'helpful_count': 15,
        'review_date': '2024-06-15'
    }
    
    with db.get_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO club_reviews (
                golf_club_id, reviewer_profile_id, source_name, rating,
                review_title, review_text, pros, cons, verified_purchase,
                helpful_count, review_date
            ) VALUES (
                %(golf_club_id)s, %(reviewer_profile_id)s, %(source_name)s, %(rating)s,
                %(review_title)s, %(review_text)s, %(pros)s, %(cons)s, %(verified_purchase)s,
                %(helpful_count)s, %(review_date)s
            )
            RETURNING id
            """,
            review_data
        )
        review_id = cursor.fetchone()['id']
    
    print(f"✓ Created review with ID: {review_id}")
    return review_id


def find_similar_reviewers(target_profile: dict):
    """Find reviewers with similar profiles for better recommendations."""
    
    # Find reviewers with similar handicap (±3)
    similar_profiles = get_reviewer_profiles(
        handicap_min=target_profile.get('handicap', 0) - 3,
        handicap_max=target_profile.get('handicap', 36) + 3,
        skill_level=target_profile.get('skill_level'),
        limit=50
    )
    
    print(f"\n✓ Found {len(similar_profiles)} reviewers with similar profiles:")
    
    for profile in similar_profiles[:5]:  # Show first 5
        print(f"  - Handicap: {profile['handicap']}, "
              f"Swing Speed: {profile['swing_speed_mph']} mph, "
              f"Skill: {profile['skill_level']}")
    
    return similar_profiles


def get_personalized_recommendations(user_profile: dict, club_id: int):
    """Get reviews from similar players for personalized recommendations."""
    
    print(f"\n--- Personalized Recommendations for Club ID {club_id} ---")
    
    # Get all reviews with profile info
    reviews = get_reviews_with_profiles(club_id)
    
    if not reviews:
        print("No reviews found for this club.")
        return
    
    # Filter reviews from similar players
    user_handicap = user_profile.get('handicap', 18)
    user_swing_speed = user_profile.get('swing_speed_mph', 90)
    
    similar_reviews = []
    for review in reviews:
        if review.get('reviewer_handicap') and review.get('reviewer_swing_speed'):
            handicap_diff = abs(review['reviewer_handicap'] - user_handicap)
            speed_diff = abs(review['reviewer_swing_speed'] - user_swing_speed)
            
            # Consider similar if handicap within 5 and swing speed within 10 mph
            if handicap_diff <= 5 and speed_diff <= 10:
                similar_reviews.append(review)
    
    print(f"\nFound {len(similar_reviews)} reviews from similar players:")
    
    for review in similar_reviews:
        print(f"\n  Rating: {review['rating']}/5.0")
        print(f"  Reviewer: Handicap {review['reviewer_handicap']}, "
              f"{review['reviewer_swing_speed']} mph swing speed")
        if review.get('review_title'):
            print(f"  Title: {review['review_title']}")
        if review.get('review_text'):
            print(f"  Review: {review['review_text'][:150]}...")
    
    # Calculate average rating from similar players
    if similar_reviews:
        avg_rating = sum(r['rating'] for r in similar_reviews if r['rating']) / len(similar_reviews)
        print(f"\n  Average rating from similar players: {avg_rating:.2f}/5.0")
    
    return similar_reviews


def main():
    """Demonstrate reviewer profile functionality."""
    
    print("=" * 70)
    print("Reviewer Profiles - Example Usage")
    print("=" * 70)
    
    # Example 1: Create a reviewer profile
    print("\n1. Creating a sample reviewer profile...")
    profile_id = create_sample_reviewer()
    
    # Example 2: Add a review with profile
    print("\n2. Adding a review linked to the profile...")
    # Note: Replace with actual club_id from your database
    # For demo purposes, we'll assume club_id = 1 exists
    with db.get_cursor() as cursor:
        cursor.execute("SELECT id FROM golf_clubs LIMIT 1")
        result = cursor.fetchone()
        if result:
            club_id = result['id']
            review_id = add_review_with_profile(profile_id, club_id)
        else:
            print("  No clubs in database yet. Skipping review creation.")
            return
    
    # Example 3: Find similar reviewers
    print("\n3. Finding reviewers with similar profiles...")
    target_profile = {
        'handicap': 12.5,
        'skill_level': 'Intermediate',
        'swing_speed_mph': 95
    }
    similar_profiles = find_similar_reviewers(target_profile)
    
    # Example 4: Get personalized recommendations
    print("\n4. Getting personalized recommendations...")
    user_profile = {
        'handicap': 14.0,
        'swing_speed_mph': 92,
        'skill_level': 'Intermediate'
    }
    similar_reviews = get_personalized_recommendations(user_profile, club_id)
    
    print("\n" + "=" * 70)
    print("Key Benefits of Reviewer Profiles:")
    print("=" * 70)
    print("""
    ✓ Match users with reviewers who have similar playing characteristics
    ✓ Weight reviews from similar players more heavily in recommendations
    ✓ Identify which clubs work best for specific player profiles
    ✓ Provide personalized insights based on handicap, swing speed, etc.
    ✓ Build collaborative filtering models using profile similarities
    ✓ Segment recommendations by player type (distance vs accuracy, etc.)
    """)
    
    print("\n" + "=" * 70)
    print("Next Steps:")
    print("=" * 70)
    print("""
    1. Scrape reviewer profiles when collecting reviews
    2. Extract profile data from review text (age, handicap mentions, etc.)
    3. Build recommendation algorithm using profile similarity
    4. Create user profiles for your recommendation system users
    5. Match user profiles with reviewer profiles for better recommendations
    """)


if __name__ == "__main__":
    main()
