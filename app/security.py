from flask import request, abort, current_app, flash, redirect, url_for, render_template
from flask_login import current_user
from functools import wraps
import functools
import time
from datetime import datetime, timedelta
from sqlalchemy.sql import select

# Import models lazily to avoid circular imports
from app.models import db

# Store for tracking login attempts (IP address -> [attempts])
login_attempts = {}
# Time window for rate limiting in seconds (e.g., 300 = 5 minutes)
RATE_LIMIT_WINDOW = 300
# Maximum number of failed attempts allowed in the time window
MAX_ATTEMPTS = 5

def ip_rate_limit(max_requests=MAX_ATTEMPTS, window=RATE_LIMIT_WINDOW):
    """
    Decorator to limit the number of login attempts from a single IP address
    within a specified time window.
    
    Args:
        max_requests (int): Maximum number of requests allowed in the time window
        window (int): Time window in seconds
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get client IP address
            ip = request.remote_addr
            current_time = time.time()
            
            # Initialize if IP not in tracking dictionary
            if ip not in login_attempts:
                login_attempts[ip] = []
            
            # Remove attempts outside the time window
            login_attempts[ip] = [attempt for attempt in login_attempts[ip] 
                                if current_time - attempt < window]
            
            # Check if max attempts exceeded
            if len(login_attempts[ip]) >= max_requests:
                # Log the blocked attempt
                print(f"Rate limit exceeded for IP: {ip}")
                
                # Calculate time until unblocked
                newest_attempt = max(login_attempts[ip])
                time_until_reset = int(window - (current_time - newest_attempt))
                
                # Return a 429 Too Many Requests error
                return render_template(
                    'errors/429.html', 
                    minutes=time_until_reset // 60,
                    seconds=time_until_reset % 60
                ), 429
            
            # Track this attempt
            login_attempts[ip].append(current_time)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def teacher_required(f):
    """
    Enhanced decorator that ensures only teachers can access specific routes
    Also logs access attempts for security auditing
    """
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if user is authenticated and is a teacher
        if not current_user.is_authenticated:
            # Log unauthorized access attempt
            log_security_event('AUTH_FAIL', 'Unauthenticated access attempt to teacher resource')
            return redirect(url_for('auth.login', next=request.url))
            
        if not current_user.is_teacher():
            # Log potential privilege escalation attempt
            log_security_event('PRIVILEGE_ESCALATION', 
                              f'Non-teacher user ({current_user.id}) attempted to access teacher resource')
            abort(403)  # Forbidden
            
        # Add security headers to response
        # Will be executed after the view function returns
        def add_security_headers(response):
            response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; object-src 'none'"
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'SAMEORIGIN'
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
            return response
        
        # Register the after_request function
        current_app.after_request_funcs.setdefault(None, []).append(add_security_headers)
        
        return f(*args, **kwargs)
    
    return decorated_function

def student_required(f):
    """
    Enhanced decorator that ensures only students can access specific routes
    Also logs access attempts for security auditing
    """
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if user is authenticated and is a student
        if not current_user.is_authenticated:
            # Log unauthorized access attempt
            log_security_event('AUTH_FAIL', 'Unauthenticated access attempt to student resource')
            return redirect(url_for('auth.login', next=request.url))
            
        if not current_user.is_student():
            # Log potential privilege escalation attempt
            log_security_event('PRIVILEGE_ESCALATION', 
                              f'Non-student user ({current_user.id}) attempted to access student resource')
            abort(403)  # Forbidden
            
        # Add security headers to response
        def add_security_headers(response):
            response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; object-src 'none'"
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'SAMEORIGIN'
            return response
        
        # Register the after_request function
        current_app.after_request_funcs.setdefault(None, []).append(add_security_headers)
        
        return f(*args, **kwargs)
    
    return decorated_function

def admin_required(f):
    """
    Decorator that ensures only admins can access specific routes
    Logs all access attempts for security auditing
    """
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if user is authenticated and is an admin
        if not current_user.is_authenticated:
            # Log unauthorized access attempt
            log_security_event('AUTH_FAIL', 'Unauthenticated access attempt to admin resource')
            return redirect(url_for('auth.login', next=request.url))
            
        if not current_user.is_admin():
            # Log potential privilege escalation attempt - high severity
            log_security_event('ADMIN_ACCESS_VIOLATION', 
                              f'Non-admin user ({current_user.id}) attempted to access admin resource',
                              severity='high')
            abort(403)  # Forbidden
              # Add security headers to response
        def add_security_headers(response):
            response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; object-src 'none'"
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'DENY'
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
            return response
        
        # Register the after_request function
        current_app.after_request_funcs.setdefault(None, []).append(add_security_headers)
        
        return f(*args, **kwargs)
    
    return decorated_function

def login_rate_limit(max_requests=MAX_ATTEMPTS, window=RATE_LIMIT_WINDOW):
    """
    Specific decorator for login routes that tracks failed login attempts
    and provides user feedback about remaining attempts
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get client IP address
            ip = request.remote_addr
            current_time = time.time()
            
            # Initialize if IP not in tracking dictionary
            if ip not in login_attempts:
                login_attempts[ip] = []
            
            # Remove attempts outside the time window
            login_attempts[ip] = [attempt for attempt in login_attempts[ip] 
                                if current_time - attempt < window]
            
            # Check if max attempts exceeded
            if len(login_attempts[ip]) >= max_requests:
                # Calculate time until unblocked
                newest_attempt = max(login_attempts[ip])
                time_until_reset = int(window - (current_time - newest_attempt))
                
                flash(f'Too many login attempts. Please try again in {time_until_reset//60} minutes and {time_until_reset%60} seconds.', 'error')
                return render_template('auth/login.html'), 429
            
            # Execute the view function and check result
            response = f(*args, **kwargs)
            
            # If the response indicates a failed login (by checking for flash message in HTML)
            # Handle both string responses and response objects with data attribute
            response_text = str(response) if isinstance(response, str) else str(getattr(response, 'data', ''))
            if request.method == 'POST' and 'Invalid username or password' in response_text:
                login_attempts[ip].append(current_time)
                
                # Warn user about remaining attempts
                attempts_left = max_requests - len(login_attempts[ip])
                if attempts_left <= 3:  # Only warn when getting close to the limit
                    flash(f'Login failed. {attempts_left} attempts remaining before temporary lockout.', 'warning')
            
            return response
        return decorated_function
    return decorator

