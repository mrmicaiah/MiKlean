"""
Authentication routes - login, register, logout.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from ..supabase_client import get_supabase_anon, get_supabase

bp = Blueprint('auth', __name__)


@bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login page and handler."""
    # If already logged in, redirect to home
    if 'access_token' in session:
        return redirect(url_for('main.today'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        
        if not email or not password:
            flash('Please enter email and password.', 'error')
            return render_template('auth/login.html')
        
        try:
            supabase = get_supabase_anon()
            response = supabase.auth.sign_in_with_password({
                'email': email,
                'password': password
            })
            
            if response.user and response.session:
                # Store session tokens
                session['access_token'] = response.session.access_token
                session['refresh_token'] = response.session.refresh_token
                session['user_id'] = response.user.id
                session['user_email'] = response.user.email
                
                flash('Welcome back!', 'success')
                return redirect(url_for('main.today'))
            else:
                flash('Invalid email or password.', 'error')
                
        except Exception as e:
            error_msg = str(e)
            if 'Invalid login credentials' in error_msg:
                flash('Invalid email or password.', 'error')
            elif 'Email not confirmed' in error_msg:
                flash('Please check your email and confirm your account first.', 'error')
            else:
                flash('Login failed. Please try again.', 'error')
    
    return render_template('auth/login.html')


@bp.route('/register', methods=['GET', 'POST'])
def register():
    """Registration page and handler."""
    # If already logged in, redirect to home
    if 'access_token' in session:
        return redirect(url_for('main.today'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        password_confirm = request.form.get('password_confirm', '')
        business_name = request.form.get('business_name', '').strip()
        
        # Validation
        errors = []
        if not email:
            errors.append('Email is required.')
        if not password:
            errors.append('Password is required.')
        if len(password) < 6:
            errors.append('Password must be at least 6 characters.')
        if password != password_confirm:
            errors.append('Passwords do not match.')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('auth/register.html', 
                                   email=email, 
                                   business_name=business_name)
        
        try:
            supabase = get_supabase_anon()
            
            # Create auth user
            response = supabase.auth.sign_up({
                'email': email,
                'password': password
            })
            
            if response.user:
                # Create user profile
                supabase_admin = get_supabase()
                supabase_admin.table('user_profiles').insert({
                    'id': response.user.id,
                    'email': email,
                    'business_name': business_name or None
                }).execute()
                
                # If session returned (email confirmation disabled), log them in
                if response.session:
                    session['access_token'] = response.session.access_token
                    session['refresh_token'] = response.session.refresh_token
                    session['user_id'] = response.user.id
                    session['user_email'] = response.user.email
                    session['is_new_user'] = True  # Flag for onboarding
                    
                    flash('Account created! Let\'s set up your business.', 'success')
                    return redirect(url_for('onboarding.start'))
                else:
                    # Email confirmation required
                    flash('Account created! Please check your email to confirm, then log in.', 'success')
                    return redirect(url_for('auth.login'))
            else:
                flash('Registration failed. Please try again.', 'error')
                
        except Exception as e:
            error_msg = str(e)
            if 'User already registered' in error_msg:
                flash('An account with this email already exists.', 'error')
            else:
                flash('Registration failed. Please try again.', 'error')
    
    return render_template('auth/register.html')


@bp.route('/logout')
def logout():
    """Log out the current user."""
    try:
        if 'access_token' in session:
            supabase = get_supabase_anon()
            supabase.auth.sign_out()
    except:
        pass  # Ignore errors during logout
    
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


@bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Password reset request page."""
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        
        if not email:
            flash('Please enter your email address.', 'error')
            return render_template('auth/forgot_password.html')
        
        try:
            supabase = get_supabase_anon()
            supabase.auth.reset_password_email(email)
            flash('If an account exists with that email, you will receive a password reset link.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            # Don't reveal whether email exists
            flash('If an account exists with that email, you will receive a password reset link.', 'success')
            return redirect(url_for('auth.login'))
    
    return render_template('auth/forgot_password.html')
