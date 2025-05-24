from app import create_app, db
from app.models import User, Exam, Question, QuestionOption, ExamAttempt, Answer, ExamReview, Notification, Group, ActivityLog, SecurityLog, GroupMembership

def create_db_tables():
    """Create all database tables based on SQLAlchemy models."""
    print("Creating database tables...")
    app = create_app()
    with app.app_context():
        db.create_all()
        
        # Verify tables were created
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        print("\nCreated tables:")
        for table in tables:
            print(f" - {table}")
        
        if 'users' in tables:
            print("\nSuccess! The 'users' table was created correctly.")
        else:
            print("\nWarning: The 'users' table was not created.")
            
        print("\nDatabase initialization complete.")

if __name__ == "__main__":
    create_db_tables()
