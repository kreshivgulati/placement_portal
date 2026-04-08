from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from database import get_db
from utils import login_required

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')
# DASHBOARD

@admin_bp.route('/dashboard')
@login_required(role='admin')
def dashboard():
    db = get_db()

    student_count   = db.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    company_count   = db.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    drive_count     = db.execute("SELECT COUNT(*) FROM placement_drives").fetchone()[0]
    app_count       = db.execute("SELECT COUNT(*) FROM applications").fetchone()[0]

    pending_companies = db.execute(
        "SELECT COUNT(*) FROM companies WHERE approval_status = 'pending'"
    ).fetchone()[0]

    pending_drives = db.execute(
        "SELECT COUNT(*) FROM placement_drives WHERE status = 'pending'"
    ).fetchone()[0]

    recent_applications = db.execute("""
        SELECT a.id, u.name AS student_name, s.student_id,
               pd.job_role, c.company_name, a.status, a.applied_at
        FROM applications a
        JOIN students s ON a.student_id = s.id
        JOIN users u ON s.user_id = u.id
        JOIN placement_drives pd ON a.drive_id = pd.id
        JOIN companies c ON pd.company_id = c.id
        ORDER BY a.applied_at DESC
        LIMIT 10
    """).fetchall()

    return render_template('admin/dashboard.html',
        student_count=student_count,
        company_count=company_count,
        drive_count=drive_count,
        app_count=app_count,
        pending_companies=pending_companies,
        pending_drives=pending_drives,
        recent_applications=recent_applications
    )

#COMPANIES
@admin_bp.route('/companies')
@login_required(role='admin')
def companies():
    db    = get_db()
    query = request.args.get('search', '').strip()

    if query:
        companies = db.execute("""
            SELECT c.*, u.email, u.status AS account_status
            FROM companies c
            JOIN users u ON c.user_id = u.id
            WHERE c.company_name LIKE ?
            ORDER BY c.created_at DESC
        """, (f'%{query}%',)).fetchall()
    else:
        companies = db.execute("""
            SELECT c.*, u.email, u.status AS account_status
            FROM companies c
            JOIN users u ON c.user_id = u.id
            ORDER BY c.created_at DESC
        """).fetchall()

    return render_template('admin/companies.html',
        companies=companies,
        search=query
    )

# blueprints/admin.py — replace company_detail() route

@admin_bp.route('/company/<int:company_id>')
@login_required(role='admin')
def company_detail(company_id):
    db = get_db()

    company = db.execute("""
        SELECT c.*, u.email, u.name, u.status AS account_status
        FROM companies c
        JOIN users u ON c.user_id = u.id
        WHERE c.id = ?
    """, (company_id,)).fetchone()

    if not company:
        flash('Company not found.', 'danger')
        return redirect(url_for('admin.companies'))

    drives = db.execute("""
        SELECT pd.*,
               (SELECT COUNT(*) FROM applications a
                WHERE a.drive_id = pd.id) AS applicant_count
        FROM placement_drives pd
        WHERE pd.company_id = ?
        ORDER BY pd.created_at DESC
    """, (company_id,)).fetchall()

    return render_template('admin/company_detail.html',
        company=company,
        drives=drives
    )
@admin_bp.route('/company/<int:company_id>/approve', methods=['POST'])
@login_required(role='admin')
def approve_company(company_id):
    db = get_db()
    db.execute(
        "UPDATE companies SET approval_status = 'approved' WHERE id = ?",
        (company_id,)
    )
    db.commit()
    flash('Company approved successfully.', 'success')
    return redirect(url_for('admin.companies'))

@admin_bp.route('/company/<int:company_id>/reject', methods=['POST'])
@login_required(role='admin')
def reject_company(company_id):
    db = get_db()
    db.execute(
        "UPDATE companies SET approval_status = 'rejected' WHERE id = ?",
        (company_id,)
    )
    db.commit()
    flash('Company rejected.', 'warning')
    return redirect(url_for('admin.companies'))
# blueprints/admin.py — add these routes

@admin_bp.route('/drive/<int:drive_id>/approve', methods=['POST'])
@login_required(role='admin')
def approve_drive(drive_id):
    db = get_db()
    db.execute(
        "UPDATE placement_drives SET status = 'approved' WHERE id = ?",
        (drive_id,)
    )
    db.commit()
    flash('Placement drive approved successfully.', 'success')
    return redirect(url_for('admin.drives'))



