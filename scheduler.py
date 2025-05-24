"""
Scheduler for periodic tasks like sending notifications about exam deadlines.
This can be run independently via a cron job or scheduled task.
"""

import os
import sys
from datetime import datetime

# Add the current directory to the path so we can import from the app package
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the app and initialize it
from app import create_app
from app.notifications import notify_exam_deadline_approaching

def run_scheduled_tasks():
    """Run all scheduled tasks"""
    print(f"[{datetime.now()}] Running scheduled tasks...")
    
    # Create app context
    app = create_app()
    with app.app_context():
        # Send notifications about upcoming exam deadlines
        notify_exam_deadline_approaching()
        print(f"[{datetime.now()}] Sent notifications about upcoming exam deadlines")
    
    print(f"[{datetime.now()}] Scheduled tasks complete")

if __name__ == "__main__":
    run_scheduled_tasks()
