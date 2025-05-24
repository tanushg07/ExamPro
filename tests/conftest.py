import os
import tempfile
import pytest
from app import create_app
from app.models import db, User, Exam, Question
from config import Config

class TestConfig(Config):
    # Use a separate test database
    SQLALCHEMY_DATABASE_URI = 'mysql+mysqlconnector://root:852456@localhost/exam_platform_test'
    WTF_CSRF_ENABLED = False
    LOGIN_DISABLED = True
    TESTING = True

@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        # Drop all tables first to ensure clean state
        db.drop_all()
        # Create all tables
        db.create_all()
        yield app
        # Cleanup after tests
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def runner(app):
    return app.test_cli_runner()

@pytest.fixture
def admin_user(app):
    user = User(
        username='admin',
        email='admin@example.com',
        user_type='admin'
    )
    user.set_password('password')
    db.session.add(user)
    db.session.commit()
    return user

@pytest.fixture
def teacher_user(app):
    user = User(
        username='teacher',
        email='teacher@example.com',
        user_type='teacher'
    )
    user.set_password('password')
    db.session.add(user)
    db.session.commit()
    return user

@pytest.fixture
def student_user(app):
    user = User(
        username='student',
        email='student@example.com',
        user_type='student'
    )
    user.set_password('password')
    db.session.add(user)
    db.session.commit()
    return user

@pytest.fixture
def auth_client(client, teacher_user):
    client.post('/login', data={
        'username': 'teacher',
        'password': 'password',
    }, follow_redirects=True)
    return client

@pytest.fixture
def sample_exam(app, teacher_user):
    exam = Exam(
        title='Test Exam',
        description='This is a test exam',
        time_limit_minutes=60,
        creator_id=teacher_user.id,
        is_published=True
    )
    db.session.add(exam)
    db.session.flush()
    mcq = Question(
        exam_id=exam.id,
        question_text='What is 2+2?',
        question_type='mcq',
        points=1,
        order=1
    )
    db.session.add(mcq)
    db.session.commit()
    return exam
