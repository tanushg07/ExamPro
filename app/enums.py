"""
Centralizes enum definitions used throughout the application.
This helps prevent migration issues and ensures consistency across the app.
"""
from enum import Enum

class VerificationStatus(Enum):
    PENDING = 'pending'
    APPROVED = 'approved'
    FLAGGED = 'flagged'
    AUTO_FLAGGED = 'auto_flagged'

class UserType(Enum):
    ADMIN = 'admin'
    TEACHER = 'teacher'
    STUDENT = 'student'

class QuestionType(Enum):
    MCQ = 'mcq'
    TEXT = 'text'
    CODE = 'code'

class NotificationType(Enum):
    INFO = 'info'
    EXAM_GRADED = 'exam_graded'
    EXAM_CREATED = 'exam_created'
    DEADLINE_APPROACHING = 'deadline_approaching'
    GROUP_INVITE = 'group_invite'
    
class SecurityEventType(Enum):
    LOGIN_FAIL = 'login_fail'
    ACCESS_VIOLATION = 'access_violation'
    SUSPICIOUS_ACTIVITY = 'suspicious_activity'
    EXAM_FLAGGED = 'exam_flagged'
    
class SecuritySeverity(Enum):
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'

# Convert enums to strings for SQLAlchemy
verification_status_enum = [e.value for e in VerificationStatus]
user_type_enum = [e.value for e in UserType]
question_type_enum = [e.value for e in QuestionType]
notification_type_enum = [e.value for e in NotificationType]
security_event_type_enum = [e.value for e in SecurityEventType]
security_severity_enum = [e.value for e in SecuritySeverity]
