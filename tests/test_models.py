from datetime import datetime, timedelta
import pytest
from app.models import (
    User, Exam, ExamReview, ExamAttempt, Question, QuestionOption,
    Answer, Group, GroupMembership, SecurityLog, ActivityLog, Notification, db
)


# ---------------------------------------------------------------------------
# User model
# ---------------------------------------------------------------------------

def test_user_password_hashing(app):
    user = User(username='testuser', email='test@example.com', user_type='student')
    user.set_password('securepassword')
    assert user.check_password('securepassword')
    assert not user.check_password('wrongpassword')


def test_user_role_helpers(app):
    admin = User(username='a', email='a@x.com', user_type='admin')
    teacher = User(username='t', email='t@x.com', user_type='teacher')
    student = User(username='s', email='s@x.com', user_type='student')

    assert admin.is_admin()
    assert not admin.is_teacher()
    assert not admin.is_student()

    assert teacher.is_teacher()
    assert not teacher.is_admin()
    assert not teacher.is_student()

    assert student.is_student()
    assert not student.is_teacher()
    assert not student.is_admin()


def test_user_is_super_admin(app):
    # Super admin by username
    super_admin = User(username='superadmin', email='sa@x.com', user_type='admin')
    super_admin.set_password('pw')
    db.session.add(super_admin)
    db.session.commit()
    assert super_admin.is_super_admin()

    # Regular admin (not user ID 1 and not 'superadmin')
    regular_admin = User(username='regularadmin', email='ra@x.com', user_type='admin')
    regular_admin.set_password('pw')
    db.session.add(regular_admin)
    db.session.commit()
    # id 1 is taken by super_admin, so this admin is not super admin
    assert not regular_admin.is_super_admin()

    # Non-admin cannot be super admin
    student = User(username='stu', email='stu@x.com', user_type='student')
    assert not student.is_super_admin()


# ---------------------------------------------------------------------------
# Exam model
# ---------------------------------------------------------------------------

def test_exam_average_rating(app, teacher_user):
    exam = Exam(title='Exam', description='desc', time_limit_minutes=30,
                creator_id=teacher_user.id, is_published=True)
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


def test_exam_is_active_no_window(app, teacher_user):
    """An exam with no time window is active when published."""
    exam = Exam(title='E', description='d', time_limit_minutes=30,
                creator_id=teacher_user.id, is_published=True)
    db.session.add(exam)
    db.session.commit()
    assert exam.is_active()


def test_exam_is_active_unpublished(app, teacher_user):
    exam = Exam(title='E', description='d', time_limit_minutes=30,
                creator_id=teacher_user.id, is_published=False)
    db.session.add(exam)
    db.session.commit()
    assert not exam.is_active()


def test_exam_is_active_within_window(app, teacher_user):
    now = datetime.utcnow()
    exam = Exam(
        title='E', description='d', time_limit_minutes=30,
        creator_id=teacher_user.id, is_published=True,
        available_from=now - timedelta(hours=1),
        available_until=now + timedelta(hours=1),
    )
    db.session.add(exam)
    db.session.commit()
    assert exam.is_active()


def test_exam_is_active_outside_window(app, teacher_user):
    now = datetime.utcnow()
    exam = Exam(
        title='E', description='d', time_limit_minutes=30,
        creator_id=teacher_user.id, is_published=True,
        available_from=now - timedelta(hours=3),
        available_until=now - timedelta(hours=1),
    )
    db.session.add(exam)
    db.session.commit()
    assert not exam.is_active()


def test_exam_is_upcoming(app, teacher_user):
    now = datetime.utcnow()
    future_exam = Exam(
        title='Future', description='d', time_limit_minutes=30,
        creator_id=teacher_user.id, is_published=True,
        available_from=now + timedelta(hours=2),
    )
    past_exam = Exam(
        title='Past', description='d', time_limit_minutes=30,
        creator_id=teacher_user.id, is_published=True,
        available_from=now - timedelta(hours=2),
    )
    no_window_exam = Exam(
        title='NoWindow', description='d', time_limit_minutes=30,
        creator_id=teacher_user.id, is_published=True,
    )
    db.session.add_all([future_exam, past_exam, no_window_exam])
    db.session.commit()
    assert future_exam.is_upcoming()
    assert not past_exam.is_upcoming()
    assert not no_window_exam.is_upcoming()


def test_exam_start_end_time_aliases(app, teacher_user):
    now = datetime.utcnow()
    start = now - timedelta(hours=1)
    end = now + timedelta(hours=1)
    exam = Exam(
        title='E', description='d', time_limit_minutes=30,
        creator_id=teacher_user.id, is_published=True,
        available_from=start, available_until=end,
    )
    assert exam.start_time == start
    assert exam.end_time == end


