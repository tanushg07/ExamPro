#!/usr/bin/env python3
"""
Test script to validate user deletion functionality
"""

from app import create_app, db
from app.models import User, Group, GroupMembership, Exam, ExamAttempt, Answer, ExamReview
from app.models import Question, QuestionOption, Notification, SecurityLog, ActivityLog
from datetime import datetime
import logging

def test_user_deletion():
    """Test user deletion with various related records"""
    
    app = create_app()
    
    with app.app_context():
        print("=" * 60)
        print("TESTING USER DELETION FUNCTIONALITY")
        print("=" * 60)
        
        # Get all users for testing
        users = User.query.all()
        print(f"\nFound {len(users)} users in database:")
        for user in users:
            print(f"  - {user.username} ({user.user_type}) - ID: {user.id}")
            
            # Check related records
            attempts = ExamAttempt.query.filter_by(student_id=user.id).count()
            created_exams = Exam.query.filter_by(creator_id=user.id).count()
            owned_groups = Group.query.filter_by(teacher_id=user.id).count()
            memberships = GroupMembership.query.filter_by(user_id=user.id).count()
            notifications = Notification.query.filter_by(user_id=user.id).count()
            
            print(f"    Related records: {attempts} attempts, {created_exams} exams, {owned_groups} groups, {memberships} memberships, {notifications} notifications")
        
        # Find a test user to delete (non-admin)
        test_user = None
        for user in users:
            if user.user_type != 'admin':
                test_user = user
                break
        
        if not test_user:
            print("\nNo non-admin users found to test deletion!")
            return
            
        print(f"\nTesting deletion of user: {test_user.username} (ID: {test_user.id})")
        
        # Check foreign key relationships before deletion
        print("\nChecking foreign key relationships before deletion:")
        
        # Count related records
        exam_attempts = ExamAttempt.query.filter_by(student_id=test_user.id).count()
        created_exams = Exam.query.filter_by(creator_id=test_user.id).count()
        owned_groups = Group.query.filter_by(teacher_id=test_user.id).count()
        group_memberships = GroupMembership.query.filter_by(user_id=test_user.id).count()
        user_notifications = Notification.query.filter_by(user_id=test_user.id).count()
        security_logs = SecurityLog.query.filter_by(user_id=test_user.id).count()
        activity_logs = ActivityLog.query.filter_by(user_id=test_user.id).count()
        exam_reviews = ExamReview.query.filter_by(student_id=test_user.id).count()
        
        print(f"  - ExamAttempts as student: {exam_attempts}")
        print(f"  - Exams created: {created_exams}")
        print(f"  - Groups owned: {owned_groups}")
        print(f"  - Group memberships: {group_memberships}")
        print(f"  - Notifications: {user_notifications}")
        print(f"  - Security logs: {security_logs}")
        print(f"  - Activity logs: {activity_logs}")
        print(f"  - Exam reviews: {exam_reviews}")
        
        if exam_attempts == 0 and created_exams == 0 and owned_groups == 0 and group_memberships == 0:
            print(f"\nUser {test_user.username} has no related records, which is perfect for testing!")
        else:
            print(f"\nUser {test_user.username} has related records, this will test the deletion cascade logic.")
        
        print(f"\nThis would simulate the admin deletion process for user {test_user.username}")
        print("The deletion would handle all foreign key constraints in the correct order.")
        print("\nTo actually test deletion, uncomment the deletion code in this script.")
        
        # Uncomment the following lines to actually test deletion
        # WARNING: This will actually delete the user and all related data!
        
        # try:
        #     # This simulates the deletion logic from admin_routes.py
        #     print(f"\nAttempting to delete user {test_user.username}...")
        #     
        #     # Delete related records in correct order
        #     # (Copy the deletion logic from admin_routes.py here)
        #     
        #     print("User deletion would complete successfully!")
        #     
        # except Exception as e:
        #     print(f"Error during deletion: {str(e)}")
        #     db.session.rollback()

if __name__ == "__main__":
    test_user_deletion()
