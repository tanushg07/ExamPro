from datetime import datetime, timedelta
import csv
from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, jsonify, abort, session, make_response
)
from flask_login import login_required, current_user
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func, desc
from sqlalchemy.sql import case
from functools import wraps

from app.models import (
    db, User, Exam, Question, QuestionOption, ExamAttempt, 
    Answer, ExamReview, Notification, Group, ActivityLog
)
from app.forms import (
    ExamForm, QuestionForm, MCQAnswerForm, TextAnswerForm,
    CodeAnswerForm, GradeAnswerForm, ExamReviewForm, ImportQuestionsForm,
    MarkAllReadForm, MarkReadForm, TakeExamForm, AddGroupExamForm
)
from app.notifications import notify_exam_graded, notify_new_exam, notify_new_review
from app.decorators import admin_required, teacher_required, student_required

# Create blueprints for organization
main_bp = Blueprint('main', __name__)
teacher_bp = Blueprint('teacher', __name__, url_prefix='/teacher')
student_bp = Blueprint('student', __name__, url_prefix='/student')


# Helper function to check if exam time has expired
def check_time_expired(attempt):
    """Check if the exam time has expired for an attempt."""
    if not attempt or not attempt.started_at or not attempt.exam:
        return True
        
    if not attempt.exam.time_limit_minutes:  # If no duration set, exam doesn't expire
        return False
        
    time_limit = attempt.started_at + timedelta(minutes=attempt.exam.time_limit_minutes)
    return datetime.utcnow() > time_limit

def validate_submission_time(attempt, submission_time):
    """Validate that a submission is being made within the time limit."""
    if not attempt or not attempt.started_at or not attempt.exam:
        return False
        
    if not attempt.exam.time_limit_minutes:  # If no duration set, submission is always valid
        return True
        
    time_limit = attempt.started_at + timedelta(minutes=attempt.exam.time_limit_minutes)
    grace_period = timedelta(minutes=1)  # 1 minute grace period for network delays
    
    return submission_time <= (time_limit + grace_period)

