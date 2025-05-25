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
from sqlalchemy.orm import joinedload
from functools import wraps
import logging

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

logger = logging.getLogger(__name__)

# Helper function to check if exam time has expired
def check_time_expired(attempt):
    """Check if the exam time has expired for an attempt."""
    if not attempt or not attempt.started_at or not attempt.exam:
        return True
    
    # Use the correct field for duration
    if not getattr(attempt.exam, 'time_limit_minutes', None):  # If no duration set, exam doesn't expire
        return False
    
    time_limit = attempt.started_at + timedelta(minutes=attempt.exam.time_limit_minutes)
    return datetime.utcnow() > time_limit

def validate_submission_time(attempt, submission_time):
    """Validate that a submission is being made within the time limit."""
    if not attempt or not attempt.started_at or not attempt.exam:
        return False
        
    if not attempt.exam.duration:  # If no duration set, submission is always valid
        return True
        
    time_limit = attempt.started_at + timedelta(minutes=attempt.exam.duration)
    grace_period = timedelta(minutes=1)  # 1 minute grace period for network delays
    
    return submission_time <= (time_limit + grace_period)


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


# Main routes
@main_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('index.html')


@main_bp.route('/dashboard')
@login_required
def dashboard():
    try:
        if current_user.is_admin():
            return redirect(url_for('main.admin_dashboard'))
        elif current_user.is_teacher():
            exams = Exam.query.filter_by(creator_id=current_user.id).all()
            return render_template('dashboard/teacher_dashboard.html', exams=exams)
        else:
            joined_groups = current_user.joined_groups.all()
            group_ids = [g.id for g in joined_groups]

            available_exams = Exam.query.filter(
                Exam.is_published == True,
                Exam.group_id.in_(group_ids)
            ).all()
            
            # Get all attempts for the student
            attempts = ExamAttempt.query.filter_by(student_id=current_user.id).all()
            # Get completed attempts and their corresponding exams
            completed_attempts = [attempt for attempt in attempts if attempt.is_completed]
            completed_exam_ids = {attempt.exam_id for attempt in completed_attempts}
            completed_exams = Exam.query.filter(Exam.id.in_(completed_exam_ids)).all()
            
            # Store the total number of available exams before filtering
            total_available_count = len(available_exams)

            # Filter out completed exams from available exams
            available_exams = [exam for exam in available_exams if exam.id not in completed_exam_ids]
            
            # Calculate and update scores for all completed attempts
            for attempt in completed_attempts:
                score_data = attempt.calculate_score()
                attempt.score = score_data['percentage']
                db.session.add(attempt)
            
            try:
                db.session.commit()
            except SQLAlchemyError as e:
                logger.error(f"Error updating scores: {str(e)}")
                db.session.rollback()
            
            # Now calculate average from all completed attempts
            scores = [attempt.score for attempt in completed_attempts if attempt.score is not None]
            if scores:
                average_score = sum(float(score) for score in scores) / len(scores)
            else:
                average_score = None
            
            return render_template(
                'dashboard/student_dashboard.html',
                available_exams=available_exams,
                completed_exams=completed_exams,
                total_available_count=total_available_count,
                average_score=average_score,
                graded_attempts=completed_attempts
            )
    except SQLAlchemyError as e:
        flash('Error loading dashboard data', 'danger')
        return redirect(url_for('main.index'))


# Teacher routes
@teacher_bp.route('/exams/new', methods=['GET', 'POST'])
@login_required
@teacher_required
def create_exam():
    form = ExamForm()
    
    # Populate class choices for the form
    groups = Group.query.filter_by(teacher_id=current_user.id).all()
    form.group_id.choices = [(g.id, g.name) for g in groups]
    
    if form.validate_on_submit():
        try:
            exam = Exam(
                title=form.title.data,
                description=form.description.data,
                time_limit_minutes=form.time_limit_minutes.data,
                creator_id=current_user.id,
                is_published=form.is_published.data,
                group_id=form.group_id.data
            )
            db.session.add(exam)
            db.session.commit()
            
            # Log exam creation
            ActivityLog.log_activity(
                user_id=current_user.id,
                action="create_exam",
                category="exam",
                details={
                    'exam_id': exam.id,
                    'title': exam.title,
                    'time_limit': exam.time_limit_minutes,
                    'group_id': exam.group_id,
                    'is_published': exam.is_published
                },
                ip_address=request.remote_addr,
                user_agent=str(request.user_agent)
            )
            
            flash('Exam created successfully!', 'success')
            return redirect(url_for('teacher.edit_exam', exam_id=exam.id))
        
        except SQLAlchemyError as e:
            db.session.rollback()
            flash('An error occurred while creating the exam.', 'danger')
            print(f"Error creating exam: {str(e)}")
    
    return render_template('teacher/create_exam.html', form=form)


@teacher_bp.route('/exams/<int:exam_id>/edit', methods=['GET', 'POST'])
@login_required
@teacher_required
def edit_exam(exam_id):
    from app.security import verify_exam_owner, log_security_event, security_rate_limiter
    
    exam = verify_exam_owner(exam_id)
    questions = Question.query.filter_by(exam_id=exam_id).order_by(Question.order).all()
    
    form = ExamForm(obj=exam)
    groups = Group.query.filter_by(teacher_id=current_user.id).all()
    form.group_id.choices = [(g.id, g.name) for g in groups]
    
    question_form = QuestionForm()
    
    if request.method == 'POST':
        if 'update_settings' in request.form:
            if form.validate_on_submit():
                try:
                    exam.title = form.title.data
                    exam.description = form.description.data
                    exam.time_limit_minutes = form.time_limit_minutes.data
                    exam.group_id = form.group_id.data
                    exam.is_published = form.is_published.data
                    db.session.commit()
                    flash('Exam settings updated successfully!', 'success')
                    return redirect(url_for('teacher.edit_exam', exam_id=exam_id))
                except SQLAlchemyError as e:
                    db.session.rollback()
                    flash('Error updating exam settings.', 'danger')
                    print(f"Error updating exam: {str(e)}")
        
        elif 'add_question' in request.form:
            if question_form.validate_on_submit():
                try:
                    question = Question(
                        exam_id=exam_id,
                        question_text=question_form.question_text.data,
                        question_type=question_form.question_type.data,
                        points=question_form.points.data,
                        order=len(questions) + 1
                    )
                    db.session.add(question)
                    
                    if question.question_type == 'mcq':
                        option_count = 0
                        for option_form in question_form.options:
                            if option_form.option_text.data:
                                option = QuestionOption(
                                    question=question,
                                    option_text=option_form.option_text.data,
                                    is_correct=option_form.is_correct.data
                                )
                                db.session.add(option)
                                option_count += 1
                    
                    db.session.commit()
                    flash('Question added successfully!', 'success')
                    return redirect(url_for('teacher.edit_exam', exam_id=exam_id))
                except SQLAlchemyError as e:
                    db.session.rollback()
                    flash('Error adding question.', 'danger')
                    print(f"Error adding question: {str(e)}")
    
    return render_template('teacher/edit_exam.html',
                         exam=exam,
                         questions=questions,
                         form=form,
                         question_form=question_form)


