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

from app.models import db, User, Exam, Question, QuestionOption, ExamAttempt, Answer, ExamReview, Notification, Group
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


@main_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('index.html')


@main_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.is_admin():
        # For admins: redirect to admin dashboard
        return redirect(url_for('main.admin_dashboard'))
    elif current_user.is_teacher():
        # For teachers: show created exams
        exams = Exam.query.filter_by(creator_id=current_user.id).all()
        return render_template('dashboard/teacher_dashboard.html', exams=exams)
    else:
        # For students: show available exams from joined groups
        joined_groups = current_user.joined_groups.all()
        group_ids = [g.id for g in joined_groups]

        # Get published exams from joined groups
        available_exams = Exam.query.filter(
            Exam.is_published == True,
            Exam.group_id.in_(group_ids)
        ).all()
        
        # Get student's attempts
        attempts = ExamAttempt.query.filter_by(student_id=current_user.id).all()
        completed_attempts = [attempt for attempt in attempts if attempt.is_completed]
        completed_exams = [attempt.exam for attempt in completed_attempts]
        
        # Calculate average score for completed exams
        average_score = 0
        if completed_attempts:
            total_score = sum(attempt.score or 0 for attempt in completed_attempts)
            average_score = total_score / len(completed_attempts)
        
        return render_template(
            'dashboard/student_dashboard.html',
            available_exams=available_exams,
            completed_exams=completed_exams,
            average_score=average_score
        )