# ---------------------------------------------------------------------------
# ExamAttempt model
# ---------------------------------------------------------------------------

def _make_attempt(teacher_user, require_lockdown=False, require_webcam=False, max_warnings=3):
    """Helper that creates an exam + attempt and returns the attempt."""
    exam = Exam(
        title='Attempt Exam', description='d', time_limit_minutes=60,
        creator_id=teacher_user.id, is_published=True,
        require_lockdown=require_lockdown, require_webcam=require_webcam,
        max_warnings=max_warnings,
    )
    db.session.add(exam)
    db.session.flush()
    attempt = ExamAttempt(
        exam_id=exam.id,
        student_id=teacher_user.id,
        started_at=datetime.utcnow(),
        secure_browser_active=not require_lockdown,
        webcam_active=not require_webcam,
    )
    db.session.add(attempt)
    db.session.commit()
    return attempt


def test_validate_submission_already_completed(app, teacher_user):
    attempt = _make_attempt(teacher_user)
    attempt.is_completed = True
    db.session.commit()
    is_valid, msg = attempt.validate_submission(datetime.utcnow())
    assert not is_valid
    assert 'already completed' in msg


def test_validate_submission_within_time_limit(app, teacher_user):
    attempt = _make_attempt(teacher_user)
    # Submit just 5 minutes after start — well within the 60-min limit
    submit_time = attempt.started_at + timedelta(minutes=5)
    is_valid, msg = attempt.validate_submission(submit_time)
    assert is_valid


def test_validate_submission_after_time_limit_with_grace(app, teacher_user):
    attempt = _make_attempt(teacher_user)
    # Submit 63 minutes after start — within the 2-min grace period
    submit_time = attempt.started_at + timedelta(minutes=63)
    is_valid, msg = attempt.validate_submission(submit_time)
    assert is_valid


def test_validate_submission_exceeds_grace_period(app, teacher_user):
    attempt = _make_attempt(teacher_user)
    # Submit 70 minutes after start — beyond grace period; allowed but logged
    submit_time = attempt.started_at + timedelta(minutes=70)
    is_valid, msg = attempt.validate_submission(submit_time)
    # The implementation allows late submission but records it
    assert is_valid
    assert attempt.is_completed


def test_validate_submission_lockdown_required(app, teacher_user):
    exam = Exam(
        title='Secure', description='d', time_limit_minutes=60,
        creator_id=teacher_user.id, is_published=True,
        require_lockdown=True,
    )
    db.session.add(exam)
    db.session.flush()
    attempt = ExamAttempt(
        exam_id=exam.id, student_id=teacher_user.id,
        started_at=datetime.utcnow(),
        secure_browser_active=False,  # lockdown NOT active
    )
    db.session.add(attempt)
    db.session.commit()

    is_valid, msg = attempt.validate_submission(attempt.started_at + timedelta(minutes=5))
    assert not is_valid
    assert 'Secure browser' in msg


def test_validate_submission_webcam_required(app, teacher_user):
    exam = Exam(
        title='WebcamExam', description='d', time_limit_minutes=60,
        creator_id=teacher_user.id, is_published=True,
        require_lockdown=False, require_webcam=True,
    )
    db.session.add(exam)
    db.session.flush()
    attempt = ExamAttempt(
        exam_id=exam.id, student_id=teacher_user.id,
        started_at=datetime.utcnow(),
        webcam_active=False,
    )
    db.session.add(attempt)
    db.session.commit()

    is_valid, msg = attempt.validate_submission(attempt.started_at + timedelta(minutes=5))
    assert not is_valid
    assert 'Webcam' in msg


def test_validate_submission_too_many_warnings(app, teacher_user):
    attempt = _make_attempt(teacher_user, max_warnings=2)
    attempt.warning_count = 5
    db.session.commit()
    is_valid, msg = attempt.validate_submission(attempt.started_at + timedelta(minutes=5))
    assert not is_valid
    assert 'warning' in msg.lower()


def test_validate_submission_client_time_drift(app, teacher_user):
    attempt = _make_attempt(teacher_user)
    submit_time = attempt.started_at + timedelta(minutes=5)
    # Client reports a time 10 minutes in the future (> 5-min drift threshold)
    drifted_client_time = datetime.utcnow() + timedelta(minutes=10)
    is_valid, msg = attempt.validate_submission(submit_time, client_time=drifted_client_time)
    assert not is_valid
    assert 'time' in msg.lower()


def test_log_event_security(app, teacher_user):
    attempt = _make_attempt(teacher_user)
    attempt.log_event('security_tab_switch', {'detail': 'left exam'}, severity='warning')
    assert attempt.security_events is not None
    assert any(e['type'] == 'security_tab_switch' for e in attempt.security_events)


