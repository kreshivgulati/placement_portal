# blueprints/company.py

from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from database import get_db
from utils import login_required

company_bp = Blueprint('company', __name__, url_prefix='/company')


# ─────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────

@company_bp.route('/dashboard')
@login_required(role='company')
def dashboard():
    db         = get_db()
    company_id = session['company_db_id']

    company = db.execute("""
        SELECT c.*, u.name, u.email, u.status AS account_status
        FROM companies c
        JOIN users u ON c.user_id = u.id
        WHERE c.id = ?
    """, (company_id,)).fetchone()

    if not company:
        flash('Company profile not found.', 'danger')
        return redirect(url_for('auth.login'))

    # All drives by this company with applicant count per drive
    drives = db.execute("""
        SELECT pd.*,
               COUNT(a.id) AS applicant_count,
               SUM(CASE WHEN a.status = 'shortlisted' THEN 1 ELSE 0 END) AS shortlisted_count,
               SUM(CASE WHEN a.status = 'selected'    THEN 1 ELSE 0 END) AS selected_count
        FROM placement_drives pd
        LEFT JOIN applications a ON a.drive_id = pd.id
        WHERE pd.company_id = ?
        GROUP BY pd.id
        ORDER BY pd.created_at DESC
    """, (company_id,)).fetchall()

    total_drives      = len(drives)
    total_applicants  = sum(d['applicant_count']  for d in drives)
    total_shortlisted = sum(d['shortlisted_count'] for d in drives)
    total_selected    = sum(d['selected_count']    for d in drives)

    return render_template('company/dashboard.html',
        company=company,
        drives=drives,
        total_drives=total_drives,
        total_applicants=total_applicants,
        total_shortlisted=total_shortlisted,
        total_selected=total_selected
    )


# ─────────────────────────────────────────
# PROFILE MANAGEMENT
# ─────────────────────────────────────────

@company_bp.route('/profile')
@login_required(role='company')
def profile():
    db         = get_db()
    company_id = session['company_db_id']

    company = db.execute("""
        SELECT c.*, u.name, u.email, u.status AS account_status
        FROM companies c
        JOIN users u ON c.user_id = u.id
        WHERE c.id = ?
    """, (company_id,)).fetchone()

    return render_template('company/profile.html', company=company)


@company_bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required(role='company')
def edit_profile():
    db         = get_db()
    company_id = session['company_db_id']

    company = db.execute("""
        SELECT c.*, u.name, u.email
        FROM companies c
        JOIN users u ON c.user_id = u.id
        WHERE c.id = ?
    """, (company_id,)).fetchone()

    if not company:
        flash('Company profile not found.', 'danger')
        return redirect(url_for('company.dashboard'))

    if request.method == 'POST':
        company_name     = request.form.get('company_name', '').strip()
        industry         = request.form.get('industry', '').strip()
        website          = request.form.get('website', '').strip()
        description      = request.form.get('description', '').strip()
        hr_contact_name  = request.form.get('hr_contact_name', '').strip()
        hr_contact_email = request.form.get('hr_contact_email', '').strip()
        hr_contact_phone = request.form.get('hr_contact_phone', '').strip()

        if not all([company_name, hr_contact_name, hr_contact_email]):
            flash('Company name, HR contact name and HR email are required.', 'danger')
            return render_template('company/edit_profile.html', company=company)

        db.execute("""
            UPDATE companies
            SET company_name     = ?,
                industry         = ?,
                website          = ?,
                description      = ?,
                hr_contact_name  = ?,
                hr_contact_email = ?,
                hr_contact_phone = ?
            WHERE id = ?
        """, (company_name, industry, website, description,
              hr_contact_name, hr_contact_email, hr_contact_phone,
              company_id))
        db.commit()

        flash('Company profile updated successfully.', 'success')
        return redirect(url_for('company.profile'))

    return render_template('company/edit_profile.html', company=company)


# ─────────────────────────────────────────
# PLACEMENT DRIVE MANAGEMENT
# ─────────────────────────────────────────