@teacher_bp.route('/exams/<int:exam_id>/questions/<int:question_id>/delete', methods=['POST'])
@login_required
@teacher_required
def delete_question(exam_id, question_id):
    question = Question.query.get_or_404(question_id)
    
    if question.exam.creator_id != current_user.id:
        abort(403)
    
    try:
        db.session.delete(question)
        db.session.commit()
        flash('Question deleted successfully!', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        flash('An error occurred while deleting the question.', 'danger')
        print(f"Error deleting question: {str(e)}")
    
    return redirect(url_for('teacher.edit_exam', exam_id=exam_id))


@teacher_bp.route('/exams/<int:exam_id>/publish', methods=['GET', 'POST'])
@login_required
@teacher_required
def publish_exam(exam_id):
    from app.security import verify_exam_owner
    from app.forms import TakeExamForm
    
    exam = verify_exam_owner(exam_id)
    
    if exam.creator_id != current_user.id:
        abort(403)
    
    if not exam.group_id:
        flash('Exam must be assigned to a class before publishing.', 'warning')
        return redirect(url_for('teacher.edit_exam', exam_id=exam_id))
    
    form = TakeExamForm()
    
    # If this is a GET request or the form hasn't been confirmed yet
    if request.method == 'GET' or not request.form.get('confirm'):
        return render_template('teacher/confirm_publish.html', exam=exam, form=form)
    
    # If this is a confirmed POST request
    was_already_published = exam.is_published
    exam.is_published = True
    db.session.commit()
    
    if not was_already_published:
        notify_new_exam(exam_id)
    
    flash('Exam published successfully!', 'success')
    return redirect(url_for('teacher.view_exam', exam_id=exam_id))


@teacher_bp.route('/exams/<int:exam_id>/unpublish', methods=['POST'])
@login_required
@teacher_required
def exam_unpublish(exam_id):
    from app.security import verify_exam_owner, log_security_event
    
    exam = verify_exam_owner(exam_id)
    
    if not exam.is_published:
        flash('This exam is already unpublished.', 'warning')
    else:
        completed_attempts = ExamAttempt.query.filter_by(
            exam_id=exam_id, 
            is_completed=True
        ).count()
        
        if completed_attempts > 0:
            flash('Cannot unpublish an exam that has completed attempts.', 'danger')
        else:
            exam.is_published = False
            db.session.commit()
            
            log_security_event('EXAM_UNPUBLISH', f'Teacher {current_user.id} unpublished exam {exam_id}')
            flash('Exam has been unpublished successfully.', 'success')
    
    return redirect(url_for('teacher.view_exam', exam_id=exam_id))


@teacher_bp.route('/exams/<int:exam_id>', methods=['GET'])
@login_required
@teacher_required
def view_exam(exam_id):
    from app.security import verify_exam_owner, log_security_event
    
    exam = verify_exam_owner(exam_id)
    
    questions = Question.query.filter_by(exam_id=exam_id).order_by(Question.order).all()
    attempts = ExamAttempt.query.filter_by(exam_id=exam_id).all()
    
    log_security_event('EXAM_ACCESS', f'Teacher {current_user.id} viewed exam {exam_id}')
    
    return render_template(
        'teacher/view_exam.html',
        exam=exam,
        questions=questions,
        attempts=attempts
    )


@teacher_bp.route('/exams/<int:exam_id>/attempts', methods=['GET'])
@login_required
@teacher_required
def view_exam_attempts(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    
    if exam.creator_id != current_user.id:
        abort(403)
    
    attempts = ExamAttempt.query.filter_by(exam_id=exam_id).order_by(ExamAttempt.started_at.desc()).all()
    
    students = {
        attempt.student_id: User.query.get(attempt.student_id).username
        for attempt in attempts
    }
    
    return render_template(
        'teacher/view_attempts.html',
        exam=exam,
        attempts=attempts,
        students=students
    )


@teacher_bp.route('/attempts/<int:attempt_id>/grade', methods=['GET', 'POST'])
@login_required
@teacher_required
def grade_attempt(attempt_id):
    # Get the attempt and verify ownership
    attempt = ExamAttempt.query.get_or_404(attempt_id)
    exam = attempt.exam
    
    if exam.creator_id != current_user.id:
        abort(403)
    
    answers = Answer.query.filter_by(attempt_id=attempt_id).all()
    grading_form = GradeAnswerForm(prefix='main')  # Main form for CSRF
    
    # Initialize counters for MCQ auto-grading
    mcq_correct = 0
    total_points = 0.0
    total_possible_points = 0.0
    
    # Auto-grade MCQ questions
    for answer in answers:
        if answer.question.question_type == 'mcq':
            total_possible_points += float(answer.question.points)
            selected_opt = answer.selected_option
            correct_opt = answer.question.options.filter_by(is_correct=True).first()
            
            if selected_opt and correct_opt and selected_opt.id == correct_opt.id:
                answer.is_correct = True
                answer.points_awarded = float(answer.question.points)
                mcq_correct += 1
            else:
                answer.is_correct = False
                answer.points_awarded = 0.0
            
            db.session.add(answer)  # Add the modified answer to the session
    
    try:
        db.session.commit()  # Save MCQ grades
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Error saving MCQ grades: {str(e)}")
        flash('Error saving MCQ grades.', 'danger')

    if request.method == 'POST':
        try:
            # Process each answer
            total_points = 0.0
            max_points = 0.0
            
            for answer in answers:
                if answer.question.question_type == 'mcq':
                    # Use auto-graded points for MCQs
                    total_points += float(answer.points_awarded or 0)
                    max_points += float(answer.question.points)
                else:
                    # Get form data for non-MCQ questions
                    points_str = request.form.get(f'points_{answer.id}', '0')
                    feedback = request.form.get(f'feedback_{answer.id}', '').strip()
                    
                    try:
                        points = float(points_str)
                        # Validate points are within bounds
                        max_question_points = float(answer.question.points)
                        points = min(max(0.0, points), max_question_points)
                        
                        # Determine if fully or partially correct
                        is_fully_correct = points == max_question_points
                        is_partially_correct = points > 0
                        
                        # Update the answer
                        answer.is_correct = is_fully_correct  # Only mark as correct if full points
                        answer.points_awarded = points
                        answer.teacher_feedback = feedback
                        db.session.add(answer)
                        
                        # Add to totals
                        total_points += points
                        max_points += max_question_points
                        
                    except (ValueError, TypeError):
                        flash(f'Invalid points value for question {answer.question.order}', 'danger')
                        points = 0.0
                        max_points += float(answer.question.points)
            
            # Update attempt with final score and grading info
            if max_points > 0:
                attempt.score = (total_points / max_points * 100)
            attempt.is_graded = True
            attempt.graded_at = datetime.utcnow()
            attempt.graded_by_id = current_user.id
            db.session.add(attempt)
            
            # Log the grading activity
            ActivityLog.log_activity(
                user_id=current_user.id,
                action="grade_attempt",
                category="exam",
                details={
                    'exam_id': exam.id,
                    'attempt_id': attempt.id,
                    'score': float(attempt.score),
                    'graded_at': attempt.graded_at.isoformat()
                },
                ip_address=request.remote_addr
            )
            
            db.session.commit()
            
            # Only notify student after successful commit
            notify_exam_graded(attempt.id)
            
            flash('Grading completed successfully!', 'success')
            return redirect(url_for('teacher.view_exam_attempts', exam_id=exam.id))
            
        except SQLAlchemyError as e:
            db.session.rollback()
            flash('Error saving grades: ' + str(e), 'danger')
            logger.error(f"Error saving grades for attempt {attempt_id}: {str(e)}")
            # Log the error
            ActivityLog.log_activity(
                user_id=current_user.id,
                action="grade_error",
                category="error",
                details={
                    'exam_id': exam.id,
                    'attempt_id': attempt.id,
                    'error': str(e)
                },
                ip_address=request.remote_addr
            )
    
    # For GET requests or if POST fails, render the grading form
    return render_template(
        'teacher/grade_attempt.html',
        attempt=attempt,
        exam=exam,
        answers=answers,
        mcq_correct=mcq_correct,
        grading_form=grading_form
    )


@teacher_bp.route('/exams/<int:exam_id>/analytics', methods=['GET'])
@login_required
@teacher_required
def exam_analytics(exam_id):
    """Generate analytics for an exam with optimized database queries"""
    from sqlalchemy.orm import joinedload
    from sqlalchemy import func, case
    from app.security import verify_exam_owner, log_security_event
    
    try:
        # Start a transaction to ensure consistent data
        with db.session.begin():
            # Verify ownership and log access
            exam = verify_exam_owner(exam_id)
            log_security_event('ANALYTICS_ACCESS', f'Teacher {current_user.id} viewed analytics for exam {exam_id}')
            
            # Get all data needed in a single efficient query
            attempts_data = db.session.query(
                ExamAttempt,
                User.username,
                ExamAttempt.score,
                ExamAttempt.completed_at,
                ExamAttempt.started_at
            ).join(
                User, ExamAttempt.student_id == User.id
            ).filter(
                ExamAttempt.exam_id == exam_id,
                ExamAttempt.is_completed == True
            ).all()
            
            if not attempts_data:
                flash('No completed attempts for this exam yet.', 'info')
                return redirect(url_for('teacher.view_exam', exam_id=exam_id))
            
            # Initialize analytics
            analytics = {
                'total_attempts': len(attempts_data),
                'avg_score': 0,
                'highest_score': 0,
                'lowest_score': 100,
                'question_stats': {},
                'completion_times': []
            }
            
            # Get question performance data in one efficient query
            question_stats = db.session.query(
                Question.id,
                Question.question_text,
                Question.points,
                Question.question_type,
                func.count(Answer.id).label('answer_count'),
                func.sum(case([(Answer.is_correct == True, 1)], else_=0)).label('correct_count')
            ).outerjoin(
                Answer, Answer.question_id == Question.id
            ).filter(
                Question.exam_id == exam_id
            ).group_by(
                Question.id
            ).all()
            
            # Process question statistics
            for q_id, q_text, points, q_type, answer_count, correct_count in question_stats:
                percent_correct = (correct_count / answer_count * 100) if answer_count > 0 else 0
                analytics['question_stats'][q_id] = {
                    'id': q_id,
                    'text': q_text,
                    'points': points,
                    'type': q_type,
                    'total_answers': answer_count,
                    'correct_answers': correct_count,
                    'percent_correct': round(percent_correct, 1)
                }
            
            # Process attempt data
            total_score = 0
            total_time = 0
            min_time = float('inf')
            max_time = 0
            
            for attempt, username, score, completed_at, started_at in attempts_data:
                if score is not None:
                    score_val = float(score)
                    total_score += score_val
                    analytics['highest_score'] = max(analytics['highest_score'], score_val)
                    analytics['lowest_score'] = min(analytics['lowest_score'], score_val)
                
                if completed_at and started_at:
                    completion_time = (completed_at - started_at).total_seconds() / 60.0
                    analytics['completion_times'].append({
                        'student': username,
                        'minutes': round(completion_time, 1)
                    })
                    total_time += completion_time
                    min_time = min(min_time, completion_time)
                    max_time = max(max_time, completion_time)
            
            # Calculate averages
            if analytics['total_attempts'] > 0:
                analytics['avg_score'] = round(total_score / analytics['total_attempts'], 1)
            
            # Calculate time statistics
            time_stats = {}
            if analytics['completion_times']:
                time_stats['avg'] = round(total_time / len(analytics['completion_times']), 1)
                time_stats['min'] = round(min_time, 1)
                time_stats['max'] = round(max_time, 1)
            
            # Sort questions by difficulty
            sorted_questions = sorted(
                analytics['question_stats'].values(),
                key=lambda x: x['percent_correct']
            )
            
            return render_template(
                'teacher/exam_analytics.html',
                exam=exam,
                analytics=analytics,
                sorted_questions=sorted_questions,
                time_stats=time_stats
            )
            
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error in exam analytics: {str(e)}")
        flash("Error generating analytics. Please try again.", "danger")
        return redirect(url_for('teacher.view_exam', exam_id=exam_id))


@teacher_bp.route('/exams/<int:exam_id>/reviews', methods=['GET'])
@login_required
@teacher_required
def view_exam_reviews(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    
    if exam.creator_id != current_user.id:
        abort(403)
    
    reviews = ExamReview.query.filter_by(exam_id=exam_id).order_by(ExamReview.created_at.desc()).all()
    
    stats = {
        'total': len(reviews),
        'average': exam.get_average_rating(),
        'counts': {
            '5': 0, '4': 0, '3': 0, '2': 0, '1': 0
        }
    }
    
    for review in reviews:
        stats['counts'][str(review.rating)] += 1
    
    if stats['total'] > 0:
        for rating in stats['counts']:
            stats['counts'][rating] = {
                'count': stats['counts'][rating],
                'percent': round((stats['counts'][rating] / stats['total']) * 100)
            }
    
    return render_template(
        'teacher/view_reviews.html',
        exam=exam,
        reviews=reviews,
        stats=stats
    )


@teacher_bp.route('/review-queue', methods=['GET'])
@login_required
@teacher_required
def review_queue():
    pending_attempts = (ExamAttempt.query
                       .join(Exam, ExamAttempt.exam_id == Exam.id)
                       .filter(Exam.creator_id == current_user.id)
                       .filter(ExamAttempt.is_completed == True)
                       .filter(ExamAttempt.is_graded == False)
                       .order_by(ExamAttempt.completed_at.desc())
                       .all())
    
    return render_template(
        'teacher/review_queue.html',
        pending_attempts=pending_attempts
    )


@teacher_bp.route('/analytics', methods=['GET'])
@login_required
@teacher_required
def view_analytics():
    total_exams = Exam.query.filter_by(creator_id=current_user.id).count()
    published_exams = Exam.query.filter_by(creator_id=current_user.id, is_published=True).count()
    
    # Get total unique students
    total_students = User.query\
        .join(User.joined_groups)\
        .filter(Group.teacher_id == current_user.id)\
        .distinct()\
        .count()
    
    # Get attempt statistics
    attempt_stats = db.session.query(
        func.count(ExamAttempt.id).label('total_attempts'),
        func.count(case([(ExamAttempt.is_completed == True, 1)])).label('completed_attempts'),
        func.avg(ExamAttempt.score).label('average_score')
    ).join(Exam).filter(Exam.creator_id == current_user.id).first()
    
    # Get monthly performance data for the past 6 months
    six_months_ago = datetime.now() - timedelta(days=180)
    monthly_stats = db.session.query(
        func.date_format(ExamAttempt.completed_at, '%Y-%m').label('month'),
        func.avg(ExamAttempt.score).label('avg_score'),
        func.count(ExamAttempt.id).label('attempt_count')
    ).join(Exam)\
     .filter(Exam.creator_id == current_user.id)\
     .filter(ExamAttempt.completed_at >= six_months_ago)\
     .filter(ExamAttempt.is_completed == True)\
     .group_by('month')\
     .order_by('month')\
     .all()
    
    # Format the data for the chart
    months = []
    scores = []
    attempts = []
    for stat in monthly_stats:
        months.append(datetime.strptime(stat.month, '%Y-%m').strftime('%B %Y'))
        scores.append(float(stat.avg_score or 0))
        attempts.append(int(stat.attempt_count or 0))
    
    # Get top performing students
    top_students = db.session.query(
        User.id, 
        User.username,
        func.avg(ExamAttempt.score).label('avg_score'),
        func.count(ExamAttempt.id).label('attempts')
    ).join(ExamAttempt, User.id == ExamAttempt.student_id)\
     .join(Exam, ExamAttempt.exam_id == Exam.id)\
     .filter(Exam.creator_id == current_user.id)\
     .filter(ExamAttempt.score.isnot(None))\
     .group_by(User.id)\
     .order_by(desc('avg_score'))\
     .limit(5)\
     .all()
    
    # Get recent activity
    recent_activity = db.session.query(
        ExamAttempt.id,
        User.username,
        Exam.title,
        ExamAttempt.score,
        ExamAttempt.submitted_at,
        ExamAttempt.completion_time
    ).join(User, ExamAttempt.student_id == User.id)\
     .join(Exam, ExamAttempt.exam_id == Exam.id)\
     .filter(Exam.creator_id == current_user.id)\
     .order_by(ExamAttempt.submitted_at.desc())\
     .limit(10)\
     .all()
    
    # Calculate average completion time
    avg_completion_time = db.session.query(
        func.avg(ExamAttempt.completion_time)
    ).join(Exam)\
     .filter(Exam.creator_id == current_user.id)\
     .filter(ExamAttempt.completion_time.isnot(None))\
     .scalar()
    
    return render_template(
        'teacher/analytics_dashboard.html',
        total_exams=total_exams,
        published_exams=published_exams,
        attempt_stats=attempt_stats,
        top_students=top_students,
        recent_activity=recent_activity,
        total_students=total_students,
        chart_data={
            'months': months,
            'scores': scores,
            'attempts': attempts
        },
        avg_completion_time=avg_completion_time
    )


@teacher_bp.route('/exams/<int:exam_id>/reviews', methods=['GET'])
@login_required
@teacher_required
def view_exam_reviews(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    
    if exam.creator_id != current_user.id:
        abort(403)
    
    reviews = ExamReview.query.filter_by(exam_id=exam_id).order_by(ExamReview.created_at.desc()).all()
    
    stats = {
        'total': len(reviews),
        'average': exam.get_average_rating(),
        'counts': {
            '5': 0, '4': 0, '3': 0, '2': 0, '1': 0
        }
    }
    
    for review in reviews:
        stats['counts'][str(review.rating)] += 1
    
    if stats['total'] > 0:
        for rating in stats['counts']:
            stats['counts'][rating] = {
                'count': stats['counts'][rating],
                'percent': round((stats['counts'][rating] / stats['total']) * 100)
            }
    
    return render_template(
        'teacher/view_reviews.html',
        exam=exam,
        reviews=reviews,
        stats=stats
    )


@teacher_bp.route('/review-queue', methods=['GET'])
@login_required
@teacher_required
def review_queue():
    pending_attempts = (ExamAttempt.query
                       .join(Exam, ExamAttempt.exam_id == Exam.id)
                       .filter(Exam.creator_id == current_user.id)
                       .filter(ExamAttempt.is_completed == True)
                       .filter(ExamAttempt.is_graded == False)
                       .order_by(ExamAttempt.completed_at.desc())
                       .all())
    
    return render_template(
        'teacher/review_queue.html',
        pending_attempts=pending_attempts
    )


@teacher_bp.route('/analytics', methods=['GET'])
@login_required
@teacher_required
def view_analytics():
    total_exams = Exam.query.filter_by(creator_id=current_user.id).count()
    published_exams = Exam.query.filter_by(creator_id=current_user.id, is_published=True).count()
    
    # Get total unique students
    total_students = User.query\
        .join(User.joined_groups)\
        .filter(Group.teacher_id == current_user.id)\
        .distinct()\
        .count()
    
    # Get attempt statistics
    attempt_stats = db.session.query(
        func.count(ExamAttempt.id).label('total_attempts'),
        func.count(case([(ExamAttempt.is_completed == True, 1)])).label('completed_attempts'),
        func.avg(ExamAttempt.score).label('average_score')
    ).join(Exam).filter(Exam.creator_id == current_user.id).first()
    
    # Get monthly performance data for the past 6 months
    six_months_ago = datetime.now() - timedelta(days=180)
    monthly_stats = db.session.query(
        func.date_format(ExamAttempt.completed_at, '%Y-%m').label('month'),
        func.avg(ExamAttempt.score).label('avg_score'),
        func.count(ExamAttempt.id).label('attempt_count')
    ).join(Exam)\
     .filter(Exam.creator_id == current_user.id)\
     .filter(ExamAttempt.completed_at >= six_months_ago)\
     .filter(ExamAttempt.is_completed == True)\
     .group_by('month')\
     .order_by('month')\
     .all()
    
    # Format the data for the chart
    months = []
    scores = []
    attempts = []
    for stat in monthly_stats:
        months.append(datetime.strptime(stat.month, '%Y-%m').strftime('%B %Y'))
        scores.append(float(stat.avg_score or 0))
        attempts.append(int(stat.attempt_count or 0))
    
    # Get top performing students
    top_students = db.session.query(
        User.id, 
        User.username,
        func.avg(ExamAttempt.score).label('avg_score'),
        func.count(ExamAttempt.id).label('attempts')
    ).join(ExamAttempt, User.id == ExamAttempt.student_id)\
     .join(Exam, ExamAttempt.exam_id == Exam.id)\
     .filter(Exam.creator_id == current_user.id)\
     .filter(ExamAttempt.score.isnot(None))\
     .group_by(User.id)\
     .order_by(desc('avg_score'))\
     .limit(5)\
     .all()
    
    # Get recent activity
    recent_activity = db.session.query(
        ExamAttempt.id,
        User.username,
        Exam.title,
        ExamAttempt.score,
        ExamAttempt.submitted_at,
        ExamAttempt.completion_time
    ).join(User, ExamAttempt.student_id == User.id)\
     .join(Exam, ExamAttempt.exam_id == Exam.id)\
     .filter(Exam.creator_id == current_user.id)\
     .order_by(ExamAttempt.submitted_at.desc())\
     .limit(10)\
     .all()
    
    # Calculate average completion time
    avg_completion_time = db.session.query(
        func.avg(ExamAttempt.completion_time)
    ).join(Exam)\
     .filter(Exam.creator_id == current_user.id)\
     .filter(ExamAttempt.completion_time.isnot(None))\
     .scalar()
    
    return render_template(
        'teacher/analytics_dashboard.html',
        total_exams=total_exams,
        published_exams=published_exams,
        attempt_stats=attempt_stats,
        top_students=top_students,
        recent_activity=recent_activity,
        total_students=total_students,
        chart_data={
            'months': months,
            'scores': scores,
            'attempts': attempts
        },
        avg_completion_time=avg_completion_time
    )


@teacher_bp.route('/exams/<int:exam_id>/reviews', methods=['GET'])
@login_required
@teacher_required
def view_exam_reviews(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    
    if exam.creator_id != current_user.id:
        abort(403)
    
    reviews = ExamReview.query.filter_by(exam_id=exam_id).order_by(ExamReview.created_at.desc()).all()
    
    stats = {
        'total': len(reviews),
        'average': exam.get_average_rating(),
        'counts': {
            '5': 0, '4': 0, '3': 0, '2': 0, '1': 0
        }
    }
    
    for review in reviews:
        stats['counts'][str(review.rating)] += 1
    
    if stats['total'] > 0:
        for rating in stats['counts']:
            stats['counts'][rating] = {
                'count': stats['counts'][rating],
                'percent': round((stats['counts'][rating] / stats['total']) * 100)
            }
    
    return render_template(
        'teacher/view_reviews.html',
        exam=exam,
        reviews=reviews,
        stats=stats
    )


@teacher_bp.route('/review-queue', methods=['GET'])
@login_required
@teacher_required
def review_queue():
    pending_attempts = (ExamAttempt.query
                       .join(Exam, ExamAttempt.exam_id == Exam.id)
                       .filter(Exam.creator_id == current_user.id)
                       .filter(ExamAttempt.is_completed == True)
                       .filter(ExamAttempt.is_graded == False)
                       .order_by(ExamAttempt.completed_at.desc())
                       .all())
    
    return render_template(
        'teacher/review_queue.html',
        pending_attempts=pending_attempts
    )


@teacher_bp.route('/analytics', methods=['GET'])
@login_required
@teacher_required
def view_analytics():
    total_exams = Exam.query.filter_by(creator_id=current_user.id).count()
    published_exams = Exam.query.filter_by(creator_id=current_user.id, is_published=True).count()
    
    # Get total unique students
    total_students = User.query\
        .join(User.joined_groups)\
        .filter(Group.teacher_id == current_user.id)\
        .distinct()\
        .count()
    
    # Get attempt statistics
    attempt_stats = db.session.query(
        func.count(ExamAttempt.id).label('total_attempts'),
        func.count(case([(ExamAttempt.is_completed == True, 1)])).label('completed_attempts'),
        func.avg(ExamAttempt.score).label('average_score')
    ).join(Exam).filter(Exam.creator_id == current_user.id).first()
    
    # Get monthly performance data for the past 6 months
    six_months_ago = datetime.now() - timedelta(days=180)
    monthly_stats = db.session.query(
        func.date_format(ExamAttempt.completed_at, '%Y-%m').label('month'),
        func.avg(ExamAttempt.score).label('avg_score'),
        func.count(ExamAttempt.id).label('attempt_count')
    ).join(Exam)\
     .filter(Exam.creator_id == current_user.id)\
     .filter(ExamAttempt.completed_at >= six_months_ago)\
     .filter(ExamAttempt.is_completed == True)\
     .group_by('month')\
     .order_by('month')\
     .all()
    
    # Format the data for the chart
    months = []
    scores = []
    attempts = []
    for stat in monthly_stats:
        months.append(datetime.strptime(stat.month, '%Y-%m').strftime('%B %Y'))
        scores.append(float(stat.avg_score or 0))
        attempts.append(int(stat.attempt_count or 0))
    
    # Get top performing students
    top_students = db.session.query(
        User.id, 
        User.username,
        func.avg(ExamAttempt.score).label('avg_score'),
        func.count(ExamAttempt.id).label('attempts')
    ).join(ExamAttempt, User.id == ExamAttempt.student_id)\
     .join(Exam, ExamAttempt.exam_id == Exam.id)\
     .filter(Exam.creator_id == current_user.id)\
     .filter(ExamAttempt.score.isnot(None))\
     .group_by(User.id)\
     .order_by(desc('avg_score'))\
     .limit(5)\
     .all()
    
    # Get recent activity
    recent_activity = db.session.query(
        ExamAttempt.id,
        User.username,
        Exam.title,
        ExamAttempt.score,
        ExamAttempt.submitted_at,
        ExamAttempt.completion_time
    ).join(User, ExamAttempt.student_id == User.id)\
     .join(Exam, ExamAttempt.exam_id == Exam.id)\
     .filter(Exam.creator_id == current_user.id)\
     .order_by(ExamAttempt.submitted_at.desc())\
     .limit(10)\
     .all()
    
    # Calculate average completion time
    avg_completion_time = db.session.query(
        func.avg(ExamAttempt.completion_time)
    ).join(Exam)\
     .filter(Exam.creator_id == current_user.id)\
     .filter(ExamAttempt.completion_time.isnot(None))\
     .scalar()
    
    return render_template(
        'teacher/analytics_dashboard.html',
        total_exams=total_exams,
        published_exams=published_exams,
        attempt_stats=attempt_stats,
        top_students=top_students,
        recent_activity=recent_activity,
        total_students=total_students,
        chart_data={
            'months': months,
            'scores': scores,
            'attempts': attempts
        },
        avg_completion_time=avg_completion_time
    )


@teacher_bp.route('/exams/<int:exam_id>/reviews', methods=['GET'])
@login_required
@teacher_required
def view_exam_reviews(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    
    if exam.creator_id != current_user.id:
        abort(403)
    
    reviews = ExamReview.query.filter_by(exam_id=exam_id).order_by(ExamReview.created_at.desc()).all()
    
    stats = {
        'total': len(reviews),
        'average': exam.get_average_rating(),
        'counts': {
            '5': 0, '4': 0, '3': 0, '2': 0, '1': 0
        }
    }
    
    for review in reviews:
        stats['counts'][str(review.rating)] += 1
    
    if stats['total'] > 0:
        for rating in stats['counts']:
            stats['counts'][rating] = {
                'count': stats['counts'][rating],
                'percent': round((stats['counts'][rating] / stats['total']) * 100)
            }
    
    return render_template(
        'teacher/view_reviews.html',
        exam=exam,
        reviews=reviews,
        stats=stats
    )


@teacher_bp.route('/review-queue', methods=['GET'])
@login_required
@teacher_required
def review_queue():
    pending_attempts = (ExamAttempt.query
                       .join(Exam, ExamAttempt.exam_id == Exam.id)
                       .filter(Exam.creator_id == current_user.id)
                       .filter(ExamAttempt.is_completed == True)
                       .filter(ExamAttempt.is_graded == False)
                       .order_by(ExamAttempt.completed_at.desc())
                       .all())
    
    return render_template(
        'teacher/review_queue.html',
        pending_attempts=pending_attempts
    )


@teacher_bp.route('/analytics', methods=['GET'])
@login_required
@teacher_required
def view_analytics():
    total_exams = Exam.query.filter_by(creator_id=current_user.id).count()
    published_exams = Exam.query.filter_by(creator_id=current_user.id, is_published=True).count()
    
    # Get total unique students
    total_students = User.query\
        .join(User.joined_groups)\
        .filter(Group.teacher_id == current_user.id)\
        .distinct()\
        .count()
    
    # Get attempt statistics
    attempt_stats = db.session.query(
        func.count(ExamAttempt.id).label('total_attempts'),
        func.count(case([(ExamAttempt.is_completed == True, 1)])).label('completed_attempts'),
        func.avg(ExamAttempt.score).label('average_score')
    ).join(Exam).filter(Exam.creator_id == current_user.id).first()
    
    # Get monthly performance data for the past 6 months
    six_months_ago = datetime.now() - timedelta(days=180)
    monthly_stats = db.session.query(
        func.date_format(ExamAttempt.completed_at, '%Y-%m').label('month'),
        func.avg(ExamAttempt.score).label('avg_score'),
        func.count(ExamAttempt.id).label('attempt_count')
    ).join(Exam)\
     .filter(Exam.creator_id == current_user.id)\
     .filter(ExamAttempt.completed_at >= six_months_ago)\
     .filter(ExamAttempt.is_completed == True)\
     .group_by('month')\
     .order_by('month')\
     .all()
    
    # Format the data for the chart
    months = []
    scores = []
    attempts = []
    for stat in monthly_stats:
        months.append(datetime.strptime(stat.month, '%Y-%m').strftime('%B %Y'))
        scores.append(float(stat.avg_score or 0))
        attempts.append(int(stat.attempt_count or 0))
    
    # Get top performing students
    top_students = db.session.query(
        User.id, 
        User.username,
        func.avg(ExamAttempt.score).label('avg_score'),
        func.count(ExamAttempt.id).label('attempts')
    ).join(ExamAttempt, User.id == ExamAttempt.student_id)\
     .join(Exam, ExamAttempt.exam_id == Exam.id)\
     .filter(Exam.creator_id == current_user.id)\
     .filter(ExamAttempt.score.isnot(None))\
     .group_by(User.id)\
     .order_by(desc('avg_score'))\
     .limit(5)\
     .all()
    
    # Get recent activity
    recent_activity = db.session.query(
        ExamAttempt.id,
        User.username,
        Exam.title,
        ExamAttempt.score,
        ExamAttempt.submitted_at,
        ExamAttempt.completion_time
    ).join(User, ExamAttempt.student_id == User.id)\
     .join(Exam, ExamAttempt.exam_id == Exam.id)\
     .filter(Exam.creator_id == current_user.id)\
     .order_by(ExamAttempt.submitted_at.desc())\
     .limit(10)\
     .all()
    
    # Calculate average completion time
    avg_completion_time = db.session.query(
        func.avg(ExamAttempt.completion_time)
    ).join(Exam)\
     .filter(Exam.creator_id == current_user.id)\
     .filter(ExamAttempt.completion_time.isnot(None))\
     .scalar()
    
    return render_template(
        'teacher/analytics_dashboard.html',
        total_exams=total_exams,
        published_exams=published_exams,
        attempt_stats=attempt_stats,
        top_students=top_students,
        recent_activity=recent_activity,
        total_students=total_students,
        chart_data={
            'months': months,
            'scores': scores,
            'attempts': attempts
        },
        avg_completion_time=avg_completion_time
    )


@teacher_bp.route('/exams/<int:exam_id>/reviews', methods=['GET'])
@login_required
@teacher_required
def view_exam_reviews(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    
    if exam.creator_id != current_user.id:
        abort(403)
    
    reviews = ExamReview.query.filter_by(exam_id=exam_id).order_by(ExamReview.created_at.desc()).all()
    
    stats = {
        'total': len(reviews),
        'average': exam.get_average_rating(),
        'counts': {
            '5': 0, '4': 0, '3': 0, '2': 0, '1': 0
        }
    }
    
    for review in reviews:
        stats['counts'][str(review.rating)] += 1
    
    if stats['total'] > 0:
        for rating in stats['counts']:
            stats['counts'][rating] = {
                'count': stats['counts'][rating],
                'percent': round((stats['counts'][rating] / stats['total']) * 100)
            }
    
    return render_template(
        'teacher/view_reviews.html',
        exam=exam,
        reviews=reviews,
        stats=stats
    )


@teacher_bp.route('/review-queue', methods=['GET'])
@login_required
@teacher_required
def review_queue():
    pending_attempts = (ExamAttempt.query
                       .join(Exam, ExamAttempt.exam_id == Exam.id)
                       .filter(Exam.creator_id == current_user.id)
                       .filter(ExamAttempt.is_completed == True)
                       .filter(ExamAttempt.is_graded == False)
                       .order_by(ExamAttempt.completed_at.desc())
                       .all())
    
    return render_template(
        'teacher/review_queue.html',
        pending_attempts=pending_attempts
    )


@teacher_bp.route('/analytics', methods=['GET'])
@login_required
@teacher_required
def view_analytics():
    total_exams = Exam.query.filter_by(creator_id=current_user.id).count()
    published_exams = Exam.query.filter_by(creator_id=current_user.id, is_published=True).count()
    
    # Get total unique students
    total_students = User.query\
        .join(User.joined_groups)\
        .filter(Group.teacher_id == current_user.id)\
        .distinct()\
        .count()
    
    # Get attempt statistics
    attempt_stats = db.session.query(
        func.count(ExamAttempt.id).label('total_attempts'),
        func.count(case([(ExamAttempt.is_completed == True, 1)])).label('completed_attempts'),
        func.avg(ExamAttempt.score).label('average_score')
    ).join(Exam).filter(Exam.creator_id == current_user.id).first()
    
    # Get monthly performance data for the past 6 months
    six_months_ago = datetime.now() - timedelta(days=180)
    monthly_stats = db.session.query(
        func.date_format(ExamAttempt.completed_at, '%Y-%m').label('month'),
        func.avg(ExamAttempt.score).label('avg_score'),
        func.count(ExamAttempt.id).label('attempt_count')
    ).join(Exam)\
     .filter(Exam.creator_id == current_user.id)\
     .filter(ExamAttempt.completed_at >= six_months_ago)\
     .filter(ExamAttempt.is_completed == True)\
     .group_by('month')\
     .order_by('month')\
     .all()
    
    # Format the data for the chart
    months = []
    scores = []
    attempts = []
    for stat in monthly_stats:
        months.append(datetime.strptime(stat.month, '%Y-%m').strftime('%B %Y'))
        scores.append(float(stat.avg_score or 0))
        attempts.append(int(stat.attempt_count or 0))
    
    # Get top performing students
    top_students = db.session.query(
        User.id, 
        User.username,
        func.avg(ExamAttempt.score).label('avg_score'),
        func.count(ExamAttempt.id).label('attempts')
    ).join(ExamAttempt, User.id == ExamAttempt.student_id)\
     .join(Exam, ExamAttempt.exam_id == Exam.id)\
     .filter(Exam.creator_id == current_user.id)\
     .filter(ExamAttempt.score.isnot(None))\
     .group_by(User.id)\
     .order_by(desc('avg_score'))\
     .limit(5)\
     .all()
    
    # Get recent activity
    recent_activity = db.session.query(
        ExamAttempt.id,
        User.username,
        Exam.title,
        ExamAttempt.score,
        ExamAttempt.submitted_at,
        ExamAttempt.completion_time
    ).join(User, ExamAttempt.student_id == User.id)\
     .join(Exam, ExamAttempt.exam_id == Exam.id)\
     .filter(Exam.creator_id == current_user.id)\
     .order_by(ExamAttempt.submitted_at.desc())\
     .limit(10)\
     .all()
    
    # Calculate average completion time
    avg_completion_time = db.session.query(
        func.avg(ExamAttempt.completion_time)
    ).join(Exam)\
     .filter(Exam.creator_id == current_user.id)\
     .filter(ExamAttempt.completion_time.isnot(None))\
     .scalar()
    
    return render_template(
        'teacher/analytics_dashboard.html',
        total_exams=total_exams,
        published_exams=published_exams,
        attempt_stats=attempt_stats,
        top_students=top_students,
        recent_activity=recent_activity,
        total_students=total_students,
        chart_data={
            'months': months,
            'scores': scores,
            'attempts': attempts
        },
        avg_completion_time=avg_completion_time
    )


@teacher_bp.route('/exams/<int:exam_id>/reviews', methods=['GET'])
@login_required
@teacher_required
def view_exam_reviews(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    
    if exam.creator_id != current_user.id:
        abort(403)
    
    reviews = ExamReview.query.filter_by(exam_id=exam_id).order_by(ExamReview.created_at.desc()).all()
    
    stats = {
        'total': len(reviews),
        'average': exam.get_average_rating(),
        'counts': {
            '5': 0, '4': 0, '3': 0, '2': 0, '1': 0
        }
    }
    
    for review in reviews:
        stats['counts'][str(review.rating)] += 1
    
    if stats['total'] > 0:
        for rating in stats['counts']:
            stats['counts'][rating] = {
                'count': stats['counts'][rating],
                'percent': round((stats['counts'][rating] / stats['total']) * 100)
            }
    
    return render_template(
        'teacher/view_reviews.html',
        exam=exam,
        reviews=reviews,
        stats=stats
    )


@teacher_bp.route('/review-queue', methods=['GET'])
@login_required
@teacher_required
def review_queue():
    pending_attempts = (ExamAttempt.query
                       .join(Exam, ExamAttempt.exam_id == Exam.id)
                       .filter(Exam.creator_id == current_user.id)
                       .filter(ExamAttempt.is_completed == True)
                       .filter(ExamAttempt.is_graded == False)
                       .order_by(ExamAttempt.completed_at.desc())
                       .all())
    
    return render_template(
        'teacher/review_queue.html',
        pending_attempts=pending_attempts
    )


@teacher_bp.route('/analytics', methods=['GET'])
@login_required
@teacher_required
def view_analytics():
    total_exams = Exam.query.filter_by(creator_id=current_user.id).count()
    published_exams = Exam.query.filter_by(creator_id=current_user.id, is_published=True).count()
    
    # Get total unique students
    total_students = User.query\
        .join(User.joined_groups)\
        .filter(Group.teacher_id == current_user.id)\
        .distinct()\
        .count()
    
    # Get attempt statistics
    attempt_stats = db.session.query(
        func.count(ExamAttempt.id).label('total_attempts'),
        func.count(case([(ExamAttempt.is_completed == True, 1)])).label('completed_attempts'),
        func.avg(ExamAttempt.score).label('average_score')
    ).join(Exam).filter(Exam.creator_id == current_user.id).first()
    
    # Get monthly performance data for the past 6 months
    six_months_ago = datetime.now() - timedelta(days=180)
    monthly_stats = db.session.query(
        func.date_format(ExamAttempt.completed_at, '%Y-%m').label('month'),
        func.avg(ExamAttempt.score).label('avg_score'),
        func.count(ExamAttempt.id).label('attempt_count')
    ).join(Exam)\
     .filter(Exam.creator_id == current_user.id)\
     .filter(ExamAttempt.completed_at >= six_months_ago)\
     .filter(ExamAttempt.is_completed == True)\
     .group_by('month')\
     .order_by('month')\
     .all()
    
    # Format the data for the chart
    months = []
    scores = []
    attempts = []
    for stat in monthly_stats:
        months.append(datetime.strptime(stat.month, '%Y-%m').strftime('%B %Y'))
        scores.append(float(stat.avg_score or 0))
        attempts.append(int(stat.attempt_count or 0))
    
    # Get top performing students
    top_students = db.session.query(
        User.id, 
        User.username,
        func.avg(ExamAttempt.score).label('avg_score'),
        func.count(ExamAttempt.id).label('attempts')
    ).join(ExamAttempt, User.id == ExamAttempt.student_id)\
     .join(Exam, ExamAttempt.exam_id == Exam.id)\
     .filter(Exam.creator_id == current_user.id)\
     .filter(ExamAttempt.score.isnot(None))\
     .group_by(User.id)\
     .order_by(desc('avg_score'))\
     .limit(5)\
     .all()
    
    # Get recent activity
    recent_activity = db.session.query(
        ExamAttempt.id,
        User.username,
        Exam.title,
        ExamAttempt.score,
        ExamAttempt.submitted_at,
        ExamAttempt.completion_time
    ).join(User, ExamAttempt.student_id == User.id)\
     .join(Exam, ExamAttempt.exam_id == Exam.id)\
     .filter(Exam.creator_id == current_user.id)\
     .order_by(ExamAttempt.submitted_at.desc())\
     .limit(10)\
     .all()
    
    # Calculate average completion time
    avg_completion_time = db.session.query(
        func.avg(ExamAttempt.completion_time)
    ).join(Exam)\
     .filter(Exam.creator_id == current_user.id)\
     .filter(ExamAttempt.completion_time.isnot(None))\
     .scalar()
    
    return render_template(
        'teacher/analytics_dashboard.html',
        total_exams=total_exams,
        published_exams=published_exams,
        attempt_stats=attempt_stats,
        top_students=top_students,
        recent_activity=recent_activity,
        total_students=total_students,
        chart_data={
            'months': months,
            'scores': scores,
            'attempts': attempts
        },
        avg_completion_time=avg_completion_time
    )


@teacher_bp.route('/exams/<int:exam_id>/reviews', methods=['GET'])
@login_required
@teacher_required
def view_exam_reviews(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    
    if exam.creator_id != current_user.id:
        abort(403)
    
    reviews = ExamReview.query.filter_by(exam_id=exam_id).order_by(ExamReview.created_at.desc()).all()
    
    stats = {
        'total': len(reviews),
        'average': exam.get_average_rating(),
        'counts': {
            '5': 0, '4': 0, '3': 0, '2': 0, '1': 0
        }
    }
    
    for review in reviews:
        stats['counts'][str(review.rating)] += 1
    
    if stats['total'] > 0:
        for rating in stats['counts']:
            stats['counts'][rating] = {
                'count': stats['counts'][rating],
                'percent': round((stats['counts'][rating] / stats['total']) * 100)
            }
    
    return render_template(
        'teacher/view_reviews.html',
        exam=exam,
        reviews=reviews,
        stats=stats
    )


@teacher_bp.route('/review-queue', methods=['GET'])
@login_required
@teacher_required
def review_queue():
    pending_attempts = (ExamAttempt.query
                       .join(Exam, ExamAttempt.exam_id == Exam.id)
                       .filter(Exam.creator_id == current_user.id)
                       .filter(ExamAttempt.is_completed == True)
                       .filter(ExamAttempt.is_graded == False)
                       .order_by(ExamAttempt.completed_at.desc())
                       .all())
    
    return render_template(
        'teacher/review_queue.html',
        pending_attempts=pending_attempts
    )


@teacher_bp.route('/analytics', methods=['GET'])
@login_required
@teacher_required
def view_analytics():
    total_exams = Exam.query.filter_by(creator_id=current_user.id).count()
    published_exams = Exam.query.filter_by(creator_id=current_user.id, is_published=True).count()
    
    # Get total unique students
    total_students = User.query\
        .join(User.joined_groups)\
        .filter(Group.teacher_id == current_user.id)\
        .distinct()\
        .count()
    
    # Get attempt statistics
    attempt_stats = db.session.query(
        func.count(ExamAttempt.id).label('total_attempts'),
        func.count(case([(ExamAttempt.is_completed == True, 1)])).label('completed_attempts'),
        func.avg(ExamAttempt.score).label('average_score')
    ).join(Exam).filter(Exam.creator_id == current_user.id).first()
    
    # Get monthly performance data for the past 6 months
    six_months_ago = datetime.now() - timedelta(days=180)
    monthly_stats = db.session.query(
        func.date_format(ExamAttempt.completed_at, '%Y-%m').label('month'),
        func.avg(ExamAttempt.score).label('avg_score'),
        func.count(ExamAttempt.id).label('attempt_count')
    ).join(Exam)\
     .filter(Exam.creator_id == current_user.id)\
     .filter(ExamAttempt.completed_at >= six_months_ago)\
     .filter(ExamAttempt.is_completed == True)\
     .group_by('month')\
     .order_by('month')\
     .all()
    
    # Format the data for the chart
    months = []
    scores = []
    attempts = []
    for stat in monthly_stats:
        months.append(datetime.strptime(stat.month, '%Y-%m').strftime('%B %Y'))
        scores.append(float(stat.avg_score or 0))
        attempts.append(int(stat.attempt_count or 0))
    
    # Get top performing students
    top_students = db.session.query(
        User.id, 
        User.username,
        func.avg(ExamAttempt.score).label('avg_score'),
        func.count(ExamAttempt.id).label('attempts')
    ).join(ExamAttempt, User.id == ExamAttempt.student_id)\
     .join(Exam, ExamAttempt.exam_id == Exam.id)\
     .filter(Exam.creator_id == current_user.id)\
     .filter(ExamAttempt.score.isnot(None))\
     .group_by(User.id)\
     .order_by(desc('avg_score'))\
     .limit(5)\
     .all()
    
    # Get recent activity
    recent_activity = db.session.query(
        ExamAttempt.id,
        User.username,
        Exam.title,
        ExamAttempt.score,
        ExamAttempt.submitted_at,
        ExamAttempt.completion_time
    ).join(User, ExamAttempt.student_id == User.id)\
     .join(Exam, ExamAttempt.exam_id == Exam.id)\
     .filter(Exam.creator_id == current_user.id)\
     .order_by(ExamAttempt.submitted_at.desc())\
     .limit(10)\
     .all()
    
    # Calculate average completion time
    avg_completion_time = db.session.query(
        func.avg(ExamAttempt.completion_time)
    ).join(Exam)\
     .filter(Exam.creator_id == current_user.id)\
     .filter(ExamAttempt.completion_time.isnot(None))\
     .scalar()
    
    return render_template(
        'teacher/analytics_dashboard.html',
        total_exams=total_exams,
        published_exams=published_exams,
        attempt_stats=attempt_stats,
        top_students=top_students,
        recent_activity=recent_activity,
        total_students=total_students,
        chart_data={
            'months': months,
            'scores': scores,
            'attempts': attempts
        },
        avg_completion_time=avg_completion_time
    )


@teacher_bp.route('/exams/<int:exam_id>/reviews', methods=['GET'])
@login_required
@teacher_required
def view_exam_reviews(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    
    if exam.creator_id != current_user.id:
        abort(403)
    
    reviews = ExamReview.query.filter_by(exam_id=exam_id).order_by(ExamReview.created_at.desc()).all()
    
    stats = {
        'total': len(reviews),
        'average': exam.get_average_rating(),
        'counts': {
            '5': 0, '4': 0, '3': 0, '2': 0, '1': 0
        }
    }
    
    for review in reviews:
        stats['counts'][str(review.rating)] += 1
    
    if stats['total'] > 0:
        for rating in stats['counts']:
            stats['counts'][rating] = {
                'count': stats['counts'][rating],
                'percent': round((stats['counts'][rating] / stats['total']) * 100)
            }
    
    return render_template(
        'teacher/view_reviews.html',
        exam=exam,
        reviews=reviews,
        stats=stats
    )


@teacher_bp.route('/review-queue', methods=['GET'])
@login_required
@teacher_required
def review_queue():
    pending_attempts = (ExamAttempt.query
                       .join(Exam, ExamAttempt.exam_id == Exam.id)
                       .filter(Exam.creator_id == current_user.id)
                       .filter(ExamAttempt.is_completed == True)
                       .filter(ExamAttempt.is_graded == False)
                       .order_by(ExamAttempt.completed_at.desc())
                       .all())
    
    return render_template(
        'teacher/review_queue.html',
        pending_attempts=pending_attempts
    )


@teacher_bp.route('/analytics', methods=['GET'])
@login_required
@teacher_required
def view_analytics():
    total_exams = Exam.query.filter_by(creator_id=current_user.id).count()
    published_exams = Exam.query.filter_by(creator_id=current_user.id, is_published=True).count()
    
    # Get total unique students
    total_students = User.query\
        .join(User.joined_groups)\
        .filter(Group.teacher_id == current_user.id)\
        .distinct()\
        .count()
    
    # Get attempt statistics
    attempt_stats = db.session.query(
        func.count(ExamAttempt.id).label('total_attempts'),
        func.count(case([(ExamAttempt.is_completed == True, 1)])).label('completed_attempts'),
        func.avg(ExamAttempt.score).label('average_score')
    ).join(Exam).filter(Exam.creator_id == current_user.id).first()
    
    # Get monthly performance data for the past 6 months
    six_months_ago = datetime.now() - timedelta(days=180)
    monthly_stats = db.session.query(
        func.date_format(ExamAttempt.completed_at, '%Y-%m').label('month'),
        func.avg(ExamAttempt.score).label('avg_score'),
        func.count(ExamAttempt.id).label('attempt_count')
    ).join(Exam)\
     .filter(Exam.creator_id == current_user.id)\
     .filter(ExamAttempt.completed_at >= six_months_ago)\
     .filter(ExamAttempt.is_completed == True)\
     .group_by('month')\
     .order_by('month')\
     .all()
    
    # Format the data for the chart
    months = []
    scores = []
    attempts = []
    for stat in monthly_stats:
        months.append(datetime.strptime(stat.month, '%Y-%m').strftime('%B %Y'))
        scores.append(float(stat.avg_score or 0))
        attempts.append(int(stat.attempt_count or 0))
    
    # Get top performing students
    top_students = db.session.query(
        User.id, 
        User.username,
        func.avg(ExamAttempt.score).label('avg_score'),
        func.count(ExamAttempt.id).label('attempts')
    ).join(ExamAttempt, User.id == ExamAttempt.student_id)\
     .join(Exam, ExamAttempt.exam_id == Exam.id)\
     .filter(Exam.creator_id == current_user.id)\
     .filter(ExamAttempt.score.isnot(None))\
     .group_by(User.id)\
     .order_by(desc('avg_score'))\
     .limit(5)\
     .all()
    
    # Get recent activity
    recent_activity = db.session.query(
        ExamAttempt.id,
        User.username,
        Exam.title,
        ExamAttempt.score,
        ExamAttempt.submitted_at,
        ExamAttempt.completion_time
    ).join(User, ExamAttempt.student_id == User.id)\
     .join(Exam, ExamAttempt.exam_id == Exam.id)\
     .filter(Exam.creator_id == current_user.id)\
     .order_by(ExamAttempt.submitted_at.desc())\
     .limit(10)\
     .all()
    
    # Calculate average completion time
    avg_completion_time = db.session.query(
        func.avg(ExamAttempt.completion_time)
    ).join(Exam)\
     .filter(Exam.creator_id == current_user.id)\
     .filter(ExamAttempt.completion_time.isnot(None))\
     .scalar()
    
    return render_template(
        'teacher/analytics_dashboard.html',
        total_exams=total_exams,
        published_exams=published_exams,
        attempt_stats=attempt_stats,
        top_students=top_students,
        recent_activity=recent_activity,
        total_students=total_students,
        chart_data={
            'months': months,
            'scores': scores,
            'attempts': attempts
        },
        avg_completion_time=avg_completion_time
    )


@teacher_bp.route('/exams/<int:exam_id>/reviews', methods=['GET'])
@login_required
@teacher_required
def view_exam_reviews(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    
    if exam.creator_id != current_user.id:
        abort(403)
    
    reviews = ExamReview.query.filter_by(exam_id=exam_id).order_by(ExamReview.created_at.desc()).all()
    
    stats = {
        'total': len(reviews),
        'average': exam.get_average_rating(),
        'counts': {
            '5': 0, '4': 0, '3': 0, '2': 0, '1': 0
        }
    }
    
    for review in reviews:
        stats['counts'][str(review.rating)] += 1
    
    if stats['total'] > 0:
        for rating in stats['counts']:
            stats['counts'][rating] = {
                'count': stats['counts'][rating],
                'percent': round((stats['counts'][rating] / stats['total']) * 100)
            }
    
    return render_template(
        'teacher/view_reviews.html',
        exam=exam,
        reviews=reviews,
        stats=stats
    )


@teacher_bp.route('/review-queue', methods=['GET'])
@login_required
@teacher_required
def review_queue():
    pending_attempts = (ExamAttempt.query
                       .join(Exam, ExamAttempt.exam_id == Exam.id)
                       .filter(Exam.creator_id == current_user.id)
                       .filter(ExamAttempt.is_completed == True)
                       .filter(ExamAttempt.is_graded == False)
                       .order_by(ExamAttempt.completed_at.desc())
                       .all())
    
    return render_template(
        'teacher/review_queue.html',
        pending_attempts=pending_attempts
    )


@teacher_bp.route('/analytics', methods=['GET'])
@login_required
@teacher_required
def view_analytics():
    total_exams = Exam.query.filter_by(creator_id=current_user.id).count()
    published_exams = Exam.query.filter_by(creator_id=current_user.id, is_published=True).count()
    
    # Get total unique students
    total_students = User.query\
        .join(User.joined_groups)\
        .filter(Group.teacher_id == current_user.id)\
        .distinct()\
        .count()
    
    # Get attempt statistics
    attempt_stats = db.session.query(
        func.count(ExamAttempt.id).label('total_attempts'),
        func.count(case([(ExamAttempt.is_completed == True, 1)])).label('completed_attempts'),
        func.avg(ExamAttempt.score).label('average_score')
    ).join(Exam).filter(Exam.creator_id == current_user.id).first()
    
    # Get monthly performance data for the past 6 months
    six_months_ago = datetime.now() - timedelta(days=180)
    monthly_stats = db.session.query(
        func.date_format(ExamAttempt.completed_at, '%Y-%m').label('month'),
        func.avg(ExamAttempt.score).label('avg_score'),
        func.count(ExamAttempt.id).label('attempt_count')
    ).join(Exam)\
     .filter(Exam.creator_id == current_user.id)\
     .filter(ExamAttempt.completed_at >= six_months_ago)\
     .filter(ExamAttempt.is_completed == True)\
     .group_by('month')\
     .order_by('month')\
     .all()
    
    # Format the data for the chart
    months = []
    scores = []
    attempts = []
    for stat in monthly_stats:
        months.append(datetime.strptime(stat.month, '%Y-%m').strftime('%B %Y'))
        scores.append(float(stat.avg_score or 0))
        attempts.append(int(stat.attempt_count or 0))
    
    # Get top performing students
    top_students = db.session.query(
        User.id, 
        User.username,
        func.avg(ExamAttempt.score).label('avg_score'),
        func.count(ExamAttempt.id).label('attempts')
    ).join(ExamAttempt, User.id == ExamAttempt.student_id)\
     .join(Exam, ExamAttempt.exam_id == Exam.id)\
     .filter(Exam.creator_id == current_user.id)\
     .filter(ExamAttempt.score.isnot(None))\
     .group_by(User.id)\
     .order_by(desc('avg_score'))\
     .limit(5)\
     .all()
    
    # Get recent activity
    recent_activity = db.session.query(
        ExamAttempt.id,
        User.username,
        Exam.title,
        ExamAttempt.score,
        ExamAttempt.submitted_at,
        ExamAttempt.completion_time
    ).join(User, ExamAttempt.student_id == User.id)\
     .join(Exam, ExamAttempt.exam_id == Exam.id)\
     .filter(Exam.creator_id == current_user.id)\
     .order_by(ExamAttempt.submitted_at.desc())\
     .limit(10)\
     .all()
    
    # Calculate average completion time
    avg_completion_time = db.session.query(
        func.avg(ExamAttempt.completion_time)
    ).join(Exam)\
     .filter(Exam.creator_id == current_user.id)\
     .filter(ExamAttempt.completion_time.isnot(None))\
     .scalar()
    
    return render_template(
        'teacher/analytics_dashboard.html',
        total_exams=total_exams,
        published_exams=published_exams,
        attempt_stats=attempt_stats,
        top_students=top_students,
        recent_activity=recent_activity,
        total_students=total_students,
        chart_data={
            'months': months,
            'scores': scores,
            'attempts': attempts
        },
        avg_completion_time=avg_completion_time
    )


@teacher_bp.route('/exams/<int:exam_id>/reviews', methods=['GET'])
@login_required
@teacher_required
def view_exam_reviews(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    
    if exam.creator_id != current_user.id:
        abort(403)
    
    reviews = ExamReview.query.filter_by(exam_id=exam_id).order_by(ExamReview.created_at.desc()).all()
    
    stats = {
        'total': len(reviews),