from app import create_app, db
from app.models import User, Group, GroupMembership

app = create_app()

with app.app_context():
    print(f'Users: {User.query.count()}')
    print(f'Groups: {Group.query.count()}')
    
    for g in Group.query.all():
        print(f'Group {g.name} (ID: {g.id}) has {g.students.count()} students')
        
        # List all students in group
        print("Students in this group:")
        for student in g.students.all():
            print(f"  - {student.username} (ID: {student.id})")
            
        # Check group memberships directly
        memberships = GroupMembership.query.filter_by(group_id=g.id).all()
        print(f"Memberships from GroupMembership table: {len(memberships)}")
        for membership in memberships:
            user = User.query.get(membership.user_id)
            if user:
                print(f"  - Membership: {user.username} (ID: {user.id})")
            else:
                print(f"  - Membership with invalid user_id: {membership.user_id}")
