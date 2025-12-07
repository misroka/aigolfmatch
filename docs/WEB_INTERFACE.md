# Web Interface Setup Guide

## Overview

A secure Flask-based web interface for accessing and managing your golf club database. Features login authentication, responsive design, and comprehensive database browsing.

## Features

✅ **Secure Authentication** - Login required for all pages
✅ **Dashboard** - Quick overview with statistics
✅ **Browse Clubs** - Filter by brand, type, year, skill level
✅ **Club Details** - Comprehensive information and reviews
✅ **Brand Directory** - View all brands and their clubs
✅ **Reviewer Profiles** - Browse player profiles
✅ **Search** - Fast search by brand or model
✅ **API Endpoints** - JSON data for integrations
✅ **Responsive Design** - Works on desktop and mobile

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

This installs Flask, Flask-Login, and other web dependencies.

### 2. Set Up Security

Generate a secure password hash:

```python
from werkzeug.security import generate_password_hash

# Generate hash for your password
password = "your_secure_password_here"
hash = generate_password_hash(password)
print(hash)
```

Update your `.env` file:

```bash
# Copy example
cp .env.example .env

# Edit .env with your values
nano .env
```

**Required Settings:**

```env
# Database (already configured)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=golf_clubs
DB_USER=postgres
DB_PASSWORD=your_db_password

# Web Application Security
SECRET_KEY=generate_a_random_secret_key_here
ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=paste_hash_from_above

# Flask Settings
FLASK_DEBUG=False
FLASK_ENV=production
```

**Generate SECRET_KEY:**

```python
import secrets
print(secrets.token_hex(32))
```

### 3. Run the Application

```bash
cd web
python app.py
```

The application will start on `http://127.0.0.1:5000`

**Access from localhost only** - Not exposed to the internet.

### 4. Login

- Open your browser to: `http://127.0.0.1:5000`
- Username: `admin` (or whatever you set in `.env`)
- Password: Your password (not the hash!)

## Security Features

### 🔒 Authentication Required
- All pages except login require authentication
- Session-based login with Flask-Login
- "Remember me" option for persistent login
- Automatic session timeout after 24 hours

### 🛡️ Secure by Default
- Binds to `127.0.0.1` only (localhost)
- Not accessible from other machines by default
- Password hashing with Werkzeug
- CSRF protection via secret key
- Session cookies are httponly

### 🔐 Password Best Practices
1. Use a strong password (12+ characters)
2. Mix uppercase, lowercase, numbers, symbols
3. Don't share your password
4. Keep your `.env` file secure
5. Don't commit `.env` to git (it's in `.gitignore`)

## Changing Your Password

```python
from werkzeug.security import generate_password_hash

# Generate new hash
new_password = "your_new_secure_password"
new_hash = generate_password_hash(new_password)
print(new_hash)
```

Update `ADMIN_PASSWORD_HASH` in `.env` with the new hash.

## Pages and Features

### Dashboard (`/`)
- Statistics overview
- Recent clubs added
- Top brands by club count
- Quick action buttons

### Browse Clubs (`/clubs`)
- Filter by brand, type, year, skill level
- Sortable table view
- View club details

### Club Detail (`/club/<id>`)
- Complete club information
- Specifications
- Reviews with reviewer profiles
- Related information

### Brands (`/brands`)
- Grid view of all brands
- Club counts per brand
- Links to brand websites
- Filter clubs by brand

### Reviewer Profiles (`/profiles`)
- Browse reviewer profiles
- Filter by handicap range
- Filter by skill level
- View detailed player stats

### Search (`/search`)
- Search by brand or model name
- Fast results
- Direct links to club details

## API Endpoints

All API endpoints require authentication.

### GET `/api/clubs`
Query clubs with filters.

**Parameters:**
- `brand` - Filter by brand name
- `type` - Filter by club type
- `year` - Filter by year
- `limit` - Max results (default: 50)

**Example:**
```bash
curl -u admin:password http://127.0.0.1:5000/api/clubs?brand=TaylorMade&year=2023
```

**Response:**
```json
{
  "clubs": [...],
  "count": 10
}
```

