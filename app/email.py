from flask import current_app, render_template
from flask_mail import Message
from threading import Thread

def send_async_email(app, msg):
    """Send email asynchronously"""
    with app.app_context():
        try:
            from flask_mail import Mail
            mail = Mail(app)
            mail.send(msg)
        except Exception as e:
            print(f"Error sending email: {str(e)}")

def send_email(subject, sender, recipients, text_body, html_body):
    """Send an email"""
    app = current_app._get_current_object()
    msg = Message(subject, sender=sender, recipients=recipients)
    msg.body = text_body
    msg.html = html_body
    
    # Send asynchronously to avoid blocking the request
    Thread(target=send_async_email, args=(app, msg)).start()

def send_exam_graded_email(student, exam_title, score):
    """
    Send email notification when an exam is graded
    
    Args:
        student: User object of the student
        exam_title: Title of the exam
        score: Dictionary with score details
    """
    send_email(
        subject=f"Exam '{exam_title}' has been graded",
        sender=current_app.config['MAIL_DEFAULT_SENDER'],
        recipients=[student.email],
        text_body=render_template(
            'email/exam_graded.txt',
            user=student,
            exam_title=exam_title,
            score=score
        ),
        html_body=render_template(
            'email/exam_graded.html',
            user=student,
            exam_title=exam_title,
            score=score
        )
    )

def send_new_exam_email(student, exam):
    """
    Send email notification when a new exam is published
    
    Args:
        student: User object of the student
        exam: Exam object
    """
    send_email(
        subject=f"New Exam Available: {exam.title}",
        sender=current_app.config['MAIL_DEFAULT_SENDER'],
        recipients=[student.email],
        text_body=render_template(
            'email/new_exam.txt',
            user=student,
            exam=exam
        ),
        html_body=render_template(
            'email/new_exam.html',
            user=student,
            exam=exam
        )
    )

def send_exam_review_email(teacher, exam_title, student_name):
    """
    Send email notification when a student submits a review for an exam
    
    Args:
        teacher: User object of the teacher
        exam_title: Title of the exam
        student_name: Name of the student who submitted the review
    """
    send_email(
        subject=f"New Review for '{exam_title}'",
        sender=current_app.config['MAIL_DEFAULT_SENDER'],
        recipients=[teacher.email],
        text_body=render_template(
            'email/exam_review.txt',
            user=teacher,
            exam_title=exam_title,
            student_name=student_name
        ),
        html_body=render_template(
            'email/exam_review.html',
            user=teacher,
            exam_title=exam_title,
            student_name=student_name
        )
    )