@company_bp.route('/drives')
@login_required(role='company')
def drives():
    db         = get_db()
    company_id = session['company_db_id']

    company = db.execute(
        "SELECT approval_status FROM companies WHERE id = ?",
        (company_id,)
    ).fetchone()

    if company['approval_status'] != 'approved':
        flash('Your company account is pending admin approval. '
              'You cannot manage drives yet.', 'warning')
        return redirect(url_for('company.dashboard'))

    sort = request.args.get('sort', 'date')
    sort_map = {
        'date':     'pd.created_at DESC',
        'deadline': 'pd.application_deadline ASC',
        'name':     'pd.job_role ASC',
    }
    order = sort_map.get(sort, 'pd.created_at DESC')

    drives = db.execute(f"""
        SELECT pd.*,
               COUNT(a.id) AS applicant_count
        FROM placement_drives pd
        LEFT JOIN applications a ON a.drive_id = pd.id
        WHERE pd.company_id = ?
        GROUP BY pd.id
        ORDER BY {order}
    """, (company_id,)).fetchall()

    return render_template('company/drives.html', drives=drives, current_sort=sort)


@company_bp.route('/drive/create', methods=['GET', 'POST'])
@login_required(role='company')
def create_drive():
    db         = get_db()
    company_id = session['company_db_id']

    # Only approved companies can create drives
    company = db.execute(
        "SELECT approval_status FROM companies WHERE id = ?",
        (company_id,)
    ).fetchone()

    if company['approval_status'] != 'approved':
        flash('Your company must be approved by admin before creating drives.', 'warning')
        return redirect(url_for('company.dashboard'))

    if request.method == 'POST':
        job_role           = request.form.get('job_role', '').strip()
        job_description     = request.form.get('job_description', '').strip()
        job_type            = request.form.get('job_type', '').strip()
        location            = request.form.get('location', '').strip()
        salary_package      = request.form.get('salary_package', '').strip()
        eligibility_cgpa    = request.form.get('eligibility_cgpa', '0.0').strip()
        eligible_branches   = request.form.getlist('eligible_branches')  # multi-select
        eligible_years      = request.form.getlist('eligible_years')     # multi-select
        application_deadline = request.form.get('application_deadline', '').strip()

        # Validation
        if not all([job_role, job_description, job_type, application_deadline]):
            flash('Job title, description, type and deadline are required.', 'danger')
            return render_template('company/create_drive.html')

        valid_job_types = ['full_time', 'internship', 'contract']
        if job_type not in valid_job_types:
            flash('Invalid job type selected.', 'danger')
            return render_template('company/create_drive.html')

        try:
            eligibility_cgpa = float(eligibility_cgpa)
        except ValueError:
            flash('Eligibility CGPA must be a valid number.', 'danger')
            return render_template('company/create_drive.html')

        if not (0.0 <= eligibility_cgpa <= 10.0):
            flash('Eligibility CGPA must be between 0.0 and 10.0.', 'danger')
            return render_template('company/create_drive.html')

        # Convert lists to comma-separated strings for storage
        eligible_branches_str = ','.join(eligible_branches) if eligible_branches else ''
        eligible_years_str    = ','.join(eligible_years)    if eligible_years    else ''

        db.execute("""
            INSERT INTO placement_drives
                (company_id, job_role, job_description, job_type,
                 location, salary_package, eligibility_cgpa,
                 eligible_branches, eligible_years,
                 application_deadline, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
        """, (company_id, job_role, job_description, job_type,
              location, salary_package, eligibility_cgpa,
              eligible_branches_str, eligible_years_str,
              application_deadline))
        db.commit()

        flash('Placement drive submitted for admin approval.', 'success')
        return redirect(url_for('company.drives'))

    return render_template('company/create_drive.html')


