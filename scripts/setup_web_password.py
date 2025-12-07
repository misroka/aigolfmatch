#!/usr/bin/env python3
"""
Script to generate a secure password hash for the web interface.
Run this to create a new admin password.
"""

from werkzeug.security import generate_password_hash
import secrets
import sys

def main():
    print("=" * 60)
    print("Golf Club Database - Password Setup")
    print("=" * 60)
    print()
    
    # Generate secret key
    print("1. SECRET_KEY (for Flask session security):")
    secret_key = secrets.token_hex(32)
    print(f"   {secret_key}")
    print()
    
    # Generate password hash
    print("2. Admin Password Setup:")
    print()
    
    while True:
        password = input("   Enter admin password: ").strip()
        
        if len(password) < 8:
            print("   ❌ Password must be at least 8 characters long")
            continue
        
        password_confirm = input("   Confirm password: ").strip()
        
        if password != password_confirm:
            print("   ❌ Passwords don't match")
            continue
        
        break
    
    password_hash = generate_password_hash(password)
    
    print()
    print("=" * 60)
    print("✅ Configuration Complete!")
    print("=" * 60)
    print()
    print("Add these to your .env file:")
    print()
    print(f"SECRET_KEY={secret_key}")
    print(f"ADMIN_USERNAME=admin")
    print(f"ADMIN_PASSWORD_HASH={password_hash}")
    print()
    print("=" * 60)
    print("Security Reminders:")
    print("=" * 60)
    print("• Keep your .env file secure")
    print("• Don't commit .env to git")
    print("• Use a strong, unique password")
    print("• The application only runs on localhost by default")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nCancelled.")
        sys.exit(1)