def reset_login_attempts(ip=None):
    """
    Reset login attempt tracking for a specific IP or all IPs
    
    Args:
        ip (str, optional): IP address to reset. If None, resets all IPs.
    """
    global login_attempts
    if ip:
        if ip in login_attempts:
            del login_attempts[ip]
    else:
        login_attempts = {}

# Import Flask's render_template and flash functions to use in the decorated function
from flask import render_template, flash

def log_security_event(event_type, description, severity='medium'):
    """
    Log a security event to the security log table or application log
    """
    try:
        # Get User ID if authenticated
        user_id = current_user.id if current_user.is_authenticated else None
        
        # Create log entry 
        from app.models import SecurityLog, db
        
        log = SecurityLog(
            event_type=event_type,
            description=description,
            user_id=user_id,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string,
            path=request.path,
            method=request.method,
            severity=severity,
            timestamp=datetime.utcnow()
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        # Log to app logger if database logging fails
        current_app.logger.error(f"Failed to log security event: {str(e)}")
        try:
            db.session.rollback()
        except:
            pass

def verify_exam_owner(exam_id):
    """
    Verify that the current user is the owner of the specified exam
    Raises 403 error if not the owner
    Returns the exam object if the user is the owner
    """
    from app.models import Exam
    
    exam = Exam.query.get_or_404(exam_id)
    
    if exam.creator_id != current_user.id and not current_user.is_admin():
        # Log unauthorized access attempt
        log_security_event('RESOURCE_ACCESS_VIOLATION', 
                         f'User {current_user.id} attempted to access exam {exam_id} owned by user {exam.creator_id}')
        abort(403)
        
    return exam

def verify_attempt_access(attempt_id):
    """
    Verify that the current user has permission to access the specified exam attempt
    Teachers can access attempts for exams they created
    Students can only access their own attempts
    """
    from app.models import ExamAttempt, Exam
    
    attempt = ExamAttempt.query.get_or_404(attempt_id)
    exam = Exam.query.get_or_404(attempt.exam_id)
    
    if current_user.is_teacher():
        if exam.creator_id != current_user.id and not current_user.is_admin():
            # Log unauthorized access attempt
            log_security_event('ATTEMPT_ACCESS_VIOLATION', 
                             f'Teacher {current_user.id} attempted to access attempt {attempt_id} for exam {exam.id} created by {exam.creator_id}')
            abort(403)
    elif current_user.is_student():
        if attempt.student_id != current_user.id:
            # Log unauthorized access attempt
            log_security_event('ATTEMPT_ACCESS_VIOLATION', 
                             f'Student {current_user.id} attempted to access attempt {attempt_id} belonging to student {attempt.student_id}')
            abort(403)
    else:
        # Neither teacher nor student
        log_security_event('ROLE_VIOLATION', 
                         f'User {current_user.id} with role {current_user.user_type} attempted to access attempt {attempt_id}')
        abort(403)
        
    return attempt

# Enhanced rate limiter for security-sensitive operations
class EnhancedRateLimiter:
    """Rate limiter with tiered restrictions and persistent tracking"""
    
    def __init__(self, default_limit=5, window_seconds=60):
        self.default_limit = default_limit
        self.window_seconds = window_seconds
        self.requests = {}  # IP address -> list of timestamps
        self.blocked_ips = {}  # IP address -> block expiry time
        
    def is_rate_limited(self, ip_address, action_type='default'):
        """
        Check if the IP address is currently rate limited
        Different action types can have different limits
        """
        now = time.time()
        
        # Check if IP is currently blocked
        if ip_address in self.blocked_ips:
            if now < self.blocked_ips[ip_address]:
                # Still blocked
                remaining = int(self.blocked_ips[ip_address] - now)
                return True, remaining
            else:
                # Block expired
                del self.blocked_ips[ip_address]
        
        # Get action-specific limits
        if action_type == 'login':
            max_requests = 5
            window = 60  # 1 minute
        elif action_type == 'password_reset':
            max_requests = 3
            window = 300  # 5 minutes
        elif action_type == 'api':
            max_requests = 30
            window = 60  # 1 minute
        else:
            max_requests = self.default_limit
            window = self.window_seconds
        
        # Initialize if IP not seen before
        if ip_address not in self.requests:
            self.requests[ip_address] = {}
        
        if action_type not in self.requests[ip_address]:
            self.requests[ip_address][action_type] = []
        
        # Remove timestamps outside the window
        self.requests[ip_address][action_type] = [
            ts for ts in self.requests[ip_address][action_type] 
            if now - ts < window
        ]
        
        # Check if over the limit
        if len(self.requests[ip_address][action_type]) >= max_requests:
            # Block this IP for a progressively longer time
            violation_count = len(self.requests[ip_address][action_type]) - max_requests + 1
            block_time = min(3600, 60 * (2 ** violation_count))  # Exponential backoff up to 1 hour
            
            self.blocked_ips[ip_address] = now + block_time
            
            # Log rate limit violation
            log_security_event('RATE_LIMIT_VIOLATION', 
                             f'IP {ip_address} exceeded rate limit for {action_type}: {max_requests} requests in {window} seconds. Blocked for {block_time} seconds',
                             severity='medium')
                             
            return True, block_time
            
        # Add current timestamp and allow request
        self.requests[ip_address][action_type].append(now)
        return False, 0

# Create global rate limiter instances
security_rate_limiter = EnhancedRateLimiter()