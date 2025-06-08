#!/usr/bin/env python3
import os
import re

def fix_all_admin_references():
    # Files to update
    files_to_update = [
        "app/admin_routes.py",
        "app/routes.py", 
        "templates/admin/create_user.html",
        "templates/admin/create_exam.html", 
        "templates/admin/edit_user.html",
        "templates/admin/all_activities.html",
        "templates/admin/settings.html"
    ]
    
    for file_path in files_to_update:
        if os.path.exists(file_path):
            print(f"Fixing {file_path}...")
            
            # Read the file
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Replace all instances
            content = content.replace("url_for('main.admin_dashboard')", "url_for('main.dashboard')")
            content = content.replace("Admin Dashboard", "Dashboard")
            
            # Write back to file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"Fixed {file_path}")
        else:
            print(f"File not found: {file_path}")

if __name__ == "__main__":
    fix_all_admin_references()
