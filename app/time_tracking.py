"""
Time tracking module for secure exam timing
"""
from datetime import datetime, timedelta
from flask import session
from app import db
from app.models import ExamAttempt
from app.security import log_security_event

class ExamTimer:
    @staticmethod
    def initialize_attempt(attempt_id):
        """Initialize server-side time tracking for an attempt"""
        session[f'exam_timer_{attempt_id}'] = {
            'start_time': datetime.utcnow().isoformat(),
            'last_sync': datetime.utcnow().isoformat(),
            'time_checks': [],
            'grace_period_used': False
        }
        
    @staticmethod
    def validate_time(attempt_id, client_time=None):
        """Validate current time against attempt's time limit"""
        attempt = ExamAttempt.query.get(attempt_id)
        if not attempt:
            return False, "Invalid attempt"
            
        timer_data = session.get(f'exam_timer_{attempt_id}')
        if not timer_data:
            return False, "Timer not initialized"
            
        now = datetime.utcnow()
        start_time = datetime.fromisoformat(timer_data['start_time'])
        
        # Calculate elapsed time using server time
        elapsed = now - start_time
        time_limit = timedelta(minutes=attempt.exam.time_limit_minutes)
        grace_period = timedelta(minutes=2)
        
        # Validate client time if provided
        if client_time:
            client_datetime = datetime.fromisoformat(client_time)
            time_diff = abs((client_datetime - now).total_seconds())
            
            # Log suspicious time differences
            if time_diff > 300:  # 5 minutes
                log_security_event('TIME_MANIPULATION', 
                    f'Suspicious time difference of {time_diff} seconds for attempt {attempt_id}',
                    user_id=attempt.student_id,
                    severity='high')
                return False, "Time validation failed"
                
        # Check if time has expired
        if elapsed > (time_limit + grace_period):
            return False, "Time expired"
            
        # Update last sync time
        timer_data['last_sync'] = now.isoformat()
        timer_data['time_checks'].append({
            'server_time': now.isoformat(),
            'client_time': client_time,
            'elapsed': elapsed.total_seconds()
        })
        session.modified = True
        
        # Calculate remaining time
        remaining = (time_limit - elapsed).total_seconds()
        if remaining < 0:
            if not timer_data['grace_period_used']:
                remaining = grace_period.total_seconds()
                timer_data['grace_period_used'] = True
            else:
                remaining = 0
                
        return True, {
            'remaining': remaining,
            'elapsed': elapsed.total_seconds(),
            'server_time': now.isoformat()
        }
        
    @staticmethod
    def cleanup_attempt(attempt_id):
        """Clean up timer data when attempt is submitted"""
        session.pop(f'exam_timer_{attempt_id}', None)
