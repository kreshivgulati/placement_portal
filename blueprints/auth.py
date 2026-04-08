from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from database import get_db
from werkzeug.security import generate_password_hash, check_password_hash

auth_bp = Blueprint('auth', __name__)


# HELPER — clear session fully on logout
def clear_session():
    session.clear()

# HOME — redirect based on role

@auth_bp.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    role = session.get('role')
    if role == 'admin':
        return redirect(url_for('admin.dashboard'))
    elif role == 'company':
        return redirect(url_for('company.dashboard'))
    elif role == 'student':
        return redirect(url_for('student.dashboard'))

    return redirect(url_for('auth.login'))


# LOGIN

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # Already logged in — redirect away
    if 'user_id' in session:
        return redirect(url_for('auth.index'))

    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()

        if not email or not password:
            flash('Email and password are required.', 'danger')
            return render_template('auth/login.html')

        db   = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()

        # Wrong email or password
        if not user or not check_password_hash(user['password'], password):
            flash('Invalid email or password.', 'danger')
            return render_template('auth/login.html')

        # Blacklisted or deactivated account
        if user['status'] in ('blacklisted', 'deactivated'):
            flash('Your account has been deactivated. '
                  'Please contact the placement cell.', 'danger')
            return render_template('auth/login.html')

        # Company must be approved before logging in
        if user['role'] == 'company':
            company = db.execute(
                "SELECT approval_status FROM companies WHERE user_id = ?",
                (user['id'],)
            ).fetchone()

            if not company:
                flash('Company profile not found. Contact admin.', 'danger')
                return render_template('auth/login.html')

            if company['approval_status'] == 'pending':
                flash('Your company registration is pending admin approval. '
                      'Please check back later.', 'warning')
                return render_template('auth/login.html')

            if company['approval_status'] == 'rejected':
                flash('Your company registration was rejected. '
                      'Please contact the placement cell.', 'danger')
                return render_template('auth/login.html')

        # ── Set session ──────────────────────────
        session['user_id'] = user['id']
        session['role']    = user['role']
        session['name']    = user['name']

        if user['role'] == 'student':
            student = db.execute(
                "SELECT id FROM students WHERE user_id = ?", (user['id'],)
            ).fetchone()
            session['student_db_id'] = student['id']

        elif user['role'] == 'company':
            company = db.execute(
                "SELECT id FROM companies WHERE user_id = ?", (user['id'],)
            ).fetchone()
            session['company_db_id'] = company['id']

        flash(f'Welcome back, {user["name"]}!', 'success')
        return redirect(url_for('auth.index'))

    return render_template('auth/login.html')


# LOGOUT

@auth_bp.route('/logout')
def logout():
    name = session.get('name', 'User')
    clear_session()
    flash(f'Goodbye, {name}. You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


# STUDENT REGISTRATION

@auth_bp.route('/register/student', methods=['GET', 'POST'])
def register_student():
    if 'user_id' in session:
        return redirect(url_for('auth.index'))

    if request.method == 'POST':
        name       = request.form.get('name', '').strip()
        email      = request.form.get('email', '').strip().lower()
        password   = request.form.get('password', '').strip()
        confirm    = request.form.get('confirm_password', '').strip()
        student_id = request.form.get('student_id', '').strip().upper()
        phone      = request.form.get('phone', '').strip()
        branch     = request.form.get('branch', '').strip()
        year       = request.form.get('year', '').strip()
        cgpa       = request.form.get('cgpa', '').strip()

        # ── Field validation ─────────────────────
        if not all([name, email, password, confirm, student_id, branch, year, cgpa]):
            flash('All fields except phone are required.', 'danger')
            return render_template('auth/register_student.html')

        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/register_student.html')

        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'danger')
            return render_template('auth/register_student.html')

        try:
            year = int(year)
            cgpa = float(cgpa)
        except ValueError:
            flash('Year must be a whole number and CGPA must be a decimal.', 'danger')
            return render_template('auth/register_student.html')

        if year not in range(1, 5):
            flash('Year must be between 1 and 4.', 'danger')
            return render_template('auth/register_student.html')

        if not (0.0 <= cgpa <= 10.0):
            flash('CGPA must be between 0.0 and 10.0.', 'danger')
            return render_template('auth/register_student.html')

        db = get_db()

        # ── Uniqueness checks ────────────────────
        if db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone():
            flash('An account with this email already exists.', 'danger')
            return render_template('auth/register_student.html')

        if db.execute(
            "SELECT id FROM students WHERE student_id = ?", (student_id,)
        ).fetchone():
            flash('This Student ID is already registered.', 'danger')
            return render_template('auth/register_student.html')

        # ── Insert user + student ────────────────
        hashed = generate_password_hash(password)

        cursor = db.execute(
            """INSERT INTO users (name, email, password, role, status)
               VALUES (?, ?, ?, 'student', 'active')""",
            (name, email, hashed)
        )
        user_id = cursor.lastrowid

        db.execute(
            """INSERT INTO students
                   (user_id, student_id, phone, branch, year, cgpa)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, student_id, phone, branch, year, cgpa)
        )
        db.commit()

        flash('Registration successful! You can now log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register_student.html')


# COMPANY REGISTRATION
@auth_bp.route('/register/company', methods=['GET', 'POST'])
def register_company():
    if 'user_id' in session:
        return redirect(url_for('auth.index'))

    if request.method == 'POST':
        # User fields
        name     = request.form.get('name', '').strip()
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        confirm  = request.form.get('confirm_password', '').strip()

        # Company fields
        company_name     = request.form.get('company_name', '').strip()
        industry         = request.form.get('industry', '').strip()
        website          = request.form.get('website', '').strip()
        description      = request.form.get('description', '').strip()
        hr_contact_name  = request.form.get('hr_contact_name', '').strip()
        hr_contact_email = request.form.get('hr_contact_email', '').strip().lower()
        hr_contact_phone = request.form.get('hr_contact_phone', '').strip()

        # ── Field validation ─────────────────────
        if not all([name, email, password, confirm,
                    company_name, hr_contact_name, hr_contact_email]):
            flash('All required fields must be filled.', 'danger')
            return render_template('auth/register_company.html')

        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/register_company.html')

        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'danger')
            return render_template('auth/register_company.html')

        db = get_db()

        # ── Uniqueness checks ────────────────────
        if db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone():
            flash('An account with this email already exists.', 'danger')
            return render_template('auth/register_company.html')

        if db.execute(
            "SELECT id FROM companies WHERE company_name = ?", (company_name,)
        ).fetchone():
            flash('A company with this name is already registered.', 'danger')
            return render_template('auth/register_company.html')

        # ── Insert user + company ────────────────
        hashed = generate_password_hash(password)

        cursor = db.execute(
            """INSERT INTO users (name, email, password, role, status)
               VALUES (?, ?, ?, 'company', 'active')""",
            (name, email, hashed)
        )
        user_id = cursor.lastrowid

        db.execute(
            """INSERT INTO companies
                   (user_id, company_name, industry, website, description,
                    hr_contact_name, hr_contact_email, hr_contact_phone,
                    approval_status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')""",
            (user_id, company_name, industry, website, description,
             hr_contact_name, hr_contact_email, hr_contact_phone)
        )
        db.commit()

        flash('Company registered successfully! '
              'Please wait for admin approval before logging in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register_company.html')