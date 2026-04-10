import pytest
from app.models import db, User, Exam


# ---------------------------------------------------------------------------
# Unauthenticated access (uses strict_client which enforces @login_required)
# ---------------------------------------------------------------------------

def test_unauthenticated_dashboard_redirects(strict_client):
    """Accessing /dashboard without login should redirect to login page."""
    response = strict_client.get('/dashboard', follow_redirects=False)
    assert response.status_code == 302
    assert 'login' in response.headers['Location']


def test_unauthenticated_profile_redirects(strict_client):
    response = strict_client.get('/profile', follow_redirects=False)
    assert response.status_code == 302
    assert 'login' in response.headers['Location']


# ---------------------------------------------------------------------------
# Authenticated routes
# ---------------------------------------------------------------------------

def test_dashboard_access(client, student_user):
    # Login as student
    client.post('/login', data={
        'username': 'student',
        'password': 'password'
    }, follow_redirects=True)
    response = client.get('/dashboard')
    assert response.status_code == 200
    assert b'available exams' in response.data or b'completed exams' in response.data


def test_teacher_create_exam(auth_client):
    response = auth_client.get('/teacher/exams/new')
    assert response.status_code == 200
    assert b'Create Exam' in response.data


def test_search_functionality(auth_client, sample_exam):
    response = auth_client.get('/search?q=Test')
    assert response.status_code == 200
    assert b'Test Exam' in response.data


def test_search_no_results(auth_client):
    """Search with no matching exams should return a 200 page (not an error)."""
    response = auth_client.get('/search?q=zzznoresults')
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Role-based access
# ---------------------------------------------------------------------------

def test_student_cannot_access_teacher_exam_creation(client, student_user):
    """A student should not be allowed to access teacher-only pages."""
    client.post('/login', data={
        'username': 'student',
        'password': 'password'
    }, follow_redirects=True)
    response = client.get('/teacher/exams/new', follow_redirects=False)
    # Expect either a redirect or a 403
    assert response.status_code in (302, 403)


def test_admin_page_requires_authentication(strict_client):
    """An unauthenticated request to an admin page should be redirected."""
    response = strict_client.get('/admin/dashboard', follow_redirects=False)
    assert response.status_code in (302, 403)


def test_teacher_review_queue_accessible(auth_client):
    """A logged-in teacher can reach the review queue."""
    response = auth_client.get('/teacher/review-queue')
    assert response.status_code == 200


def test_teacher_analytics_accessible(auth_client):
    """A logged-in teacher can reach the analytics page."""
    response = auth_client.get('/teacher/analytics')
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Error pages
# ---------------------------------------------------------------------------

def test_404_returns_error_page(client):
    response = client.get('/this/route/does/not/exist/at/all')
    assert response.status_code == 404