@company_bp.route('/drive/<int:drive_id>/edit', methods=['GET', 'POST'])
@login_required(role='company')
def edit_drive(drive_id):
    db         = get_db()
    company_id = session['company_db_id']

    drive = db.execute("""
        SELECT * FROM placement_drives
        WHERE id = ? AND company_id = ?
    """, (drive_id, company_id)).fetchone()

    if not drive:
        flash('Drive not found or access denied.', 'danger')
        return redirect(url_for('company.drives'))

    # Cannot edit a closed or rejected drive
    if drive['status'] in ('closed', 'rejected'):
        flash('This drive cannot be edited.', 'warning')
        return redirect(url_for('company.drives'))

    if request.method == 'POST':
        job_role            = request.form.get('job_role', '').strip()
        job_description      = request.form.get('job_description', '').strip()
        job_type             = request.form.get('job_type', '').strip()
        location             = request.form.get('location', '').strip()
        salary_package       = request.form.get('salary_package', '').strip()
        eligibility_cgpa     = request.form.get('eligibility_cgpa', '0.0').strip()
        eligible_branches    = request.form.getlist('eligible_branches')
        eligible_years       = request.form.getlist('eligible_years')
        application_deadline = request.form.get('application_deadline', '').strip()

        if not all([job_role, job_description, job_type, application_deadline]):
            flash('Job role, description, type and deadline are required.', 'danger')
            return render_template('company/edit_drive.html', drive=drive)

        try:
            eligibility_cgpa = float(eligibility_cgpa)
        except ValueError:
            flash('Eligibility CGPA must be a valid number.', 'danger')
            return render_template('company/edit_drive.html', drive=drive)

        if not (0.0 <= eligibility_cgpa <= 10.0):
            flash('Eligibility CGPA must be between 0.0 and 10.0.', 'danger')
            return render_template('company/edit_drive.html', drive=drive)

        eligible_branches_str = ','.join(eligible_branches) if eligible_branches else ''
        eligible_years_str    = ','.join(eligible_years)    if eligible_years    else ''

        # Editing resets drive back to pending for re-approval
        db.execute("""
            UPDATE placement_drives
            SET job_role            = ?,
                job_description      = ?,
                job_type             = ?,
                location             = ?,
                salary_package       = ?,
                eligibility_cgpa     = ?,
                eligible_branches    = ?,
                eligible_years       = ?,
                application_deadline = ?,
                status               = 'pending'
            WHERE id = ? AND company_id = ?
        """, (job_role, job_description, job_type, location,
              salary_package, eligibility_cgpa,
              eligible_branches_str, eligible_years_str,
              application_deadline, drive_id, company_id))
        db.commit()

        flash('Drive updated and resubmitted for admin approval.', 'success')
        return redirect(url_for('company.drives'))

    return render_template('company/edit_drive.html', drive=drive)


@company_bp.route('/drive/<int:drive_id>/close', methods=['POST'])
@login_required(role='company')
def close_drive(drive_id):
    db         = get_db()
    company_id = session['company_db_id']

    drive = db.execute("""
        SELECT * FROM placement_drives
        WHERE id = ? AND company_id = ?
    """, (drive_id, company_id)).fetchone()

    if not drive:
        flash('Drive not found or access denied.', 'danger')
        return redirect(url_for('company.drives'))

    if drive['status'] == 'closed':
        flash('Drive is already closed.', 'info')
        return redirect(url_for('company.drives'))

    db.execute(
        "UPDATE placement_drives SET status = 'closed' WHERE id = ?",
        (drive_id,)
    )
    db.commit()
    flash('Placement drive has been closed.', 'secondary')
    return redirect(url_for('company.drives'))


@company_bp.route('/drive/<int:drive_id>/delete', methods=['POST'])
@login_required(role='company')
def delete_drive(drive_id):
    db         = get_db()
    company_id = session['company_db_id']

    drive = db.execute("""
        SELECT * FROM placement_drives
        WHERE id = ? AND company_id = ?
    """, (drive_id, company_id)).fetchone()

    if not drive:
        flash('Drive not found or access denied.', 'danger')
        return redirect(url_for('company.drives'))

    # Only allow deletion of pending or rejected drives
    if drive['status'] in ('approved', 'closed'):
        flash('Approved or closed drives cannot be deleted. Close it first.', 'warning')
        return redirect(url_for('company.drives'))

    db.execute("DELETE FROM placement_drives WHERE id = ?", (drive_id,))
    db.commit()
    flash('Placement drive deleted.', 'danger')
    return redirect(url_for('company.drives'))


# ─────────────────────────────────────────
# APPLICATIONS & SHORTLISTING
# ─────────────────────────────────────────

