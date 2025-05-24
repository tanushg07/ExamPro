from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, session
from flask_login import login_required, current_user
from sqlalchemy.exc import SQLAlchemyError
from app.models import db, Group, GroupMembership, User, Exam
from app.forms import CreateGroupForm, JoinGroupForm, TakeExamForm
from app.decorators import teacher_required
from app.notifications import notify_student_group_exams

group_bp = Blueprint('group', __name__, url_prefix='/groups')

@group_bp.route('/')
@login_required
def list_groups():
    """List groups based on user role"""
    if current_user.is_teacher():
        # Teachers see groups they created
        groups = Group.query.filter_by(teacher_id=current_user.id).all()
        return render_template('groups/teacher_groups.html', groups=groups)
    else:
        # Students see groups they're members of
        groups = current_user.joined_groups.all()
        return render_template('groups/student_groups.html', groups=groups)

@group_bp.route('/create', methods=['GET', 'POST'])
@login_required
@teacher_required
def create_group():
    """Create a new class group"""
    form = CreateGroupForm()
    
    if form.validate_on_submit():
        try:
            group = Group(
                name=form.name.data,
                description=form.description.data,
                subject=form.subject.data,
                section=form.section.data,
                room=form.room.data,
                teacher_id=current_user.id
            )
            # Generate unique joining code
            group.code = group.generate_code()
            
            db.session.add(group)
            db.session.commit()
            
            flash(f'Class created successfully! Share class code {group.code} with your students.', 'success')
            return redirect(url_for('group.view_group', group_id=group.id))
            
        except SQLAlchemyError as e:
            db.session.rollback()
            flash('Error creating class. Please try again.', 'danger')
            print(f"Error creating class: {str(e)}")
    
    return render_template('groups/create_group.html', form=form)

@group_bp.route('/<int:group_id>')
@login_required
def view_group(group_id):
    """View class details and stream"""
    group = Group.query.get_or_404(group_id)
    
    # Check if user has access to the group
    if not (current_user.id == group.teacher_id or current_user in group.students):
        flash('You do not have access to this class.', 'warning')
        return redirect(url_for('group.list_groups'))
    
    # Get exams categorized by status
    active_exams = group.get_active_exams()
    upcoming_exams = group.get_upcoming_exams()
    past_exams = group.get_past_exams()
    
    # Get members count
    student_count = group.students.count()
    
    return render_template(
        'groups/view_group.html',
        group=group,
        active_exams=active_exams,
        upcoming_exams=upcoming_exams,
        past_exams=past_exams,
        student_count=student_count,
        is_teacher=current_user.id == group.teacher_id
    )

@group_bp.route('/join', methods=['GET', 'POST'])
@login_required
def join_group():
    """Join a group using a code"""
    if current_user.is_teacher():
        flash('Teachers cannot join groups.', 'warning')
        return redirect(url_for('group.list_groups'))
    
    form = JoinGroupForm()
    if form.validate_on_submit():
        group = Group.query.filter_by(code=form.code.data.upper()).first()
        
        if not group:
            flash('Invalid group code.', 'danger')
            return redirect(url_for('group.join_group'))
        
        if current_user in group.students:
            flash('You are already a member of this group.', 'info')
            return redirect(url_for('group.view_group', group_id=group.id))
        
        # Store the group ID in the session and redirect to confirmation page
        session['joining_group_id'] = group.id
        return redirect(url_for('group.confirm_join', group_id=group.id))
    
    return render_template('groups/join_group.html', form=form)

@group_bp.route('/confirm-join/<int:group_id>', methods=['GET', 'POST'])
@login_required
def confirm_join(group_id):
    """Confirm joining a group"""
    # Security check - make sure this is the group they were trying to join
    if session.get('joining_group_id') != group_id:
        flash('Invalid request. Please try again.', 'danger')
        return redirect(url_for('group.join_group'))
    
    group = Group.query.get_or_404(group_id)
    
    # Already a member check
    if current_user in group.students:
        flash('You are already a member of this group.', 'info')
        return redirect(url_for('group.view_group', group_id=group.id))
    
    # Create form for CSRF protection
    form = TakeExamForm()
    
    if request.method == 'POST' and request.form.get('confirm') == 'true':
        try:
            # Create explicit membership entry
            membership = GroupMembership(user_id=current_user.id, group_id=group.id)
            db.session.add(membership)
            
            # Also add to the relationship to ensure consistency
            if current_user not in group.students:
                group.students.append(current_user)
                
            db.session.commit()
            
            # Clean up session
            session.pop('joining_group_id', None)
            
            # Notify student about available exams in this group
            notify_student_group_exams(current_user.id, group.id)
            
            flash(f'Successfully joined {group.name}!', 'success')
            return redirect(url_for('group.view_group', group_id=group.id))
            
        except SQLAlchemyError as e:
            db.session.rollback()
            flash('Error joining group. Please try again.', 'danger')
            print(f"Error joining group: {str(e)}")
    
    return render_template('groups/confirm_join.html', form=form, group=group)

