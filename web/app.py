"""
Flask web application for golf club database management.
Secure interface with authentication.
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash, abort
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from werkzeug.exceptions import HTTPException
from functools import wraps
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import sys
from pathlib import Path
import secrets
import time
from collections import OrderedDict, deque
from threading import Lock
from urllib.parse import urlsplit
from uuid import uuid4

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.db import (
    get_clubs, get_brands, get_club_types, get_club_by_id,
    get_reviewer_profiles, get_reviews_with_profiles, db
)
from database.fitting import (
    validate_profile, validate_outcome, get_recommendation_candidates,
    save_fitting_outcome, delete_fitting_outcomes, get_recommendation_health,
    is_model_current
)
from recommender import recommend, load_model

load_dotenv()

app = Flask(__name__)
production = os.getenv('APP_ENV', 'development') == 'production'
secret_key = os.getenv('SECRET_KEY')
if production and (not secret_key or len(secret_key) < 32 or
                   not os.getenv('ADMIN_PASSWORD_HASH')):
    raise RuntimeError('Production requires SECRET_KEY (at least 32 characters) and ADMIN_PASSWORD_HASH.')
app.config['SECRET_KEY'] = secret_key or secrets.token_hex(32)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=production, REMEMBER_COOKIE_HTTPONLY=True,
    REMEMBER_COOKIE_SECURE=production, REMEMBER_COOKIE_SAMESITE='Lax',
    MAX_CONTENT_LENGTH=16 * 1024
)
_request_windows = OrderedDict()
_request_lock = Lock()


def csrf_token():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_urlsafe(32)
    return session['csrf_token']


app.jinja_env.globals['csrf_token'] = csrf_token


@app.before_request
def protect_requests():
    if request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}:
        provided = request.headers.get('X-CSRF-Token') or request.form.get('csrf_token', '')
        expected = session.get('csrf_token', '')
        if not expected or not secrets.compare_digest(expected, provided):
            abort(400, description='Missing or invalid CSRF token.')
    if request.endpoint in {'login', 'api_recommendations', 'api_outcomes'}:
        if request.method not in {'POST', 'DELETE'}:
            return
        key = (request.remote_addr, request.endpoint)
        now = time.monotonic()
        with _request_lock:
            window = _request_windows.setdefault(key, deque())
            _request_windows.move_to_end(key)
            while window and window[0] <= now - 60:
                window.popleft()
            if len(window) >= 20:
                return jsonify(error='Too many requests. Try again in one minute.'), 429, {'Retry-After': '60'}
            window.append(now)
            while len(_request_windows) > 10000:
                _request_windows.popitem(last=False)


@app.after_request
def security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'same-origin'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
    )
    if request.endpoint != 'static':
        response.headers['Cache-Control'] = 'no-store'
    if production:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000'
    return response

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
ADMIN_PASSWORD_HASH = os.getenv('ADMIN_PASSWORD_HASH')


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
        
        if (ADMIN_PASSWORD_HASH and username == ADMIN_USERNAME and password and
                check_password_hash(ADMIN_PASSWORD_HASH, password)):
            user = User('1', username)
            login_user(user, remember=remember)
            
            next_page = request.args.get('next', '')
            destination = url_for('index')
            if (next_page.startswith('/') and not next_page.startswith('//') and '\\' not in next_page and
                    not any(ord(char) < 32 for char in next_page)):
                try:
                    parsed = urlsplit(next_page)
                    endpoint, values = app.url_map.bind('').match(parsed.path, method='GET')
                    if endpoint in {'index', 'clubs', 'club_detail', 'brands', 'profiles',
                                    'search', 'recommendation_page'}:
                        destination = url_for(endpoint, **values)
                except (HTTPException, ValueError):
                    pass
            return redirect(destination)
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')


@app.route('/logout', methods=['POST'])
@login_required
def logout():
    """Logout user."""
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))


@app.route('/recommend')
def recommendation_page():
    if 'golfer_id' not in session:
        session['golfer_id'] = str(uuid4())
    return render_template('recommend.html')


def json_payload():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ValueError('A JSON object is required.')
    return payload


@app.route('/api/recommendations', methods=['POST'])
def api_recommendations():
    started = time.monotonic()
    try:
        profile = validate_profile(json_payload())
        candidates = get_recommendation_candidates(profile['club_type'])
        model = None
        model_path = os.getenv('RECOMMENDER_MODEL_PATH')
        if model_path:
            try:
                model = load_model(model_path)
                if model is not None and model.get('quality_gate') != 'passed':
                    model = None
                if model is not None and not is_model_current(model):
                    model = None
                    app.logger.warning('Model consent manifest invalid; using baseline.')
            except (ValueError, OSError):
                app.logger.warning('Recommendation model unavailable; using baseline.')
        results = recommend(profile, candidates, model=model, limit=5)
        app.logger.info('recommendations count=%d latency_ms=%.1f model=%s',
                        len(results), (time.monotonic() - started) * 1000,
                        'ml' if model else 'baseline')
        return jsonify(recommendations=results,
                       notice='Suggestions are not a professional fitting or evidence of causal improvement.')
    except ValueError:
        return jsonify(error='Invalid questionnaire. Check the required fields and allowed ranges.'), 400
    except HTTPException:
        raise
    except Exception:
        app.logger.error('Recommendation service failed.')
        return jsonify(error='Recommendation service temporarily unavailable.'), 503


@app.route('/api/outcomes', methods=['POST', 'DELETE'])
def api_outcomes():
    if request.method == 'DELETE':
        golfer_id = session.get('golfer_id')
        try:
            count = delete_fitting_outcomes(golfer_id) if golfer_id else 0
            return jsonify(deleted=count)
        except Exception:
            app.logger.error('Outcome withdrawal failed.')
            return jsonify(error='Feedback service temporarily unavailable.'), 503
    try:
        payload = json_payload()
        if 'golfer_id' not in session:
            session['golfer_id'] = str(uuid4())
        payload['golfer_id'] = session['golfer_id']
        outcome_id = save_fitting_outcome(validate_outcome(payload))
        return jsonify(id=outcome_id), 201
    except ValueError:
        return jsonify(error='Invalid feedback or missing consent. Check measurements, timestamp and club compatibility.'), 400
    except HTTPException:
        raise
    except Exception:
        app.logger.error('Outcome collection failed.')
        return jsonify(error='Feedback service temporarily unavailable.'), 503


@app.route('/health')
def health():
    try:
        with db.get_cursor() as cursor:
            cursor.execute('SELECT 1')
        return jsonify(status='ok')
    except Exception:
        return jsonify(status='unavailable'), 503


@app.route('/api/recommendation-health')
@login_required
def recommendation_health():
    try:
        summary = get_recommendation_health()
        return jsonify(summary), 200 if summary.get('database_available') else 503
    except Exception:
        return jsonify(error='Monitoring temporarily unavailable.'), 503


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


@app.errorhandler(413)
def request_too_large(error):
    return jsonify(error='Request exceeds the 16 KiB limit.'), 413


@app.errorhandler(500)
def server_error(error):
    """500 error handler."""
    return render_template('500.html'), 500


if __name__ == '__main__':
    # Development server - DO NOT use in production
    app.run(
        host='127.0.0.1',  # Only accessible from localhost
        port=5000,
        debug=not production and os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    )