@company_bp.route('/drive/<int:drive_id>/applications')
@login_required(role='company')
def drive_applications(drive_id):
    db         = get_db()
    company_id = session['company_db_id']

    drive = db.execute("""
        SELECT * FROM placement_drives
        WHERE id = ? AND company_id = ?
    """, (drive_id, company_id)).fetchone()

    if not drive:
        flash('Drive not found or access denied.', 'danger')
        return redirect(url_for('company.drives'))

    status_filter = request.args.get('status', '').strip()
    search        = request.args.get('q', '').strip()
    sort          = request.args.get('sort', 'date')

    sql = """
        SELECT a.*, u.name AS student_name, s.student_id,
               s.branch, s.year, s.cgpa, s.skills,
               s.resume_path, u.email AS student_email, s.phone
        FROM applications a
        JOIN students s ON a.student_id = s.id
        JOIN users u ON s.user_id = u.id
        WHERE a.drive_id = ?
    """
    params = [drive_id]

    if status_filter:
        sql += " AND a.status = ?"
        params.append(status_filter)

    if search:
        sql += " AND (u.name LIKE ? OR s.student_id LIKE ? OR s.branch LIKE ?)"
        like = f'%{search}%'
        params += [like, like, like]

    sort_map = {
        'date': 'a.applied_at DESC',
        'cgpa': 's.cgpa DESC',
        'name': 'u.name ASC',
    }
    sql += f" ORDER BY {sort_map.get(sort, 'a.applied_at DESC')}"

    applications = db.execute(sql, params).fetchall()

    counts = db.execute("""
        SELECT status, COUNT(*) AS cnt
        FROM applications
        WHERE drive_id = ?
        GROUP BY status
    """, (drive_id,)).fetchall()
    status_counts = {row['status']: row['cnt'] for row in counts}

    return render_template('company/drive_applications.html',
        drive=drive,
        applications=applications,
        status_counts=status_counts,
        selected_status=status_filter
    )

@company_bp.route('/application/<int:application_id>/update-status', methods=['POST'])
@login_required(role='company')
def update_application_status(application_id):
    db         = get_db()
    company_id = session['company_db_id']

    new_status = request.form.get('status', '').strip()
    remarks    = request.form.get('remarks', '').strip()

    valid_statuses = ['applied', 'shortlisted', 'selected', 'rejected']
    if new_status not in valid_statuses:
        flash('Invalid status provided.', 'danger')
        return redirect(request.referrer or url_for('company.drives'))

    # Verify the application belongs to one of this company's drives
    application = db.execute("""
        SELECT a.*, pd.company_id, a.drive_id
        FROM applications a
        JOIN placement_drives pd ON a.drive_id = pd.id
        WHERE a.id = ? AND pd.company_id = ?
    """, (application_id, company_id)).fetchone()

    if not application:
        flash('Application not found or access denied.', 'danger')
        return redirect(url_for('company.drives'))

    db.execute("""
        UPDATE applications
        SET status = ?, remarks = ?
        WHERE id = ?
    """, (new_status, remarks, application_id))
    db.commit()

    flash(f'Application status updated to "{new_status}".', 'success')
    return redirect(url_for('company.drive_applications',
                            drive_id=application['drive_id']))


@company_bp.route('/drive/<int:drive_id>/application/<int:application_id>')
@login_required(role='company')
def application_detail(drive_id, application_id):
    db         = get_db()
    company_id = session['company_db_id']

    # Verify drive belongs to this company
    drive = db.execute("""
        SELECT * FROM placement_drives
        WHERE id = ? AND company_id = ?
    """, (drive_id, company_id)).fetchone()

    if not drive:
        flash('Drive not found or access denied.', 'danger')
        return redirect(url_for('company.drives'))

    application = db.execute("""
        SELECT a.*, u.name AS student_name, u.email AS student_email,
               s.student_id, s.branch, s.year, s.cgpa,
               s.skills, s.resume_path, s.phone
        FROM applications a
        JOIN students s ON a.student_id = s.id
        JOIN users u ON s.user_id = u.id
        WHERE a.id = ? AND a.drive_id = ?
    """, (application_id, drive_id)).fetchone()

    if not application:
        flash('Application not found.', 'danger')
        return redirect(url_for('company.drive_applications', drive_id=drive_id))

    return render_template('company/application_detail.html',
        drive=drive,
        application=application
    )