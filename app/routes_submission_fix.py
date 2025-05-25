from datetime import datetime, timedelta
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

def validate_submission_time(attempt, submission_time):
    """Validate that a submission is being made within the time limit."""
    if not attempt or not attempt.started_at or not attempt.exam:
        return False
        
    if not attempt.exam.time_limit_minutes:  # If no duration set, submission is always valid
        return True
        
    time_limit = attempt.started_at + timedelta(minutes=attempt.exam.time_limit_minutes)
    grace_period = timedelta(minutes=2)  # 2 minute grace period for network delays
    
    if submission_time > (time_limit + grace_period):
        # Log late submission attempt if we have access to ActivityLog
        try:
            ActivityLog.log_activity(
                user_id=attempt.student_id,
                action="late_submission_attempt",
                category="attempt",
                details={
                    'exam_id': attempt.exam.id,
                    'attempt_id': attempt.id,
                    'submission_time': submission_time.isoformat(),
                    'time_limit': time_limit.isoformat(),
                    'minutes_late': (submission_time - time_limit).total_seconds() / 60
                }
            )
        except:
            # If logging fails, just continue - this is not critical
            pass
        return False
    
    return True

def check_time_expired(attempt):
    """Check if the exam time has expired for an attempt."""
    if not attempt or not attempt.started_at or not attempt.exam:
        return True
        
    if not attempt.exam.time_limit_minutes:  # If no duration set, exam doesn't expire
        return False
        
    time_limit = attempt.started_at + timedelta(minutes=attempt.exam.time_limit_minutes)
    return datetime.utcnow() > time_limit

@student_bp.route('/exam/<int:exam_id>/submit', methods=['POST'])
@login_required
@student_required
def submit_exam(exam_id):
    """Handle exam submission."""
    attempt = ExamAttempt.query.filter_by(
        student_id=current_user.id,
        exam_id=exam_id,
        is_completed=False
    ).first()

    if not attempt:
        return jsonify({
            'status': 'error',
            'message': 'No active exam attempt found'
        }), 400

    submission_time = datetime.utcnow()
    
    # Validate submission time
    if not validate_submission_time(attempt, submission_time):
        return jsonify({
            'status': 'error',
            'message': 'Exam time has expired'
        }), 400

    if check_time_expired(attempt):
        return jsonify({
            'status': 'error',
            'message': 'Exam time has expired'
        }), 400

    try:
        # Mark attempt as completed with consistent timestamps
        attempt.is_completed = True
        attempt.submitted_at = submission_time
        attempt.completed_at = submission_time
        attempt.last_activity = submission_time
        
        # Add completion activity log
        ActivityLog.log_activity(
            user_id=current_user.id,
            action="exam_completed",
            category="attempt",
            details={
                'exam_id': exam_id,
                'attempt_id': attempt.id,
                'submission_time': submission_time.isoformat()
            }
        )
        
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Exam submitted successfully'
        })
        
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': 'Database error occurred'
        }), 500
