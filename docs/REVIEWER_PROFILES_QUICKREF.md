# Reviewer Profiles - Quick Reference

## Database Tables

### `reviewer_profiles`
Stores detailed player information for personalized recommendations.

**Key Fields:**
- `handicap` - Golf handicap (most important for matching)
- `swing_speed_mph` - Driver swing speed
- `skill_level` - Beginner/Intermediate/Advanced/Professional
- `ball_flight` - Draw, Fade, Straight, Hook, Slice
- `game_improvement_priority` - What player wants to improve

### `club_reviews` (Enhanced)
Now links to reviewer profiles:
- `reviewer_profile_id` - Foreign key to reviewer_profiles
- `review_text` - Full review content
- `verified_purchase` - Purchase verification

## Quick Usage

### Create Profile
```python
from database.db import get_or_create_reviewer_profile

profile_id = get_or_create_reviewer_profile({
    'external_id': 'user123',
    'source_name': 'Global Golf',
    'handicap': 12.5,
    'swing_speed_mph': 95,
    'skill_level': 'Intermediate',
    'ball_flight': 'Fade'
})
```

### Add Review with Profile
```python
from database.db import db

with db.get_cursor() as cursor:
    cursor.execute("""
        INSERT INTO club_reviews (
            golf_club_id, reviewer_profile_id, rating, review_text
        ) VALUES (%s, %s, %s, %s)
    """, (club_id, profile_id, 4.5, "Great club!"))
```

### Find Similar Reviewers
```python
from database.db import get_reviewer_profiles

similar = get_reviewer_profiles(
    handicap_min=10, handicap_max=15,
    swing_speed_min=90, swing_speed_max=100
)
```

### Get Personalized Reviews
```python
from database.db import get_reviews_with_profiles

reviews = get_reviews_with_profiles(club_id=123)
# Filter by similarity to user
```

## SQL Queries

### Reviews from Similar Players
```sql
SELECT cr.*, rp.handicap, rp.swing_speed_mph
FROM club_reviews cr
JOIN reviewer_profiles rp ON cr.reviewer_profile_id = rp.id
WHERE cr.golf_club_id = 123
  AND rp.handicap BETWEEN 10 AND 15
  AND rp.swing_speed_mph BETWEEN 90 AND 100;
```

### Best Clubs for a Profile Segment
```sql
SELECT gc.brand_id, gc.model_name, AVG(cr.rating) as avg_rating
FROM golf_clubs gc
JOIN club_reviews cr ON gc.id = cr.golf_club_id
JOIN reviewer_profiles rp ON cr.reviewer_profile_id = rp.id
WHERE rp.skill_level = 'Intermediate'
  AND rp.handicap BETWEEN 10 AND 20
GROUP BY gc.id, gc.brand_id, gc.model_name
HAVING COUNT(cr.id) >= 3
ORDER BY avg_rating DESC
LIMIT 10;
```

## Migration

For existing databases:
```bash
python scripts/migrate_add_reviewer_profiles.py
```

## Testing

Run the example:
```bash
python examples/reviewer_profiles_example.py
```

## Key Formulas

### Similarity Score
```python
def similarity(user, reviewer):
    handicap_diff = abs(user.handicap - reviewer.handicap)
    speed_diff = abs(user.swing_speed - reviewer.swing_speed)
    
    # Lower is more similar
    return (handicap_diff / 5) + (speed_diff / 10)
```

### Weighted Rating
```python
def weighted_rating(reviews, user_profile):
    total = 0
    weights = 0
    
    for review in reviews:
        similarity = calculate_similarity(user_profile, review.profile)
        weight = 1 / (1 + similarity)  # Higher weight for more similar
        total += review.rating * weight
        weights += weight
    
    return total / weights
```

## Best Practices

✅ **DO:**
- Store anonymized data only
- Handle missing profile fields gracefully
- Update profiles over time as players improve
- Use similarity matching for recommendations
- Weight reviews by profile similarity

❌ **DON'T:**
- Store personally identifiable information
- Require complete profiles (allow partial)
- Ignore reviews without profiles
- Assume profiles never change
- Give equal weight to all reviews

## Documentation

- Full guide: `docs/REVIEWER_PROFILES.md`
- Summary: `docs/REVIEWER_PROFILES_SUMMARY.md`
- Database schema: `database/schema.sql`
- Example code: `examples/reviewer_profiles_example.py`

## Support

Profile fields are optional - reviews without profiles still work!
The system gracefully handles missing data and provides fallbacks.
