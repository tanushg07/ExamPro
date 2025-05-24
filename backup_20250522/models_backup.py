from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, login_manager

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    user_type = db.Column(db.String(20), nullable=False)  # admin/teacher/student
    created_at = db.Column(db.DateTime, default=datetime.utcnow)    # Relationships
    exams_created = db.relationship('Exam', foreign_keys='Exam.creator_id', lazy='dynamic')
    exam_attempts = db.relationship('ExamAttempt', backref='student', lazy='dynamic')
    exam_reviews = db.relationship('ExamReview', foreign_keys='ExamReview.student_id', backref=db.backref('reviewer', lazy='joined'), lazy='dynamic')
    notifications = db.relationship('Notification', foreign_keys='Notification.user_id', backref=db.backref('notification_user', lazy='joined'), lazy='dynamic')    security_logs = db.relationship('SecurityLog', backref='user', lazy='dynamic')
    owned_groups = db.relationship('Group', foreign_keys='Group.teacher_id', lazy='dynamic')
    joined_groups = db.relationship('Group', secondary='group_membership', lazy='dynamic')
    
    def set_password(self, password):
        # Using PBKDF2-SHA256 as specified
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def is_teacher(self):
        return self.user_type == 'teacher'
    
    def is_student(self):
        return self.user_type == 'student'
    
    def is_admin(self):
        return self.user_type == 'admin'


class Exam(db.Model):
    __tablename__ = 'exams'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    time_limit_minutes = db.Column(db.Integer, nullable=False)
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'))  # Optional group association
    is_published = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Security settings
    require_lockdown = db.Column(db.Boolean, default=True)  # Require secure browser
    allow_calculator = db.Column(db.Boolean, default=False)
    allow_scratch_pad = db.Column(db.Boolean, default=True)
    randomize_questions = db.Column(db.Boolean, default=True)
    one_question_at_time = db.Column(db.Boolean, default=False)
    prevent_copy_paste = db.Column(db.Boolean, default=True)
    require_webcam = db.Column(db.Boolean, default=False)
    allow_backward_navigation = db.Column(db.Boolean, default=True)
    show_remaining_time = db.Column(db.Boolean, default=True)
    auto_submit = db.Column(db.Boolean, default=True)
    
    # Enhanced security settings
    require_face_verification = db.Column(db.Boolean, default=False)  # Verify student face before exam
    proctor_monitoring = db.Column(db.Boolean, default=False)  # Enable live proctoring
    monitor_screen_share = db.Column(db.Boolean, default=False)  # Require screen sharing
    periodic_checks = db.Column(db.Integer, default=0)  # Number of minutes between checks (0 = disabled)
    detect_browser_exit = db.Column(db.Boolean, default=True)  # Track if browser is closed/switched
    max_warnings = db.Column(db.Integer, default=3)  # Max number of warnings before auto-submit
    block_virtual_machines = db.Column(db.Boolean, default=True)  # Block access from VMs
    browser_fullscreen = db.Column(db.Boolean, default=True)  # Require fullscreen mode
    restrict_keyboard = db.Column(db.Boolean, default=True)  # Block keyboard shortcuts
    block_external_displays = db.Column(db.Boolean, default=True)  # Block external monitors
      # Access settings
    access_code = db.Column(db.String(10), nullable=True)
    allowed_ip_range = db.Column(db.String(100), nullable=True)  # Allowed IP range
    available_from = db.Column(db.DateTime, nullable=True)
    available_until = db.Column(db.DateTime, nullable=True)
    max_attempts = db.Column(db.Integer, default=1)
    
    # Proctor settings
    proctor_instructions = db.Column(db.Text, nullable=True)  # Instructions for proctors
    proctor_notes = db.Column(db.Text, nullable=True)  # Notes visible only to proctors
    max_students_per_proctor = db.Column(db.Integer, default=20)  # Max students per proctor
    proctor_join_before = db.Column(db.Integer, default=15)  # Minutes before exam starts
    
    # Relationships
    questions = db.relationship('Question', backref='exam', lazy='dynamic', cascade='all, delete-orphan')
    attempts = db.relationship('ExamAttempt', backref='exam', lazy='dynamic', cascade='all, delete-orphan')
    reviews = db.relationship('ExamReview', backref='exam', lazy='dynamic')
    creator = db.relationship('User', backref='created_exams', foreign_keys=[creator_id])
    group = db.relationship('Group', backref=db.backref('exams', lazy='dynamic'), foreign_keys=[group_id])
    
    def get_average_rating(self):
        """Calculate the average rating for this exam based on student reviews"""
        reviews = self.reviews.all()
        if not reviews:
            return None
        
        total = sum(review.rating for review in reviews)
        return round(total / len(reviews), 1)


