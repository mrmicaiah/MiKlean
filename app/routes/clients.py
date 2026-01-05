"""
Client routes - list, add, view, edit prospects and clients.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from ..auth import login_required, get_current_user_id
from ..supabase_client import get_supabase

bp = Blueprint('clients', __name__)


def format_full_address(client):
    """Format full address string from components."""
    parts = []
    if client.get('street1'):
        parts.append(client['street1'])
    if client.get('street2'):
        parts.append(client['street2'])
    
    city_state_zip = []
    if client.get('city'):
        city_state_zip.append(client['city'])
    if client.get('state'):
        city_state_zip.append(client['state'])
    if client.get('zip_code'):
        city_state_zip.append(client['zip_code'])
    
    if city_state_zip:
        parts.append(', '.join(city_state_zip[:2]) + (' ' + city_state_zip[2] if len(city_state_zip) > 2 else ''))
    
    return ', '.join(parts) if parts else ''


@bp.route('/clients')
@login_required
def list_clients():
    """List all clients/prospects."""
    user_id = get_current_user_id()
    filter_type = request.args.get('type', 'all')
    search = request.args.get('search', '').strip()
    
    supabase = get_supabase()
    
    # Build query
    query = supabase.table('clients').select('*').eq('user_id', user_id)
    
    if filter_type in ['prospect', 'client', 'inactive']:
        query = query.eq('type', filter_type)
    
    if search:
        query = query.or_(f"name.ilike.%{search}%,phone.ilike.%{search}%,city.ilike.%{search}%")
    
    response = query.order('name').execute()
    clients = response.data if response.data else []
    
    # Add formatted address to each client
    for client in clients:
        client['address'] = format_full_address(client)
    
    # Get counts
    count_response = supabase.table('clients').select('type').eq('user_id', user_id).execute()
    all_clients = count_response.data if count_response.data else []
    counts = {
        'all': len(all_clients),
        'prospect': sum(1 for c in all_clients if c['type'] == 'prospect'),
        'client': sum(1 for c in all_clients if c['type'] == 'client'),
    }
    
    return render_template('clients/list.html', 
                           clients=clients, 
                           filter_type=filter_type,
                           search=search,
                           counts=counts)


@bp.route('/clients/new', methods=['GET', 'POST'])
@login_required
def new_client():
    """Add a new prospect."""
    user_id = get_current_user_id()
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip() or None
        notes = request.form.get('notes', '').strip() or None
        
        # Address fields
        street1 = request.form.get('street1', '').strip()
        street2 = request.form.get('street2', '').strip() or None
        city = request.form.get('city', '').strip()
        state = request.form.get('state', '').strip()
        zip_code = request.form.get('zip_code', '').strip()
        
        # Validation
        errors = []
        if not name:
            errors.append('Name is required.')
        if not phone:
            errors.append('Phone is required.')
        if not street1:
            errors.append('Street address is required.')
        if not city:
            errors.append('City is required.')
        if not state:
            errors.append('State is required.')
        if not zip_code:
            errors.append('ZIP code is required.')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('clients/new.html',
                                   name=name, phone=phone, email=email, notes=notes,
                                   street1=street1, street2=street2, city=city, 
                                   state=state, zip_code=zip_code)
        
        # Build full address for legacy compatibility
        address = format_full_address({
            'street1': street1, 'street2': street2,
            'city': city, 'state': state, 'zip_code': zip_code
        })
        
        try:
            supabase = get_supabase()
            response = supabase.table('clients').insert({
                'user_id': user_id,
                'name': name,
                'phone': phone,
                'email': email,
                'notes': notes,
                'address': address,
                'street1': street1,
                'street2': street2,
                'city': city,
                'state': state,
                'zip_code': zip_code,
                'type': 'prospect'
            }).execute()
            
            if response.data:
                flash(f'{name} added as a prospect.', 'success')
                return redirect(url_for('clients.view_client', client_id=response.data[0]['id']))
            else:
                flash('Failed to add prospect.', 'error')
                
        except Exception as e:
            flash('Failed to add prospect.', 'error')
    
    return render_template('clients/new.html')


@bp.route('/clients/<client_id>')
@login_required
def view_client(client_id):
    """View client detail."""
    user_id = get_current_user_id()
    supabase = get_supabase()
    
    # Get client
    response = supabase.table('clients')\
        .select('*')\
        .eq('id', client_id)\
        .eq('user_id', user_id)\
        .single()\
        .execute()
    
    if not response.data:
        flash('Client not found.', 'error')
        return redirect(url_for('clients.list_clients'))
    
    client = response.data
    client['address'] = format_full_address(client)
    
    # Get estimates
    estimates_response = supabase.table('estimates')\
        .select('*')\
        .eq('client_id', client_id)\
        .order('created_at', desc=True)\
        .execute()
    estimates = estimates_response.data if estimates_response.data else []
    
    # Get upcoming visits
    from datetime import date
    today = date.today().isoformat()
    
    upcoming_response = supabase.table('visits')\
        .select('*')\
        .eq('client_id', client_id)\
        .eq('status', 'scheduled')\
        .gte('scheduled_date', today)\
        .order('scheduled_date')\
        .limit(10)\
        .execute()
    upcoming_visits = upcoming_response.data if upcoming_response.data else []
    
    # Get past visits
    past_response = supabase.table('visits')\
        .select('*')\
        .eq('client_id', client_id)\
        .neq('status', 'scheduled')\
        .order('scheduled_date', desc=True)\
        .limit(10)\
        .execute()
    past_visits = past_response.data if past_response.data else []
    
    # Get invoices
    invoices_response = supabase.table('invoices')\
        .select('*')\
        .eq('client_id', client_id)\
        .order('created_at', desc=True)\
        .limit(10)\
        .execute()
    invoices = invoices_response.data if invoices_response.data else []
    
    return render_template('clients/view.html',
                           client=client,
                           estimates=estimates,
                           upcoming_visits=upcoming_visits,
                           past_visits=past_visits,
                           invoices=invoices)


@bp.route('/clients/<client_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_client(client_id):
    """Edit a client."""
    user_id = get_current_user_id()
    supabase = get_supabase()
    
    # Get client
    response = supabase.table('clients')\
        .select('*')\
        .eq('id', client_id)\
        .eq('user_id', user_id)\
        .single()\
        .execute()
    
    if not response.data:
        flash('Client not found.', 'error')
        return redirect(url_for('clients.list_clients'))
    
    client = response.data
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip() or None
        notes = request.form.get('notes', '').strip() or None
        client_type = request.form.get('type', 'prospect')
        
        # Address fields
        street1 = request.form.get('street1', '').strip()
        street2 = request.form.get('street2', '').strip() or None
        city = request.form.get('city', '').strip()
        state = request.form.get('state', '').strip()
        zip_code = request.form.get('zip_code', '').strip()
        
        # Validation
        errors = []
        if not name:
            errors.append('Name is required.')
        if not phone:
            errors.append('Phone is required.')
        if not street1:
            errors.append('Street address is required.')
        if not city:
            errors.append('City is required.')
        if not state:
            errors.append('State is required.')
        if not zip_code:
            errors.append('ZIP code is required.')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            client.update({
                'name': name, 'phone': phone, 'email': email, 'notes': notes,
                'street1': street1, 'street2': street2, 'city': city,
                'state': state, 'zip_code': zip_code, 'type': client_type
            })
            return render_template('clients/edit.html', client=client)
        
        # Build full address
        address = format_full_address({
            'street1': street1, 'street2': street2,
            'city': city, 'state': state, 'zip_code': zip_code
        })
        
        try:
            supabase.table('clients').update({
                'name': name,
                'phone': phone,
                'email': email,
                'notes': notes,
                'address': address,
                'street1': street1,
                'street2': street2,
                'city': city,
                'state': state,
                'zip_code': zip_code,
                'type': client_type
            }).eq('id', client_id).eq('user_id', user_id).execute()
            
            flash('Client updated.', 'success')
            return redirect(url_for('clients.view_client', client_id=client_id))
            
        except Exception as e:
            flash('Failed to update client.', 'error')
    
    return render_template('clients/edit.html', client=client)


@bp.route('/clients/<client_id>/convert', methods=['POST'])
@login_required
def convert_to_client(client_id):
    """Convert a prospect to a client."""
    user_id = get_current_user_id()
    supabase = get_supabase()
    
    try:
        supabase.table('clients').update({
            'type': 'client'
        }).eq('id', client_id).eq('user_id', user_id).execute()
        
        flash('Converted to client.', 'success')
    except:
        flash('Failed to convert.', 'error')
    
    return redirect(url_for('clients.view_client', client_id=client_id))


@bp.route('/clients/<client_id>/deactivate', methods=['POST'])
@login_required
def deactivate_client(client_id):
    """Mark a client as inactive."""
    user_id = get_current_user_id()
    supabase = get_supabase()
    
    cancel_visits = request.form.get('cancel_visits') == 'on'
    
    try:
        # Update client type
        supabase.table('clients').update({
            'type': 'inactive'
        }).eq('id', client_id).eq('user_id', user_id).execute()
        
        # Optionally cancel future visits
        if cancel_visits:
            from datetime import date
            supabase.table('visits').update({
                'status': 'cancelled'
            }).eq('client_id', client_id)\
              .eq('user_id', user_id)\
              .eq('status', 'scheduled')\
              .gte('scheduled_date', date.today().isoformat())\
              .execute()
        
        flash('Client deactivated.', 'success')
    except:
        flash('Failed to deactivate.', 'error')
    
    return redirect(url_for('clients.view_client', client_id=client_id))
