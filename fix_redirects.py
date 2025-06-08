#!/usr/bin/env python3

# Simple script to replace admin_dashboard redirects

import re

def fix_admin_routes():
    file_path = "app/admin_routes.py"
    
    # Read the file
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace all instances of main.admin_dashboard with main.dashboard
    content = content.replace("url_for('main.admin_dashboard')", "url_for('main.dashboard')")
    
    # Write back to file
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("Fixed admin route redirects")

if __name__ == "__main__":
    fix_admin_routes()