# Submission handler function
def handle_exam_submission(exam, attempt, request_form):
    """Handle exam submission with proper error handling"""
    submission_time = datetime.utcnow()
    
    # Log submission attempt
    ActivityLog.log_activity(
        user_id=current_user.id,
        action="submit_exam",
        category="attempt",
        details={
            'exam_id': exam.id,
            'attempt_id': attempt.id,
            'submission_time': submission_time.isoformat(),
            'client_time': request_form.get('client_time')
        },
        ip_address=request.remote_addr
    )
    
    # Check if exam was already completed (prevent double submission)
    if attempt.is_completed:
        return jsonify({
            'success': False,
            'message': 'This exam has already been submitted.',
            'redirect_url': url_for('student.view_result', attempt_id=attempt.id)
        }), 400
    
    # Validate submission time - allow it even if time expired to prevent data loss
    is_valid_time = validate_submission_time(attempt, submission_time)
    
    if not is_valid_time:
        print(f"Submission time validation failed, but proceeding with submission")
        # We continue with submission even if time expired, but log it
        
    try:
        # Save final answers
        save_answers(request_form, attempt, is_final_submission=True)
        
        # Mark attempt as completed
        attempt.is_completed = True
        attempt.submitted_at = submission_time
        attempt.completed_at = submission_time  # Make sure completed_at is also set
        
        # Ensure we calculate and store the score
        try:
            score_data = attempt.calculate_score()
            attempt.score = score_data['percentage']
            # Only mark as fully graded if all MCQ (automatic grading)
            has_non_mcq = db.session.query(Question).filter(
                Question.exam_id == exam.id,
                Question.question_type != 'mcq'
            ).first() is None
            attempt.is_graded = has_non_mcq
        except Exception as e:
            print(f"Error calculating score during submission: {str(e)}")
        
        # If time was expired, log it specially
        if not is_valid_time:
            ActivityLog.log_activity(
                user_id=current_user.id,
                action="time_expired_submission",
                category="attempt",
                details={
                    'exam_id': exam.id,
                    'attempt_id': attempt.id,
                    'submission_time': submission_time.isoformat()
                },
                ip_address=request.remote_addr
            )
        else:
            # Log successful submission
            ActivityLog.log_activity(
                user_id=current_user.id,
                action="exam_submitted",
                category="attempt",
                details={
                    'exam_id': exam.id,
                    'attempt_id': attempt.id,
                    'submission_time': submission_time.isoformat()
                },
                ip_address=request.remote_addr
            )
        
        db.session.commit()
        
        # Return success response with redirect URL
        return jsonify({
            'success': True,
            'message': 'Exam submitted successfully',
            'redirect_url': url_for('student.view_result', attempt_id=attempt.id)
        })
        
    except SQLAlchemyError as e:
        db.session.rollback()
        error_msg = str(e)
        print(f"Database error during exam submission: {error_msg}")
        # Log the error
        ActivityLog.log_activity(
            user_id=current_user.id,
            action="submission_error",
            category="attempt",
            details={
                'exam_id': exam.id,
                'attempt_id': attempt.id,
                'error': error_msg,
                'type': 'database_error'
            },
            ip_address=request.remote_addr
        )
        return jsonify({
            'success': False,
            'message': "Database error submitting exam. Your answers are saved and you can try submitting again.",
            'error': 'database_error',
            'details': error_msg
        }), 500
    except Exception as e:
        db.session.rollback()
        error_msg = str(e)
        print(f"Unexpected error during exam submission: {error_msg}")
        # Log the error
        ActivityLog.log_activity(
            user_id=current_user.id,
            action="submission_error",
            category="attempt",
            details={
                'exam_id': exam.id,
                'attempt_id': attempt.id,
                'error': error_msg,
                'type': 'unexpected_error'
            },
            ip_address=request.remote_addr
        )
        return jsonify({
            'success': False,
            'message': "Error submitting exam. Your answers are saved and you can try submitting again.",
            'error': 'unexpected_error',
            'details': error_msg
        }), 500


# Improved save_answers function
def save_answers(form_data, attempt, is_final_submission=False):
    """
    Save or update answers for an exam attempt.
    If is_final_submission is True, also update submitted_at timestamp.
    """
    saved_question_ids = set()
    
    # First, find all answer keys (both question_id and answer_X format)
    question_keys = {}
    for key, value in form_data.items():
        if key.startswith('question_id'):
            try:
                question_id = int(value)
                question_keys[question_id] = None
            except (ValueError, TypeError):
                continue
        
        elif key.startswith('answer_'):
            try:
                question_id = int(key.split('_')[1])
                question_keys[question_id] = value
            except (ValueError, TypeError, IndexError):
                continue
    
    # Process all collected questions
    for question_id, value in question_keys.items():
        try:
            question = Question.query.get(question_id)
            if not question or question.exam_id != attempt.exam_id:
                continue
                
            saved_question_ids.add(question_id)
            
            answer = Answer.query.filter_by(
                attempt_id=attempt.id,
                question_id=question_id
            ).first()
            
            if not answer:
                answer = Answer(
                    attempt_id=attempt.id,
                    question_id=question_id
                )
                db.session.add(answer)
            
            if value is None:
                answer_key = f'answer_{question_id}'
                value = form_data.get(answer_key)
                if value is None:
                    continue
            
            if question.question_type == 'mcq':
                try:
                    option_id = int(value)
                    option = QuestionOption.query.filter_by(
                        id=option_id,
                        question_id=question_id
                    ).first()
                    if option:
                        answer.selected_option_id = option_id
                        # Auto-grade MCQ questions
                        answer.is_correct = option.is_correct
                except (ValueError, TypeError):
                    continue
                    
            elif question.question_type in ['text', 'code']:
                answer.text_answer = value
                if question.question_type == 'code':
                    answer.code_answer = value
            
            db.session.flush()
                
        except Exception:
            db.session.rollback()
            continue
    
    return True


