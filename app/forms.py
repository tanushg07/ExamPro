from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import (
    StringField, PasswordField, BooleanField, SubmitField,
    TextAreaField, IntegerField, SelectField, RadioField,
    DateTimeField, FieldList, FormField
)
from wtforms.validators import (
    DataRequired, Email, Length, EqualTo, Optional,
    ValidationError, NumberRange
)
from datetime import datetime

from app.models import User

class UserEditForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=64)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    user_type = SelectField('User Type', choices=[('student', 'Student'), ('teacher', 'Teacher'), ('admin', 'Admin')], validators=[DataRequired()])
    submit = SubmitField('Save Changes')

class CreateUserForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=64)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=6),
        EqualTo('password_confirm', message='Passwords must match')
    ])
    password_confirm = PasswordField('Confirm Password', validators=[DataRequired()])
    user_type = SelectField('User Type', choices=[('student', 'Student'), ('teacher', 'Teacher'), ('admin', 'Admin')], validators=[DataRequired()])
    submit = SubmitField('Create User')

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Log In')


class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[
        DataRequired(),
        Length(min=4, max=64, message='Username must be between 4 and 64 characters')
    ])
    email = StringField('Email', validators=[
        DataRequired(),
        Email(),
        Length(max=120)
    ])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=8, message='Password must be at least 8 characters')
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])
    user_type = SelectField('Register as', choices=[('teacher', 'Teacher'), ('admin', 'Admin')], validators=[DataRequired()])
    submit = SubmitField('Register')
    
    # Custom validators
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username is already taken.')
    
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email address is already registered.')


class ExamForm(FlaskForm):
    # Basic settings
    title = StringField('Exam Title', validators=[
        DataRequired(),
        Length(min=5, max=255)
    ])
    description = TextAreaField('Description')
    group_id = SelectField('Class', coerce=int, validators=[DataRequired(message="Please select a class")])  # Make class selection required
    time_limit_minutes = IntegerField('Time Limit (minutes)', validators=[
        DataRequired(),
        NumberRange(min=5, max=300, message='Time limit must be between 5 and 300 minutes')
    ])
    
    # Basic Security settings
    require_lockdown = BooleanField('Require Secure Browser Mode', default=True,
        description='Force students to use the secure browser mode')
    allow_calculator = BooleanField('Allow Calculator', default=False,
        description='Enable built-in calculator tool')
    allow_scratch_pad = BooleanField('Allow Scratch Pad', default=True,
        description='Enable digital scratch pad for notes')
    randomize_questions = BooleanField('Randomize Questions', default=True,
        description='Present questions in random order to each student')
    one_question_at_time = BooleanField('One Question at a Time', default=False,
        description='Display questions one at a time')
    prevent_copy_paste = BooleanField('Prevent Copy/Paste', default=True,
        description='Disable copy/paste functionality')
    
    # Enhanced Security settings
    require_webcam = BooleanField('Require Webcam', default=False,
        description='Enable webcam monitoring during exam')
    require_face_verification = BooleanField('Face Verification', default=False,
        description='Verify student identity before exam using facial recognition')
    proctor_monitoring = BooleanField('Live Proctoring', default=False,
        description='Enable live proctoring by teachers/proctors')
    monitor_screen_share = BooleanField('Screen Monitoring', default=False,
        description='Capture periodic screenshots or require screen sharing')
    periodic_checks = IntegerField('Periodic Checks (minutes)', default=0,
        validators=[NumberRange(min=0, max=30)],
        description='Take webcam/screen snapshots every X minutes (0 to disable)')
    
    # Environment Security
    detect_browser_exit = BooleanField('Detect Browser Exit', default=True,
        description='Track if student switches/closes browser')
    max_warnings = IntegerField('Maximum Warnings', default=3,
        validators=[NumberRange(min=1, max=10)],
        description='Number of warnings before automatic submission')
    block_virtual_machines = BooleanField('Block Virtual Machines', default=True,
        description='Prevent access from virtual machines')
    browser_fullscreen = BooleanField('Require Fullscreen', default=True,
        description='Force browser to stay in fullscreen mode')
    restrict_keyboard = BooleanField('Restrict Keyboard', default=True, 
        description='Block system keyboard shortcuts')
    block_external_displays = BooleanField('Block External Displays', default=True,
        description='Prevent use of multiple monitors')
    
    # Access Control
    access_code = StringField('Access Code', 
        validators=[Optional(), Length(min=4, max=10)],
        description='Code required to start exam')
    ip_range = StringField('Allowed IP Range', 
        validators=[Optional()],
        description='Restrict access to specific IP range (e.g., 192.168.1.0/24)')
    available_from = DateTimeField('Available From',
        validators=[Optional()],
        format='%Y-%m-%d %H:%M',
        description='When the exam becomes available')
    available_until = DateTimeField('Available Until',
        validators=[Optional()],
        format='%Y-%m-%d %H:%M',
        description='When the exam access expires')
    max_attempts = IntegerField('Maximum Attempts',
        validators=[NumberRange(min=1, max=10)],
        default=1,
        description='Number of attempts allowed per student')
    
    # Proctor Settings
    proctor_instructions = TextAreaField('Proctor Instructions',
        description='Special instructions for proctors monitoring this exam')
    max_students_per_proctor = IntegerField('Students per Proctor',
        validators=[NumberRange(min=1, max=50)],
        default=20,
        description='Maximum number of students per proctor')
    proctor_join_before = IntegerField('Proctor Join Time',
        validators=[NumberRange(min=5, max=60)],
        default=15,
        description='Minutes before exam start that proctors should join')
    
    # Navigation and Display
    allow_backward_navigation = BooleanField('Allow Going Back', default=True,
        description='Allow reviewing previous questions')
    show_remaining_time = BooleanField('Show Time Remaining', default=True,
        description='Display countdown timer to students')
    auto_submit = BooleanField('Auto-submit on Time Up', default=True,
        description='Automatically submit when time expires')
    
    is_published = BooleanField('Publish Immediately')
    submit = SubmitField('Create Exam')

    def validate_time_limit_minutes(self, field):
        """Validate time limit against availability window"""
        if field.data < 5:
            raise ValidationError('Time limit must be at least 5 minutes')
        if field.data > 300:
            raise ValidationError('Time limit cannot exceed 300 minutes')
            
        # If availability window is set, validate time limit fits within it
        if self.available_from.data and self.available_until.data:
            window_minutes = (self.available_until.data - self.available_from.data).total_seconds() / 60
            if field.data > window_minutes:
                raise ValidationError('Time limit cannot exceed availability window')
                
    def validate_available_from(self, field):
        """Validate exam start time"""
        if field.data:
            now = datetime.utcnow()
            if field.data < now:
                raise ValidationError('Start time must be in the future')
                
    def validate_available_until(self, field):
        """Validate exam end time"""
        if field.data and self.available_from.data:
            if field.data <= self.available_from.data:
                raise ValidationError('End time must be after start time')
                
            # Ensure reasonable duration
            duration = (field.data - self.available_from.data).total_seconds() / 3600  # hours
            if duration > 168:  # 1 week
                raise ValidationError('Exam cannot be available for more than 1 week')
                
    def validate_max_attempts(self, field):
        """Validate maximum attempts"""
        if field.data and field.data < 1:
            raise ValidationError('Must allow at least 1 attempt')
            
        if self.group_id.data:
            from app.models import Group
            group = Group.query.get(self.group_id.data)
            if group and field.data > group.students.count() * 2:
                raise ValidationError('Maximum attempts seems unusually high for class size')
  


