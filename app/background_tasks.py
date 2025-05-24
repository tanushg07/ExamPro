"""
Background task scheduler for the application.
This runs periodic tasks in the background.
"""

import threading
import time
import logging
from datetime import datetime, timedelta
from typing import Callable, Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Store for registered tasks
tasks = {}
running = False
stop_event = threading.Event()

def register_task(func: Callable, interval: int, name: str = None):
    """
    Register a task to be run at specified intervals.
    
    Args:
        func: The function to run
        interval: Interval in seconds
        name: Optional name for the task (defaults to function name)
    """
    task_name = name or func.__name__
    tasks[task_name] = {
        'func': func,
        'interval': interval,
        'last_run': None,
        'next_run': datetime.now()
    }
    logger.info(f"Registered task: {task_name} to run every {interval} seconds")
    return task_name

def start_scheduler(app):
    """
    Start the task scheduler in a background thread
    
    Args:
        app: Flask application instance for context
    """
    global running
    if running:
        logger.warning("Scheduler is already running")
        return
    
    running = True
    
    # Run the scheduler in a separate thread
    scheduler_thread = threading.Thread(target=_run_scheduler, args=(app,))
    scheduler_thread.daemon = True  # Daemon thread will close when main thread exits
    scheduler_thread.start()
    
    logger.info("Background task scheduler started")

def _run_scheduler(app):
    """
    Main scheduler loop - runs in a separate thread
    
    Args:
        app: Flask application instance for context
    """
    while not stop_event.is_set():
        now = datetime.now()
        
        for name, task in tasks.items():
            # Check if it's time to run this task
            if task['next_run'] <= now:
                logger.info(f"Running task: {name}")
                  # Run the task with app context
                with app.app_context():
                    try:
                        # First verify database connection is available
                        from app.models import db
                        try:
                            # Test the database connection before proceeding
                            db.session.execute("SELECT 1").fetchone()
                        except Exception as conn_error:
                            logger.error(f"Database connection not available for task {name}: {str(conn_error)}")
                            continue  # Skip this task execution
                            
                        # Run the task
                        task['func']()
                        logger.info(f"Task {name} completed successfully")
                    except Exception as e:
                        logger.error(f"Error running task {name}: {str(e)}")
                        try:
                            # Clean up any failed db transactions
                            from app.models import db
                            db.session.rollback()
                        except Exception as db_error:
                            logger.error(f"Failed to roll back transaction: {str(db_error)}")
                
                # Update last_run and schedule next run
                task['last_run'] = now
                task['next_run'] = now + timedelta(seconds=task['interval'])
        
        # Sleep for a bit to avoid high CPU usage
        time.sleep(5)
    
    logger.info("Background task scheduler stopped")

def stop_scheduler():
    """Stop the scheduler"""
    global running
    if running:
        stop_event.set()
        running = False
        logger.info("Stopping background task scheduler")
