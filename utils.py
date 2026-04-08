from functools import wraps
from flask import session, redirect, url_for, flash

def login_required(role=None):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please log in to continue.', 'warning')
                return redirect(url_for('auth.login'))
            if role and session.get('role') != role:
                flash('You are not authorized to access this page.', 'danger')
                return redirect(url_for('auth.login'))
            return f(*args, **kwargs)
        return wrapper
    return decorator