@student_bp.route('/exams/<int:exam_id>/submit', methods=['POST'])
@login_required
@student_required
def submit_exam(exam_id):
    """Dedicated route for exam submissions to avoid URL issues"""
    exam = Exam.query.get_or_404(exam_id)
    
    # Verify the student is eligible to take this exam
    if exam.group_id:
        group = Group.query.get(exam.group_id)
        if group and current_user not in group.students:
            return jsonify({
                'success': False,
                'message': 'You are not enrolled in this class.'
            }), 403
    
    # Get the current attempt
    attempt = ExamAttempt.query.filter_by(
        student_id=current_user.id,
        exam_id=exam_id,
        is_completed=False
    ).first()
    
    if not attempt:
        return jsonify({
            'success': False,
            'message': 'No active exam attempt found.'
        }), 404
    
    # Validate CSRF token
    form = TakeExamForm()
    if not form.validate_on_submit():
        ActivityLog.log_activity(
            user_id=current_user.id,
            action="csrf_error",
            category="attempt",
            details={
                'exam_id': exam.id,
                'attempt_id': attempt.id,
            },
            ip_address=request.remote_addr
        )
        return jsonify({
            'success': False,
            'message': 'Invalid form submission. Please refresh the page and try again.',
            'error': 'csrf_error'
        }), 400
    
    # Handle the actual submission
    return handle_exam_submission(exam, attempt, request.form)


