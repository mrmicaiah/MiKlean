"""
MiKlean - Simple app for small cleaning businesses
"""
from flask import Flask
from .config import Config


def create_app(config_class=Config):
    """Application factory."""
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Register blueprints
    from .routes import auth, main, clients, estimates, visits, invoices, settings, api, onboarding, help
    
    app.register_blueprint(auth.bp)
    app.register_blueprint(main.bp)
    app.register_blueprint(clients.bp)
    app.register_blueprint(estimates.bp)
    app.register_blueprint(visits.bp)
    app.register_blueprint(invoices.bp)
    app.register_blueprint(settings.bp)
    app.register_blueprint(api.bp)
    app.register_blueprint(onboarding.bp)
    app.register_blueprint(help.bp)
    
    # Register error handlers
    from .errors import register_error_handlers
    register_error_handlers(app)
    
    return app
