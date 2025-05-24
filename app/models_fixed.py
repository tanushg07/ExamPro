"""
Database models for the examination platform.
This version addresses data integrity, performance, and architectural issues.
"""
from datetime import datetime, timedelta
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func, case, text
from app import db, login_manager
from app.enums import (
    VerificationStatus, UserType, QuestionType, 
    verification_status_enum, user_type_enum, question_type_enum
)
import json
import logging

# Configure logging
logger = logging.getLogger(__name__)

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    user_type = db.Column(db.Enum(*user_type_enum, name='user_type_enum'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships - carefully managed to prevent cascading deletes of critical data
    created_exams = db.relationship('Exam', foreign_keys='Exam.creator_id', 
                                  back_populates='creator', lazy='dynamic')
    exam_attempts = db.relationship('ExamAttempt', backref='student', lazy='joined')
    exam_reviews = db.relationship('ExamReview', foreign_keys='ExamReview.student_id', 
                                 backref=db.backref('reviewer', lazy='joined'))
    notifications = db.relationship('Notification', foreign_keys='Notification.user_id', 
                                  backref=db.backref('notification_user', lazy='joined'), 
                                  cascade='all, delete-orphan')
    security_logs = db.relationship('SecurityLog', backref='user', lazy='joined')
    owned_groups = db.relationship('Group', foreign_keys='Group.teacher_id', 
                                 back_populates='teacher', lazy='dynamic')
    joined_groups = db.relationship('Group', secondary='group_membership', 
                                  back_populates='students', lazy='dynamic')
    activity_logs = db.relationship('ActivityLog', backref='user', lazy='dynamic',
                                  cascade='all, delete-orphan')
    
    def set_password(self, password):
        """Set a secure password hash using PBKDF2-SHA256"""
        if not password or len(password) < 8:
            raise ValueError("Password must be at least 8 characters long")
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')
    
    def check_password(self, password):
        """Verify a password against the stored hash"""
        if not password:
            return False
        return check_password_hash(self.password_hash, password)
    
    def is_teacher(self):
        """Check if user is a teacher"""
        return self.user_type == UserType.TEACHER.value
    
    def is_student(self):
        """Check if user is a student"""
        return self.user_type == UserType.STUDENT.value
    
    def is_admin(self):
        """Check if user is an admin"""
        return self.user_type == UserType.ADMIN.value
    
    def __repr__(self):
        return f'<User {self.username}>'


class Exam(db.Model):
    __tablename__ = 'exams'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    time_limit_minutes = db.Column(db.Integer, nullable=False)
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id', onupdate='CASCADE'), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id', onupdate='CASCADE', ondelete='SET NULL'))
    is_published = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Availability settings
    available_from = db.Column(db.DateTime, nullable=True)
    available_until = db.Column(db.DateTime, nullable=True)
    
    # Security settings
    require_lockdown = db.Column(db.Boolean, default=True)
    allow_calculator = db.Column(db.Boolean, default=False)  
    allow_scratch_pad = db.Column(db.Boolean, default=True)
    randomize_questions = db.Column(db.Boolean, default=True)
    one_question_at_time = db.Column(db.Boolean, default=False)
    prevent_copy_paste = db.Column(db.Boolean, default=True)
    require_webcam = db.Column(db.Boolean, default=False)
    max_warnings = db.Column(db.Integer, default=3)
    
    # Version control
    version = db.Column(db.Integer, default=1, nullable=False)
    
    # Relationships with proper cascade behavior
    creator = db.relationship('User', back_populates='created_exams', foreign_keys=[creator_id])
    group = db.relationship('Group', back_populates='exams', foreign_keys=[group_id])
    questions = db.relationship('Question', backref='exam', lazy='joined', 
                              cascade='all, delete-orphan')
    attempts = db.relationship('ExamAttempt', backref='exam', lazy='dynamic')
    reviews = db.relationship('ExamReview', backref='exam', lazy='dynamic')
    
    # Add indexes for common queries
    __table_args__ = (
        db.Index('idx_exam_availability', 'is_published', 'available_from', 'available_until'),
        db.Index('idx_exam_creator', 'creator_id'),
        db.Index('idx_exam_group', 'group_id'),
    )
    
    def get_average_rating(self):
        """Calculate the average rating for this exam based on student reviews"""
        try:
            # Efficient database query instead of loading all objects
            result = db.session.query(func.avg(ExamReview.rating))\
                .filter(ExamReview.exam_id == self.id)\
                .scalar()
            
            if result is None:
                return None
                
            return round(float(result), 1)
        except SQLAlchemyError as e:
            logger.error(f"Error calculating average rating: {str(e)}")
            return None
    
    def is_active(self):
        """Check if the exam is currently active (within the available time window)"""
        now = datetime.utcnow()
        if not self.available_from or not self.available_until:
            return self.is_published
        return self.is_published and self.available_from <= now <= self.available_until
    
    def is_upcoming(self):
        """Check if the exam is scheduled for a future date"""
        now = datetime.utcnow()
        if not self.available_from:
            return False
        return self.is_published and self.available_from > now
    
    @property
    def max_score(self):
        """Calculate the maximum possible score for this exam"""
        try:
            return db.session.query(func.sum(Question.points))\
                .filter(Question.exam_id == self.id)\
                .scalar() or 0
        except SQLAlchemyError as e:
            logger.error(f"Error calculating max score: {str(e)}")
            return 0
    
    @property
    def start_time(self):
        """Alias for available_from for template compatibility"""
        return self.available_from
        
    @property
    def end_time(self):
        """Alias for available_until for template compatibility"""
        return self.available_until
    
    def __repr__(self):
        return f'<Exam {self.title}>'


