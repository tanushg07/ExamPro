from app.models import User, Exam, ExamReview

def test_user_password_hashing(app):
    user = User(username='testuser', email='test@example.com', user_type='student')
    user.set_password('securepassword')
    assert user.check_password('securepassword')
    assert not user.check_password('wrongpassword')

def test_exam_average_rating(app, teacher_user):
    exam = Exam(title='Exam', description='desc', time_limit_minutes=30, creator_id=teacher_user.id, is_published=True)
    from app.models import db
    db.session.add(exam)
    db.session.commit()
    # No reviews yet
    assert exam.get_average_rating() is None
    # Add reviews
    review1 = ExamReview(exam_id=exam.id, student_id=teacher_user.id, rating=4)
    review2 = ExamReview(exam_id=exam.id, student_id=teacher_user.id, rating=2)
    db.session.add_all([review1, review2])
    db.session.commit()
    assert exam.get_average_rating() == 3.0
