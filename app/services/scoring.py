"""
Services module for handling business logic related to scoring and grading.
This separates business logic from models, improving maintainability.
"""
from sqlalchemy.exc import SQLAlchemyError
from app import db
from app.enums import QuestionType
import logging

# Configure logging
logger = logging.getLogger(__name__)

def calculate_attempt_score(attempt):
    """
    Calculate the score for an exam attempt
    
    Args:
        attempt: The ExamAttempt object to calculate score for
        
    Returns:
        dict: Dictionary with earned points, total points, and percentage
    """
    from app.models_fixed import Question, Answer, QuestionOption
    
    try:
        # Start a nested transaction to ensure consistency
        with db.session.begin_nested():
            # Get total possible points in a single query
            total_points = db.session.query(db.func.sum(Question.points))\
                .filter(Question.exam_id == attempt.exam_id)\
                .scalar() or 0
            
            if total_points == 0:
                return {'earned': 0, 'total': 0, 'percentage': 0}
            
            # Get all answers with their question points in a single query
            answers_with_points = db.session.query(
                Answer.id,
                Answer.points_awarded,
                Answer.selected_option_id,
                Question.points,
                Question.question_type
            ).join(Question).filter(
                Answer.attempt_id == attempt.id
            ).all()
            earned_points = 0
            answers_to_update = []
            for answer_id, points_awarded, selected_option_id, max_points, question_type in answers_with_points:
                if question_type == QuestionType.MCQ.value:
                    # For MCQ questions
                    if points_awarded is None and selected_option_id is not None:
                        # Auto-grade ungraded MCQ questions
                        answer = db.session.query(Answer).get(answer_id)
                        question = answer.question
                        
                        correct_option = db.session.query(QuestionOption).filter(
                            QuestionOption.question_id == question.id,
                            QuestionOption.is_correct == True
                        ).first()
                        
                        # MCQ is either full points or zero
                        is_correct = correct_option and selected_option_id == correct_option.id
                        answer.points_awarded = max_points if is_correct else 0
                        answer.is_correct = is_correct
                        
                        if is_correct:
                            earned_points += max_points
                        answers_to_update.append(answer)
                    elif points_awarded is not None:
                        # Use existing points for graded MCQ
                        earned_points += points_awarded
                else:
                    # For non-MCQ questions (essay, code, etc)
                    if points_awarded is not None:
                        # Always use the actual points awarded for non-MCQ
                        if 0 <= points_awarded <= max_points:
                            earned_points += points_awarded
                            # Update is_correct based on partial credit
                            answer = db.session.query(Answer).get(answer_id)
                            answer.is_correct = (points_awarded > 0)
                            answers_to_update.append(answer)
                        else:
                            logger.warning(f"Invalid points_awarded value for answer {answer_id}: {points_awarded}")
                            earned_points += 0  # Default to 0 for invalid values
            
            # Bulk update any answers that were auto-graded
            if answers_to_update:
                for answer in answers_to_update:
                    db.session.add(answer)
            
            # Calculate percentage with proper decimal handling
            percentage = round((earned_points / total_points * 100), 2) if total_points > 0 else 0
            
            # Update the attempt's score
            attempt.score = percentage
            if not attempt.needs_grading:
                attempt.is_graded = True
            
            db.session.add(attempt)
            
            return {
                'earned': earned_points,
                'total': total_points,
                'percentage': percentage
            }
            
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Error calculating score for attempt {attempt.id}: {str(e)}")
        raise ValueError(f"Error calculating score: {str(e)}")