### GET `/api/stats`
Get database statistics.

**Response:**
```json
{
  "overall": {
    "brand_count": 17,
    "club_count": 45,
    "review_count": 5,
    "profile_count": 2
  },
  "by_year": [...],
  "by_type": [...]
}
```

## Advanced Configuration

### Custom Port

Edit `web/app.py` and change:

```python
app.run(host='127.0.0.1', port=5000)
```

### Enable Debug Mode (Development Only)

In `.env`:
```env
FLASK_DEBUG=True
```

**⚠️ Never use debug mode in production!**

### Multiple Users

The current implementation supports a single admin user. To add multiple users:

1. Create a `users` table in the database
2. Update the User model in `app.py`
3. Implement user management pages
4. Update `load_user()` to query from database

## Production Deployment

For production use, **don't use the built-in Flask server**. Instead:

### Option 1: Gunicorn (Recommended)

```bash
pip install gunicorn

# Run with Gunicorn
cd web
gunicorn -w 4 -b 127.0.0.1:5000 app:app
```

### Option 2: uWSGI

```bash
pip install uwsgi

# Run with uWSGI
cd web
uwsgi --http 127.0.0.1:5000 --wsgi-file app.py --callable app --processes 4
```

### Option 3: Docker

Create `Dockerfile` in web directory:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
```

### Reverse Proxy (nginx)

For HTTPS and additional security, use nginx:

```nginx
server {
    listen 443 ssl;
    server_name yourdomain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Accessing from Other Devices

**⚠️ Security Warning:** Only do this if you trust your network!

Change in `app.py`:
```python
app.run(host='0.0.0.0', port=5000)  # Accessible from network
```

Then access from other devices using: `http://YOUR_IP:5000`

Find your IP:
```bash
# Linux/Mac
ip addr show  # or ifconfig

# Windows
ipconfig
```

## Troubleshooting

### "Address already in use"
Another process is using port 5000. Either:
- Stop that process
- Use a different port

### "Can't connect to database"
Check your `.env` database settings and ensure PostgreSQL is running:
```bash
psql golf_clubs -c "SELECT 1"
```

### "Login fails with correct password"
Make sure you're using the password itself, not the hash.
Regenerate the hash if needed:
```python
from werkzeug.security import generate_password_hash
print(generate_password_hash("your_password"))
```

### "Page not loading"
Check if the server is running:
```bash
curl http://127.0.0.1:5000
```

## Stopping the Server

Press `Ctrl+C` in the terminal where the server is running.

## Customization

### Change Colors

Edit `web/static/css/style.css` and modify the `:root` variables:

```css
:root {
    --primary-color: #2c5282;  /* Change this */
    --secondary-color: #4299e1;  /* And this */
    ...
}
```

### Add Features

1. Create new template in `web/templates/`
2. Add route in `web/app.py`
3. Add navigation link in `web/templates/base.html`

### Customize Logo

Replace `⛳` in `base.html` with your own logo image.

## File Structure

```
web/
├── app.py                 # Main Flask application
├── static/
│   ├── css/
│   │   └── style.css     # Styles
│   └── js/
│       └── main.js       # JavaScript
└── templates/
    ├── base.html         # Base template
    ├── login.html        # Login page
    ├── index.html        # Dashboard
    ├── clubs.html        # Browse clubs
    ├── club_detail.html  # Club details
    ├── brands.html       # Brands directory
    ├── profiles.html     # Reviewer profiles
    ├── search.html       # Search page
    ├── 404.html          # Not found
    └── 500.html          # Server error
```

## Support

- Flask docs: https://flask.palletsprojects.com/
- Flask-Login docs: https://flask-login.readthedocs.io/
- Security guide: https://flask.palletsprojects.com/en/latest/security/

## Summary

You now have a secure, feature-rich web interface for your golf club database that:
- Requires authentication
- Runs locally (not exposed to internet)
- Provides comprehensive database browsing
- Includes API endpoints for integrations
- Features a modern, responsive design

🏌️‍♂️ **Enjoy your private golf club database interface!**