@group_bp.route('/<int:group_id>/leave', methods=['POST'])
@login_required
def leave_group(group_id):
    """Leave a group"""
    if current_user.is_teacher():
        flash('Teachers cannot leave groups.', 'warning')
        return redirect(url_for('group.list_groups'))
    
    group = Group.query.get_or_404(group_id)
    
    if current_user not in group.students:
        flash('You are not a member of this group.', 'warning')
        return redirect(url_for('group.list_groups'))
    
    try:
        group.students.remove(current_user)
        db.session.commit()
        flash(f'Successfully left {group.name}.', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        flash('Error leaving group. Please try again.', 'danger')
        print(f"Error leaving group: {str(e)}")
    
    return redirect(url_for('group.list_groups'))

@group_bp.route('/<int:group_id>/members')
@login_required
def list_members(group_id):
    """List all members of a group"""
    group = Group.query.get_or_404(group_id)
    
    # Check if user has access to the group
    if not (current_user.id == group.teacher_id or current_user in group.students):
        flash('You do not have access to this group.', 'warning')
        return redirect(url_for('group.list_groups'))
    
    # Get students using both methods to ensure we show everyone
    students_from_relationship = set(group.students)
    
    # Also get students from membership table directly
    memberships = GroupMembership.query.filter_by(group_id=group.id).all()
    student_ids = [m.user_id for m in memberships]
    students_from_memberships = set(User.query.filter(User.id.in_(student_ids)).all())
    
    # Combine both sets to get all students
    all_students = list(students_from_relationship.union(students_from_memberships))
    
    return render_template(
        'groups/members.html',
        group=group,
        all_students=all_students,
        is_teacher=current_user.id == group.teacher_id
    )

@group_bp.route('/<int:group_id>/remove/<int:user_id>', methods=['POST'])
@login_required
@teacher_required
def remove_member(group_id, user_id):
    """Remove a member from the group (teacher only)"""
    group = Group.query.get_or_404(group_id)
    
    # Verify teacher owns the group
    if group.teacher_id != current_user.id:
        flash('You do not have permission to remove members from this group.', 'warning')
        return redirect(url_for('group.list_groups'))
    
    user = User.query.get_or_404(user_id)
    try:
        # Remove from relationship
        if user in group.students:
            group.students.remove(user)
        
        # Also remove from membership table directly
        GroupMembership.query.filter_by(
            user_id=user.id,
            group_id=group.id
        ).delete()
        
        db.session.commit()
        flash(f'Successfully removed {user.username} from {group.name}.', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        flash('Error removing member. Please try again.', 'danger')
        print(f"Error removing member: {str(e)}")
    
    return redirect(url_for('group.list_members', group_id=group_id))

@group_bp.route('/<int:group_id>/archive', methods=['POST'])
@login_required
@teacher_required
def archive_group(group_id):
    """Archive or unarchive a class group"""
    group = Group.query.get_or_404(group_id)
    
    # Verify teacher owns the group
    if group.teacher_id != current_user.id:
        flash('You do not have permission to archive this class.', 'warning')
        return redirect(url_for('group.list_groups'))
    
    try:
        # Toggle archived status
        group.archived = not group.archived
        db.session.commit()
        status = 'archived' if group.archived else 'unarchived'
        flash(f'Successfully {status} {group.name}.', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        flash('Error updating class. Please try again.', 'danger')
        print(f"Error updating class: {str(e)}")
    
    return redirect(url_for('group.view_group', group_id=group.id))

@group_bp.route('/debug-members/<int:group_id>')
@login_required
def debug_members(group_id):
    """Debug route to check group memberships"""
    if not current_user.is_teacher():
        flash('Only teachers can access this debug route.', 'warning')
        return redirect(url_for('group.list_groups'))
    
    group = Group.query.get_or_404(group_id)
    
    # Check if user is the teacher of this group
    if group.teacher_id != current_user.id:
        flash('You do not have access to this debug information.', 'warning')
        return redirect(url_for('group.list_groups'))
    
    # Get students using relationship
    students_via_relationship = group.students.all()
    
    # Get students via direct query
    memberships = GroupMembership.query.filter_by(group_id=group_id).all()
    student_ids = [membership.user_id for membership in memberships]
    students_via_query = User.query.filter(User.id.in_(student_ids)).all() if student_ids else []
    
    return render_template(
        'groups/debug_members.html',
        group=group,
        students_via_relationship=students_via_relationship,
        students_via_query=students_via_query,
        memberships=memberships
    )

@group_bp.route('/fix-memberships/<int:group_id>', methods=['POST'])
@login_required
def fix_memberships(group_id):
    """Fix inconsistent group memberships"""
    if not current_user.is_teacher():
        flash('Only teachers can access this function.', 'warning')
        return redirect(url_for('group.list_groups'))
    
    group = Group.query.get_or_404(group_id)
    
    # Check if user is the teacher of this group
    if group.teacher_id != current_user.id:
        flash('You do not have permission to fix memberships for this group.', 'warning')
        return redirect(url_for('group.list_groups'))
    
    try:
        # Get all students who should be in the group
        memberships = GroupMembership.query.filter_by(group_id=group_id).all()
        expected_student_ids = {membership.user_id for membership in memberships}
        
        # Get all students who are in the relationship
        actual_students = group.students.all()
        actual_student_ids = {student.id for student in actual_students}
        
        # Find missing students
        missing_student_ids = expected_student_ids - actual_student_ids
        
        # Add missing students to the relationship
        for student_id in missing_student_ids:
            student = User.query.get(student_id)
            if student:
                group.students.append(student)
        
        # Commit changes
        db.session.commit()
        
        flash(f'Successfully fixed {len(missing_student_ids)} membership(s).', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        flash(f'Error fixing memberships: {str(e)}', 'danger')
    
    return redirect(url_for('group.debug_members', group_id=group_id))
