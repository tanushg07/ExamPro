"""
Service initialization module that registers all services.
"""
from app.services import scoring, validation, security, exam

# This module can be used to initialize services with configuration
# and register any hooks or startup procedures

def init_app(app):
    """Initialize services with the Flask app"""
    # Add any initialization code needed for services
    pass