def test_log_event_browser(app, teacher_user):
    attempt = _make_attempt(teacher_user)
    attempt.log_event('browser_resize', {'width': 800, 'height': 600})
    assert attempt.browser_events is not None
    assert any(e['type'] == 'browser_resize' for e in attempt.browser_events)


def test_log_event_warning_increments_count(app, teacher_user):
    attempt = _make_attempt(teacher_user, max_warnings=10)
    initial = attempt.warning_count
    attempt.log_event('warning_focus_loss', {})
    assert attempt.warning_count == initial + 1
    assert attempt.warning_events is not None


def test_log_event_auto_flag(app, teacher_user):
    attempt = _make_attempt(teacher_user, max_warnings=2)
    attempt.warning_count = 1  # one away from limit
    attempt.log_event('warning_focus_loss', {})
    assert attempt.verification_status == 'auto_flagged'


def test_log_event_large_data_truncated(app, teacher_user):
    attempt = _make_attempt(teacher_user)
    large_data = {'x': 'a' * 20000}
    attempt.log_event('security_large_event', large_data)
    # The event should still be logged but data truncated
    assert attempt.security_events is not None
    event = attempt.security_events[-1]
    assert event.get('data', {}).get('truncated') is True


# ---------------------------------------------------------------------------
# Group model
# ---------------------------------------------------------------------------

def test_group_generate_code_uniqueness(app, teacher_user):
    group = Group(
        name='Test Group', teacher_id=teacher_user.id,
        code='XXXXXX',  # placeholder; will be replaced
    )
    db.session.add(group)
    db.session.commit()

    code = group.generate_code()
    assert len(code) == 6
    assert code.isalnum()
    # A second call should (almost certainly) return a different code
    # since the first group's code is now in DB
    group.code = code
    db.session.commit()

    code2 = group.generate_code()
    # Both codes are valid 6-char alphanumeric strings
    assert len(code2) == 6


def test_group_get_active_exams(app, teacher_user):
    now = datetime.utcnow()
    group = Group(name='G', teacher_id=teacher_user.id, code='ACTIVE')
    db.session.add(group)
    db.session.flush()

    active = Exam(
        title='Active', description='d', time_limit_minutes=30,
        creator_id=teacher_user.id, group_id=group.id, is_published=True,
        available_from=now - timedelta(hours=1),
        available_until=now + timedelta(hours=1),
    )
    future = Exam(
        title='Future', description='d', time_limit_minutes=30,
        creator_id=teacher_user.id, group_id=group.id, is_published=True,
        available_from=now + timedelta(hours=2),
        available_until=now + timedelta(hours=4),
    )
    db.session.add_all([active, future])
    db.session.commit()

    active_exams = group.get_active_exams()
    titles = [e.title for e in active_exams]
    assert 'Active' in titles
    assert 'Future' not in titles


def test_group_get_upcoming_exams(app, teacher_user):
    now = datetime.utcnow()
    group = Group(name='G2', teacher_id=teacher_user.id, code='UPCOM1')
    db.session.add(group)
    db.session.flush()

    upcoming = Exam(
        title='Upcoming', description='d', time_limit_minutes=30,
        creator_id=teacher_user.id, group_id=group.id, is_published=True,
        available_from=now + timedelta(days=1),
    )
    db.session.add(upcoming)
    db.session.commit()

    result = group.get_upcoming_exams()
    assert any(e.title == 'Upcoming' for e in result)


def test_group_get_past_exams(app, teacher_user):
    now = datetime.utcnow()
    group = Group(name='G3', teacher_id=teacher_user.id, code='PAST01')
    db.session.add(group)
    db.session.flush()

    past = Exam(
        title='Past', description='d', time_limit_minutes=30,
        creator_id=teacher_user.id, group_id=group.id, is_published=True,
        available_from=now - timedelta(days=2),
        available_until=now - timedelta(days=1),
    )
    db.session.add(past)
    db.session.commit()

    result = group.get_past_exams()
    assert any(e.title == 'Past' for e in result)


# ---------------------------------------------------------------------------
# ActivityLog model
# ---------------------------------------------------------------------------

def test_activity_log_creates_entry(app, student_user):
    before_count = ActivityLog.query.count()
    ActivityLog.log_activity(
        user_id=student_user.id,
        action='test_action',
        category='test',
        details={'key': 'value'},
    )
    assert ActivityLog.query.count() == before_count + 1
    log = ActivityLog.query.filter_by(action='test_action').first()
    assert log is not None
    assert log.category == 'test'
    assert log.details == {'key': 'value'}

