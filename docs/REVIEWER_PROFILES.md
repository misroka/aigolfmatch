# Reviewer Profiles for Personalized Recommendations

## Overview

The reviewer profiles system enables personalized golf club recommendations by tracking detailed information about reviewers, including their physical characteristics, skill level, and swing preferences. This allows the recommendation engine to match users with reviews from similar players, providing more relevant and accurate suggestions.

## Database Schema

### `reviewer_profiles` Table

Stores comprehensive information about golf club reviewers.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | SERIAL | Primary key |
| `external_id` | VARCHAR(100) | ID from review source (e.g., user123) |
| `source_name` | VARCHAR(100) | Where the profile came from |
| `age` | INTEGER | Reviewer's age |
| `weight_lbs` | INTEGER | Weight in pounds |
| `height_inches` | INTEGER | Height in inches |
| `gender` | VARCHAR(20) | Male, Female, Other |
| `handicap` | DECIMAL(4,1) | Golf handicap index |
| `average_drive_distance_yards` | INTEGER | Average driving distance |
| `swing_speed_mph` | INTEGER | Driver swing speed |
| `swing_tempo` | VARCHAR(20) | Slow, Moderate, Fast |
| `ball_flight` | VARCHAR(30) | Draw, Fade, Straight, Hook, Slice |
| `skill_level` | VARCHAR(50) | Beginner, Intermediate, Advanced, Professional |
| `years_playing` | INTEGER | Years playing golf |
| `rounds_per_year` | INTEGER | Rounds played per year |
| `primary_miss` | VARCHAR(30) | Left, Right, Short, Long |
| `launch_angle_preference` | VARCHAR(20) | Low, Mid, High |
| `spin_preference` | VARCHAR(20) | Low, Mid, High |
| `feel_preference` | VARCHAR(20) | Soft, Medium, Firm |
| `game_improvement_priority` | VARCHAR(100) | What player wants to improve |
| `budget_range` | VARCHAR(50) | Price range (e.g., "$500-1000") |
| `notes` | TEXT | Additional information |

### Updated `club_reviews` Table

Now includes a link to reviewer profiles.

**New/Updated Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `reviewer_profile_id` | INTEGER | Foreign key to reviewer_profiles |
| `review_text` | TEXT | Full text of the review |
| `review_title` | VARCHAR(255) | Review title/headline |
| `verified_purchase` | BOOLEAN | Whether reviewer purchased the club |
| `helpful_count` | INTEGER | Number of helpful votes |

## Why Reviewer Profiles Matter

### 1. **Better Matching**
Match users with reviewers who have similar:
- Handicap levels
- Swing speeds
- Physical characteristics
- Playing style

### 2. **Weighted Recommendations**
Reviews from similar players should carry more weight:
```python
# A 5-star review from someone with your swing speed is more valuable
# than a 5-star review from someone who swings 20 mph faster
```

### 3. **Segment-Specific Insights**
Different clubs work for different players:
- High handicappers need forgiveness
- Low handicappers want control
- Fast swingers need stiff shafts
- Slower swingers need regular flex

### 4. **Profile-Based Filtering**
"Show me reviews from players with 10-15 handicap and 90-100 mph swing speed"

## Usage Examples

### Creating a Reviewer Profile

```python
from database.db import get_or_create_reviewer_profile

reviewer_data = {
    'external_id': 'john_doe_123',
    'source_name': 'Global Golf',
    'age': 35,
    'handicap': 12.5,
    'swing_speed_mph': 95,
    'skill_level': 'Intermediate',
    'ball_flight': 'Slight Fade',
    'game_improvement_priority': 'Accuracy and Forgiveness',
    # ... other fields
}

profile_id = get_or_create_reviewer_profile(reviewer_data)
```

### Adding a Review with Profile

```python
from database.db import db

review_data = {
    'golf_club_id': 123,
    'reviewer_profile_id': profile_id,
    'rating': 4.5,
    'review_title': 'Great forgiveness',
    'review_text': 'These irons helped me hit more greens...',
    'verified_purchase': True
}

with db.get_cursor() as cursor:
    cursor.execute(
        """
        INSERT INTO club_reviews (
            golf_club_id, reviewer_profile_id, rating,
            review_title, review_text, verified_purchase
        ) VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (review_data['golf_club_id'], review_data['reviewer_profile_id'],
         review_data['rating'], review_data['review_title'],
         review_data['review_text'], review_data['verified_purchase'])
    )
```

### Finding Similar Reviewers

```python
from database.db import get_reviewer_profiles

# Find reviewers with similar handicap and swing speed
similar_profiles = get_reviewer_profiles(
    handicap_min=10.0,
    handicap_max=15.0,
    swing_speed_min=90,
    swing_speed_max=100,
    skill_level='Intermediate'
)
```

### Getting Personalized Recommendations

```python
from database.db import get_reviews_with_profiles

# Get reviews for a specific club with reviewer profile info
reviews = get_reviews_with_profiles(club_id=123)

# Filter to similar players
user_handicap = 12.0
user_swing_speed = 95

relevant_reviews = [
    r for r in reviews
    if r['reviewer_handicap'] and
    abs(r['reviewer_handicap'] - user_handicap) <= 5 and
    abs(r['reviewer_swing_speed'] - user_swing_speed) <= 10
]

# Calculate weighted average
avg_rating = sum(r['rating'] for r in relevant_reviews) / len(relevant_reviews)
```

## Data Collection Strategies

### 1. **Direct Profile Information**
Some review sites display reviewer profiles:
- Golf Galaxy reviews often show handicap
- PGA Superstore reviews may show skill level
- Forum posts often include signatures with stats

