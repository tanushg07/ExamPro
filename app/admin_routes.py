from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, current_app
from flask_login import login_required, current_user
from sqlalchemy.exc import SQLAlchemyError
from .decorators import admin_required
from .models import (
    db, User, Exam, ExamAttempt, Question, QuestionOption, 
    Answer, ExamReview, ActivityLog
)
from .forms import UserEditForm, CreateUserForm, ExamForm
from werkzeug.security import generate_password_hash
import json
from datetime import datetime

# Create blueprint
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/activity-logs')
@login_required
@admin_required
def activity_logs():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    # Filter parameters
    user_id = request.args.get('user_id', type=int)
    category = request.args.get('category')
    action = request.args.get('action')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # Base query
    query = ActivityLog.query.join(User).order_by(ActivityLog.created_at.desc())
    
    # Apply filters
    if user_id:
        query = query.filter(ActivityLog.user_id == user_id)
    if category:
        query = query.filter(ActivityLog.category == category)
    if action:
        query = query.filter(ActivityLog.action == action)
    if start_date:
        query = query.filter(ActivityLog.created_at >= start_date)
    if end_date:
        query = query.filter(ActivityLog.created_at <= end_date)
    
    # Pagination
    logs = query.paginate(page=page, per_page=per_page)
    
    # Get unique categories and actions for filter dropdowns
    categories = db.session.query(ActivityLog.category).distinct().all()
    actions = db.session.query(ActivityLog.action).distinct().all()
    users = User.query.order_by(User.username).all()
    
    return render_template(
        'admin/activity_logs.html',
        logs=logs,
        categories=categories,
        actions=actions,
        users=users
    )