@student_bp.route('/exams/<int:exam_id>/take', methods=['GET', 'POST'])
@login_required
@student_required
def take_exam(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    now = datetime.utcnow()
    
    # Log attempt to start exam
    ActivityLog.log_activity(
        user_id=current_user.id,
        action="start_exam",
        category="attempt",
        details={
            'exam_id': exam.id,
            'exam_title': exam.title,
            'creator_id': exam.creator_id,
            'timestamp': now.isoformat()
        },
        ip_address=request.remote_addr,
        user_agent=str(request.user_agent)
    )
    
    # Check if exam is published
    if not exam.is_published:
        flash('This exam is not available for taking.', 'warning')
        return redirect(url_for('main.dashboard'))
        
    # Check if exam is within availability window
    if exam.available_from and now < exam.available_from:
        flash(f'This exam is not available yet. It will be available from {exam.available_from}.', 'warning')
        return redirect(url_for('main.dashboard'))
        
    if exam.available_until and now > exam.available_until:
        flash('This exam is no longer available.', 'danger')
        return redirect(url_for('main.dashboard'))
        
    # Check if the exam is from a group the student is part of
    if exam.group_id:
        group = Group.query.get(exam.group_id)
        if group and current_user not in group.students:
            flash('You need to join the class to access this exam.', 'warning')
            return redirect(url_for('group.join_group'))
    
    # Check if student has already completed this exam
    existing_attempt = ExamAttempt.query.filter_by(
        student_id=current_user.id,
        exam_id=exam_id,
        is_completed=True
    ).first()
    
    if existing_attempt:
        flash('You have already completed this exam.', 'info')
        return redirect(url_for('student.view_result', attempt_id=existing_attempt.id))
    
    # Get or create an attempt
    attempt = ExamAttempt.query.filter_by(
        student_id=current_user.id,
        exam_id=exam_id,
        is_completed=False
    ).first()
    
    if not attempt:
        attempt = ExamAttempt(
            student_id=current_user.id,
            exam_id=exam_id,
            started_at=datetime.utcnow()
        )
        db.session.add(attempt)
        try:
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            flash('Error starting exam. Please try again.', 'danger')
            return redirect(url_for('main.dashboard'))
    
    # Create main form for CSRF protection
    form = TakeExamForm()
    
    # Handle AJAX requests for saving answers
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' and request.method == 'POST':
        # Validate CSRF token
        if not form.validate_on_submit():
            return jsonify({
                'success': False,
                'message': 'Invalid form submission. Please refresh the page and try again.',
                'error': 'csrf_error'
            }), 400
            
        if check_time_expired(attempt):
            attempt.is_completed = True
            attempt.submitted_at = datetime.utcnow()
            attempt.completed_at = datetime.utcnow()
            try:
                db.session.commit()
            except SQLAlchemyError:
                db.session.rollback()
                
            return jsonify({
                'success': False,
                'message': 'Exam time has expired',
                'redirect_url': url_for('student.view_result', attempt_id=attempt.id)
            }), 400
            
        try:
            # Process form data
            save_answers(request.form, attempt)
            
            # Log what's being saved for debugging
            print(f"Saving answers for attempt {attempt.id}, form keys: {list(request.form.keys())}")
            
            # Commit the changes
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': 'Answers saved successfully',
                'saved_at': datetime.utcnow().isoformat()
            })
            
        except SQLAlchemyError as e:
            db.session.rollback()
            error_msg = str(e)
            print(f"Error saving answers: {error_msg}")
            # Log the error details
            ActivityLog.log_activity(
                user_id=current_user.id,
                action="save_error",
                category="attempt",
                details={
                    'exam_id': exam.id,
                    'attempt_id': attempt.id,
                    'error': error_msg
                },
                ip_address=request.remote_addr
            )
            return jsonify({
                'success': False,
                'message': "Database error while saving answers. Please try again.",
                'error': 'database_error',
                'details': error_msg
            }), 500
        except Exception as e:
            db.session.rollback()
            error_msg = str(e)
            print(f"Unexpected error saving answers: {error_msg}")
            # Log the error details
            ActivityLog.log_activity(
                user_id=current_user.id,
                action="save_error",
                category="attempt",
                details={
                    'exam_id': exam.id,
                    'attempt_id': attempt.id,
                    'error': error_msg
                },
                ip_address=request.remote_addr
            )
            return jsonify({
                'success': False,
                'message': "Error saving answers. Please try again.",
                'error': 'unexpected_error',
                'details': error_msg
            }), 500
            
    # Handle final submission
    if request.method == 'POST' and 'submit_exam' in request.form:
        return handle_exam_submission(exam, attempt, request.form)
    
    # Get all questions
    questions = Question.query.filter_by(exam_id=exam_id).order_by(Question.order).all()
    
    # Prepare forms for each question type
    answer_forms = {}
    existing_answers = {}
    
    # Get existing answers if any
    answers = Answer.query.filter_by(attempt_id=attempt.id).all()
    for answer in answers:
        existing_answers[answer.question_id] = answer
    
    for question in questions:
        if question.question_type == 'mcq':
            form = MCQAnswerForm()
            if question.id in existing_answers:
                form.selected_option.data = existing_answers[question.id].selected_option_id
            answer_forms[question.id] = form
            
        elif question.question_type == 'text':
            form = TextAnswerForm()
            if question.id in existing_answers:
                form.answer_text.data = existing_answers[question.id].text_answer
            answer_forms[question.id] = form
            
        elif question.question_type == 'code':
            form = CodeAnswerForm()
            if question.id in existing_answers:
                answer = existing_answers[question.id]
                form.code_answer.data = getattr(answer, 'code_answer', None) or answer.text_answer
            answer_forms[question.id] = form
    
    # Return the template with all necessary context
    return render_template(
        'student/take_exam.html',
        exam=exam,
        attempt=attempt,
        questions=questions,
        answer_forms=answer_forms,
        form=form  # Main form for CSRF protection
    )


@student_bp.route('/exams/<int:exam_id>/<path:undefined_path>', methods=['GET', 'POST'])
@login_required
@student_required
def handle_undefined_exam_path(exam_id, undefined_path):
    """Handle undefined paths related to exams and redirect to the correct route"""
    # Log the redirect attempt
    print(f"Redirecting from undefined path: /student/exams/{exam_id}/{undefined_path}")
    
    # Check if this is likely an exam submission attempt
    if undefined_path == 'undefined' and request.method == 'POST':
        # Forward to the dedicated submit_exam route
        return submit_exam(exam_id)
    
    # For GET requests or other undefined paths, redirect to the take exam page
    return redirect(url_for('student.take_exam', exam_id=exam_id))
