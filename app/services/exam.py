"""
Services module for handling exam-related business logic.
This separates exam management logic from models, improving maintainability.
"""
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError
from app import db
import logging

# Configure logging
logger = logging.getLogger(__name__)

def get_student_exams(student_id, status='all'):
    """
    Get exams for a student with efficient querying
    
    Args:
        student_id: The ID of the student
        status: Filter by exam status ('active', 'upcoming', 'past', 'all')
        
    Returns:
        list: List of exam objects
    """
    from app.models_fixed import Exam, GroupMembership, Group
    
    try:
        now = datetime.utcnow()
        
        # Get all groups the student is in
        subquery = db.session.query(GroupMembership.group_id)\
            .filter(GroupMembership.user_id == student_id)\
            .subquery()
            
        # Base query to get published exams for the student's groups
        query = db.session.query(Exam)\
            .filter(Exam.is_published == True)\
            .filter(Exam.group_id.in_(subquery))
            
        # Apply status filter
        if status == 'active':
            query = query.filter(
                (Exam.available_from <= now) | (Exam.available_from == None),
                (Exam.available_until >= now) | (Exam.available_until == None)
            )
        elif status == 'upcoming':
            query = query.filter(Exam.available_from > now)
        elif status == 'past':
            query = query.filter(Exam.available_until < now)
            
        return query.all()
    except SQLAlchemyError as e:
        logger.error(f"Error getting student exams: {str(e)}")
        return []

def get_teacher_exams(teacher_id, status='all', group_id=None):
    """
    Get exams created by a teacher with efficient querying
    
    Args:
        teacher_id: The ID of the teacher
        status: Filter by exam status ('active', 'upcoming', 'past', 'all')
        group_id: Optional group ID filter
        
    Returns:
        list: List of exam objects
    """
    from app.models_fixed import Exam
    
    try:
        now = datetime.utcnow()
        
        # Base query for teacher's exams
        query = db.session.query(Exam).filter(Exam.creator_id == teacher_id)
        
        # Apply group filter if specified
        if group_id:
            query = query.filter(Exam.group_id == group_id)
            
        # Apply status filter
        if status == 'active':
            query = query.filter(
                Exam.is_published == True,
                (Exam.available_from <= now) | (Exam.available_from == None),
                (Exam.available_until >= now) | (Exam.available_until == None)
            )
        elif status == 'upcoming':
            query = query.filter(
                Exam.is_published == True,
                Exam.available_from > now
            )
        elif status == 'past':
            query = query.filter(
                Exam.is_published == True,
                Exam.available_until < now
            )
        elif status == 'draft':
            query = query.filter(Exam.is_published == False)
            
        return query.all()
    except SQLAlchemyError as e:
        logger.error(f"Error getting teacher exams: {str(e)}")
        return []

def create_exam_version(exam_id):
    """
    Create a new version of an exam
    
    Args:
        exam_id: The ID of the exam to version
        
    Returns:
        Exam: The new exam version object
    """
    from app.models_fixed import Exam, Question, QuestionOption
    
    try:
        # Start a transaction
        with db.session.begin():
            # Get the original exam
            original_exam = db.session.query(Exam).get(exam_id)
            if not original_exam:
                raise ValueError(f"Exam with ID {exam_id} not found")
                
            # Create a new exam with the same properties
            new_exam = Exam(
                title=f"{original_exam.title} (v{original_exam.version + 1})",
                description=original_exam.description,
                time_limit_minutes=original_exam.time_limit_minutes,
                creator_id=original_exam.creator_id,
                group_id=original_exam.group_id,
                is_published=False,  # New version starts as unpublished
                require_lockdown=original_exam.require_lockdown,
                allow_calculator=original_exam.allow_calculator,
                allow_scratch_pad=original_exam.allow_scratch_pad,
                randomize_questions=original_exam.randomize_questions,
                one_question_at_time=original_exam.one_question_at_time,
                prevent_copy_paste=original_exam.prevent_copy_paste,
                require_webcam=original_exam.require_webcam,
                max_warnings=original_exam.max_warnings,
                version=original_exam.version + 1
            )
            db.session.add(new_exam)
            db.session.flush()  # Ensure new_exam has an ID before creating questions
            
            # Copy all questions
            for question in original_exam.questions:
                new_question = Question(
                    exam_id=new_exam.id,
                    question_text=question.question_text,
                    question_type=question.question_type,
                    points=question.points,
                    order=question.order,
                    version=question.version
                )
                db.session.add(new_question)
                db.session.flush()
                
                # Copy all options for MCQ questions
                for option in question.options:
                    new_option = QuestionOption(
                        question_id=new_question.id,
                        option_text=option.option_text,
                        is_correct=option.is_correct,
                        order=option.order
                    )
                    db.session.add(new_option)
            
            # Log the versioning
            from app.models_fixed import ActivityLog
            ActivityLog.log_activity(
                user_id=original_exam.creator_id,
                action='create_version',
                category='exam',
                details={
                    'original_exam_id': original_exam.id,
                    'new_exam_id': new_exam.id,
                    'version': new_exam.version
                }
            )
            
            return new_exam
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Error creating exam version: {str(e)}")
        raise ValueError(f"Error creating exam version: {str(e)}")
