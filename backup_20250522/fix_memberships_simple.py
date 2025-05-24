from app import create_app, db
from app.models import User, Group, GroupMembership

app = create_app()

with app.app_context():
    print("\n===== FIXING GROUP MEMBERSHIP ISSUES =====\n")
    
    # Get all groups
    groups = Group.query.all()
    print(f"Total groups: {len(groups)}")
    
    fixed_count = 0
    
    for group in groups:
        print(f"\nChecking Group: {group.name} (ID: {group.id})")
        
        # Get students via relationship
        students_via_relationship = list(group.students)
        print(f"Students via relationship: {len(students_via_relationship)}")
        
        # Get memberships directly
        memberships = GroupMembership.query.filter_by(group_id=group.id).all()
        print(f"Students via memberships: {len(memberships)}")
        
        # Identify inconsistencies
        membership_student_ids = {m.user_id for m in memberships}
        relationship_student_ids = {s.id for s in students_via_relationship}
        
        missing_from_relationship = membership_student_ids - relationship_student_ids
        
        # Fix students missing from relationship
        for student_id in missing_from_relationship:
            student = User.query.get(student_id)
            if student:
                group.students.append(student)
                fixed_count += 1
                print(f"Added {student.username} to group {group.name} relationship")
    
    # Commit changes
    if fixed_count > 0:
        try:
            db.session.commit()
            print(f"\nSuccessfully fixed {fixed_count} membership issues!")
        except Exception as e:
            db.session.rollback()
            print(f"\nError fixing memberships: {str(e)}")
    else:
        print("\nNo membership issues to fix!")