class MCQOptionForm(FlaskForm):
    option_text = StringField('Option')  # Removed DataRequired to allow empty options
    is_correct = BooleanField('Correct Answer', default=False)
    
    class Meta:
        # Disable CSRF for this subform as it's part of a larger form
        csrf = False


class QuestionForm(FlaskForm):
    question_text = TextAreaField('Question', validators=[
        DataRequired(message="Question text is required"),
        Length(min=1, max=5000, message="Question text must be between 1 and 5000 characters")
    ])
    question_type = SelectField('Question Type', choices=[
        ('mcq', 'Multiple Choice'),
        ('code', 'Programming/Code'),
        ('text', 'Text/Essay')
    ], validators=[DataRequired(message="Please select a question type")])
    points = IntegerField('Points', validators=[
        DataRequired(message="Points value is required"),
        NumberRange(min=1, max=100, message="Points must be between 1 and 100")
    ], default=1)
    options = FieldList(FormField(MCQOptionForm), min_entries=4, max_entries=10)
    submit = SubmitField('Add Question')
    
    def validate(self, extra_validators=None):
        """Custom validation for the question form"""
        # First run parent class validation with any extra validators
        if not FlaskForm.validate(self, extra_validators):
            return False
            
        if self.question_text.data and len(self.question_text.data.strip()) < 10:
            self.question_text.errors.append('Question text must be at least 10 characters long')
            return False
            
        if self.question_type.data == 'mcq':
            # Validate MCQ specific requirements
            valid_options = [opt for opt in self.options if opt.option_text.data and opt.option_text.data.strip()]
            if len(valid_options) < 2:
                self.question_type.errors.append('MCQ questions must have at least 2 non-empty options')
                return False
                
            if not any(opt.is_correct.data for opt in valid_options):
                self.question_type.errors.append('At least one option must be marked as correct')
                return False
                
            # Ensure first two options are filled
            if not (self.options[0].option_text.data and self.options[0].option_text.data.strip() and
                   self.options[1].option_text.data and self.options[1].option_text.data.strip()):
                self.question_type.errors.append('The first two options are required')
                return False
                
        elif self.question_type.data == 'code':
            # Add specific validation for code questions if needed
            if len(self.question_text.data.strip()) < 20:
                self.question_text.errors.append('Code questions should have detailed instructions (at least 20 characters)')
                return False
                
        elif self.question_type.data == 'text':
            # Add specific validation for text questions if needed
            if len(self.question_text.data.strip()) < 15:
                self.question_text.errors.append('Text questions should be clear and detailed (at least 15 characters)')
                return False
                
        return True


