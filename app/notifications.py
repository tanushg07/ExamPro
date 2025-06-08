from app.models import db, Notification, User, ExamAttempt, Exam, ExamReview, Group
from flask_login import current_user
from app.email import send_exam_graded_email, send_new_exam_email, send_exam_review_email
from datetime import datetime, timedelta
import logging

# Configure logging
logger = logging.getLogger(__name__)

def send_notification(user_id, message, notification_type, related_id=None):
    """
    Send a notification to a specific user
    
    Args:
        user_id (int): The ID of the user to notify
        message (str): The notification message
        notification_type (str): Type of notification (info, exam_graded, etc)
        related_id (int, optional): ID of the related entity (exam, attempt)
    """
    notification = Notification(
        user_id=user_id,
        message=message,
        type=notification_type,
        related_id=related_id
    )
    db.session.add(notification)
    db.session.commit()


def notify_exam_graded(attempt_id):
    """
    Notify a student that their exam has been graded
    
    Args:
        attempt_id (int): The ID of the graded exam attempt
    """
    attempt = ExamAttempt.query.get(attempt_id)
    if attempt:
        exam = attempt.exam
        student = User.query.get(attempt.student_id)
        
        # Send in-app notification
        send_notification(
            user_id=attempt.student_id,
            message=f"Your exam '{exam.title}' has been graded.",
            notification_type='exam_graded',
            related_id=attempt_id
        )
        
        # Send email notification
        score = attempt.calculate_score()
        send_exam_graded_email(student, exam.title, score)


def notify_new_exam(exam_id):
    """
    Notify all students about a new exam
    
    Args:
        exam_id (int): The ID of the newly published exam
    """
    exam = Exam.query.get(exam_id)
    if exam and exam.is_published:
        # Get all student users
        students = User.query.filter_by(user_type='student').all()
        
        for student in students:
            # Send in-app notification
            send_notification(
                user_id=student.id,
                message=f"New exam available: '{exam.title}'",
                notification_type='new_exam',
                related_id=exam_id
            )
            
            # Send email notification
            send_new_exam_email(student, exam)


def notify_new_review(review_id, exam_id):
    """
    Notify the teacher about a new review on their exam
    
    Args:
        review_id (int): The ID of the new review
        exam_id (int): The ID of the reviewed exam
    """
    exam = Exam.query.get(exam_id)
    if exam:
        send_notification(
            user_id=exam.creator_id,
            message=f"A new review has been submitted for your exam '{exam.title}'",
            notification_type='new_review',
            related_id=exam_id
        )


def notify_exam_time_window(student_id, exam_id, message_type):
    """
    Notify a student about exam availability window
    
    Args:
        student_id (int): The ID of the student to notify
        exam_id (int): The ID of the exam
        message_type (str): Type of notification ('exam_started' or 'exam_ending')
    """
    exam = Exam.query.get(exam_id)
    if exam:
        if message_type == 'exam_started':
            message = f"Exam '{exam.title}' is now available to take."
            notification_type = 'exam_started'
        else:  # exam_ending
            message = f"Exam '{exam.title}' will end soon."
            notification_type = 'exam_ending'
        
        send_notification(
            user_id=student_id,
            message=message,
            notification_type=notification_type,
            related_id=exam_id
        )

def notify_student_group_exams(student_id, group_id):
    """
    Notify a student about active exams when joining a group
    
    Args:
        student_id (int): The ID of the student
        group_id (int): The ID of the group joined
    """
    group = Group.query.get(group_id)
    if group:
        # Get all active exams for this group
        active_exams = group.get_active_exams()
        
        for exam in active_exams:
            send_notification(
                user_id=student_id,
                message=f"New exam available in {group.name}: '{exam.title}'",
                notification_type='new_exam',
                related_id=exam.id
            )