class Question(db.Model):
    __tablename__ = 'questions'
    
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('exams.id'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    question_type = db.Column(db.String(20), nullable=False)  # mcq/code/text
    points = db.Column(db.Integer, nullable=False, default=1)
    order = db.Column(db.Integer, nullable=False, default=0)
    
    # Relationships
    options = db.relationship('QuestionOption', backref='question', lazy='dynamic', cascade='all, delete-orphan')
    answers = db.relationship('Answer', backref='question', lazy='dynamic')


class QuestionOption(db.Model):
    __tablename__ = 'question_options'
    
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    option_text = db.Column(db.Text, nullable=False)
    is_correct = db.Column(db.Boolean, default=False)
    order = db.Column(db.Integer, nullable=False, default=0)


class ExamAttempt(db.Model):
    __tablename__ = 'exam_attempts'
    
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('exams.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
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
    environment_verified = db.Column(db.Boolean, default=False)
    
    # Browser State
    is_fullscreen = db.Column(db.Boolean, default=False)
    secure_browser_active = db.Column(db.Boolean, default=False)
    webcam_active = db.Column(db.Boolean, default=False)
    screen_share_active = db.Column(db.Boolean, default=False)
    
    # Event Logs 
    security_events = db.Column(db.JSON, nullable=True)
    browser_events = db.Column(db.JSON, nullable=True)
    warning_events = db.Column(db.JSON, nullable=True)
    verification_status = db.Column(db.Enum('pending', 'approved', 'flagged', name='verification_status_enum'), default='pending')

    # Relationships
    answers = db.relationship('Answer', backref='attempt', lazy='dynamic', cascade='all, delete-orphan')
    
    def calculate_score(self):
        """Calculate the total score for this attempt"""
        total_points = db.session.query(db.func.sum(Question.points)).filter(Question.exam_id == self.exam_id).scalar() or 0
        earned_points = 0
        
        for answer in self.answers:
            if answer.is_correct:
                earned_points += answer.question.points
        
        return {
            'earned': earned_points,
            'total': total_points,
            'percentage': (earned_points / total_points * 100) if total_points > 0 else 0
        }
    
    @property
    def needs_grading(self):
        """Check if this attempt has any non-MCQ questions that need grading"""
        # Get all answers for non-MCQ questions
        non_mcq_answers = [answer for answer in self.answers if answer.question.question_type != 'mcq']
        
        # If there are non-MCQ answers and not all of them have been graded
        return len(non_mcq_answers) > 0 and any(answer.is_correct is None for answer in non_mcq_answers)


class Answer(db.Model):
    __tablename__ = 'answers'
    
    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey('exam_attempts.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    selected_option_id = db.Column(db.Integer, db.ForeignKey('question_options.id'), nullable=True)
    text_answer = db.Column(db.Text, nullable=True)
    code_answer = db.Column(db.Text, nullable=True)  # New field for code answers
    is_correct = db.Column(db.Boolean, nullable=True)  # For MCQs, auto-graded. For code/text, needs teacher grading
    teacher_feedback = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship to the selected option (if MCQ)
    selected_option = db.relationship('QuestionOption')


class ExamReview(db.Model):
    __tablename__ = 'exam_reviews'
    
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('exams.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1-5 stars
    feedback = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    # Both relationships are managed by their respective parent classes
    # student relationship is managed by the User class


class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(50), nullable=False)  # 'info', 'exam_graded', 'exam_created', etc.
    related_id = db.Column(db.Integer, nullable=True)  # Optional ID of related entity (exam, attempt)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship is managed by User class


class SecurityLog(db.Model):
    """
    Table for tracking security-related events in the system
    Used for auditing, forensics, and detecting potential threats
    """
    __tablename__ = 'security_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(50), nullable=False)  # LOGIN_FAIL, ACCESS_VIOLATION, etc.
    description = db.Column(db.String(255), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # May be anonymous
    ip_address = db.Column(db.String(50), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    path = db.Column(db.String(255), nullable=True)
    method = db.Column(db.String(10), nullable=True)  # HTTP method
    severity = db.Column(db.String(10), nullable=False, default='medium')  # low, medium, high
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship is already defined in the User model

    def __repr__(self):
        return f'<SecurityLog {self.id}: {self.event_type}>'


class Group(db.Model):
    """Model for managing class/course groups (Google Classroom style)"""
    __tablename__ = 'groups'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    subject = db.Column(db.String(50))  # Subject area
    section = db.Column(db.String(20))  # Class section/period
    room = db.Column(db.String(20))  # Physical or virtual room
    code = db.Column(db.String(6), unique=True, nullable=False)  # Joining code for students
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    archived = db.Column(db.Boolean, default=False)  # For archiving old classes
    
    # Link to User model through GroupMembership for students
    students = db.relationship('User', 
                           secondary='group_membership',
                           backref=db.backref('enrolled_groups', lazy='dynamic'),
                           lazy='dynamic')
      # Direct link to teacher
    teacher = db.relationship('User', backref=db.backref('owned_classes', lazy='dynamic'), foreign_keys=[teacher_id])
    
    # Link to exams
    exams = db.relationship('Exam', backref='class_group', lazy='dynamic')
    
    def generate_code(self):
        """Generate a unique joining code"""
        import random
        import string
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            if not Group.query.filter_by(code=code).first():
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


class GroupMembership(db.Model):
    """Model for managing group memberships"""
    __tablename__ = 'group_membership'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Add unique constraint to prevent duplicate memberships
    __table_args__ = (db.UniqueConstraint('user_id', 'group_id'),)