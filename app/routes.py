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
            
            attempts = ExamAttempt.query.filter_by(student_id=current_user.id).all()
            completed_attempts = [attempt for attempt in attempts if attempt.is_completed]
            completed_exams = [attempt.exam for attempt in completed_attempts]
            
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
    attempt = ExamAttempt.query.get_or_404(attempt_id)
    exam = attempt.exam

    if exam.creator_id != current_user.id:
        abort(403)

    answers = Answer.query.filter_by(attempt_id=attempt_id).all()

    # Create a main form for CSRF protection
    grading_form = GradeAnswerForm(prefix='main')

    grading_forms = {}
    for answer in answers:
        if answer.question.question_type != 'mcq':
            form = GradeAnswerForm(prefix=f'answer_{answer.id}')
            form.points_awarded.default = answer.question.points if answer.is_correct else 0
            grading_forms[answer.id] = form

    return render_template(
        'teacher/grade_attempt.html',
        attempt=attempt,
        exam=exam,
        answers=answers,
        grading_forms=grading_forms,
        grading_form=grading_form  # Add the main form for CSRF protection
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
    
    attempt_stats = db.session.query(
        func.count(ExamAttempt.id).label('total_attempts'),
        func.count(case([(ExamAttempt.is_completed == True, 1)])).label('completed_attempts'),
        func.avg(ExamAttempt.score).label('average_score')
    ).join(Exam).filter(Exam.creator_id == current_user.id).first()
    
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
    
    recent_activity = db.session.query(
        ExamAttempt.id,
        User.username,
        Exam.title,
        ExamAttempt.score,
        ExamAttempt.submitted_at
    ).join(User, ExamAttempt.student_id == User.id)\
     .join(Exam, ExamAttempt.exam_id == Exam.id)\
     .filter(Exam.creator_id == current_user.id)\
     .order_by(ExamAttempt.submitted_at.desc())\
     .limit(10)\
     .all()
    
    return render_template(
        'teacher/analytics_dashboard.html',
        total_exams=total_exams,
        published_exams=published_exams,
        attempt_stats=attempt_stats,
        top_students=top_students,
        recent_activity=recent_activity
    )


@teacher_bp.route('/exams/export', methods=['GET'])
@login_required
@teacher_required
def export_exams():
    from io import StringIO
    from app.security import log_security_event
    
    log_security_event('DATA_EXPORT', f'Teacher {current_user.id} exported exam data')
    
    csv_data = StringIO()
    csv_writer = csv.writer(csv_data)
    
    csv_writer.writerow(['Exam ID', 'Title', 'Description', 'Time Limit', 'Status', 
                         'Created Date', 'Questions', 'Total Attempts', 'Avg Score'])
    
    exams = Exam.query.filter_by(creator_id=current_user.id).all()
    
    for exam in exams:
        question_count = Question.query.filter_by(exam_id=exam.id).count()
        attempts = ExamAttempt.query.filter_by(exam_id=exam.id, is_completed=True).all()
        attempts_count = len(attempts)
        
        if attempts_count > 0:
            total_score = sum(attempt.calculate_score()['percentage'] for attempt in attempts)
            avg_score = f"{(total_score / attempts_count):.1f}"
        else:
            avg_score = "N/A"
        
        status = 'Published' if exam.is_published else 'Draft'
        created_date = exam.created_at.strftime('%Y-%m-%d')
        
        csv_writer.writerow([
            exam.id, 
            exam.title, 
            exam.description[:50] + '...' if exam.description and len(exam.description) > 50 else exam.description,
            f"{exam.time_limit_minutes} minutes",
            status,
            created_date,
            question_count,
            attempts_count,
            avg_score
        ])
    
    response = make_response(csv_data.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=exam_data.csv'
    response.headers['Content-type'] = 'text/csv'
    return response


@teacher_bp.route('/exams/<int:exam_id>/import-questions', methods=['GET', 'POST'])
@login_required
@teacher_required
def import_questions(exam_id):
    from app.security import verify_exam_owner
    
    exam = verify_exam_owner(exam_id)
    
    form = ImportQuestionsForm()
    
    # Check if we need to show the confirmation page for replacing questions
    if form.validate_on_submit() and form.replace_existing.data and not request.form.get('confirm_replace'):
        # Store the file in the session temporarily
        if form.template_file.data:
            file_contents = form.template_file.data.read().decode('utf-8')
            session['import_file_contents'] = file_contents
            
            # Count existing questions for confirmation message
            existing_questions = Question.query.filter_by(exam_id=exam_id).count()
            
            return render_template(
                'teacher/confirm_replace.html', 
                form=form, 
                exam=exam, 
                existing_questions=existing_questions
            )
    
    # If form is submitted and valid
    if form.validate_on_submit():
        try:
            # If we're coming from the confirmation page, get the file contents from the session
            if request.form.get('confirm_replace') and 'import_file_contents' in session:
                file_contents = session.pop('import_file_contents')
            else:
                file_contents = form.template_file.data.read().decode('utf-8')
            
            from io import StringIO
            
            reader = csv.DictReader(StringIO(file_contents))
            question_count = 0
            
            # If replacing existing questions, delete them first
            if form.replace_existing.data or request.form.get('replace_existing') == 'y':
                # Delete all existing questions for this exam
                existing_questions = Question.query.filter_by(exam_id=exam_id).all()
                for question in existing_questions:
                    db.session.delete(question)
                db.session.flush()
                flash(f'Deleted {len(existing_questions)} existing questions.', 'info')
            
            for row in reader:
                question = Question(
                    exam_id=exam_id,
                    question_text=row['question_text'],
                    question_type=row['question_type'],
                    points=int(row['points']),
                    order=Question.query.filter_by(exam_id=exam_id).count() + 1
                )
                db.session.add(question)
                db.session.flush()
                
                if question.question_type == 'mcq' and 'options' in row:
                    options = row['options'].split('|')
                    correct_answer = int(row.get('correct_answer', 0))
                    
                    for i, option_text in enumerate(options):
                        option = QuestionOption(
                            question_id=question.id,
                            option_text=option_text.strip(),
                            is_correct=(i == correct_answer)
                        )
                        db.session.add(option)
                
                question_count += 1
            
            db.session.commit()
            flash(f'Successfully imported {question_count} questions.', 'success')
            return redirect(url_for('teacher.edit_exam', exam_id=exam_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error importing questions: {str(e)}', 'danger')
    
    return render_template('teacher/import_questions.html', form=form, exam=exam)


@teacher_bp.route('/import-questions-template', methods=['GET'])
@login_required
@teacher_required
def download_template():
    from io import StringIO
    
    csv_data = StringIO()
    csv_writer = csv.writer(csv_data)
    
    csv_writer.writerow(['question_text', 'question_type', 'points', 'options', 'correct_answer'])
    
    csv_writer.writerow(['What is 2+2?', 'mcq', '5', '2|3|4|5', '2'])
    csv_writer.writerow(['Explain recursion.', 'text', '10', '', ''])
    csv_writer.writerow(['Write a function to calculate factorial.', 'code', '15', '', ''])
    
    response = make_response(csv_data.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=question_template.csv'
    response.headers['Content-type'] = 'text/csv'
    return response


# Student routes
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
        # Validate CSRF token
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
                'client_time': request.form.get('client_time')
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
        
        # Validate submission time
        if not validate_submission_time(attempt, submission_time):
            try:
                attempt.is_completed = True
                attempt.submitted_at = submission_time
                # Log time expired submission
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
                db.session.commit()
                
                return jsonify({
                    'success': True,
                    'message': 'Exam submitted (after time limit)',
                    'redirect_url': url_for('student.view_result', attempt_id=attempt.id)
                })
            except SQLAlchemyError as e:
                db.session.rollback()
                error_msg = str(e)
                print(f"Error submitting exam (time expired): {error_msg}")
                # Log the error
                ActivityLog.log_activity(
                    user_id=current_user.id,
                    action="submission_error",
                    category="attempt",
                    details={
                        'exam_id': exam.id,
                        'attempt_id': attempt.id,
                        'error': error_msg,
                        'type': 'time_expired'
                    },
                    ip_address=request.remote_addr
                )
                return jsonify({
                    'success': False,
                    'message': "Error submitting exam. Please try again.",
                    'error': 'database_error',
                    'details': error_msg
                }), 500
        
        try:
            # Save final answers
            save_answers(request.form, attempt, is_final_submission=True)
            
            # Mark attempt as completed
            attempt.is_completed = True
            attempt.submitted_at = submission_time
            
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


@student_bp.route('/exams/get_server_time', methods=['GET'])
@login_required
def get_server_time():
    """Endpoint to synchronize client time with server time."""
    return datetime.utcnow().isoformat()


@main_bp.route('/search')
@login_required
def search():
    query = request.args.get('q', '').strip()
    if not query:
        return redirect(url_for('main.dashboard'))

    if current_user.is_teacher():
        # Teachers can search their own exams
        exams = Exam.query.filter(
            Exam.creator_id == current_user.id,
            Exam.title.ilike(f'%{query}%')
        ).all()
        template = 'partials/teacher_search_results.html' if request.headers.get('HX-Request') else 'search.html'
        return render_template(template, exams=exams, query=query)
    else:
        # Students can search published exams
        exams = Exam.query.filter(
            Exam.is_published == True,
            Exam.title.ilike(f'%{query}%')
        ).all()
        
        # Get student's attempts for these exams
        attempts = {
            a.exam_id: a for a in ExamAttempt.query.filter(
                ExamAttempt.student_id == current_user.id,
                ExamAttempt.exam_id.in_([e.id for e in exams])
            ).all()
        }
        
        template = 'partials/student_search_results.html' if request.headers.get('HX-Request') else 'search.html'
        return render_template(template, exams=exams, attempts=attempts, query=query)


@main_bp.route('/notifications', methods=['GET', 'POST'])
@login_required
def notifications():
    # Get user's notifications ordered by creation time
    notifications = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(Notification.created_at.desc()).all()
    
    mark_all_form = MarkAllReadForm()
    mark_read_form = MarkReadForm()
    
    return render_template('notifications.html', 
                         notifications=notifications,
                         mark_all_form=mark_all_form,
                         mark_read_form=mark_read_form)


@main_bp.route('/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_read():
    form = MarkAllReadForm()
    if form.validate_on_submit():
        try:
            Notification.query.filter_by(
                user_id=current_user.id,
                is_read=False
            ).update({'is_read': True})
            db.session.commit()
            flash('All notifications marked as read.', 'success')
        except SQLAlchemyError as e:
            db.session.rollback()
            flash('Error marking notifications as read.', 'danger')
    
    return redirect(url_for('main.notifications'))


@main_bp.route('/notifications/<int:notification_id>/mark-read', methods=['POST'])
@login_required
def mark_read(notification_id):
    form = MarkReadForm()
    if form.validate_on_submit():
        try:
            notification = Notification.query.get_or_404(notification_id)
            if notification.user_id != current_user.id:
                abort(403)
            notification.is_read = True
            db.session.commit()
            flash('Notification marked as read.', 'success')
        except SQLAlchemyError as e:
            db.session.rollback()
            flash('Error marking notification as read.', 'danger')
    
    return redirect(url_for('main.notifications'))


@student_bp.route('/attempts/<int:attempt_id>/result')
@login_required
@student_required
def view_result(attempt_id):
    """View exam attempt results with optimized data loading"""
    try:
        # Load all related data in a single query using joinedload
        attempt = ExamAttempt.query.options(
            joinedload(ExamAttempt.exam),
            joinedload(ExamAttempt.answers).joinedload(Answer.question),
            joinedload(ExamAttempt.answers).joinedload(Answer.selected_option)
        ).get_or_404(attempt_id)
        
        # Verify ownership
        if attempt.student_id != current_user.id:
            logger.warning(f"Unauthorized access attempt to result {attempt_id} by user {current_user.id}")
            abort(403)
        
        # Since we're using joined load, these won't trigger additional queries
        answers = attempt.answers
        
        # Use a transaction to ensure consistent score calculation
        with db.session.begin():
            score = attempt.calculate_score()
            
            # Log the activity
            ActivityLog.log_activity(
                user_id=current_user.id,
                action="view_result",
                category="exam",
                details={
                    'exam_id': attempt.exam_id,
                    'attempt_id': attempt.id,
                    'score': float(attempt.score) if attempt.score else None,
                    'viewed_at': datetime.utcnow().isoformat()
                }
            )
        
        return render_template(
            'student/view_result.html',
            attempt=attempt,
            answers=answers,
            score=score
        )
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error in view_result: {str(e)}")
        flash("Error loading results. Please try again.", "danger")
        return redirect(url_for('main.dashboard'))


@main_bp.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    # Gather data for admin control center
    from app.models import User, Exam, ExamAttempt, Notification
    users = User.query.all()
    exams = Exam.query.all()
    attempts = ExamAttempt.query.all()
    notifications = Notification.query.order_by(Notification.created_at.desc()).limit(10).all()
    return render_template('dashboard/admin_dashboard.html', users=users, exams=exams, attempts=attempts, notifications=notifications)


@teacher_bp.route('/gradebook', methods=['GET'])
@login_required
@teacher_required
def gradebook():
    """
    Display gradebook with student scores across all exams or filtered by group/exam
    """
    group_id = request.args.get('group_id', type=int)
    exam_id = request.args.get('exam_id', type=int)
    sort_by = request.args.get('sort', 'name')
    
    # Get groups taught by this teacher
    groups = Group.query.filter_by(teacher_id=current_user.id).all()
    
    # Get exams created by this teacher
    exams_query = Exam.query.filter_by(creator_id=current_user.id)
    
    # Apply group filter if provided
    if group_id:
        group = Group.query.get_or_404(group_id)
        if group.teacher_id != current_user.id:
            flash('You do not have access to this group\'s gradebook.', 'warning')
            return redirect(url_for('teacher.gradebook'))
        
        students = group.students.all()
        exams_query = exams_query.filter_by(group_id=group_id)
    else:
        # Get all students who have taken the teacher's exams
        group = None
        students_query = db.session.query(User).join(
            ExamAttempt, User.id == ExamAttempt.student_id
        ).join(
            Exam, ExamAttempt.exam_id == Exam.id
        ).filter(
            Exam.creator_id == current_user.id,
            User.user_type == 'student'
        ).distinct()
        
        students = students_query.all()
    
    # Apply exam filter if provided
    if exam_id:
        exam = Exam.query.get_or_404(exam_id)
        if exam.creator_id != current_user.id:
            flash('You do not have access to this exam\'s gradebook.', 'warning')
            return redirect(url_for('teacher.gradebook'))
        
        exam_list = [exam]
    else:
        exam_list = exams_query.all()
    
    # Get all attempts for these students and exams
    attempts_query = ExamAttempt.query.join(
        Exam, ExamAttempt.exam_id == Exam.id
    ).filter(
        Exam.creator_id == current_user.id,
        ExamAttempt.student_id.in_([s.id for s in students]) if students else True,
        ExamAttempt.exam_id.in_([e.id for e in exam_list]) if exam_list else True
    )
    
    # Sort students based on sort parameter
    if sort_by == 'name':
        students.sort(key=lambda s: s.username.lower())
    elif sort_by == 'needs_grading':
        # Create a dict to store which students need grading
        needs_grading = {}
        for attempt in attempts_query:
            if not attempt.is_graded and attempt.needs_grading:
                needs_grading[attempt.student_id] = True
        
        # Sort with students needing grading first
        students.sort(key=lambda s: (0 if needs_grading.get(s.id) else 1, s.username.lower()))
    
    # Create a dictionary of attempts for quick lookup
    attempts = {}
    for attempt in attempts_query:
        attempts[(attempt.student_id, attempt.exam_id)] = attempt
    
    return render_template('teacher/gradebook.html',
        students=students,
        exam_list=exam_list,
        attempts=attempts,
        groups=groups,
        exams=Exam.query.filter_by(creator_id=current_user.id).all(),
        group=group,
        exam=Exam.query.get(exam_id) if exam_id else None,
        sort_by=sort_by
    )


@teacher_bp.route('/gradebook/export', methods=['GET'])
@login_required
@teacher_required
def export_gradebook():
    """
    Export gradebook as CSV file
    """
    group_id = request.args.get('group_id', type=int)
    exam_id = request.args.get('exam_id', type=int)
    
    # Build the query based on filters
    exams_query = Exam.query.filter_by(creator_id=current_user.id)
    
    if group_id:
        group = Group.query.get_or_404(group_id)
        if group.teacher_id != current_user.id:
            flash('You do not have access to this group\'s gradebook.', 'warning')
            return redirect(url_for('teacher.gradebook'))
        
        students = group.students.all()
        exams_query = exams_query.filter_by(group_id=group_id)
    else:
        # Get all students who have taken the teacher's exams
        students_query = db.session.query(User).join(
            ExamAttempt, User.id == ExamAttempt.student_id
        ).join(
            Exam, ExamAttempt.exam_id == Exam.id
        ).filter(
            Exam.creator_id == current_user.id,
            User.user_type == 'student'
        ).distinct()
        
        students = students_query.all()
    
    # Apply exam filter if provided
    if exam_id:
        exam = Exam.query.get_or_404(exam_id)
        if exam.creator_id != current_user.id:
            flash('You do not have access to this exam\'s gradebook.', 'warning')
            return redirect(url_for('teacher.gradebook'))
        
        exams = [exam]
    else:
        exams = exams_query.all()
    
    # Get all attempts
    attempts_query = ExamAttempt.query.join(
        Exam, ExamAttempt.exam_id == Exam.id
    ).filter(
        Exam.creator_id == current_user.id,
        ExamAttempt.student_id.in_([s.id for s in students]) if students else True,
        ExamAttempt.exam_id.in_([e.id for e in exams]) if exams else True
    )
    
    # Create a dictionary of attempts for quick lookup
    attempts = {}
    for attempt in attempts_query:
        attempts[(attempt.student_id, attempt.exam_id)] = attempt
    
    # Create CSV response
    import csv
    from io import StringIO
    
    output = StringIO()
    writer = csv.writer(output)
    
    # Write header row
    header = ['Student', 'Email']
    for exam in exams:
        header.append(exam.title)
    header.append('Average')
    writer.writerow(header)
    
    # Write data rows
    for student in students:
        row = [student.username, student.email]
        
        # Add scores for each exam
        total_score = 0
        score_count = 0
        
        for exam in exams:
            attempt = attempts.get((student.id, exam.id))
            if attempt and attempt.is_graded:
                row.append(f"{attempt.score:.1f}%")
                total_score += attempt.score
                score_count += 1
            else:
                row.append("Not Attempted" if not attempt else "Needs Grading")
        
        # Calculate average
        if score_count > 0:
            average = total_score / score_count
            row.append(f"{average:.1f}%")
        else:
            row.append("N/A")
        
        writer.writerow(row)
    
    # Set response headers
    from flask import Response
    group_name = Group.query.get(group_id).name if group_id else "All-Classes"
    filename = f"gradebook-{group_name}-{datetime.now().strftime('%Y-%m-%d')}.csv"
    
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Cache-Control': 'no-cache'
        }
    )


@teacher_bp.route('/attempts/<int:attempt_id>')
@login_required
@teacher_required
def view_attempt(attempt_id):
    """View details of a single exam attempt"""
    attempt = ExamAttempt.query.get_or_404(attempt_id)
    
    # Make sure the teacher created this exam
    if attempt.exam.creator_id != current_user.id:
        abort(403)
        
    answers = attempt.answers.all()
    return render_template(
        'teacher/view_attempt.html',
        attempt=attempt,
        answers=answers
    )


@student_bp.route('/exams/<int:exam_id>/review', methods=['GET', 'POST'])
@login_required
@student_required
def review_exam(exam_id):
    """Allow students to leave a review for an exam they've completed"""
    exam = Exam.query.get_or_404(exam_id)
    # Check if student completed this exam
    attempt = ExamAttempt.query.filter_by(
        student_id=current_user.id,
        exam_id=exam_id,
        is_completed=True
    ).first()
    if not attempt:
        flash('You need to complete the exam before reviewing it.', 'warning')
        return redirect(url_for('main.dashboard'))
    # Get existing review if any
    review = ExamReview.query.filter_by(
        exam_id=exam_id,
        student_id=current_user.id
    ).first()
    form = ExamReviewForm(obj=review)
    if form.validate_on_submit():
        try:
            if not review:
                review = ExamReview(
                    exam_id=exam_id,
                    student_id=current_user.id
                )
            review.rating = form.rating.data
            review.feedback = form.feedback.data
            if not review.id:
                db.session.add(review)
            db.session.commit()
            notify_new_review(review.id)
            flash('Your review has been submitted successfully!', 'success')
            return redirect(url_for('student.view_result', attempt_id=attempt.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error submitting review: {str(e)}', 'danger')
    return render_template(
        'student/review_exam.html',
        exam=exam,
        form=form,
        is_update=review is not None
    )
