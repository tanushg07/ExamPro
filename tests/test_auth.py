import pytest
from app.models import User

def test_register_and_login(client, app):    # Register a new user
    with app.app_context():
        response = client.post('/register', data={
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'newpassword123',
            'password_confirm': 'newpassword123',  # Correct field name
            'user_type': 'student',
            'csrf_token': 'dummy'  # Add CSRF token since WTF_CSRF_ENABLED is True
        }, follow_redirects=True)
        # Check that the user was created
        assert User.query.filter_by(username='newuser').first() is not None

    # Login with the new user
    response = client.post('/login', data={
        'username': 'newuser',
        'password': 'newpassword123'
    }, follow_redirects=True)
    assert b'dashboard' in response.data or b'Logout' in response.data


def test_invalid_login(client, app, student_user):
    # Wrong password
    response = client.post('/login', data={
        'username': 'student',
        'password': 'wrongpassword'
    }, follow_redirects=True)
    assert b'Invalid username or password' in response.data

    # Nonexistent user
    response = client.post('/login', data={
        'username': 'ghost',
        'password': 'irrelevant'
    }, follow_redirects=True)
    assert b'Invalid username or password' in response.data


def test_logout(client, app, student_user):
    # Login first
    client.post('/login', data={
        'username': 'student',
        'password': 'password'
    }, follow_redirects=True)
    # Logout
    response = client.get('/logout', follow_redirects=True)
    assert b'logged out' in response.data or b'Login' in response.data
