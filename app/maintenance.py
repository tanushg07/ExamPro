"""
Cleanup tasks for exam platform maintenance
"""
from datetime import datetime, timedelta
from sqlalchemy import and_, or_, func
from app import db
from app.models import ExamAttempt, SecurityLog, Notification, Exam

def cleanup_old_events(days_to_keep=30):
    """Clean up old security events and logs"""
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        # Get completed attempts older than cutoff
        old_attempts = ExamAttempt.query.filter(
            ExamAttempt.completed_at < cutoff_date
        ).all()
        
        for attempt in old_attempts:
            # Clear event logs but keep summary
            if attempt.security_events:
                # Keep only critical events
                critical_events = [
                    event for event in attempt.security_events
                    if event.get('severity') == 'high'
                ]
                attempt.security_events = critical_events[:10]  # Keep last 10 critical events
                
            attempt.browser_events = None
            attempt.warning_events = None
            
        # Delete old security logs
        SecurityLog.query.filter(
            SecurityLog.timestamp < cutoff_date
        ).delete()
        
        # Delete old read notifications
        Notification.query.filter(and_(
            Notification.created_at < cutoff_date,
            Notification.is_read == True
        )).delete()
        
        db.session.commit()
        return True, "Cleanup completed successfully"
        
    except Exception as e:
        db.session.rollback()
        return False, f"Error during cleanup: {str(e)}"
        
def cleanup_incomplete_attempts():
    """Clean up stale incomplete attempts"""
    try:
        now = datetime.utcnow()
        
        # Find attempts that are incomplete but past their time limit
        stale_attempts = ExamAttempt.query.join(
            Exam
        ).filter(
            ExamAttempt.is_completed == False,
            ExamAttempt.started_at < (now - func.interval(Exam.time_limit_minutes, 'minute'))
        ).all()
        
        for attempt in stale_attempts:
            # Mark as completed with auto-submission
            attempt.is_completed = True
            attempt.completed_at = attempt.started_at + timedelta(minutes=attempt.exam.time_limit_minutes)
            attempt.submitted_at = now
            attempt.verification_status = 'auto_flagged'
            
            # Log auto-submission
            if not attempt.security_events:
                attempt.security_events = []
            attempt.security_events.append({
                'type': 'AUTO_SUBMISSION',
                'timestamp': now.isoformat(),
                'severity': 'warning',
                'data': {
                    'reason': 'time_expired',
                    'started_at': attempt.started_at.isoformat(),
                    'time_limit': attempt.exam.time_limit_minutes
                }
            })
            
        db.session.commit()
        return True, f"Processed {len(stale_attempts)} stale attempts"
        
    except Exception as e:
        db.session.rollback()
        return False, f"Error processing stale attempts: {str(e)}"

def vacuum_database():
    """Run database maintenance tasks"""
    try:
        # Using raw SQL for database-specific operations
        if db.engine.dialect.name == 'mysql':
            db.session.execute('OPTIMIZE TABLE exam_attempts, security_logs, notifications')
        elif db.engine.dialect.name == 'postgresql':
            db.session.execute('VACUUM ANALYZE exam_attempts, security_logs, notifications')
            
        db.session.commit()
        return True, "Database maintenance completed"
        
    except Exception as e:
        db.session.rollback()
        return False, f"Error during database maintenance: {str(e)}"
