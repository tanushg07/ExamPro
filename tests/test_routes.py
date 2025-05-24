import pytest

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
