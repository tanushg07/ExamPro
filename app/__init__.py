from flask import Flask, render_template, request
from flask_login import LoginManager, current_user
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect
from datetime import timedelta

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

# User loader for Flask-Login
@login_manager.user_loader
def load_user(id):
    from app.models import User
    return User.query.get(int(id))

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
    migrate = Migrate(app, db)    # Configure CSRF for AJAX
    @app.before_request
    def csrf_protect():
        if request.method != 'GET':
            token = request.headers.get('X-CSRF-Token')
            if token:
                return token

    # Add context processor to make models available in templates
    @app.context_processor
    def inject_models():
        from app.models import Notification
        return dict(Notification=Notification)
    
    # Register background tasks
    # Register blueprints first to ensure models are fully loaded
    from app.auth import auth_bp
    from app.admin_routes import admin_bp  # Import admin_bp first
    from app.routes import main_bp, teacher_bp, student_bp
    from app.group_routes import group_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(teacher_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(group_bp)
    
    # Now initialize background tasks with a fully set up app
    with app.app_context():
        from app.background_tasks import register_task, start_scheduler
        from app.notifications import notify_exam_deadline_approaching
        
        # Ensure database is initialized
        db.create_all()
        
        # Register the notification task to run every hour
        register_task(notify_exam_deadline_approaching, 3600, "exam_deadline_notifications")
        
    # Start the scheduler in the background
        start_scheduler(app)
    
    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('errors/403.html'), 403
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('errors/500.html'), 500
        
    @app.errorhandler(429)
    def too_many_requests(error):
        return render_template('errors/429.html', 
                              minutes=5,
                              seconds=0), 429
    
    # Context processors
    @app.context_processor
    def inject_user():
        return dict(current_user=current_user)
      # Register template filters
    from app.filters import timesince, format_datetime, format_timedelta
    app.jinja_env.filters['timesince'] = timesince
    app.jinja_env.filters['datetime'] = format_datetime  # Register as 'datetime' to match template usage
    app.jinja_env.filters['timedelta'] = format_timedelta  # Add timedelta filter
    
    return app

# Import for render_template and current_user
from flask import render_template
from flask_login import current_user