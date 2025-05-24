"""
Group Membership Fixer

This script diagnoses and fixes issues with group memberships in the database.
It checks both sides of the User-Group many-to-many relationship and ensures
they're in sync.
"""

from app import create_app, db
from app.models import User, Group, GroupMembership

app = create_app()
with app.app_context():
    print("\n===== DIAGNOSING GROUP MEMBERSHIP ISSUES =====\n")
    
    # Get all groups
    groups = Group.query.all()
    print(f"Total groups: {len(groups)}")
    
    # Check each group
    for group in groups:
        print(f"\nChecking Group: {group.name} (ID: {group.id})")
        print(f"Teacher: {User.query.get(group.teacher_id).username if User.query.get(group.teacher_id) else 'Unknown'}")
        
        # Get students via relationship
        students_via_relationship = list(group.students)
        print(f"Students via group.students: {len(students_via_relationship)}")
        for student in students_via_relationship:
            print(f"  - {student.username} (ID: {student.id})")
        
        # Get memberships directly from join table
        memberships = GroupMembership.query.filter_by(group_id=group.id).all()
        print(f"Memberships in GroupMembership table: {len(memberships)}")
        for membership in memberships:
            student = User.query.get(membership.user_id)
            print(f"  - {student.username if student else 'Unknown'} (ID: {membership.user_id})")
        
        # Check for mismatches
        membership_student_ids = {m.user_id for m in memberships}
        relationship_student_ids = {s.id for s in students_via_relationship}
        
        missing_from_relationship = membership_student_ids - relationship_student_ids
        missing_from_memberships = relationship_student_ids - membership_student_ids
        
        if missing_from_relationship:
            print(f"WARNING: {len(missing_from_relationship)} students in memberships table but not in relationship")
            print("These students will not appear in the teacher's view.")
            for student_id in missing_from_relationship:
                student = User.query.get(student_id)
                print(f"  - {student.username if student else 'Unknown'} (ID: {student_id})")
        
        if missing_from_memberships:
            print(f"WARNING: {len(missing_from_memberships)} students in relationship but not in memberships table")
            for student_id in missing_from_memberships:
                student = User.query.get(student_id)
                print(f"  - {student.username if student else 'Unknown'} (ID: {student_id})")
      print("\n===== FIXING MEMBERSHIP ISSUES =====\n")
    fixed_count = 0
    for group in groups:
        # Get current memberships and relationships
        memberships = GroupMembership.query.filter_by(group_id=group.id).all()
        membership_student_ids = {m.user_id for m in memberships}
        relationship_student_ids = {s.id for s in group.students}
        
        # Fix students missing from relationship
        missing_from_relationship = membership_student_ids - relationship_student_ids
        for student_id in missing_from_relationship:
            student = User.query.get(student_id)
            if student:
                group.students.append(student)
                fixed_count += 1
                print(f"Added student {student.username} to group {group.name} relationship")
        
        # Fix students missing from memberships table
        missing_from_memberships = relationship_student_ids - membership_student_ids
        for student_id in missing_from_memberships:
            student = User.query.get(student_id)
            if student:
                new_membership = GroupMembership(user_id=student_id, group_id=group.id)
                db.session.add(new_membership)
                fixed_count += 1
                print(f"Added student {student.username} to GroupMembership table for group {group.name}")
    
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
