import os
import mysql.connector
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def setup_database():
    # Get database configuration from environment
    db_config = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'user': os.getenv('DB_USER'),
        'password': os.getenv('DB_PASSWORD'),
        'database': os.getenv('DB_NAME', 'exam_platform')
    }

    try:
        # Create connection without database
        conn = mysql.connector.connect(
            host=db_config['host'],
            user=db_config['user'],
            password=db_config['password']
        )
        cursor = conn.cursor()

        # Create database if it doesn't exist
        print("Creating database if it doesn't exist...")
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_config['database']}")
        cursor.execute(f"USE {db_config['database']}")

        # Read and execute schema file
        print("Creating tables...")
        with open('exam_platform.sql', 'r') as f:
            schema = f.read()
            for statement in schema.split(';'):
                if statement.strip():
                    cursor.execute(statement)
            conn.commit()

        # Read and execute sample data if in development
        if os.getenv('FLASK_ENV') == 'development':
            print("Inserting sample data...")
            with open('insert_data.sql', 'r') as f:
                data = f.read()
                for statement in data.split(';'):
                    if statement.strip():
                        try:
                            cursor.execute(statement)
                            conn.commit()
                        except mysql.connector.Error as err:
                            print(f"Error executing statement: {err}")
                            conn.rollback()

        print("Database setup completed successfully!")

    except mysql.connector.Error as err:
        print(f"Error: {err}")
        raise

    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

if __name__ == '__main__':
    setup_database()
