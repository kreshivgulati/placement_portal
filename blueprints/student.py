# blueprints/student.py

from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from database import get_db
from utils import login_required
import os
from werkzeug.utils import secure_filename

student_bp = Blueprint('student', __name__, url_prefix='/student')

UPLOAD_FOLDER   = os.path.join('static', 'uploads', 'resumes')
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# DASHBOARD
@student_bp.route('/dashboard')
@login_required(role='student')
def dashboard():
    db         = get_db()
    student_id = session['student_db_id']
     # ── ADD THIS ──
    student = db.execute("""
        SELECT s.*, u.name, u.email, u.status AS account_status
        FROM students s
        JOIN users u ON s.user_id = u.id
        WHERE s.id = ?
    """, (student_id,)).fetchone()
    open_drives = db.execute("""
        SELECT pd.*, c.company_name
        FROM placement_drives pd
        JOIN companies c ON pd.company_id = c.id
        WHERE pd.status = 'approved'
          AND pd.application_deadline >= DATE('now')
        ORDER BY pd.application_deadline ASC
    """).fetchall()

    # Drives already applied to
    applied = db.execute("""
        SELECT a.*, pd.job_role, c.company_name,
               pd.application_deadline, pd.status AS drive_status
        FROM applications a
        JOIN placement_drives pd ON a.drive_id = pd.id
        JOIN companies c ON pd.company_id = c.id
        WHERE a.student_id = ?
        ORDER BY a.applied_at DESC
    """, (student_id,)).fetchall()

    # IDs of drives already applied to (used in template to disable apply button)
    applied_drive_ids = {row['drive_id'] for row in applied}

    return render_template('student/dashboard.html',
        student=student,
        open_drives=open_drives,
        applied=applied,
        applied_drive_ids=applied_drive_ids
    )
# PROFILE

@student_bp.route('/profile')
@login_required(role='student')
def profile():
    db         = get_db()
    student_id = session['student_db_id']

    student = db.execute("""
        SELECT s.*, u.name, u.email, u.status
        FROM students s
        JOIN users u ON s.user_id = u.id
        WHERE s.id = ?
    """, (student_id,)).fetchone()

    return render_template('student/profile.html', student=student)


@student_bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required(role='student')
def edit_profile():
    db         = get_db()
    student_id = session['student_db_id']

    student = db.execute("""
        SELECT s.*, u.name, u.email
        FROM students s
        JOIN users u ON s.user_id = u.id
        WHERE s.id = ?
    """, (student_id,)).fetchone()

    if not student:
        flash('Student profile not found.', 'danger')
        return redirect(url_for('student.dashboard'))

    if request.method == 'POST':
        name   = request.form.get('name', '').strip()
        phone  = request.form.get('phone', '').strip()
        branch = request.form.get('branch', '').strip()
        year   = request.form.get('year', '').strip()
        cgpa   = request.form.get('cgpa', '').strip()
        skills = request.form.get('skills', '').strip()

        # Validation
        if not all([name, branch, year, cgpa]):
            flash('Name, branch, year and CGPA are required.', 'danger')
            return render_template('student/edit_profile.html', student=student)

        try:
            year = int(year)
            cgpa = float(cgpa)
        except ValueError:
            flash('Year must be a whole number and CGPA must be a decimal.', 'danger')
            return render_template('student/edit_profile.html', student=student)

        if not (0.0 <= cgpa <= 10.0):
            flash('CGPA must be between 0.0 and 10.0.', 'danger')
            return render_template('student/edit_profile.html', student=student)

        if year not in range(1, 5):
            flash('Year must be between 1 and 4.', 'danger')
            return render_template('student/edit_profile.html', student=student)

        # Handle resume upload
        resume_path = student['resume_path']
        file = request.files.get('resume')
        if file and file.filename != '':
            if not allowed_file(file.filename):
                flash('Only PDF, DOC, and DOCX files are allowed for resume.', 'danger')
                return render_template('student/edit_profile.html', student=student)

            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            filename    = secure_filename(f"student_{student_id}_{file.filename}")
            resume_path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(resume_path)

        db.execute(
            "UPDATE users SET name = ? WHERE id = ?",
            (name, student['user_id'])
        )
        db.execute("""
            UPDATE students
            SET phone = ?, branch = ?, year = ?, cgpa = ?, skills = ?, resume_path = ?
            WHERE id = ?
        """, (phone, branch, year, cgpa, skills, resume_path, student_id))
        db.commit()

        flash('Profile updated successfully.', 'success')
        return redirect(url_for('student.profile'))

    return render_template('student/edit_profile.html', student=student)

