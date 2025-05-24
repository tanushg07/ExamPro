"""
Command-line script to apply all fixes to the examination platform.
This will:
1. Update models to use the fixed version
2. Run database migrations to fix schema issues
3. Update app initialization to use fixed components
"""
import os
import sys
import shutil
import logging
import argparse
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('fix_platform.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def backup_file(filepath):
    """Create a backup of a file with timestamp"""
    if not os.path.exists(filepath):
        logger.error(f"File not found: {filepath}")
        return False
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{filepath}.backup_{timestamp}"
    
    try:
        shutil.copy2(filepath, backup_path)
        logger.info(f"Created backup: {backup_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to backup {filepath}: {str(e)}")
        return False

def replace_file(source, destination):
    """Replace a file with another, creating a backup first"""
    if not backup_file(destination):
        return False
    
    try:
        shutil.copy2(source, destination)
        logger.info(f"Replaced {destination} with {source}")
        return True
    except Exception as e:
        logger.error(f"Failed to replace {destination}: {str(e)}")
        return False

def run_flask_command(command):
    """Run a Flask CLI command"""
    try:
        os.system(f"flask {command}")
        logger.info(f"Successfully ran 'flask {command}'")
        return True
    except Exception as e:
        logger.error(f"Error running 'flask {command}': {str(e)}")
        return False

def run_migration_script():
    """Run the database migration script"""
    try:
        from migrations.fix_schema import run_migration
        run_migration()
        logger.info("Successfully ran database migration")
        return True
    except Exception as e:
        logger.error(f"Error running database migration: {str(e)}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Fix the examination platform")
    parser.add_argument("--skip-backup", action="store_true", help="Skip creating backups")
    parser.add_argument("--skip-migration", action="store_true", help="Skip database migration")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    args = parser.parse_args()
    
    logger.info("Starting platform fixes")
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    app_dir = os.path.join(base_dir, "app")
    
    # Step 1: Check if all required files exist
    required_files = [
        os.path.join(app_dir, "models_fixed.py"),
        os.path.join(app_dir, "__init__fixed.py"),
        os.path.join(app_dir, "enums.py"),
        os.path.join(base_dir, "migrations", "fix_schema.py")
    ]
    
    for file in required_files:
        if not os.path.exists(file):
            logger.error(f"Required file not found: {file}")
            return False
    
    # Step 2: Backup current files if not skipped
    if not args.skip_backup and not args.dry_run:
        files_to_backup = [
            os.path.join(app_dir, "models.py"),
            os.path.join(app_dir, "__init__.py")
        ]
        
        for file in files_to_backup:
            if not backup_file(file):
                logger.error("Backup creation failed, aborting")
                return False
    
    # Step 3: Replace files with fixed versions
    if not args.dry_run:
        replacements = [
            (os.path.join(app_dir, "models_fixed.py"), os.path.join(app_dir, "models.py")),
            (os.path.join(app_dir, "__init__fixed.py"), os.path.join(app_dir, "__init__.py"))
        ]
        
        for source, destination in replacements:
            if not replace_file(source, destination):
                logger.error("File replacement failed, aborting")
                return False
    else:
        logger.info("DRY RUN: Would replace models.py and __init__.py with fixed versions")
    
    # Step 4: Run database migrations if not skipped
    if not args.skip_migration and not args.dry_run:
        logger.info("Running database migration")
        success = run_migration_script()
        if not success:
            logger.error("Database migration failed, aborting")
            return False
    elif args.dry_run:
        logger.info("DRY RUN: Would run database migration script")
    
    # Step 5: Update Flask-Migrate to recognize changes
    if not args.dry_run:
        logger.info("Updating Flask-Migrate")
        run_flask_command("db stamp head")
        run_flask_command("db migrate -m 'Apply fixed models'")
        run_flask_command("db upgrade")
    else:
        logger.info("DRY RUN: Would update Flask-Migrate database")
    
    logger.info("Platform fixes completed successfully")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
