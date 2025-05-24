from functools import wraps
from flask import abort, request
from flask_login import current_user
from .models import ActivityLog

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def log_activity(action=None, category=None):
    """
    Decorator to log user activities
    Example usage:
    @log_activity(action="create_exam", category="exam")
    def create_exam():
        ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get the activity details
            current_action = action if action else f.__name__
            current_category = category if category else f.__module__.split('.')[-1]
            
            # Execute the route function
            result = f(*args, **kwargs)
            
            # Only log if user is authenticated
            if current_user.is_authenticated:
                # Collect request details
                details = {
                    'method': request.method,
                    'path': request.path,
                    'args': dict(request.args),
                    'endpoint': request.endpoint
                }
                
                # Add route parameters if any
                if kwargs:
                    details['params'] = kwargs
                
                # Log the activity
                ActivityLog.log_activity(
                    user_id=current_user.id,
                    action=current_action,
                    category=current_category,
                    details=details,
                    ip_address=request.remote_addr,
                    user_agent=str(request.user_agent)
                )
            
            return result
        return decorated_function
    return decorator

def teacher_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_teacher():
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def student_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_student():
            abort(403)
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function
