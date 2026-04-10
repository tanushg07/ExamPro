"""
Tests for the enums module.
Verifies that every enum has the expected members and that the convenience
string-list helpers are correctly derived from those members.
"""
import pytest
from app.enums import (
    VerificationStatus,
    UserType,
    QuestionType,
    NotificationType,
    SecurityEventType,
    SecuritySeverity,
    verification_status_enum,
    user_type_enum,
    question_type_enum,
    notification_type_enum,
    security_event_type_enum,
    security_severity_enum,
)


# ---------------------------------------------------------------------------
# VerificationStatus
# ---------------------------------------------------------------------------

def test_verification_status_members():
    assert VerificationStatus.PENDING.value == 'pending'
    assert VerificationStatus.APPROVED.value == 'approved'
    assert VerificationStatus.FLAGGED.value == 'flagged'
    assert VerificationStatus.AUTO_FLAGGED.value == 'auto_flagged'


def test_verification_status_list():
    assert set(verification_status_enum) == {'pending', 'approved', 'flagged', 'auto_flagged'}
    assert len(verification_status_enum) == len(VerificationStatus)


# ---------------------------------------------------------------------------
# UserType
# ---------------------------------------------------------------------------

def test_user_type_members():
    assert UserType.ADMIN.value == 'admin'
    assert UserType.TEACHER.value == 'teacher'
    assert UserType.STUDENT.value == 'student'


def test_user_type_list():
    assert set(user_type_enum) == {'admin', 'teacher', 'student'}
    assert len(user_type_enum) == len(UserType)


# ---------------------------------------------------------------------------
# QuestionType
# ---------------------------------------------------------------------------

def test_question_type_members():
    assert QuestionType.MCQ.value == 'mcq'
    assert QuestionType.TEXT.value == 'text'
    assert QuestionType.CODE.value == 'code'


def test_question_type_list():
    assert set(question_type_enum) == {'mcq', 'text', 'code'}
    assert len(question_type_enum) == len(QuestionType)


# ---------------------------------------------------------------------------
# NotificationType
# ---------------------------------------------------------------------------

def test_notification_type_members():
    assert NotificationType.INFO.value == 'info'
    assert NotificationType.EXAM_GRADED.value == 'exam_graded'
    assert NotificationType.EXAM_CREATED.value == 'exam_created'
    assert NotificationType.DEADLINE_APPROACHING.value == 'deadline_approaching'
    assert NotificationType.GROUP_INVITE.value == 'group_invite'


def test_notification_type_list():
    expected = {'info', 'exam_graded', 'exam_created', 'deadline_approaching', 'group_invite'}
    assert set(notification_type_enum) == expected
    assert len(notification_type_enum) == len(NotificationType)


# ---------------------------------------------------------------------------
# SecurityEventType
# ---------------------------------------------------------------------------

def test_security_event_type_members():
    assert SecurityEventType.LOGIN_FAIL.value == 'login_fail'
    assert SecurityEventType.ACCESS_VIOLATION.value == 'access_violation'
    assert SecurityEventType.SUSPICIOUS_ACTIVITY.value == 'suspicious_activity'
    assert SecurityEventType.EXAM_FLAGGED.value == 'exam_flagged'


def test_security_event_type_list():
    expected = {'login_fail', 'access_violation', 'suspicious_activity', 'exam_flagged'}
    assert set(security_event_type_enum) == expected
    assert len(security_event_type_enum) == len(SecurityEventType)


# ---------------------------------------------------------------------------
# SecuritySeverity
# ---------------------------------------------------------------------------

def test_security_severity_members():
    assert SecuritySeverity.LOW.value == 'low'
    assert SecuritySeverity.MEDIUM.value == 'medium'
    assert SecuritySeverity.HIGH.value == 'high'


def test_security_severity_list():
    assert set(security_severity_enum) == {'low', 'medium', 'high'}
    assert len(security_severity_enum) == len(SecuritySeverity)


# ---------------------------------------------------------------------------
# Enum uniqueness – no two members should share the same value
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("enum_cls", [
    VerificationStatus,
    UserType,
    QuestionType,
    NotificationType,
    SecurityEventType,
    SecuritySeverity,
])
def test_enum_values_are_unique(enum_cls):
    values = [m.value for m in enum_cls]
    assert len(values) == len(set(values)), f"Duplicate values found in {enum_cls.__name__}"
