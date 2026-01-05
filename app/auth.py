"""
Authentication utilities.
"""
from functools import wraps
from flask import session, redirect, url_for, g, flash
from .supabase_client import get_supabase_anon, get_supabase


def login_required(f):
    """Decorator to require authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'access_token' not in session:
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('auth.login'))
        
        # Verify token is still valid
        try:
            supabase = get_supabase_anon()
            supabase.auth.set_session(
                session['access_token'],
                session.get('refresh_token', '')
            )
            response = supabase.auth.get_user()
            
            if not response or not response.user:
                session.clear()
                flash('Session expired. Please log in again.', 'warning')
                return redirect(url_for('auth.login'))
            
            # Store user in g for easy access
            g.user = response.user
            g.user_id = response.user.id
            
        except Exception as e:
            session.clear()
            flash('Session error. Please log in again.', 'warning')
            return redirect(url_for('auth.login'))
        
        return f(*args, **kwargs)
    return decorated_function


def get_current_user():
    """Get the currently authenticated user."""
    return getattr(g, 'user', None)


def get_current_user_id():
    """Get the currently authenticated user's ID."""
    return getattr(g, 'user_id', None)


def get_user_profile():
    """Get the current user's profile from database."""
    user_id = get_current_user_id()
    if not user_id:
        return None
    
    supabase = get_supabase()
    response = supabase.table('user_profiles').select('*').eq('id', user_id).single().execute()
    return response.data if response.data else None