@admin_bp.route('/company/<int:company_id>/blacklist', methods=['POST'])
@login_required(role='admin')
def blacklist_company(company_id):
    db = get_db()
    company = db.execute(
        "SELECT user_id FROM companies WHERE id = ?", (company_id,)
    ).fetchone()

    if not company:
        flash('Company not found.', 'danger')
        return redirect(url_for('admin.companies'))

    db.execute(
        "UPDATE users SET status = 'blacklisted' WHERE id = ?",
        (company['user_id'],)
    )
    db.commit()
    flash('Company account has been blacklisted.', 'danger')
    return redirect(url_for('admin.company_detail', company_id=company_id))


@admin_bp.route('/company/<int:company_id>/delete', methods=['POST'])
@login_required(role='admin')
def delete_company(company_id):
    db = get_db()
    company = db.execute(
        "SELECT user_id FROM companies WHERE id = ?", (company_id,)
    ).fetchone()

    if not company:
        flash('Company not found.', 'danger')
        return redirect(url_for('admin.companies'))

    # Deleting the user cascades to companies, drives, applications
    db.execute("DELETE FROM users WHERE id = ?", (company['user_id'],))
    db.commit()
    flash('Company deleted permanently.', 'danger')
    return redirect(url_for('admin.companies'))

@admin_bp.route('/students')
@login_required(role='admin')
def students():
    db     = get_db()
    search = request.args.get('search', '').strip()
    branch = request.args.get('branch', '').strip()
    year   = request.args.get('year', '').strip()
    status = request.args.get('status', '').strip()

    sql = """
        SELECT s.*, u.name, u.email, u.status AS account_status
        FROM students s
        JOIN users u ON s.user_id = u.id
        WHERE 1=1
    """
    params = []

    if search:
        sql += """
            AND (
                u.name LIKE ?
                OR s.student_id LIKE ?
                OR u.email LIKE ?
                OR s.phone LIKE ?
            )
        """
        like = f'%{search}%'
        params += [like, like, like, like]

    if branch:
        sql += " AND s.branch = ?"
        params.append(branch)

    if year:
        sql += " AND s.year = ?"
        params.append(int(year))   # cast to int — s.year is INTEGER in schema

    if status:
        sql += " AND u.status = ?"
        params.append(status)

    sql += " ORDER BY u.name ASC"

    students = db.execute(sql, params).fetchall()

    return render_template('admin/students.html',
        students=students,
        search=search
    )

@admin_bp.route('/student/<int:student_id>')
@login_required(role='admin')
def student_detail(student_id):
    db = get_db()

    student = db.execute("""
        SELECT s.*, u.name, u.email, u.status AS account_status
        FROM students s
        JOIN users u ON s.user_id = u.id
        WHERE s.id = ?
    """, (student_id,)).fetchone()

    if not student:
        flash('Student not found.', 'danger')
        return redirect(url_for('admin.students'))

    applications = db.execute("""
        SELECT a.*, pd.job_role, c.company_name, a.status, a.applied_at
        FROM applications a
        JOIN placement_drives pd ON a.drive_id = pd.id
        JOIN companies c ON pd.company_id = c.id
        WHERE a.student_id = ?
        ORDER BY a.applied_at DESC
    """, (student_id,)).fetchall()

    return render_template('admin/student_detail.html',
        student=student,
        applications=applications
    )