### 2. **Extract from Review Text**
Use NLP to extract profile data:
```python
# Example patterns to look for in review text:
# "I'm a 15 handicap..."
# "I swing around 95 mph..."
# "As a beginner golfer..."
# "I'm 6'2" and 210 lbs..."
```

### 3. **Infer from Club Choices**
Make educated guesses:
- Reviewing cavity-back irons → likely higher handicap
- Reviewing stiff flex shafts → likely faster swing speed
- Reviewing game-improvement clubs → likely beginner/intermediate

### 4. **User-Submitted Profiles**
If building your own review system:
- Ask users to create profiles
- Make it optional but incentivize (show personalized recommendations)
- Pre-fill with reasonable defaults

## Recommendation Algorithm Ideas

### 1. **Similarity Score**
Calculate how similar a reviewer is to the target user:

```python
def calculate_similarity(user_profile, reviewer_profile):
    score = 0
    
    # Handicap similarity (most important)
    if user_profile['handicap'] and reviewer_profile['handicap']:
        handicap_diff = abs(user_profile['handicap'] - reviewer_profile['handicap'])
        score += max(0, 10 - handicap_diff)  # 0-10 points
    
    # Swing speed similarity
    if user_profile['swing_speed'] and reviewer_profile['swing_speed']:
        speed_diff = abs(user_profile['swing_speed'] - reviewer_profile['swing_speed'])
        score += max(0, 20 - speed_diff) / 2  # 0-10 points
    
    # Skill level match
    skill_match = {
        'Beginner': 1,
        'Intermediate': 2,
        'Advanced': 3,
        'Professional': 4
    }
    if user_profile['skill_level'] == reviewer_profile['skill_level']:
        score += 5
    elif abs(skill_match.get(user_profile['skill_level'], 0) - 
             skill_match.get(reviewer_profile['skill_level'], 0)) == 1:
        score += 3
    
    # Ball flight similarity
    if user_profile.get('ball_flight') == reviewer_profile.get('ball_flight'):
        score += 3
    
    return score
```

### 2. **Weighted Average Rating**
Weight reviews by similarity:

```python
def get_weighted_rating(club_id, user_profile):
    reviews = get_reviews_with_profiles(club_id)
    
    weighted_sum = 0
    weight_total = 0
    
    for review in reviews:
        if review['reviewer_profile_id']:
            similarity = calculate_similarity(user_profile, review)
            weighted_sum += review['rating'] * similarity
            weight_total += similarity
    
    return weighted_sum / weight_total if weight_total > 0 else 0
```

### 3. **Profile-Based Filtering**
Filter clubs that work well for similar players:

```sql
SELECT gc.*, AVG(cr.rating) as avg_rating_from_similar
FROM golf_clubs gc
JOIN club_reviews cr ON gc.id = cr.golf_club_id
JOIN reviewer_profiles rp ON cr.reviewer_profile_id = rp.id
WHERE rp.handicap BETWEEN 10 AND 15
  AND rp.swing_speed_mph BETWEEN 90 AND 100
GROUP BY gc.id
HAVING COUNT(cr.id) >= 3  -- At least 3 reviews
ORDER BY avg_rating_from_similar DESC
LIMIT 10
```

### 4. **Collaborative Filtering**
"Players like you also liked these clubs"

```python
# Find reviewers similar to user
similar_reviewers = find_similar_reviewers(user_profile)

# Find clubs highly rated by similar reviewers
clubs_liked_by_similar = get_highly_rated_clubs_by_reviewers(similar_reviewers)

# Recommend clubs user hasn't reviewed yet
recommendations = [c for c in clubs_liked_by_similar if c not in user_owned_clubs]
```

## Migration Guide

If you have an existing database, run the migration:

```bash
python scripts/migrate_add_reviewer_profiles.py
```

This will:
1. Create the `reviewer_profiles` table
2. Add `reviewer_profile_id` to `club_reviews`
3. Add additional review fields (review_text, review_title, etc.)
4. Create necessary indexes

## Best Practices

### 1. **Privacy**
- Don't store personally identifiable information
- Use external_id instead of real names
- Aggregate data for display

### 2. **Data Quality**
- Validate handicap ranges (0-36 typical)
- Validate swing speeds (60-130 mph typical)
- Handle missing data gracefully

### 3. **Progressive Enhancement**
- Reviews without profiles are still valuable
- Allow reviews without requiring profile creation
- Infer profile data when possible

### 4. **Update Profiles Over Time**
- Players improve and their profiles change
- Track profile history if needed
- Use most recent profile data

## Future Enhancements

1. **Equipment History**
   - Track what clubs reviewer has owned
   - Use past preferences to improve matching

2. **Play Style Tags**
   - Add tags like "Distance focused", "Accuracy focused"
   - Enable multi-dimensional matching

3. **Performance Metrics**
   - Track actual results (GIR, fairways hit)
   - Validate claims with data

4. **Social Features**
   - Follow reviewers with similar profiles
   - Create reviewer reputation scores

## Example Query Script

Run the example:
```bash
python examples/reviewer_profiles_example.py
```

This demonstrates:
- Creating reviewer profiles
- Linking reviews to profiles
- Finding similar reviewers
- Generating personalized recommendations

## See Also

- Database schema: `database/schema.sql`
- Database utilities: `database/db.py`
- Data models: `models/club.py`
- Migration script: `scripts/migrate_add_reviewer_profiles.py`
- Example usage: `examples/reviewer_profiles_example.py`
