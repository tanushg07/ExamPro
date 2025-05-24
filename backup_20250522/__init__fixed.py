"""
Updated application initialization file that uses the fixed models
and incorporates the new services layer.
"""
from flask import Flask, render_template, request
from flask_login import LoginManager, current_user
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect
from datetime import timedelta
import logging

from config import Config

# Initialize Flask extensions
db = SQLAlchemy()
mail = Mail()
csrf = CSRFProtect()

# Initialize LoginManager
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# User loader for Flask-Login
@login_manager.user_loader
def load_user(id):
    from app.models_fixed import User
    try:
        return User.query.get(int(id))
    except Exception as e:
        logger.error(f"Error loading user {id}: {str(e)}")
        return None

def create_app(config_class=Config):
    app = Flask(__name__, 
                template_folder='../templates',
                static_folder='../static')
    
    # Load configuration
    app.config.from_object(config_class)
    
    # Register filters
    from app.filters import format_datetime, timesince
    app.jinja_env.filters['format_datetime'] = format_datetime
    app.jinja_env.filters['timesince'] = timesince
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)
    migrate = Migrate(app, db)
    
    # Configure CSRF for AJAX
    @app.before_request
    def csrf_protect():
        if request.method != 'GET':
            token = request.headers.get('X-CSRF-Token')
            if token:
                return token

    # Add context processor to make models available in templates
    @app.context_processor
    def inject_models():
        from app.models_fixed import Notification
        return dict(Notification=Notification)
    
    # Register blueprints first to ensure models are fully loaded
    from app.auth import auth_bp
    from app.admin_routes import admin_bp
    from app.routes import main_bp, teacher_bp, student_bp
    from app.group_routes import group_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(teacher_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(group_bp)
    
    # Initialize services
    from app.services import init_app as init_services
    init_services(app)
    
    # Now initialize background tasks with a fully set up app
    with app.app_context():
        # Ensure database is initialized
        db.create_all()
        
        # Register background tasks
        from app.background_tasks import register_task, start_scheduler
        from app.notifications import notify_exam_deadline_approaching
        
        # Register the notification task to run every hour
        register_task(notify_exam_deadline_approaching, 3600, "exam_deadline_notifications")
        
        # Start the scheduler in the background
        start_scheduler(app)
    
    # Error handlers with improved logging
    @app.errorhandler(404)
    def not_found_error(error):
        logger.warning(f"404 error: {request.path} - User: {current_user.id if not current_user.is_anonymous else 'anonymous'}")
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(403)
    def forbidden_error(error):
        logger.warning(f"403 error: {request.path} - User: {current_user.id if not current_user.is_anonymous else 'anonymous'}")
        return render_template('errors/403.html'), 403
    
    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"500 error: {str(error)} - Path: {request.path} - User: {current_user.id if not current_user.is_anonymous else 'anonymous'}")
        db.session.rollback()
        return render_template('errors/500.html'), 500
    
    # Log application startup
    logger.info("Application started successfully")
    
    return app