@admin_bp.route('/student/<int:student_id>/edit', methods=['GET', 'POST'])
@login_required(role='admin')
def edit_student(student_id):
    db = get_db()

    student = db.execute("""
        SELECT s.*, u.name, u.email
        FROM students s
        JOIN users u ON s.user_id = u.id
        WHERE s.id = ?
    """, (student_id,)).fetchone()

    if not student:
        flash('Student not found.', 'danger')
        return redirect(url_for('admin.students'))

    if request.method == 'POST':
        name   = request.form.get('name', '').strip()
        email  = request.form.get('email', '').strip()
        branch = request.form.get('branch', '').strip()
        year   = request.form.get('year', '').strip()
        cgpa   = request.form.get('cgpa', '').strip()
        phone  = request.form.get('phone', '').strip()

        # Basic validation
        if not all([name, email, branch, year, cgpa]):
            flash('All required fields must be filled.', 'danger')
            return render_template('admin/edit_student.html', student=student)

        try:
            year = int(year)
            cgpa = float(cgpa)
        except ValueError:
            flash('Year must be an integer and CGPA must be a number.', 'danger')
            return render_template('admin/edit_student.html', student=student)

        if not (0.0 <= cgpa <= 10.0):
            flash('CGPA must be between 0.0 and 10.0.', 'danger')
            return render_template('admin/edit_student.html', student=student)

        db.execute(
            "UPDATE users SET name = ?, email = ? WHERE id = ?",
            (name, email, student['user_id'])
        )
        db.execute(
            "UPDATE students SET branch = ?, year = ?, cgpa = ?, phone = ? WHERE id = ?",
            (branch, year, cgpa, phone, student_id)
        )
        db.commit()
        flash('Student updated successfully.', 'success')
        return redirect(url_for('admin.student_detail', student_id=student_id))

    return render_template('admin/edit_student.html', student=student)
@admin_bp.route('/student/<int:student_id>/activate', methods=['POST'])
def activate_student(student_id):
    db = get_db()
    student = db.execute('SELECT user_id FROM students WHERE id=?', [student_id]).fetchone()
    db.execute("UPDATE users SET status='active' WHERE id=?", [student['user_id']])
    db.commit()
    return redirect(url_for('admin.student_detail', student_id=student_id))
@admin_bp.route('/student/<int:student_id>/blacklist', methods=['POST'])
@login_required(role='admin')
def blacklist_student(student_id):
    db = get_db()
    student = db.execute(
        "SELECT user_id FROM students WHERE id = ?", (student_id,)
    ).fetchone()

    if not student:
        flash('Student not found.', 'danger')
        return redirect(url_for('admin.students'))

    db.execute(
        "UPDATE users SET status = 'blacklisted' WHERE id = ?",
        (student['user_id'],)
    )
    db.commit()
    flash('Student has been blacklisted.', 'danger')
    return redirect(url_for('admin.student_detail', student_id=student_id))

@admin_bp.route('/company/<int:company_id>/activate', methods=['POST'])
@login_required(role='admin')
def activate_company(company_id):
    db = get_db()
    company = db.execute(
        "SELECT user_id FROM companies WHERE id = ?", (company_id,)
    ).fetchone()

    if not company:
        flash('Company not found.', 'danger')
        return redirect(url_for('admin.companies'))

    db.execute(
        "UPDATE users SET status = 'active' WHERE id = ?",
        (company['user_id'],)
    )
    db.commit()
    flash('Company account re-activated.', 'success')
    return redirect(url_for('admin.company_detail', company_id=company_id))
@admin_bp.route('/student/<int:student_id>/delete', methods=['POST'])
@login_required(role='admin')
def delete_student(student_id):
    db = get_db()
    student = db.execute(
        "SELECT user_id FROM students WHERE id = ?", (student_id,)
    ).fetchone()

    if not student:
        flash('Student not found.', 'danger')
        return redirect(url_for('admin.students'))

    db.execute("DELETE FROM users WHERE id = ?", (student['user_id'],))
    db.commit()
    flash('Student deleted permanently.', 'danger')
    return redirect(url_for('admin.students'))

#PLACEMENT DRIVE 
# blueprints/admin.py — replace drives() route

@admin_bp.route('/drives')
@login_required(role='admin')
def drives():
    db     = get_db()
    status = request.args.get('status', '').strip()
    search = request.args.get('search', '').strip()

    sql    = """
        SELECT pd.*, c.company_name,
               (SELECT COUNT(*) FROM applications a WHERE a.drive_id = pd.id) AS applicant_count
        FROM placement_drives pd
        JOIN companies c ON pd.company_id = c.id
        WHERE 1=1
    """
    params = []

    if status:
        sql += " AND pd.status = ?"
        params.append(status)

    if search:
        sql += " AND (pd.job_role LIKE ? OR c.company_name LIKE ?)"
        params += [f'%{search}%', f'%{search}%']

    sql += " ORDER BY pd.created_at DESC"

    drives = db.execute(sql, params).fetchall()

    return render_template('admin/drives.html',
        drives=drives,
        selected_status=status
    )
