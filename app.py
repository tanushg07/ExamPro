from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

from app import create_app, db
from app.models import User, Exam, Question, QuestionOption, ExamAttempt, Answer
import sys  # Added for better error handling

app = create_app()

@app.shell_context_processor
def make_shell_context():
    return {
        'db': db, 
        'User': User, 
        'Exam': Exam,
        'Question': Question,
        'QuestionOption': QuestionOption,
        'ExamAttempt': ExamAttempt,
        'Answer': Answer
    }

if __name__ == '__main__':
    print("=" * 50)
    print("STARTING APPLICATION")
    print("=" * 50)
    print("\nChecking database connection...")
    
    # Test database connection
    from sqlalchemy import text
    try:
        with app.app_context():
            # Verify database connection
            result = db.session.execute(text("SELECT 1")).fetchone()
            if result and result[0] == 1:
                print("Database connection successful")
            else:
                print("Database connection verification failed")
                sys.exit(1)
                  # Verify tables exist (optional but recommended)
            try:
                db.session.execute(text("SELECT 1 FROM users LIMIT 1")).fetchone()
            except Exception as e:
                print(f"Warning: Potential database schema issue - {str(e)}")
                # Create tables if they don't exist
                print("Attempting to create missing tables...")
                db.create_all()
                print("Tables created successfully!")
            print("\nInitializing application...")
        app.run(host='0.0.0.0', port=5000, debug=True)  # Added explicit host/port
        
    except Exception as e:
        print(f"\nERROR: Failed to start application - {str(e)}", file=sys.stderr)
        print("\nApplication failed to start. Please check the error message above.")
        sys.exit(1)  # Exit with error code