#PLACEMENT DRIVES
# blueprints/student.py  —  replace the drives() route

@student_bp.route('/drives')
@login_required(role='student')
def drives():
    db         = get_db()
    student_id = session['student_db_id']

    q        = request.args.get('q', '').strip()
    job_type = request.args.get('type', '').strip()

    # Build query dynamically based on filters
    sql    = """
        SELECT pd.*, c.company_name
        FROM placement_drives pd
        JOIN companies c ON pd.company_id = c.id
        WHERE pd.status = 'approved'
          AND pd.application_deadline >= DATE('now')
    """
    params = []

    if q:
        sql += " AND (pd.job_role LIKE ? OR c.company_name LIKE ? OR pd.location LIKE ?)"
        params += [f'%{q}%', f'%{q}%', f'%{q}%']

    if job_type:
        sql += " AND pd.job_type = ?"
        params.append(job_type)

    sql += " ORDER BY pd.application_deadline ASC"

    drives = db.execute(sql, params).fetchall()

    # IDs of already-applied drives
    applied_rows      = db.execute(
        "SELECT drive_id FROM applications WHERE student_id = ?", (student_id,)
    ).fetchall()
    applied_drive_ids = {row['drive_id'] for row in applied_rows}

    student = db.execute(
        "SELECT branch, cgpa, year FROM students WHERE id = ?",
        (student_id,)
    ).fetchone()

    return render_template('student/drives.html',
        drives=drives,
        student=student,
        applied_drive_ids=applied_drive_ids
    )

# blueprints/student.py — replace drive_detail() route

@student_bp.route('/drive/<int:drive_id>')
@login_required(role='student')
def drive_detail(drive_id):
    db         = get_db()
    student_id = session['student_db_id']

    drive = db.execute("""
        SELECT pd.*,
               c.company_name,
               c.website,
               c.hr_contact_name,
               c.hr_contact_email,
               c.description AS company_description
        FROM placement_drives pd
        JOIN companies c ON pd.company_id = c.id
        WHERE pd.id = ? AND pd.status = 'approved'
    """, (drive_id,)).fetchone()

    if not drive:
        flash('Drive not found or not available.', 'danger')
        return redirect(url_for('student.drives'))

    already_applied = db.execute("""
        SELECT id FROM applications
        WHERE student_id = ? AND drive_id = ?
    """, (student_id, drive_id)).fetchone()

    return render_template('student/drive_detail.html',
        drive=drive,
        already_applied=already_applied
    )


# APPLICATIONS

@student_bp.route('/apply/<int:drive_id>', methods=['POST'])
@login_required(role='student')
def apply(drive_id):
    db         = get_db()
    student_id = session['student_db_id']

    # Check drive exists and is approved
    drive = db.execute("""
        SELECT * FROM placement_drives
        WHERE id = ? AND status = 'approved'
          AND application_deadline >= DATE('now')
    """, (drive_id,)).fetchone()

    if not drive:
        flash('This drive is not available for applications.', 'danger')
        return redirect(url_for('student.drives'))

    # Check for duplicate application
    existing = db.execute("""
        SELECT id FROM applications
        WHERE student_id = ? AND drive_id = ?
    """, (student_id, drive_id)).fetchone()

    if existing:
        flash('You have already applied to this placement drive.', 'warning')
        return redirect(url_for('student.drive_detail', drive_id=drive_id))

    # Eligibility check — CGPA
    student = db.execute(
        "SELECT cgpa, branch, year FROM students WHERE id = ?",
        (student_id,)
    ).fetchone()

    if student['cgpa'] < drive['eligibility_cgpa']:
        flash(
            f"You do not meet the minimum CGPA requirement of {drive['eligibility_cgpa']}.",
            'danger'
        )
        return redirect(url_for('student.drive_detail', drive_id=drive_id))

    # Eligibility check — Branch
    if drive['eligible_branches']:
        allowed_branches = [b.strip() for b in drive['eligible_branches'].split(',')]
        if student['branch'] not in allowed_branches:
            flash('Your branch is not eligible for this drive.', 'danger')
            return redirect(url_for('student.drive_detail', drive_id=drive_id))

    # Eligibility check — Year
    if drive['eligible_years']:
        allowed_years = [int(y.strip()) for y in drive['eligible_years'].split(',')]
        if student['year'] not in allowed_years:
            flash('Your year of study is not eligible for this drive.', 'danger')
            return redirect(url_for('student.drive_detail', drive_id=drive_id))

    # All checks passed — insert application
    db.execute("""
        INSERT INTO applications (student_id, drive_id, status)
        VALUES (?, ?, 'applied')
    """, (student_id, drive_id))
    db.commit()

    flash('Application submitted successfully!', 'success')
    return redirect(url_for('student.my_applications'))


