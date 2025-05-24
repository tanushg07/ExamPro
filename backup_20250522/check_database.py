from app import create_app, db
from app.models import User, Exam, Question, QuestionOption, ExamAttempt, Answer, ExamReview, Notification, Group, ActivityLog

def check_and_create_tables():
    """
    Check if tables exist and create them if they don't.
    This function will use SQLAlchemy to create tables based on the models.
    """
    print("Initializing application...")
    app = create_app()
    
    with app.app_context():
        # Check if users table exists
        try:
            result = db.session.execute(db.text("SELECT 1 FROM users LIMIT 1"))
            print("Users table exists!")
        except Exception as e:
            print(f"Users table check failed: {e}")
            print("Creating all tables based on models...")
            db.create_all()
            print("Tables created successfully!")
        
        # Print all table names to verify
        print("\nVerifying database tables:")
        insp = db.inspect(db.engine)
        tables = insp.get_table_names()
        for table in tables:
            print(f" - {table}")

if __name__ == "__main__":
    check_and_create_tables()