# blueprints/admin.py — replace drive_detail() route

@admin_bp.route('/drive/<int:drive_id>')
@login_required(role='admin')
def drive_detail(drive_id):
    db = get_db()

    drive = db.execute("""
        SELECT pd.*, c.company_name, c.id AS company_id
        FROM placement_drives pd
        JOIN companies c ON pd.company_id = c.id
        WHERE pd.id = ?
    """, (drive_id,)).fetchone()

    if not drive:
        flash('Placement drive not found.', 'danger')
        return redirect(url_for('admin.drives'))

    applications = db.execute("""
        SELECT a.*,
               u.name  AS student_name,
               s.id    AS student_db_id,
               s.student_id,
               s.branch,
               s.year,
               s.cgpa,
               s.resume_path
        FROM applications a
        JOIN students s ON a.student_id = s.id
        JOIN users u    ON s.user_id    = u.id
        WHERE a.drive_id = ?
        ORDER BY a.applied_at DESC
    """, (drive_id,)).fetchall()

    return render_template('admin/drive_detail.html',
        drive=drive,
        applications=applications
    )
@admin_bp.route('/drive/<int:drive_id>/reject', methods=['POST'])
@login_required(role='admin')
def reject_drive(drive_id):
    db = get_db()
    db.execute(
        "UPDATE placement_drives SET status = 'rejected' WHERE id = ?",
        (drive_id,)
    )
    db.commit()
    flash('Placement drive rejected.', 'warning')
    return redirect(url_for('admin.drives'))


@admin_bp.route('/drive/<int:drive_id>/close', methods=['POST'])
@login_required(role='admin')
def close_drive(drive_id):
    db = get_db()
    db.execute(
        "UPDATE placement_drives SET status = 'closed' WHERE id = ?",
        (drive_id,)
    )
    db.commit()
    flash('Placement drive closed.', 'secondary')
    return redirect(url_for('admin.drive_detail', drive_id=drive_id))


# blueprints/admin.py — replace applications() route

@admin_bp.route('/applications')
@login_required(role='admin')
def applications():
    db     = get_db()
    status = request.args.get('status', '').strip()
    search = request.args.get('search', '').strip()

    sql = """
        SELECT a.*, u.name AS student_name, s.student_id, s.cgpa,
               pd.job_role, pd.id, c.company_name, a.applied_at
        FROM applications a
        JOIN students s ON a.student_id = s.id
        JOIN users u ON s.user_id = u.id
        JOIN placement_drives pd ON a.drive_id = pd.id
        JOIN companies c ON pd.company_id = c.id
        WHERE 1=1
    """
    params = []

    if status:
        sql += " AND a.status = ?"
        params.append(status)

    if search:
        sql += " AND (u.name LIKE ? OR s.student_id LIKE ? OR pd.job_title LIKE ?)"
        params += [f'%{search}%', f'%{search}%', f'%{search}%']

    sql += " ORDER BY a.applied_at DESC"

    apps = db.execute(sql, params).fetchall()

    return render_template('admin/applications.html',
        applications=apps,
        selected_status=status
    )
    db     = get_db()
    status = request.args.get('status', '').strip()

    if status:
        apps = db.execute("""
            SELECT a.*, u.name AS student_name, s.student_id,
                   pd.job_role, c.company_name, a.applied_at
            FROM applications a
            JOIN students s ON a.student_id = s.id
            JOIN users u ON s.user_id = u.id
            JOIN placement_drives pd ON a.drive_id = pd.id
            JOIN companies c ON pd.company_id = c.id
            WHERE a.status = ?
            ORDER BY a.applied_at DESC
        """, (status,)).fetchall()
    else:
        apps = db.execute("""
            SELECT a.*, u.name AS student_name, s.student_id,
                   pd.job_role, c.company_name, a.applied_at
            FROM applications a
            JOIN students s ON a.student_id = s.id
            JOIN users u ON s.user_id = u.id
            JOIN placement_drives pd ON a.drive_id = pd.id
            JOIN companies c ON pd.company_id = c.id
            ORDER BY a.applied_at DESC
        """).fetchall()

    return render_template('admin/applications.html',
        applications=apps,
        selected_status=status
    )