@student_bp.route('/applications')
@login_required(role='student')
def my_applications():
    db         = get_db()
    student_id = session['student_db_id']

    applications = db.execute("""
        SELECT a.*, pd.job_role, pd.job_type, pd.location,
               pd.salary_package, pd.application_deadline,
               pd.status AS drive_status, c.company_name
        FROM applications a
        JOIN placement_drives pd ON a.drive_id = pd.id
        JOIN companies c ON pd.company_id = c.id
        WHERE a.student_id = ?
        ORDER BY a.applied_at DESC
    """, (student_id,)).fetchall()

    return render_template('student/my_applications.html',
        applications=applications
    )


# PLACEMENT HISTORY
# ─────────────────────────────────────────

@student_bp.route('/history')
@login_required(role='student')
def history():
    db         = get_db()
    student_id = session['student_db_id']

    # Only show selected or rejected — completed drives
    history = db.execute("""
        SELECT a.*, pd.job_role, pd.job_type, pd.location,
               pd.salary_package, c.company_name,
               pd.status AS drive_status, a.applied_at
        FROM applications a
        JOIN placement_drives pd ON a.drive_id = pd.id
        JOIN companies c ON pd.company_id = c.id
        WHERE a.student_id = ?
          AND (a.status IN ('selected', 'rejected')
               OR pd.status = 'closed')
        ORDER BY a.applied_at DESC
    """, (student_id,)).fetchall()

    # Summary counts
    selected_count   = sum(1 for row in history if row['status'] == 'selected')
    rejected_count   = sum(1 for row in history if row['status'] == 'rejected')
    shortlisted_count = sum(1 for row in history if row['status'] == 'shortlisted')

    return render_template('student/history.html',
        history=history,
        selected_count=selected_count,
        rejected_count=rejected_count,
        shortlisted_count=shortlisted_count
    )



UPLOAD_FOLDER = 'static/resumes'
ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@student_bp.route('/resume/upload', methods=['POST'])
@login_required(role='student')
def upload_resume():
    db         = get_db()
    student_id = session['student_db_id']

    if 'resume' not in request.files:
        flash('No file selected.', 'danger')
        return redirect(url_for('student.dashboard'))

    file = request.files['resume']

    if file.filename == '':
        flash('No file selected.', 'danger')
        return redirect(url_for('student.dashboard'))

    if not allowed_file(file.filename):
        flash('Only PDF files are allowed.', 'danger')
        return redirect(url_for('student.dashboard'))

    if len(file.read()) > 5 * 1024 * 1024:   # 5 MB limit
        flash('File size must be under 5 MB.', 'danger')
        return redirect(url_for('student.dashboard'))
    file.seek(0)  # reset after reading for size check

    # Save as student_<id>.pdf so each upload overwrites the old one
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    filename = f"student_{student_id}.pdf"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    db.execute(
        "UPDATE students SET resume_path = ? WHERE id = ?",
        (filepath, student_id)
    )
    db.commit()
    flash('Resume uploaded successfully.', 'success')
    return redirect(url_for('student.dashboard'))


@student_bp.route('/resume/delete', methods=['POST'])
@login_required(role='student')
def delete_resume():
    db         = get_db()
    student_id = session['student_db_id']

    student = db.execute(
        "SELECT resume_path FROM students WHERE id = ?", (student_id,)
    ).fetchone()

    if student and student['resume_path']:
        if os.path.exists(student['resume_path']):
            os.remove(student['resume_path'])
        db.execute(
            "UPDATE students SET resume_path = NULL WHERE id = ?", (student_id,)
        )
        db.commit()
        flash('Resume removed.', 'success')
    else:
        flash('No resume to delete.', 'info')

    return redirect(url_for('student.dashboard'))