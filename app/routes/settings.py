"""
Settings routes - business info, Google Calendar connection.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, session
from ..auth import login_required, get_current_user_id, get_user_profile
from ..supabase_client import get_supabase

bp = Blueprint('settings', __name__, url_prefix='/settings')


@bp.route('/')
@login_required
def index():
    """Settings page."""
    profile = get_user_profile()
    user_email = session.get('user_email', '')
    
    return render_template('settings/index.html', 
                           profile=profile,
                           user_email=user_email)


@bp.route('/business', methods=['GET', 'POST'])
@login_required
def business_info():
    """Edit business information."""
    user_id = get_current_user_id()
    supabase = get_supabase()
    profile = get_user_profile()
    
    if request.method == 'POST':
        business_name = request.form.get('business_name', '').strip() or None
        business_phone = request.form.get('business_phone', '').strip() or None
        
        try:
            supabase.table('user_profiles').update({
                'business_name': business_name,
                'business_phone': business_phone
            }).eq('id', user_id).execute()
            
            flash('Business information updated.', 'success')
            return redirect(url_for('settings.index'))
            
        except Exception as e:
            flash('Failed to update business information.', 'error')
    
    return render_template('settings/business.html', profile=profile)


@bp.route('/payment', methods=['GET', 'POST'])
@login_required
def payment_instructions():
    """Edit payment instructions."""
    user_id = get_current_user_id()
    supabase = get_supabase()
    profile = get_user_profile()
    
    if request.method == 'POST':
        payment_instructions = request.form.get('payment_instructions', '').strip() or None
        
        try:
            supabase.table('user_profiles').update({
                'payment_instructions': payment_instructions
            }).eq('id', user_id).execute()
            
            flash('Payment instructions updated.', 'success')
            return redirect(url_for('settings.index'))
            
        except Exception as e:
            flash('Failed to update payment instructions.', 'error')
    
    return render_template('settings/payment.html', profile=profile)


@bp.route('/logo', methods=['GET', 'POST'])
@login_required
def upload_logo():
    """Upload business logo."""
    user_id = get_current_user_id()
    supabase = get_supabase()
    profile = get_user_profile()
    
    if request.method == 'POST':
        if 'logo' not in request.files:
            flash('No file selected.', 'error')
            return redirect(url_for('settings.upload_logo'))
        
        file = request.files['logo']
        
        if file.filename == '':
            flash('No file selected.', 'error')
            return redirect(url_for('settings.upload_logo'))
        
        # Check file type
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
        file_ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
        
        if file_ext not in allowed_extensions:
            flash('Please upload a PNG, JPG, or GIF image.', 'error')
            return redirect(url_for('settings.upload_logo'))
        
        try:
            # Read file data
            file_data = file.read()
            
            # Upload to Supabase Storage
            path = f"logos/{user_id}/logo.{file_ext}"
            
            # Delete old logo if exists
            try:
                supabase.storage.from_('miklean-files').remove([path])
            except:
                pass
            
            # Upload new logo
            supabase.storage.from_('miklean-files').upload(
                path,
                file_data,
                {'content-type': f'image/{file_ext}'}
            )
            
            # Get public URL
            logo_url = supabase.storage.from_('miklean-files').get_public_url(path)
            
            # Update profile
            supabase.table('user_profiles').update({
                'business_logo_url': logo_url
            }).eq('id', user_id).execute()
            
            flash('Logo uploaded.', 'success')
            return redirect(url_for('settings.index'))
            
        except Exception as e:
            flash('Failed to upload logo. Please try again.', 'error')
    
    return render_template('settings/logo.html', profile=profile)


@bp.route('/google/connect')
@login_required
def google_connect():
    """Start Google OAuth flow for Calendar access."""
    # TODO: Implement Google OAuth
    # This requires setting up Google Cloud project, OAuth credentials, etc.
    flash('Google Calendar integration coming soon.', 'info')
    return redirect(url_for('settings.index'))


@bp.route('/google/callback')
@login_required
def google_callback():
    """Handle Google OAuth callback."""
    # TODO: Implement OAuth callback
    return redirect(url_for('settings.index'))


@bp.route('/google/disconnect', methods=['POST'])
@login_required
def google_disconnect():
    """Disconnect Google Calendar."""
    user_id = get_current_user_id()
    supabase = get_supabase()
    
    try:
        supabase.table('user_profiles').update({
            'google_access_token': None,
            'google_refresh_token': None,
            'google_token_expiry': None,
            'google_calendar_id': None
        }).eq('id', user_id).execute()
        
        flash('Google Calendar disconnected.', 'success')
        
    except Exception as e:
        flash('Failed to disconnect Google Calendar.', 'error')
    
    return redirect(url_for('settings.index'))
