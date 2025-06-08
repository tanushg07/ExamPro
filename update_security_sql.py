#!/usr/bin/env python3
"""
Simple SQL script to update existing ExamAttempt records with default security information
"""

print("SQL commands to run in your MySQL database:")
print("=" * 60)
print()

sql_commands = [
    "-- Update NULL user_agent values",
    "UPDATE exam_attempts SET user_agent = 'Unknown Browser (Legacy)' WHERE user_agent IS NULL;",
    "",
    "-- Update NULL ip_address values", 
    "UPDATE exam_attempts SET ip_address = '0.0.0.0' WHERE ip_address IS NULL;",
    "",
    "-- Update NULL verification_status values",
    "UPDATE exam_attempts SET verification_status = 'approved' WHERE verification_status IS NULL;",
    "",
    "-- Update NULL browser_fingerprint values",
    "UPDATE exam_attempts SET browser_fingerprint = 'legacy-fingerprint' WHERE browser_fingerprint IS NULL;",
    "",
    "-- Update NULL warning_count values",
    "UPDATE exam_attempts SET warning_count = 0 WHERE warning_count IS NULL;",
    "",
    "-- Update NULL focus_losses values", 
    "UPDATE exam_attempts SET focus_losses = 0 WHERE focus_losses IS NULL;",
    "",
    "-- Update NULL window_switches values",
    "UPDATE exam_attempts SET window_switches = 0 WHERE window_switches IS NULL;",
    "",
    "-- Check the results",
    "SELECT id, user_agent, ip_address, verification_status FROM exam_attempts LIMIT 10;",
]

for cmd in sql_commands:
    print(cmd)

print()
print("INSTRUCTIONS:")
print("-" * 20)
print("1. Connect to your MySQL database")
print("2. Run the above SQL commands")
print("3. This will populate all NULL security fields with default values")
print("4. After running, test creating a new exam attempt to verify the fix")