class MCQAnswerForm(FlaskForm):
    selected_option = RadioField('Select Answer', coerce=int)


class TextAnswerForm(FlaskForm):
    answer_text = TextAreaField('Your Answer', validators=[DataRequired()])


class CodeAnswerForm(FlaskForm):
    code_answer = TextAreaField('Your Code', validators=[DataRequired()])


class TakeExamForm(FlaskForm):
    """Form for exam submission - mainly for CSRF protection"""
    pass

class GradeAnswerForm(FlaskForm):
    is_correct = BooleanField('Correct')
    points_awarded = IntegerField('Points Awarded', validators=[NumberRange(min=0)])
    feedback = TextAreaField('Feedback')
    submit = SubmitField('Save Grading')


class ExamReviewForm(FlaskForm):
    rating = RadioField('Rating', 
                       choices=[('5', '★★★★★'), ('4', '★★★★'), ('3', '★★★'), ('2', '★★'), ('1', '★')],
                       validators=[DataRequired(message='Please select a rating')])
    feedback = TextAreaField('Your Feedback', 
                           validators=[Length(max=500, message='Feedback must be less than 500 characters')])
    submit = SubmitField('Submit Review')


class ImportQuestionsForm(FlaskForm):
    template_file = FileField('Template File', validators=[
        DataRequired(),
        FileAllowed(['csv'], 'CSV files only!')
    ])
    replace_existing = BooleanField('Replace Existing Questions')
    submit = SubmitField('Import Questions')


class MarkAllReadForm(FlaskForm):
    submit = SubmitField('Mark All Read')

class MarkReadForm(FlaskForm):
    submit = SubmitField('Mark Read')

class PasswordUpdateForm(FlaskForm):
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[
        DataRequired(),
        Length(min=8, message='Password must be at least 8 characters')
    ])
    confirm_password = PasswordField('Confirm New Password', validators=[
        DataRequired(),
        EqualTo('new_password', message='Passwords must match')
    ])
    submit = SubmitField('Update Password')

class CreateGroupForm(FlaskForm):
    """Form for creating a new group"""
    name = StringField('Class Name', validators=[
        DataRequired(),
        Length(min=4, max=100, message='Class name must be between 4 and 100 characters')
    ])
    description = TextAreaField('Description', validators=[
        Length(max=500, message='Description cannot exceed 500 characters')
    ])
    subject = StringField('Subject', validators=[
        Length(max=50, message='Subject cannot exceed 50 characters')
    ])
    section = StringField('Section', validators=[
        Length(max=20, message='Section cannot exceed 20 characters')
    ])
    room = StringField('Room', validators=[
        Length(max=20, message='Room cannot exceed 20 characters')
    ])
    submit = SubmitField('Create Class')

class JoinGroupForm(FlaskForm):
    """Form for joining a group using a code"""
    code = StringField('Class Code', validators=[
        DataRequired(),
        Length(min=6, max=6, message='Class code must be 6 characters'),
        # Custom validator for format can be added here
    ])
    submit = SubmitField('Join Class')

    def validate_code(self, field):
        # Convert to uppercase for consistency
        field.data = field.data.upper()
        # Only allow uppercase letters and numbers
        if not field.data.isalnum():
            raise ValidationError('Class code can only contain letters and numbers')

class AddGroupExamForm(FlaskForm):
    group_id = SelectField('Class', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Add to Class')

    def __init__(self, teacher_id, *args, **kwargs):
        super(AddGroupExamForm, self).__init__(*args, **kwargs)
        from app.models import Group
        # Only show groups where this teacher is the owner
        self.group_id.choices = [
            (g.id, g.name) for g in Group.query.filter_by(teacher_id=teacher_id).all()
        ]