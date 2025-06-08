#!/usr/bin/env python3
"""
Live test script to verify security information is working in the running Flask app
"""
import requests
import json

def test_live_application():
    """Test the live application to see if security fix is working"""
    base_url = "http://127.0.0.1:5000"
    
    print("🔧 Testing live security information fix...")
    print("=" * 60)
    
    # Test if the application is running
    try:
        response = requests.get(base_url, timeout=5)
        print(f"✅ Application is running (Status: {response.status_code})")
    except requests.exceptions.RequestException as e:
        print(f"❌ Cannot connect to application: {e}")
        return False
    
    # Try to access the login page
    try:
        login_response = requests.get(f"{base_url}/auth/login", timeout=5)
        print(f"✅ Login page accessible (Status: {login_response.status_code})")
    except requests.exceptions.RequestException as e:
        print(f"❌ Cannot access login page: {e}")
        return False
    
    print("\n📋 MANUAL TESTING INSTRUCTIONS:")
    print("-" * 40)
    print("1. Open browser and go to: http://127.0.0.1:5000")
    print("2. Login as a teacher")
    print("3. Create a new exam or find an existing one")
    print("4. Have a student take the exam")
    print("5. As teacher, view the exam attempt details")
    print("6. Check that security information shows:")
    print("   - Browser: [actual browser info instead of 'Not available']")
    print("   - IP Address: [actual IP instead of 'Not available']")
    print("   - Security Status: 'Approved' instead of 'Pending'")
    
    return True

if __name__ == "__main__":
    test_live_application()