def notify_exam_deadline_approaching():
    """
    Send notifications to students for upcoming exam deadlines
    Should be triggered by a scheduled task
    """
    logger.info("Running exam deadline notification check")
    try:
        # Get a fresh session
        from flask import current_app
        
        # Check if database is properly initialized and connected
        try:
            if db.session is None or db.engine is None:
                logger.error("Database session or engine not initialized for background task")
                return 0
                
            # Test connection by executing a simple query that should always work
            db.session.execute("SELECT 1").fetchone()
            logger.info("Database connection verified for notification task")
        except Exception as e:
            logger.error(f"Error in exam deadline notifications: {str(e)}")
            return 0
            
        # Reset the session to ensure we have a clean slate
        try:
            db.session.remove()
        except:
            logger.warning("Could not remove existing session")
            
        now = datetime.utcnow()
        soon = now + timedelta(hours=24)  # 24 hours from now
        
        try:
            # Find exams ending within the next 24 hours
            upcoming_deadlines = Exam.query.filter(
                Exam.is_published == True,
                Exam.available_until.isnot(None),
                Exam.available_until > now,
                Exam.available_until <= soon            ).all()
            
            logger.info(f"Found {len(upcoming_deadlines)} exams with upcoming deadlines")
            notification_count = 0
            
            for exam in upcoming_deadlines:
                # Get all students who should be notified
                if exam.group_id:
                    # For class exams, notify students in the group
                    group = Group.query.get(exam.group_id)
                    if group:
                        students = group.students.all()
                    else:
                        students = []
                else:
                    # For public exams, notify all students
                    students = User.query.filter_by(user_type='student').all()
                
                # Check which students haven't completed this exam yet
                for student in students:
                    attempt = ExamAttempt.query.filter_by(
                        exam_id=exam.id,
                        student_id=student.id,
                        is_completed=True
                        ).first()
                    
                    # Only notify students who haven't completed the exam
                    if not attempt:
                        hours_remaining = int((exam.available_until - now).total_seconds() / 3600)
                        message = f"Exam '{exam.title}' ends in {hours_remaining} hours"
                        
                        send_notification(
                            user_id=student.id,
                            message=message,
                            notification_type='exam_ending',
                            related_id=exam.id
                        )
                        notification_count += 1
            
            logger.info(f"Sent {notification_count} exam deadline notifications")
            return notification_count
            
        except Exception as e:
            try:
                db.session.rollback()  # Roll back any failed transactions
            except:
                pass
            logger.error(f"Database error in exam deadline notifications: {str(e)}")
            return 0
            
    except Exception as e:
        logger.error(f"Error in exam deadline notifications: {str(e)}")
        return 0

def notify_admins_exam_created(exam_id, action_type='created'):
    """
    Notify all admin users when a teacher creates or publishes an exam
    
    Args:
        exam_id (int): The ID of the exam that was created/published
        action_type (str): 'created' or 'published' to specify the action
    """
    try:
        exam = Exam.query.get(exam_id)
        if not exam:
            logger.warning(f"Exam {exam_id} not found for admin notification")
            return
            
        # Get teacher information
        teacher = User.query.get(exam.creator_id)
        teacher_name = teacher.username if teacher else 'Unknown'
        
        # Get all admin users
        admin_users = User.query.filter_by(user_type='admin').all()
        
        if action_type == 'published':
            message = f"Teacher {teacher_name} published exam '{exam.title}'"
            notification_type = 'teacher_exam_published'
        else:
            message = f"Teacher {teacher_name} created exam '{exam.title}'"
            notification_type = 'teacher_exam_created'
            
        # Send notification to each admin
        for admin in admin_users:
            send_notification(
                user_id=admin.id,
                message=message,
                notification_type=notification_type,
                related_id=exam_id
            )
            
        # Commit notifications
        db.session.commit()
        logger.info(f"Sent {len(admin_users)} admin notifications for exam {action_type}: {exam.title}")
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error sending admin notifications for exam {action_type}: {str(e)}")

def notify_admins_exam_completed(attempt_id):
    """
    Notify all admin users when a student completes an exam
    
    Args:
        attempt_id (int): The ID of the completed exam attempt
    """
    try:
        attempt = ExamAttempt.query.get(attempt_id)
        if not attempt or not attempt.is_completed:
            logger.warning(f"Attempt {attempt_id} not found or not completed for admin notification")
            return
            
        exam = attempt.exam
        student = User.query.get(attempt.student_id)
        
        student_name = student.username if student else 'Unknown'
        exam_title = exam.title if exam else 'Unknown Exam'
        
        # Get all admin users
        admin_users = User.query.filter_by(user_type='admin').all()
        
        message = f"Student {student_name} completed exam '{exam_title}'"
        notification_type = 'student_exam_completed'
        
        # Send notification to each admin
        for admin in admin_users:
            send_notification(
                user_id=admin.id,
                message=message,
                notification_type=notification_type,
                related_id=attempt_id
            )
            
        # Commit notifications
        db.session.commit()
        logger.info(f"Sent {len(admin_users)} admin notifications for exam completion: {exam_title} by {student_name}")
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error sending admin notifications for exam completion: {str(e)}")
