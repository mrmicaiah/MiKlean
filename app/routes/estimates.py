"""
Estimate routes - create, view, edit, send, accept, PDF download.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_file
from datetime import datetime
import secrets
from ..auth import login_required, get_current_user_id, get_user_profile
from ..supabase_client import get_supabase

bp = Blueprint('estimates', __name__)


@bp.route('/clients/<client_id>/estimates/new', methods=['GET', 'POST'])
@login_required
def new_estimate(client_id):
    """Create a new estimate for a client."""
    user_id = get_current_user_id()
    supabase = get_supabase()
    
    # Get client
    client_response = supabase.table('clients')\
        .select('*')\
        .eq('id', client_id)\
        .eq('user_id', user_id)\
        .single()\
        .execute()
    
    if not client_response.data:
        flash('Client not found.', 'error')
        return redirect(url_for('clients.list_clients'))
    
    client = client_response.data
    
    if request.method == 'POST':
        description = request.form.get('description', '').strip()
        price_per_visit = request.form.get('price_per_visit', '').strip()
        frequency = request.form.get('frequency', '').strip()
        preferred_day = request.form.get('preferred_day', '').strip() or None
        preferred_time = request.form.get('preferred_time', '').strip() or None
        show_monthly_rate = request.form.get('show_monthly_rate') == 'on'
        
        # Validation
        errors = []
        if not description:
            errors.append('Service description is required.')
        if not price_per_visit:
            errors.append('Price per visit is required.')
        else:
            try:
                price_per_visit = float(price_per_visit.replace('$', '').replace(',', ''))
                if price_per_visit <= 0:
                    errors.append('Price must be greater than zero.')
            except ValueError:
                errors.append('Invalid price format.')
        if frequency not in ['weekly', 'biweekly', 'monthly', 'one_time']:
            errors.append('Please select a frequency.')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('estimates/new.html', client=client,
                                   description=description, 
                                   price_per_visit=request.form.get('price_per_visit'),
                                   frequency=frequency,
                                   preferred_day=preferred_day,
                                   preferred_time=preferred_time,
                                   show_monthly_rate=show_monthly_rate)
        
        try:
            response = supabase.table('estimates').insert({
                'client_id': client_id,
                'user_id': user_id,
                'description': description,
                'price_per_visit': price_per_visit,
                'frequency': frequency,
                'preferred_day': preferred_day,
                'preferred_time': preferred_time,
                'show_monthly_rate': show_monthly_rate if frequency != 'one_time' else False,
                'status': 'draft'
            }).execute()
            
            if response.data:
                flash('Estimate created.', 'success')
                return redirect(url_for('estimates.view_estimate', estimate_id=response.data[0]['id']))
            else:
                flash('Failed to create estimate.', 'error')
                
        except Exception as e:
            flash('Failed to create estimate.', 'error')
    
    return render_template('estimates/new.html', client=client)


@bp.route('/estimates/<estimate_id>')
@login_required
def view_estimate(estimate_id):
    """View estimate detail."""
    user_id = get_current_user_id()
    supabase = get_supabase()
    
    # Get estimate with client info
    response = supabase.table('estimates')\
        .select('*, clients(name, phone, email, address)')\
        .eq('id', estimate_id)\
        .eq('user_id', user_id)\
        .single()\
        .execute()
    
    if not response.data:
        flash('Estimate not found.', 'error')
        return redirect(url_for('clients.list_clients'))
    
    estimate = response.data
    
    # Calculate monthly rate
    monthly_rate = calculate_monthly_rate(estimate['price_per_visit'], estimate['frequency'])
    
    return render_template('estimates/view.html', 
                           estimate=estimate,
                           monthly_rate=monthly_rate)


@bp.route('/estimates/<estimate_id>/accept', methods=['POST'])
@login_required
def accept_estimate(estimate_id):
    """Manually accept an estimate from the app."""
    user_id = get_current_user_id()
    supabase = get_supabase()
    
    # Get estimate
    response = supabase.table('estimates')\
        .select('*, clients(name)')\
        .eq('id', estimate_id)\
        .eq('user_id', user_id)\
        .single()\
        .execute()
    
    if not response.data:
        flash('Estimate not found.', 'error')
        return redirect(url_for('clients.list_clients'))
    
    estimate = response.data
    
    # Already accepted?
    if estimate['status'] == 'accepted':
        flash('Estimate already accepted.', 'info')
        return redirect(url_for('estimates.view_estimate', estimate_id=estimate_id))
    
    try:
        # Accept the estimate
        supabase.table('estimates').update({
            'status': 'accepted',
            'accepted_at': datetime.utcnow().isoformat()
        }).eq('id', estimate_id).execute()
        
        # Convert prospect to client if needed
        supabase.table('clients').update({
            'type': 'client'
        }).eq('id', estimate['client_id']).eq('type', 'prospect').execute()
        
        flash(f'Estimate accepted! {estimate["clients"]["name"]} is now a client.', 'success')
        
    except Exception as e:
        flash('Failed to accept estimate.', 'error')
    
    return redirect(url_for('estimates.view_estimate', estimate_id=estimate_id))


@bp.route('/estimates/<estimate_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_estimate(estimate_id):
    """Edit an estimate."""
    user_id = get_current_user_id()
    supabase = get_supabase()
    
    # Get estimate
    response = supabase.table('estimates')\
        .select('*, clients(name)')\
        .eq('id', estimate_id)\
        .eq('user_id', user_id)\
        .single()\
        .execute()
    
    if not response.data:
        flash('Estimate not found.', 'error')
        return redirect(url_for('clients.list_clients'))
    
    estimate = response.data
    
    # Can only edit draft or sent estimates
    if estimate['status'] not in ['draft', 'sent']:
        flash('Cannot edit an accepted estimate.', 'error')
        return redirect(url_for('estimates.view_estimate', estimate_id=estimate_id))
    
    if request.method == 'POST':
        description = request.form.get('description', '').strip()
        price_per_visit = request.form.get('price_per_visit', '').strip()
        frequency = request.form.get('frequency', '').strip()
        preferred_day = request.form.get('preferred_day', '').strip() or None
        preferred_time = request.form.get('preferred_time', '').strip() or None
        show_monthly_rate = request.form.get('show_monthly_rate') == 'on'
        
        # Validation
        errors = []
        if not description:
            errors.append('Service description is required.')
        if not price_per_visit:
            errors.append('Price per visit is required.')
        else:
            try:
                price_per_visit = float(price_per_visit.replace('$', '').replace(',', ''))
                if price_per_visit <= 0:
                    errors.append('Price must be greater than zero.')
            except ValueError:
                errors.append('Invalid price format.')
        if frequency not in ['weekly', 'biweekly', 'monthly', 'one_time']:
            errors.append('Please select a frequency.')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            estimate.update({
                'description': description,
                'price_per_visit': request.form.get('price_per_visit'),
                'frequency': frequency,
                'preferred_day': preferred_day,
                'preferred_time': preferred_time,
                'show_monthly_rate': show_monthly_rate
            })
            return render_template('estimates/edit.html', estimate=estimate)
        
        try:
            supabase.table('estimates').update({
                'description': description,
                'price_per_visit': price_per_visit,
                'frequency': frequency,
                'preferred_day': preferred_day,
                'preferred_time': preferred_time,
                'show_monthly_rate': show_monthly_rate if frequency != 'one_time' else False
            }).eq('id', estimate_id).eq('user_id', user_id).execute()
            
            flash('Estimate updated.', 'success')
            return redirect(url_for('estimates.view_estimate', estimate_id=estimate_id))
            
        except Exception as e:
            flash('Failed to update estimate.', 'error')
    
    return render_template('estimates/edit.html', estimate=estimate)


@bp.route('/estimates/<estimate_id>/preview')
@login_required
def preview_estimate(estimate_id):
    """Preview estimate as client will see it."""
    user_id = get_current_user_id()
    supabase = get_supabase()
    
    # Get estimate with client info
    response = supabase.table('estimates')\
        .select('*, clients(name, phone, email, address)')\
        .eq('id', estimate_id)\
        .eq('user_id', user_id)\
        .single()\
        .execute()
    
    if not response.data:
        flash('Estimate not found.', 'error')
        return redirect(url_for('clients.list_clients'))
    
    estimate = response.data
    profile = get_user_profile()
    monthly_rate = calculate_monthly_rate(estimate['price_per_visit'], estimate['frequency'])
    
    return render_template('estimates/preview.html',
                           estimate=estimate,
                           profile=profile,
                           monthly_rate=monthly_rate,
                           is_preview=True)


@bp.route('/estimates/<estimate_id>/pdf')
@login_required
def download_estimate_pdf(estimate_id):
    """Download estimate as PDF."""
    user_id = get_current_user_id()
    supabase = get_supabase()
    
    # Get estimate with client info
    response = supabase.table('estimates')\
        .select('*, clients(name, phone, email, address)')\
        .eq('id', estimate_id)\
        .eq('user_id', user_id)\
        .single()\
        .execute()
    
    if not response.data:
        flash('Estimate not found.', 'error')
        return redirect(url_for('clients.list_clients'))
    
    estimate = response.data
    profile = get_user_profile()
    monthly_rate = calculate_monthly_rate(estimate['price_per_visit'], estimate['frequency'])
    
    # Generate PDF
    from ..services.pdf import generate_estimate_pdf
    pdf_file = generate_estimate_pdf(estimate, profile, monthly_rate)
    
    filename = f"Estimate_{estimate['clients']['name'].replace(' ', '_')}.pdf"
    
    return send_file(
        pdf_file,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )


@bp.route('/estimates/<estimate_id>/send', methods=['GET', 'POST'])
@login_required
def send_estimate(estimate_id):
    """Send estimate to client."""
    user_id = get_current_user_id()
    supabase = get_supabase()
    
    # Get estimate with client info
    response = supabase.table('estimates')\
        .select('*, clients(name, phone, email)')\
        .eq('id', estimate_id)\
        .eq('user_id', user_id)\
        .single()\
        .execute()
    
    if not response.data:
        flash('Estimate not found.', 'error')
        return redirect(url_for('clients.list_clients'))
    
    estimate = response.data
    client = estimate['clients']
    
    if request.method == 'POST':
        send_method = request.form.get('method')
        
        # Generate accept token if not exists
        if not estimate.get('accept_token'):
            accept_token = secrets.token_urlsafe(32)
            supabase.table('estimates').update({
                'accept_token': accept_token
            }).eq('id', estimate_id).execute()
        else:
            accept_token = estimate['accept_token']
        
        accept_url = f"{current_app.config['APP_URL']}/accept/{estimate_id}/{accept_token}"
        
        if send_method == 'email':
            if not client.get('email'):
                flash('Client has no email address. Please add one first.', 'error')
                return redirect(url_for('clients.edit_client', client_id=estimate['client_id']))
            
            # TODO: Send email via SendGrid with PDF attachment
            # For now, mark as sent
            supabase.table('estimates').update({
                'status': 'sent',
                'sent_at': datetime.utcnow().isoformat()
            }).eq('id', estimate_id).execute()
            
            flash(f'Estimate sent to {client["email"]}.', 'success')
            return redirect(url_for('estimates.view_estimate', estimate_id=estimate_id))
            
        elif send_method == 'text':
            # Generate SMS message
            profile = get_user_profile()
            business_name = profile.get('business_name') or 'Your cleaner'
            message = f"Hi {client['name']}! {business_name} sent you an estimate. View and accept here: {accept_url}"
            
            # Update status
            supabase.table('estimates').update({
                'status': 'sent',
                'sent_at': datetime.utcnow().isoformat()
            }).eq('id', estimate_id).execute()
            
            # Redirect to SMS app
            sms_url = f"sms:{client['phone']}?body={message}"
            return redirect(sms_url)
    
    return render_template('estimates/send.html', estimate=estimate, client=client)


@bp.route('/accept/<estimate_id>/<token>')
def accept_estimate_page(estimate_id, token):
    """Public page for client to accept estimate."""
    supabase = get_supabase()
    
    # Get estimate by token (no user auth required)
    response = supabase.table('estimates')\
        .select('*, clients(name), user_profiles!estimates_user_id_fkey(business_name, business_phone)')\
        .eq('id', estimate_id)\
        .eq('accept_token', token)\
        .single()\
        .execute()
    
    if not response.data:
        return render_template('estimates/accept_invalid.html'), 404
    
    estimate = response.data
    
    # Already accepted?
    if estimate['status'] == 'accepted':
        return render_template('estimates/accept_already.html', estimate=estimate)
    
    monthly_rate = calculate_monthly_rate(estimate['price_per_visit'], estimate['frequency'])
    
    return render_template('estimates/accept.html',
                           estimate=estimate,
                           monthly_rate=monthly_rate,
                           token=token)


@bp.route('/accept/<estimate_id>/<token>/confirm', methods=['POST'])
def confirm_accept_estimate(estimate_id, token):
    """Handle estimate acceptance from public link."""
    supabase = get_supabase()
    
    # Verify token
    response = supabase.table('estimates')\
        .select('*, clients(name)')\
        .eq('id', estimate_id)\
        .eq('accept_token', token)\
        .single()\
        .execute()
    
    if not response.data:
        return render_template('estimates/accept_invalid.html'), 404
    
    estimate = response.data
    
    if estimate['status'] == 'accepted':
        return render_template('estimates/accept_already.html', estimate=estimate)
    
    # Accept the estimate
    supabase.table('estimates').update({
        'status': 'accepted',
        'accepted_at': datetime.utcnow().isoformat()
    }).eq('id', estimate_id).execute()
    
    # Convert prospect to client if needed
    supabase.table('clients').update({
        'type': 'client'
    }).eq('id', estimate['client_id']).eq('type', 'prospect').execute()
    
    return render_template('estimates/accept_success.html', estimate=estimate)


def calculate_monthly_rate(price_per_visit, frequency):
    """Calculate monthly rate based on frequency."""
    if frequency == 'weekly':
        return price_per_visit * 4.33
    elif frequency == 'biweekly':
        return price_per_visit * 2.17
    elif frequency == 'monthly':
        return price_per_visit
    else:  # one_time
        return None
