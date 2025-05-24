from app import create_app, db
from app.models import User, Group, GroupMembership

def verify_group_memberships():
    app = create_app()
    with app.app_context():
        print("\n===== VERIFYING GROUP MEMBERSHIPS =====\n")
        
        groups = Group.query.all()
        all_consistent = True
        
        for group in groups:
            print(f"Group: {group.name} (ID: {group.id})")
            
            # Get students from relationship
            students_via_relationship = set(student.id for student in group.students)
            
            # Get students from membership table
            memberships = GroupMembership.query.filter_by(group_id=group.id).all()
            students_via_membership = set(membership.user_id for membership in memberships)
            
            # Check for inconsistencies
            if students_via_relationship != students_via_membership:
                all_consistent = False
                print(f"  WARNING: Inconsistency detected!")
                print(f"  Students in relationship: {len(students_via_relationship)}")
                print(f"  Students in membership table: {len(students_via_membership)}")
                
                # Show missing students
                missing_from_relationship = students_via_membership - students_via_relationship
                if missing_from_relationship:
                    print(f"  Students missing from relationship: {missing_from_relationship}")
                
                missing_from_membership = students_via_relationship - students_via_membership
                if missing_from_membership:
                    print(f"  Students missing from membership table: {missing_from_membership}")
            else:
                print(f"  ✓ Consistent! {len(students_via_relationship)} students")
            
            print()
        
        if all_consistent:
            print("All group memberships are consistent! 🎉")
        else:
            print("Some inconsistencies were found. Run fix_memberships_simple.py to fix them.")

if __name__ == "__main__":
    verify_group_memberships()
