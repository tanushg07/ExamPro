#!/usr/bin/env python3
"""
Test script to verify that new ExamAttempt records get security information initialized
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
from app import create_app, db
from app.models import ExamAttempt, User, Exam
from app.exam_security import ExamSecurity
from flask import Flask
from unittest.mock import Mock, patch

def test_security_initialization():
    """Test that ExamSecurity.initialize_monitoring works correctly"""
    
    app = create_app()
    
    with app.app_context():
        # Create a test request context
        with app.test_request_context(
            '/test', 
            environ_base={'REMOTE_ADDR': '192.168.1.100'},
            headers={'User-Agent': 'Mozilla/5.0 (Test Browser)'}
        ):
            print("Testing ExamSecurity.initialize_monitoring()...")
            
            # Create a mock exam attempt
            attempt = ExamAttempt(
                student_id=1,
                exam_id=1,
                started_at=datetime.utcnow()
            )
            
            # Test the initialize_monitoring function
            try:
                ExamSecurity.initialize_monitoring(attempt)
                
                print(f"✓ IP Address populated: {attempt.ip_address}")
                print(f"✓ User Agent populated: {attempt.user_agent}")
                print(f"✓ Browser fingerprint: {attempt.browser_fingerprint}")
                print(f"✓ Environment verified: {attempt.environment_verified}")
                print(f"✓ Verification status: {attempt.verification_status}")
                
                # Check that key fields are not None
                assert attempt.ip_address is not None, "IP address should be populated"
                assert attempt.user_agent is not None, "User agent should be populated"
                assert attempt.browser_fingerprint is not None, "Browser fingerprint should be populated"
                
                print("\n✅ ExamSecurity.initialize_monitoring() works correctly!")
                return True
                
            except Exception as e:
                print(f"❌ Error testing security initialization: {e}")
                return False

def test_exam_attempt_creation_flow():
    """Test the complete exam attempt creation flow including security initialization"""
    
    app = create_app()
    
    with app.app_context():
        with app.test_request_context(
            '/student/exams/1/take',
            environ_base={'REMOTE_ADDR': '192.168.1.100'},
            headers={'User-Agent': 'Mozilla/5.0 (Test Browser)'}
        ):
            print("\nTesting exam attempt creation flow...")
            
            try:
                # Simulate the exam attempt creation process from routes.py
                attempt = ExamAttempt(
                    student_id=1,
                    exam_id=1,
                    started_at=datetime.utcnow()
                )
                
                # This would normally be done by db.session.add() and flush()
                # but we'll just assign an ID for testing
                attempt.id = 999
                
                # Initialize security monitoring (this is what our fix adds)
                ExamSecurity.initialize_monitoring(attempt)
                
                print(f"✓ Attempt created with security info:")
                print(f"  - IP: {attempt.ip_address}")
                print(f"  - User Agent: {attempt.user_agent}")
                print(f"  - Browser Fingerprint: {attempt.browser_fingerprint}")
                print(f"  - Verification Status: {attempt.verification_status}")
                
                # Verify that the fields that were showing as "Not available" are now populated
                assert attempt.ip_address != "Not available", "IP should not be 'Not available'"
                assert attempt.user_agent != "Not available", "User agent should not be 'Not available'"
                assert attempt.verification_status != "Pending", "Status should not be 'Pending' after initialization"
                
                print("\n✅ Exam attempt creation flow works correctly!")
                return True
                
            except Exception as e:
                print(f"❌ Error testing exam attempt creation: {e}")
                import traceback
                traceback.print_exc()
                return False

if __name__ == "__main__":
    print("🔧 Testing security information initialization fix...")
    print("=" * 60)
    
    test1_pass = test_security_initialization()
    test2_pass = test_exam_attempt_creation_flow()
    
    print("\n" + "=" * 60)
    
    if test1_pass and test2_pass:
        print("🎉 All tests passed! The security information fix is working.")
        print("\nWhat this means:")
        print("- New exam attempts will have IP address, browser info, and security status")
        print("- The 'Not available' and 'Pending' issues should be resolved")
        print("- Teachers will see proper security information in attempt details")
    else:
        print("❌ Some tests failed. Please check the implementation.")
        sys.exit(1)
