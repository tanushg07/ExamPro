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
