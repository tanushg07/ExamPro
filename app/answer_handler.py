"""
Enhanced answer handling with concurrency control
"""
from datetime import datetime
from sqlalchemy.orm import with_for_update
from sqlalchemy.exc import IntegrityError
from app import db
from app.models import Answer, ExamAttempt, Question
from app.exam_security import ExamSecurity
from app.time_tracking import ExamTimer

class AnswerHandler:
    @staticmethod
    def save_answer(attempt_id, question_id, answer_data, client_time=None):
        """
        Save an answer with optimistic locking and version control
        Returns (success, message, answer_id)
        """
        try:
            # Get attempt with row lock
            attempt = ExamAttempt.query.with_for_update().get(attempt_id)
            if not attempt:
                return False, "Invalid attempt", None
                
            # Validate time
            timer_valid, timer_data = ExamTimer.validate_time(attempt_id, client_time)
            if not timer_valid:
                return False, timer_data, None
                
            # Get or create answer
            answer = Answer.query.filter_by(
                attempt_id=attempt_id,
                question_id=question_id
            ).with_for_update().first()
            
            if not answer:
                answer = Answer(
                    attempt_id=attempt_id,
                    question_id=question_id
                )
                
            # Update answer fields based on type
            if answer_data.get('type') == 'mcq':
                answer.selected_option_id = answer_data.get('selected_option_id')
                answer.is_correct = answer_data.get('is_correct')
            elif answer_data.get('type') == 'text':
                answer.text_answer = answer_data.get('text')
                answer.is_correct = None  # Needs manual grading
            elif answer_data.get('type') == 'code':
                answer.code_answer = answer_data.get('code')
                answer.is_correct = None  # Needs manual grading
                
            # Update metadata
            answer.created_at = datetime.utcnow()
            attempt.answer_version += 1
            attempt.last_sync_time = datetime.utcnow()
            attempt.client_timestamp = client_time
            
            # Log answer submission
            ExamSecurity.log_security_event(
                attempt,
                'ANSWER_SUBMISSION',
                {
                    'question_id': question_id,
                    'version': attempt.answer_version,
                    'type': answer_data.get('type')
                }
            )
            
            # Save changes
            if not answer.id:
                db.session.add(answer)
            db.session.commit()
            
            return True, "Answer saved successfully", answer.id
            
        except IntegrityError:
            db.session.rollback()
            return False, "Concurrent update detected - please try again", None
        except Exception as e:
            db.session.rollback()
            return False, f"Error saving answer: {str(e)}", None
            
    @staticmethod
    def submit_attempt(attempt_id, submission_data):
        """
        Submit an exam attempt with final validation
        """
        try:
            # Get attempt with lock
            attempt = ExamAttempt.query.with_for_update().get(attempt_id)
            if not attempt:
                return False, "Invalid attempt"
                
            # Validate submission
            valid, message = attempt.validate_submission(
                datetime.utcnow(),
                submission_data.get('client_time')
            )
            if not valid:
                return False, message
                
            # Update attempt status
            attempt.is_completed = True
            attempt.completed_at = datetime.utcnow()
            attempt.submitted_at = datetime.utcnow()
            attempt.submission_ip = submission_data.get('ip_address')
            attempt.submission_location = submission_data.get('location')
            
            # Auto-grade MCQ questions if not already graded
            AnswerHandler._auto_grade_mcq(attempt)
            
            # Log submission
            ExamSecurity.log_security_event(
                attempt,
                'EXAM_SUBMISSION',
                submission_data,
                'info'
            )
            
            # Clean up
            ExamTimer.cleanup_attempt(attempt_id)
            
            db.session.commit()
            return True, "Exam submitted successfully"
            
        except Exception as e:
            db.session.rollback()
            print(f"Error in submit_attempt: {e}")  # For debugging
            return False, f"Error submitting exam: {str(e)}"
            
    @staticmethod
    def _auto_grade_mcq(attempt):
        """Auto-grade all MCQ questions in the attempt"""
        mcq_answers = Answer.query.join(
            Question
        ).filter(
            Answer.attempt_id == attempt.id,
            Question.question_type == 'mcq',
            Answer.is_correct.is_(None)
        ).all()
        
        for answer in mcq_answers:
            if answer.selected_option:
                answer.is_correct = answer.selected_option.is_correct
                
        attempt.is_graded = all(a.is_correct is not None for a in attempt.answers)