@admin_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    form = UserEditForm(obj=user)
    
    if form.validate_on_submit():
        if user.user_type == 'admin' and not current_user.id == user.id:
            flash('Cannot modify another admin user.', 'danger')
            return redirect(url_for('main.admin_dashboard'))
        
        try:
            user.username = form.username.data
            user.email = form.email.data
            user.user_type = form.user_type.data
            db.session.commit()
            flash('User updated successfully!', 'success')
            return redirect(url_for('main.admin_dashboard'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash('Error updating user.', 'danger')
    
    return render_template('admin/edit_user.html', form=form, user=user)

@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    
    if user.user_type == 'admin':
        flash('Cannot delete admin users.', 'danger')
        return redirect(url_for('main.admin_dashboard'))
    
    if user.id == current_user.id:
        flash('Cannot delete your own account.', 'danger')
        return redirect(url_for('main.admin_dashboard'))
    
    try:
        # Delete related records first
        ExamAttempt.query.filter_by(student_id=user.id).delete()
        Exam.query.filter_by(creator_id=user.id).delete()
        db.session.delete(user)
        db.session.commit()
        flash('User deleted successfully!', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        flash('Error deleting user.', 'danger')
    
    return redirect(url_for('main.admin_dashboard'))

@admin_bp.route('/exams/<int:exam_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_exam(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    try:
        exam_details = {
            'exam_id': exam.id,
            'title': exam.title,
            'creator_id': exam.creator_id,
            'is_published': exam.is_published,
            'group_id': exam.group_id
        }
        
        # Delete in correct order to handle foreign key constraints
        # 1. Delete answers from exam attempts
        for attempt in ExamAttempt.query.filter_by(exam_id=exam.id).all():
            db.session.query(Answer).filter_by(attempt_id=attempt.id).delete()
        
        # 2. Delete exam attempts
        attempts_count = ExamAttempt.query.filter_by(exam_id=exam.id).delete()
        
        # 3. Delete exam reviews
        reviews_count = db.session.query(ExamReview).filter_by(exam_id=exam.id).delete()
        
        # 4. Delete question options and questions
        questions_count = 0
        for question in Question.query.filter_by(exam_id=exam.id).all():
            questions_count += 1
            db.session.query(QuestionOption).filter_by(question_id=question.id).delete()
        Question.query.filter_by(exam_id=exam.id).delete()
        
        # 5. Finally delete the exam
        db.session.delete(exam)
        db.session.commit()
        
        # Log exam deletion
        ActivityLog.log_activity(
            user_id=current_user.id,
            action="delete_exam",
            category="exam",
            details={
                **exam_details,
                'deleted_items': {
                    'attempts': attempts_count,
                    'reviews': reviews_count,
                    'questions': questions_count
                }
            },
            ip_address=request.remote_addr,
            user_agent=str(request.user_agent)
        )
        
        flash('Exam deleted successfully!', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        flash('Error deleting exam: ' + str(e), 'danger')
    
    return redirect(url_for('main.admin_dashboard'))

@admin_bp.route('/exams/<int:exam_id>/toggle-publish', methods=['POST'])
@login_required
@admin_required
def toggle_exam_publish(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    
    try:
        exam.is_published = not exam.is_published
        db.session.commit()
        status = 'published' if exam.is_published else 'unpublished'
        flash(f'Exam {status} successfully!', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        flash('Error updating exam status.', 'danger')
    
    return redirect(url_for('main.admin_dashboard'))

@admin_bp.route('/users/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_user():
    form = CreateUserForm()
    if form.validate_on_submit():
        try:
            # Check if username or email already exists
            if User.query.filter_by(username=form.username.data).first():
                flash('Username already exists.', 'danger')
                return render_template('admin/create_user.html', form=form)
            
            if User.query.filter_by(email=form.email.data).first():
                flash('Email already exists.', 'danger')
                return render_template('admin/create_user.html', form=form)
            
            user = User(
                username=form.username.data,
                email=form.email.data,
                user_type=form.user_type.data,
                password_hash=generate_password_hash(form.password.data)
            )
            db.session.add(user)
            db.session.commit()
            flash('User created successfully!', 'success')
            return redirect(url_for('main.admin_dashboard'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash('Error creating user.', 'danger')
    
    return render_template('admin/create_user.html', form=form)

@admin_bp.route('/exams/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_exam():
    form = ExamForm()
    if form.validate_on_submit():
        try:
            exam = Exam(
                title=form.title.data,
                description=form.description.data,
                time_limit_minutes=form.time_limit_minutes.data,
                creator_id=current_user.id,
                is_published=form.is_published.data
            )
            db.session.add(exam)
            db.session.commit()
            flash('Exam created successfully!', 'success')
            return redirect(url_for('main.admin_dashboard'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash('Error creating exam.', 'danger')
    
    return render_template('admin/create_exam.html', form=form)

@admin_bp.route('/backup', methods=['POST'])
@login_required
@admin_required
def backup_data():
    try:
        # Get selected backup options
        backup_users = 'backup_users' in request.form
        backup_exams = 'backup_exams' in request.form
        backup_attempts = 'backup_attempts' in request.form
        
        # Create backup timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_data = {}
        
        if backup_users:
            users = User.query.all()
            backup_data['users'] = [
                {
                    'username': user.username,
                    'email': user.email,
                    'user_type': user.user_type,
                    'created_at': user.created_at.isoformat()
                } for user in users
            ]
        
        if backup_exams:
            exams = Exam.query.all()
            backup_data['exams'] = [
                {
                    'title': exam.title,
                    'description': exam.description,
                    'time_limit_minutes': exam.time_limit_minutes,
                    'is_published': exam.is_published,
                    'created_at': exam.created_at.isoformat()
                } for exam in exams
            ]
        
        if backup_attempts:
            attempts = ExamAttempt.query.all()
            backup_data['attempts'] = [
                {
                    'student_id': attempt.student_id,
                    'exam_id': attempt.exam_id,
                    'started_at': attempt.started_at.isoformat() if attempt.started_at else None,
                    'completed_at': attempt.completed_at.isoformat() if attempt.completed_at else None,
                    'score': attempt.score
                } for attempt in attempts
            ]
        
        # Create JSON file
        backup_file = f'backup_{timestamp}.json'
        with open(backup_file, 'w') as f:
            json.dump(backup_data, f, indent=4)
        
        flash('Backup created successfully!', 'success')
        return redirect(url_for('main.admin_dashboard'))
        
    except Exception as e:
        flash('Error creating backup: ' + str(e), 'danger')
        return redirect(url_for('main.admin_dashboard'))

@admin_bp.route('/system-logs')
@login_required
@admin_required
def system_logs():
    # Get system logs (example implementation)
    logs = [
        {'timestamp': datetime.now(), 'level': 'INFO', 'message': 'System started successfully'},
        {'timestamp': datetime.now(), 'level': 'WARNING', 'message': 'High CPU usage detected'},
        # Add more logs as needed
    ]
    return render_template('admin/system_logs.html', logs=logs)

@admin_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@admin_required
def system_settings():
    if request.method == 'POST':
        try:            # Update system settings
            current_app.config['MAIL_SERVER'] = request.form.get('mail_server')
            current_app.config['MAIL_PORT'] = int(request.form.get('mail_port'))
            # Add more settings as needed
            
            flash('Settings updated successfully!', 'success')
        except Exception as e:
            flash('Error updating settings: ' + str(e), 'danger')
    
    return render_template('admin/settings.html')

@admin_bp.route('/send-mass-email', methods=['POST'])
@login_required
@admin_required
def send_mass_email():
    try:
        recipient_group = request.form.get('recipient_group')
        subject = request.form.get('subject')
        content = request.form.get('content')
        
        # Get recipients based on selected group
        if recipient_group == 'all':
            recipients = User.query.all()
        elif recipient_group == 'teachers':
            recipients = User.query.filter_by(user_type='teacher').all()
        else:  # students
            recipients = User.query.filter_by(user_type='student').all()
        
        # Send emails (implement actual email sending logic)
        for recipient in recipients:
            # Add to email queue or send directly
            pass
        
        flash(f'Email sent to {len(recipients)} recipients!', 'success')
    except Exception as e:
        flash('Error sending email: ' + str(e), 'danger')
    
    return redirect(url_for('main.admin_dashboard'))
