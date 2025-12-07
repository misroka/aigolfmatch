"""
Flask web application for golf club database management.
Secure interface with authentication.
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.db import (
    get_clubs, get_brands, get_club_types, get_club_by_id,
    get_reviewer_profiles, get_reviews_with_profiles, db
)

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', os.urandom(24).hex())
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'


class User(UserMixin):
    """Simple user model for authentication."""
    def __init__(self, id, username):
        self.id = id
        self.username = username


# Simple in-memory user store (for single user)
# In production, use a proper database
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD_HASH = os.getenv('ADMIN_PASSWORD_HASH', 
                                 generate_password_hash('changeme123'))


@login_manager.user_loader
def load_user(user_id):
    """Load user by ID."""
    if user_id == '1':
        return User('1', ADMIN_USERNAME)
    return None


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page."""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = request.form.get('remember', False)
        
        if username == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD_HASH, password):
            user = User('1', username)
            login_user(user, remember=remember)
            
            next_page = request.args.get('next')
            return redirect(next_page if next_page else url_for('index'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    """Logout user."""
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))


@app.route('/')
@login_required
def index():
    """Dashboard/home page."""
    # Get statistics
    with db.get_cursor() as cursor:
        cursor.execute("SELECT COUNT(*) as count FROM brands")
        brand_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM golf_clubs")
        club_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM club_reviews")
        review_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM reviewer_profiles")
        profile_count = cursor.fetchone()['count']
        
        # Recent clubs
        cursor.execute("""
            SELECT b.name as brand, gc.model_name, gc.year_released, ct.name as type
            FROM golf_clubs gc
            JOIN brands b ON gc.brand_id = b.id
            JOIN club_types ct ON gc.club_type_id = ct.id
            ORDER BY gc.created_at DESC
            LIMIT 10
        """)
        recent_clubs = cursor.fetchall()
        
        # Top brands
        cursor.execute("""
            SELECT b.name, COUNT(gc.id) as club_count
            FROM brands b
            LEFT JOIN golf_clubs gc ON b.id = gc.brand_id
            GROUP BY b.name
            HAVING COUNT(gc.id) > 0
            ORDER BY club_count DESC
            LIMIT 5
        """)
        top_brands = cursor.fetchall()
    
    stats = {
        'brands': brand_count,
        'clubs': club_count,
        'reviews': review_count,
        'profiles': profile_count
    }
    
    return render_template('index.html', 
                          stats=stats, 
                          recent_clubs=recent_clubs,
                          top_brands=top_brands)


@app.route('/clubs')
@login_required
def clubs():
    """Browse clubs page."""
    brand = request.args.get('brand')
    club_type = request.args.get('type')
    year = request.args.get('year', type=int)
    skill_level = request.args.get('skill')
    limit = request.args.get('limit', 50, type=int)
    
    clubs = get_clubs(
        brand=brand,
        club_type=club_type,
        year=year,
        skill_level=skill_level,
        limit=limit
    )
    
    brands = get_brands()
    club_types = get_club_types()
    
    return render_template('clubs.html',
                          clubs=clubs,
                          brands=brands,
                          club_types=club_types,
                          filters={
                              'brand': brand,
                              'type': club_type,
                              'year': year,
                              'skill': skill_level
                          })


@app.route('/club/<int:club_id>')
@login_required
def club_detail(club_id):
    """Club detail page."""
    club = get_club_by_id(club_id)
    
    if not club:
        flash('Club not found', 'error')
        return redirect(url_for('clubs'))
    
    # Get reviews with profiles
    reviews = get_reviews_with_profiles(club_id)
    
    return render_template('club_detail.html', club=club, reviews=reviews)


