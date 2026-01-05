"""
Supabase client initialization.
"""
from supabase import create_client, Client
from flask import current_app, g


def get_supabase() -> Client:
    """Get Supabase client for current request."""
    if 'supabase' not in g:
        g.supabase = create_client(
            current_app.config['SUPABASE_URL'],
            current_app.config['SUPABASE_SERVICE_KEY']
        )
    return g.supabase


def get_supabase_anon() -> Client:
    """Get Supabase client with anon key (for auth operations)."""
    if 'supabase_anon' not in g:
        g.supabase_anon = create_client(
            current_app.config['SUPABASE_URL'],
            current_app.config['SUPABASE_ANON_KEY']
        )
    return g.supabase_anon
