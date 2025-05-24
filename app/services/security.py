"""
Services module for handling security-related business logic.
This separates security logic from models, improving maintainability.
"""
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError
from app import db
from app.enums import VerificationStatus
import logging

# Configure logging
logger = logging.getLogger(__name__)

def log_security_event(exam_attempt, event_type, data, severity='info', ip_address=None, user_agent=None):
    """
    Log a security event with proper transaction handling
    
    Args:
        exam_attempt: The ExamAttempt object
        event_type: The type of security event
        data: The event data
        severity: The event severity (info, warning, error)
        ip_address: The IP address of the client
        user_agent: The user agent of the client
        
    Returns:
        bool: True if logging was successful, False otherwise
    """
    from app.models_fixed import SecurityLog
    from app.services.validation import validate_json_size
    
    # Validate and potentially truncate the data
    validated_data = validate_json_size(data)
    
    # Create the event object
    timestamp = datetime.utcnow()
    event = {
        'type': event_type,
        'timestamp': timestamp.isoformat(),
        'data': validated_data,
        'severity': severity
    }
    
    try:
        # Start a transaction
        with db.session.begin():
            # Update the appropriate event list based on type
            if event_type.startswith('security_'):
                exam_attempt.security_events = exam_attempt.security_events or []
                exam_attempt.security_events.append(event)
            elif event_type.startswith('browser_'):
                exam_attempt.browser_events = exam_attempt.browser_events or []
                exam_attempt.browser_events.append(event)
            elif event_type.startswith('warning_'):
                exam_attempt.warning_events = exam_attempt.warning_events or []
                exam_attempt.warning_events.append(event)
                exam_attempt.warning_count += 1
                
                # Auto-flag if too many events
                max_warnings = getattr(exam_attempt.exam, 'max_warnings', 3)
                if exam_attempt.warning_count >= max_warnings:
                    exam_attempt.verification_status = VerificationStatus.AUTO_FLAGGED.value
            
            # Add the security log
            security_log = SecurityLog(
                event_type=event_type,
                description=f"Event logged for exam attempt {exam_attempt.id}",
                user_id=exam_attempt.student_id,
                ip_address=ip_address,
                user_agent=user_agent,
                severity=severity,
                details=event
            )
            db.session.add(security_log)
            db.session.add(exam_attempt)
            
        return True
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Error logging security event: {str(e)}")
        return False

def verify_exam_environment(exam_attempt, security_checks):
    """
    Verify the exam environment meets security requirements
    
    Args:
        exam_attempt: The ExamAttempt object
        security_checks: Dictionary of security checks to verify
        
    Returns:
        tuple: (is_verified, list of failed checks)
    """
    from app.services.validation import validate_json_size
    
    # Validate and potentially truncate the security checks
    security_checks = validate_json_size(security_checks)
    
    # Required security checks based on exam settings
    required_checks = []
    failed_checks = []
    
    # Add required checks based on exam settings
    if exam_attempt.exam.require_lockdown:
        required_checks.append('secure_browser')
    if exam_attempt.exam.require_webcam:
        required_checks.append('webcam')
    if exam_attempt.exam.prevent_copy_paste:
        required_checks.append('copy_paste_disabled')
        
    # Always required checks
    required_checks.extend(['browser_integrity', 'fullscreen'])
    
    # Check each required security feature
    for check in required_checks:
        if check not in security_checks or not security_checks[check]:
            failed_checks.append(check)
            
    # Update the attempt with the verification results
    exam_attempt.server_side_checks = {
        'timestamp': datetime.utcnow().isoformat(),
        'required_checks': required_checks,
        'provided_checks': list(security_checks.keys()),
        'failed_checks': failed_checks,
        'is_verified': len(failed_checks) == 0
    }
    
    # Update the verification status
    exam_attempt.environment_verified = len(failed_checks) == 0
    
    try:
        db.session.add(exam_attempt)
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Error updating environment verification: {str(e)}")
        
    return len(failed_checks) == 0, failed_checks