@app.route('/brands')
@login_required
def brands():
    """Brands page."""
    brands = get_brands()
    
    # Get club count for each brand
    with db.get_cursor() as cursor:
        cursor.execute("""
            SELECT b.id, b.name, b.country, b.website,
                   COUNT(gc.id) as club_count
            FROM brands b
            LEFT JOIN golf_clubs gc ON b.id = gc.brand_id
            GROUP BY b.id, b.name, b.country, b.website
            ORDER BY club_count DESC, b.name
        """)
        brands_with_counts = cursor.fetchall()
    
    return render_template('brands.html', brands=brands_with_counts)


@app.route('/profiles')
@login_required
def profiles():
    """Reviewer profiles page."""
    handicap_min = request.args.get('handicap_min', type=float)
    handicap_max = request.args.get('handicap_max', type=float)
    skill_level = request.args.get('skill')
    limit = request.args.get('limit', 50, type=int)
    
    profiles = get_reviewer_profiles(
        handicap_min=handicap_min,
        handicap_max=handicap_max,
        skill_level=skill_level,
        limit=limit
    )
    
    return render_template('profiles.html', 
                          profiles=profiles,
                          filters={
                              'handicap_min': handicap_min,
                              'handicap_max': handicap_max,
                              'skill': skill_level
                          })


@app.route('/search')
@login_required
def search():
    """Search page."""
    query = request.args.get('q', '')
    
    if not query:
        return render_template('search.html', clubs=[], query='')
    
    # Search in brand names and model names
    with db.get_cursor() as cursor:
        cursor.execute("""
            SELECT gc.*, b.name as brand_name, ct.name as club_type_name
            FROM golf_clubs gc
            JOIN brands b ON gc.brand_id = b.id
            JOIN club_types ct ON gc.club_type_id = ct.id
            WHERE b.name ILIKE %s OR gc.model_name ILIKE %s
            ORDER BY gc.year_released DESC
            LIMIT 50
        """, (f'%{query}%', f'%{query}%'))
        results = cursor.fetchall()
    
    return render_template('search.html', clubs=results, query=query)


@app.route('/api/clubs')
@login_required
def api_clubs():
    """API endpoint for clubs."""
    brand = request.args.get('brand')
    club_type = request.args.get('type')
    year = request.args.get('year', type=int)
    limit = request.args.get('limit', 50, type=int)
    
    clubs = get_clubs(
        brand=brand,
        club_type=club_type,
        year=year,
        limit=limit
    )
    
    return jsonify({
        'clubs': clubs,
        'count': len(clubs)
    })


@app.route('/api/stats')
@login_required
def api_stats():
    """API endpoint for statistics."""
    with db.get_cursor() as cursor:
        # Overall stats
        cursor.execute("""
            SELECT 
                (SELECT COUNT(*) FROM brands) as brand_count,
                (SELECT COUNT(*) FROM golf_clubs) as club_count,
                (SELECT COUNT(*) FROM club_reviews) as review_count,
                (SELECT COUNT(*) FROM reviewer_profiles) as profile_count
        """)
        stats = cursor.fetchone()
        
        # Clubs by year
        cursor.execute("""
            SELECT year_released, COUNT(*) as count
            FROM golf_clubs
            GROUP BY year_released
            ORDER BY year_released DESC
            LIMIT 10
        """)
        by_year = cursor.fetchall()
        
        # Clubs by type
        cursor.execute("""
            SELECT ct.name, COUNT(gc.id) as count
            FROM club_types ct
            LEFT JOIN golf_clubs gc ON ct.id = gc.club_type_id
            GROUP BY ct.name
            ORDER BY count DESC
        """)
        by_type = cursor.fetchall()
    
    return jsonify({
        'overall': dict(stats),
        'by_year': by_year,
        'by_type': by_type
    })


@app.errorhandler(404)
def not_found(error):
    """404 error handler."""
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(error):
    """500 error handler."""
    return render_template('500.html'), 500


if __name__ == '__main__':
    # Development server - DO NOT use in production
    app.run(
        host='127.0.0.1',  # Only accessible from localhost
        port=5000,
        debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    )
