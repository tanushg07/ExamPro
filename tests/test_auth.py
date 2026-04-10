import pytest
from app.models import User


def test_register_redirects_to_login(client):
    """Registration is disabled; any POST to /register should redirect to login."""
    response = client.post('/register', data={
        'username': 'newuser',
        'email': 'newuser@example.com',
        'password': 'newpassword123',
        'confirm_password': 'newpassword123',
        'user_type': 'student',
    }, follow_redirects=False)
    # Expect a redirect (302) pointing to the login page
    assert response.status_code == 302
    assert 'login' in response.headers['Location']


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


def test_login_success_redirects_to_dashboard(client, student_user):
    """A valid login should redirect to the dashboard."""
    response = client.post('/login', data={
        'username': 'student',
        'password': 'password'
    }, follow_redirects=False)
    assert response.status_code == 302
    assert 'dashboard' in response.headers['Location']


def test_login_get_returns_form(client):
    """GET /login should return the login page."""
    response = client.get('/login')
    assert response.status_code == 200
    assert b'Login' in response.data


def test_already_authenticated_redirected(client, student_user):
    """An already-logged-in user hitting /login should be redirected."""
    client.post('/login', data={
        'username': 'student',
        'password': 'password'
    }, follow_redirects=True)
    response = client.get('/login', follow_redirects=False)
    # Should redirect away from the login page
    assert response.status_code == 302