class Question(db.Model):
    __tablename__ = 'questions'
    
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('exams.id', ondelete='CASCADE'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    question_type = db.Column(db.Enum(*question_type_enum, name='question_type_enum'), nullable=False)
    points = db.Column(db.Integer, nullable=False, default=1)
    order = db.Column(db.Integer, nullable=False, default=0)
    
    # Version control
    version = db.Column(db.Integer, default=1, nullable=False)
    
    # Relationships
    options = db.relationship('QuestionOption', backref='question', lazy='joined', 
                            cascade='all, delete-orphan')
    answers = db.relationship('Answer', backref='question', lazy='dynamic')
    
    # Add indexes for common queries
    __table_args__ = (
        db.Index('idx_question_exam', 'exam_id'),
        db.Index('idx_question_type', 'question_type'),
    )
    
    def validate(self):
        """Validate the question has the correct options for its type"""
        if self.question_type == QuestionType.MCQ.value:
            # MCQ questions must have at least 2 options and exactly 1 correct answer
            if len(self.options) < 2:
                return False, "MCQ questions must have at least 2 options"
                
            correct_count = sum(1 for option in self.options if option.is_correct)
            if correct_count != 1:
                return False, "MCQ questions must have exactly 1 correct answer"
                
        return True, "Valid"
    
    def __repr__(self):
        return f'<Question {self.id} for Exam {self.exam_id}>'


class QuestionOption(db.Model):
    __tablename__ = 'question_options'
    
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id', ondelete='CASCADE'), nullable=False)
    option_text = db.Column(db.Text, nullable=False)
    is_correct = db.Column(db.Boolean, default=False)
    order = db.Column(db.Integer, nullable=False, default=0)
    
    # Add index for common query
    __table_args__ = (
        db.Index('idx_option_question', 'question_id'),
    )
    
    def __repr__(self):
        return f'<Option {self.id} for Question {self.question_id}>'


# Constants for event data size
MAX_EVENT_DATA_SIZE = 10000
MAX_WARNINGS_DEFAULT = 3

class ExamAttempt(db.Model):
    __tablename__ = 'exam_attempts'
    
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('exams.id', ondelete='CASCADE'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    is_completed = db.Column(db.Boolean, default=False)
    is_graded = db.Column(db.Boolean, default=False)
    score = db.Column(db.DECIMAL(5,2), nullable=True)
    
    # Security Monitoring
    browser_fingerprint = db.Column(db.String(255), nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    screen_resolution = db.Column(db.String(20), nullable=True)
    window_switches = db.Column(db.Integer, default=0)
    focus_losses = db.Column(db.Integer, default=0)
    warning_count = db.Column(db.Integer, default=0)
    last_check_time = db.Column(db.DateTime, nullable=True)
    submitted_at = db.Column(db.DateTime, nullable=True)
    environment_verified = db.Column(db.Boolean, default=False)
    submission_ip = db.Column(db.String(45), nullable=True)
    submission_location = db.Column(db.String(100), nullable=True)
    time_zone = db.Column(db.String(50), nullable=True)
    
    # Browser State
    is_fullscreen = db.Column(db.Boolean, default=False)
    secure_browser_active = db.Column(db.Boolean, default=False)
    webcam_active = db.Column(db.Boolean, default=False)
    screen_share_active = db.Column(db.Boolean, default=False)
    
    # Event Logs with size limits and structure validation
    security_events = db.Column(db.JSON, nullable=True)
    browser_events = db.Column(db.JSON, nullable=True)
    warning_events = db.Column(db.JSON, nullable=True)
    verification_status = db.Column(db.Enum(*verification_status_enum, name='verification_status_enum'), 
                                  default=VerificationStatus.PENDING.value)
    server_side_checks = db.Column(db.JSON, nullable=True)
    
    # Version control for answers
    answer_version = db.Column(db.Integer, default=1, nullable=False)
    last_sync_time = db.Column(db.DateTime, nullable=True)
    client_timestamp = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    answers = db.relationship('Answer', backref='attempt', lazy='joined', 
                            cascade='all, delete-orphan')
    
    # Add indexes for common queries
    __table_args__ = (
        db.Index('idx_exam_time', 'exam_id', 'started_at'),
        db.Index('idx_student_grading', 'student_id', 'is_graded'),
        db.Index('idx_verification', 'verification_status'),
        db.Index('idx_security', 'warning_count'),
        db.Index('idx_attempt_completion', 'is_completed', 'completed_at'),
        db.UniqueConstraint('exam_id', 'student_id', 'answer_version', name='uq_attempt_version')
    )
    
    def calculate_score(self):
        """Calculate the total score for this attempt"""
        # Move business logic to a service layer
        from app.services.scoring import calculate_attempt_score
        return calculate_attempt_score(self)
    
    @property
    def needs_grading(self):
        """Check if this attempt has any non-MCQ questions that need grading"""
        try:
            # Efficient query that doesn't load objects into memory
            return db.session.query(Answer).join(Question).filter(
                Answer.attempt_id == self.id,
                Question.question_type != QuestionType.MCQ.value,
                Answer.is_correct.is_(None)
            ).limit(1).count() > 0
        except SQLAlchemyError as e:
            logger.error(f"Error checking if attempt needs grading: {str(e)}")
            return False
    
    def validate_submission(self, submission_time, client_time=None):
        """
        Validate a submission attempt with comprehensive checks
        Returns (is_valid, message)
        """
        if self.is_completed:
            return False, "Attempt already completed"
            
        now = datetime.utcnow()
        
        # Check exam availability window
        if self.exam.available_until and now > self.exam.available_until:
            # Allow submission even after window expiry, but log it
            pass
            
        # Validate time limit
        time_limit = self.started_at + timedelta(minutes=self.exam.time_limit_minutes)
        grace_period = timedelta(minutes=2)  # 2 minute grace period
        
        if submission_time > (time_limit + grace_period):
            return False, "Time limit exceeded"
            
        # Check for suspicious time differences
        if client_time:
            time_diff = abs((client_time - now).total_seconds())
            if time_diff > 300:  # 5 minutes
                return False, "Client time significantly differs from server time"
                
        # Validate security requirements
        if self.exam.require_lockdown and not self.secure_browser_active:
            return False, "Secure browser requirement not met"
            
        if self.exam.require_webcam and not self.webcam_active:
            return False, "Webcam requirement not met"
            
        max_warnings = getattr(self.exam, 'max_warnings', MAX_WARNINGS_DEFAULT)
        if self.warning_count > max_warnings:
            return False, "Maximum warning count exceeded"
            
        return True, "Submission validated"
    
    def log_event(self, event_type, data, severity='info'):
        """Log a security or browser event with proper validation"""
        try:
            # Sanitize and validate input
            if isinstance(data, dict):
                data_str = json.dumps(data)
            else:
                data_str = str(data)
                
            if len(data_str) > MAX_EVENT_DATA_SIZE:
                data = {'error': 'Event data too large', 'truncated': True}
                
            timestamp = datetime.utcnow()
            event = {
                'type': event_type,
                'timestamp': timestamp.isoformat(),
                'data': data,
                'severity': severity
            }
            
            # Handle different event types
            if event_type.startswith('security_'):
                self.security_events = self.security_events or []
                self.security_events.append(event)
            elif event_type.startswith('browser_'):
                self.browser_events = self.browser_events or []
                self.browser_events.append(event)
            elif event_type.startswith('warning_'):
                self.warning_events = self.warning_events or []
                self.warning_events.append(event)
                self.warning_count += 1
                
                # Auto-flag if too many events
                max_warnings = getattr(self.exam, 'max_warnings', MAX_WARNINGS_DEFAULT)
                if self.warning_count >= max_warnings:
                    self.verification_status = VerificationStatus.AUTO_FLAGGED.value
                    
            db.session.add(self)
            
            # Log to security logs for audit purposes
            if event_type.startswith('security_') or severity in ('warning', 'error'):
                security_log = SecurityLog(
                    event_type=event_type,
                    description=f"Event logged for exam attempt {self.id}",
                    user_id=self.student_id,
                    severity=severity,
                    details={'event': event}
                )
                db.session.add(security_log)
            
            db.session.commit()
            return True
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error logging event: {str(e)}")
            return False
    
    def __repr__(self):
        return f'<ExamAttempt {self.id} by Student {self.student_id}>'


class Answer(db.Model):
    __tablename__ = 'answers'
    
    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey('exam_attempts.id', ondelete='CASCADE'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id', ondelete='CASCADE'), nullable=False)
    selected_option_id = db.Column(db.Integer, db.ForeignKey('question_options.id', ondelete='SET NULL'), nullable=True)
    text_answer = db.Column(db.Text, nullable=True)
    code_answer = db.Column(db.Text, nullable=True)
    is_correct = db.Column(db.Boolean, nullable=True)
    teacher_feedback = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Version control
    version = db.Column(db.Integer, default=1, nullable=False)
    
    # Relationship to the selected option (if MCQ)
    selected_option = db.relationship('QuestionOption')
    
    # Add indexes for common queries
    __table_args__ = (
        db.Index('idx_answer_attempt', 'attempt_id'),
        db.Index('idx_answer_question', 'question_id'),
        db.UniqueConstraint('attempt_id', 'question_id', name='uq_answer_question')
    )
    
    def sanitize_input(self):
        """Sanitize user input to prevent XSS and injection attacks"""
        import bleach
        
        if self.text_answer:
            self.text_answer = bleach.clean(
                self.text_answer,
                tags=['p', 'b', 'i', 'u', 'ul', 'ol', 'li', 'br'],
                attributes={},
                strip=True
            )
            
        if self.code_answer:
            # Allow code syntax but remove script tags or other dangerous content
            self.code_answer = bleach.clean(
                self.code_answer,
                tags=['pre', 'code', 'span'],
                attributes={'span': ['class']},
                strip=True
            )
    
    def __repr__(self):
        return f'<Answer {self.id} for Question {self.question_id}>'


class ExamReview(db.Model):
    __tablename__ = 'exam_reviews'
    
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('exams.id', ondelete='CASCADE'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    feedback = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Add validation constraint
    __table_args__ = (
        db.CheckConstraint('rating >= 1 AND rating <= 5', name='chk_rating_range'),
        db.UniqueConstraint('exam_id', 'student_id', name='uq_exam_review')
    )
    
    def __repr__(self):
        return f'<ExamReview {self.id} for Exam {self.exam_id}>'


class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    related_id = db.Column(db.Integer, nullable=True)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Add index for common queries
    __table_args__ = (
        db.Index('idx_notification_user', 'user_id', 'is_read'),
    )
    
    def __repr__(self):
        return f'<Notification {self.id} for User {self.user_id}>'


class SecurityLog(db.Model):
    """
    Table for tracking security-related events in the system
    Used for auditing, forensics, and detecting potential threats
    """
    __tablename__ = 'security_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    ip_address = db.Column(db.String(50), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    path = db.Column(db.String(255), nullable=True)
    method = db.Column(db.String(10), nullable=True)
    severity = db.Column(db.String(10), nullable=False, default='medium')
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    details = db.Column(db.JSON, nullable=True)
    
    # Add indexes for security analysis
    __table_args__ = (
        db.Index('idx_security_log_type', 'event_type', 'severity'),
        db.Index('idx_security_log_user', 'user_id'),
        db.Index('idx_security_log_ip', 'ip_address'),
        db.Index('idx_security_log_time', 'timestamp'),
    )

    def __repr__(self):
        return f'<SecurityLog {self.id}: {self.event_type}>'


class Group(db.Model):
    """Model for managing class/course groups (Google Classroom style)"""
    __tablename__ = 'groups'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    subject = db.Column(db.String(50))
    section = db.Column(db.String(20))
    room = db.Column(db.String(20))
    code = db.Column(db.String(6), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    archived = db.Column(db.Boolean, default=False)
    
    # Relationships
    students = db.relationship('User', secondary='group_membership', 
                             back_populates='joined_groups', lazy='dynamic')
    teacher = db.relationship('User', back_populates='owned_groups', 
                            foreign_keys=[teacher_id])
    exams = db.relationship('Exam', back_populates='group', lazy='dynamic', 
                          foreign_keys='Exam.group_id')
    
    # Add indexes for common queries
    __table_args__ = (
        db.Index('idx_group_teacher', 'teacher_id'),
        db.Index('idx_group_code', 'code'),
        db.Index('idx_group_archived', 'archived'),
    )
    
    def generate_code(self):
        """Generate a unique joining code"""
        import random
        import string
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            existing = Group.query.filter_by(code=code).first()
            if not existing:
                return code
    
    def get_active_exams(self):
        """Get all published exams for this class that are currently active"""
        now = datetime.utcnow()
        return self.exams.filter(
            Exam.is_published == True,
            (Exam.available_from <= now) | (Exam.available_from == None),
            (Exam.available_until >= now) | (Exam.available_until == None)
        ).all()
    
    def get_upcoming_exams(self):
        """Get all published exams that aren't active yet"""
        now = datetime.utcnow()
        return self.exams.filter(
            Exam.is_published == True,
            Exam.available_from > now
        ).all()
    
    def get_past_exams(self):
        """Get all completed exams"""
        now = datetime.utcnow()
        return self.exams.filter(
            Exam.is_published == True,
            Exam.available_until < now
        ).all()
    
    def __repr__(self):
        return f'<Group {self.name}>'


class GroupMembership(db.Model):
    """Model for managing group memberships"""
    __tablename__ = 'group_membership'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id', ondelete='CASCADE'), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Add unique constraint to prevent duplicate memberships
    __table_args__ = (
        db.UniqueConstraint('user_id', 'group_id'),
        db.Index('idx_membership_user', 'user_id'),
        db.Index('idx_membership_group', 'group_id'),
    )
    
    def __repr__(self):
        return f'<GroupMembership User:{self.user_id} Group:{self.group_id}>'


class ActivityLog(db.Model):
    """Model for tracking all user activities"""
    __tablename__ = 'activity_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    action = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    details = db.Column(db.JSON, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Add indexes for activity analysis
    __table_args__ = (
        db.Index('idx_activity_user', 'user_id'),
        db.Index('idx_activity_category', 'category'),
        db.Index('idx_activity_time', 'created_at'),
        db.Index('idx_activity_action', 'action'),
    )

    @classmethod
    def log_activity(cls, user_id, action, category, details=None, ip_address=None, user_agent=None):
        """Create and save a new activity log entry with transaction handling"""
        log = cls(
            user_id=user_id,
            action=action,
            category=category,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        try:
            db.session.add(log)
            db.session.commit()
            return log
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Error logging activity: {str(e)}")
            return None
    
    def __repr__(self):
        return f'<ActivityLog {self.id}: {self.category}.{self.action}>'


@login_manager.user_loader
def load_user(user_id):
    """Load a user from the database based on their ID"""
    try:
        return User.query.get(int(user_id))
    except (ValueError, SQLAlchemyError) as e:
        logger.error(f"Error loading user {user_id}: {str(e)}")
        return None
