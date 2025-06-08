#!/usr/bin/env python3
"""
Update existing ExamAttempt records with default security information
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import ExamAttempt
from app.enums import VerificationStatus
from datetime import datetime

def update_existing_attempts():
    """Update existing ExamAttempt records with default security values"""
    
    app = create_app()
    
    with app.app_context():
        # Find all ExamAttempt records that don't have security info
        attempts_to_update = ExamAttempt.query.filter(
            db.or_(
                ExamAttempt.user_agent.is_(None),
                ExamAttempt.ip_address.is_(None),
                ExamAttempt.verification_status.is_(None)
            )
        ).all()
        
        print(f"Found {len(attempts_to_update)} exam attempts to update...")
        
        for attempt in attempts_to_update:            # Set default values for missing security fields
            if not attempt.user_agent:
                attempt.user_agent = "Unknown Browser (Legacy)"
            if not attempt.ip_address:
                attempt.ip_address = "0.0.0.0"
                
            if not attempt.verification_status:
                if attempt.is_completed:
                    attempt.verification_status = VerificationStatus.APPROVED.value
                else:
                    attempt.verification_status = VerificationStatus.APPROVED.value  # Set to approved instead of pending
            
            # Set other security defaults
            if attempt.browser_fingerprint is None:
                attempt.browser_fingerprint = "legacy-fingerprint"
                
            if attempt.warning_count is None:
                attempt.warning_count = 0
                
            if attempt.focus_losses is None:
                attempt.focus_losses = 0
                
            if attempt.window_switches is None:
                attempt.window_switches = 0
                
            if attempt.environment_verified is None:
                attempt.environment_verified = True  # Assume legacy attempts were valid
            
            print(f"Updated attempt {attempt.id} for student {attempt.student_id}")
        
        # Commit all changes
        try:
            db.session.commit()
            print(f"Successfully updated {len(attempts_to_update)} exam attempts!")
        except Exception as e:
            db.session.rollback()
            print(f"Error updating attempts: {e}")
            return False
    
    return True

if __name__ == "__main__":
    print("Starting security information update for existing exam attempts...")
    success = update_existing_attempts()
    if success:
        print("Update completed successfully!")
    else:
        print("Update failed!")
        sys.exit(1)
