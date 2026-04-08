CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN('admin','company','student')),
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN('active','deactivated','blacklisted')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS students(
    ID INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    student_id TEXT NOT NULL UNIQUE,
    phone TEXT,
    branch TEXT not NULL,
    year INTEGER NOT NULL,
    cgpa REAL NOT NULL,
    resume_path TEXT,
    skills TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    company_name TEXT NOT NULL,
    industry TEXT,
    website TEXT,
    hr_contact_name TEXT,
    hr_contact_email TEXT,
    hr_contact_phone TEXT,
    description TEXT,
    approval_status TEXT NOT NULL DEFAULT 'pending'
        CHECK(approval_status IN ('pending', 'approved', 'rejected')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    drive_id INTEGER NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'applied'
        CHECK(status IN ('applied', 'shortlisted', 'selected', 'rejected')),
    remarks TEXT,                         -- optional note from company
    UNIQUE(student_id, drive_id),         -- prevents duplicate applications
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    FOREIGN KEY (drive_id) REFERENCES placement_drives(id) ON DELETE CASCADE
);
DROP TABLE IF EXISTS placement_drives;

CREATE TABLE placement_drives (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    job_role TEXT NOT NULL,
    job_description TEXT NOT NULL,
    job_type TEXT NOT NULL CHECK(job_type IN ('full_time','internship','contract')),
    location TEXT,
    salary_package TEXT,
    eligibility_cgpa REAL DEFAULT 0.0,
    eligible_branches TEXT,
    eligible_years TEXT,
    application_deadline DATE NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK(status IN ('pending','approved','rejected','closed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
);