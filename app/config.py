"""
Application configuration.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration."""
    
    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-change-in-production'
    
    # Supabase
    SUPABASE_URL = os.environ.get('SUPABASE_URL')
    SUPABASE_ANON_KEY = os.environ.get('SUPABASE_ANON_KEY')
    SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_KEY')
    
    # SendGrid
    SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY')
    SENDGRID_FROM_EMAIL = os.environ.get('SENDGRID_FROM_EMAIL', 'noreply@miklean.app')
    
    # Google OAuth
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
    
    # Encryption (for Google tokens)
    ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY')
    
    # Cron secret (for scheduled tasks)
    CRON_SECRET = os.environ.get('CRON_SECRET')
    
    # App settings
    APP_NAME = 'MiKlean'
    APP_URL = os.environ.get('APP_URL', 'http://localhost:5000')


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False


# Config mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
