"""
Visit routes - view, complete, schedule, cancel.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from ..auth import login_required, get_current_user_id
from ..supabase_client import get_supabase

bp = Blueprint('visits', __name__)


@bp.route('/schedule')
@login_required
def pick_client_for_schedule():
    """Pick a client to schedule a visit for."""
    user_id = get_current_user_id()
    supabase = get_supabase()
    
    search = request.args.get('search', '').strip()
    
    # Get all clients (both prospects and clients can be scheduled)
    query = supabase.table('clients')\
        .select('id, name, phone, address, type')\
        .eq('user_id', user_id)\
        .order('name')
    
    if search:
        query = query.ilike('name', f'%{search}%')
    
    response = query.execute()
    clients = response.data if response.data else []
    
    return render_template('visits/pick_client.html', clients=clients, search=search)


@bp.route('/clients/<client_id>/schedule', methods=['GET', 'POST'])
@login_required
def schedule_visits(client_id):
    """Add a client to the schedule - either one-time or recurring."""
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
    
    # Get their most recent accepted estimate for defaults
    estimate_response = supabase.table('estimates')\
        .select('*')\
        .eq('client_id', client_id)\
        .eq('status', 'accepted')\
        .order('accepted_at', desc=True)\
        .limit(1)\
        .execute()
    
    estimate = estimate_response.data[0] if estimate_response.data else None
    
    if request.method == 'POST':
        start_date_str = request.form.get('start_date', '').strip()
        schedule_type = request.form.get('frequency', 'one_time')  # one_time or recurring
        recurring_frequency = request.form.get('recurring_frequency', 'weekly')
        custom_months = request.form.get('custom_months', '3')
        num_visits = int(request.form.get('num_visits', '8'))
        preferred_time_str = request.form.get('preferred_time', '').strip() or None
        price_str = request.form.get('price', '').strip()
        
        # Validation
        errors = []
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except ValueError:
            errors.append('Invalid start date.')
            start_date = None
        
        # Parse price
        price = None
        if price_str:
            try:
                # Remove $ and commas
                price_clean = price_str.replace('$', '').replace(',', '').strip()
                price = float(Decimal(price_clean))
            except (InvalidOperation, ValueError):
                errors.append('Invalid price format.')
        
        if not price:
            errors.append('Price is required.')
        
        # Parse custom months if needed
        if recurring_frequency == 'custom':
            try:
                custom_months_int = int(custom_months)
                if custom_months_int < 1 or custom_months_int > 12:
                    errors.append('Custom months must be between 1 and 12.')
            except ValueError:
                errors.append('Invalid custom months value.')
                custom_months_int = 3
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('visits/schedule.html', 
                                   client=client, 
                                   estimate=estimate)
        
        # Parse time if provided
        scheduled_time = None
        if preferred_time_str:
            try:
                scheduled_time = datetime.strptime(preferred_time_str, '%H:%M').time()
            except:
                pass
        
        # Generate visits
        visits_to_create = []
        estimate_id = estimate['id'] if estimate else None
        
        if schedule_type == 'one_time':
            # Single visit only
            visits_to_create.append({
                'client_id': client_id,
                'user_id': user_id,
                'estimate_id': estimate_id,
                'scheduled_date': start_date.isoformat(),
                'scheduled_time': scheduled_time.isoformat() if scheduled_time else None,
                'status': 'scheduled',
                'is_recurring': False,
                'price': price
            })
        else:
            # Recurring visits
            current_date = start_date
            interval_days = get_interval_days(recurring_frequency, custom_months_int if recurring_frequency == 'custom' else None)
            
            # Store the frequency string for maintaining rolling window
            freq_to_store = recurring_frequency
            if recurring_frequency == 'custom':
                freq_to_store = f'custom_{custom_months_int}'
            
            for _ in range(num_visits):
                visits_to_create.append({
                    'client_id': client_id,
                    'user_id': user_id,
                    'estimate_id': estimate_id,
                    'scheduled_date': current_date.isoformat(),
                    'scheduled_time': scheduled_time.isoformat() if scheduled_time else None,
                    'status': 'scheduled',
                    'is_recurring': True,
                    'recurring_frequency': freq_to_store,
                    'price': price
                })
                current_date = add_interval(current_date, recurring_frequency, custom_months_int if recurring_frequency == 'custom' else None)
        
        try:
            supabase.table('visits').insert(visits_to_create).execute()
            
            if schedule_type == 'one_time':
                flash(f'Visit scheduled for {client["name"]} on {start_date.strftime("%b %d")}.', 'success')
            else:
                flash(f'{len(visits_to_create)} visits scheduled for {client["name"]}.', 'success')
            return redirect(url_for('main.calendar', date_str=start_date.isoformat()))
            
        except Exception as e:
            flash('Failed to schedule visits.', 'error')
    
    return render_template('visits/schedule.html', client=client, estimate=estimate)


@bp.route('/visits/<visit_id>')
@login_required
def view_visit(visit_id):
    """View visit detail."""
    user_id = get_current_user_id()
    supabase = get_supabase()
    
    # Get visit with client info
    response = supabase.table('visits')\
        .select('*, clients(name, phone, address, notes), estimates(price_per_visit, frequency)')\
        .eq('id', visit_id)\
        .eq('user_id', user_id)\
        .single()\
        .execute()
    
    if not response.data:
        flash('Visit not found.', 'error')
        return redirect(url_for('main.today'))
    
    visit = response.data
    
    return render_template('visits/view.html', visit=visit)


@bp.route('/visits/<visit_id>/complete', methods=['POST'])
@login_required
def complete_visit(visit_id):
    """Mark a visit as complete."""
    user_id = get_current_user_id()
    supabase = get_supabase()
    
    notes = request.form.get('notes', '').strip() or None
    
    try:
        # Get visit info first
        visit_response = supabase.table('visits')\
            .select('*')\
            .eq('id', visit_id)\
            .eq('user_id', user_id)\
            .single()\
            .execute()
        
        if not visit_response.data:
            flash('Visit not found.', 'error')
            return redirect(url_for('main.today'))
        
        visit = visit_response.data
        
        # Mark as complete
        supabase.table('visits').update({
            'status': 'completed',
            'completion_notes': notes,
            'completed_at': datetime.utcnow().isoformat()
        }).eq('id', visit_id).eq('user_id', user_id).execute()
        
        # Only create new visits if this is a recurring visit
        if visit.get('is_recurring') and visit.get('recurring_frequency'):
            maintain_rolling_window(
                supabase, 
                user_id, 
                visit['client_id'], 
                visit.get('estimate_id'),
                visit['recurring_frequency'],
                visit.get('price')
            )
        
        flash('Visit marked as complete.', 'success')
        
    except Exception as e:
        flash('Failed to complete visit.', 'error')
    
    # Redirect back to where they came from, or today
    next_url = request.form.get('next') or url_for('main.today')
    return redirect(next_url)


@bp.route('/visits/<visit_id>/cancel', methods=['POST'])
@login_required
def cancel_visit(visit_id):
    """Cancel a scheduled visit."""
    user_id = get_current_user_id()
    supabase = get_supabase()
    
    try:
        supabase.table('visits').update({
            'status': 'cancelled'
        }).eq('id', visit_id).eq('user_id', user_id).eq('status', 'scheduled').execute()
        
        flash('Visit cancelled.', 'success')
        
    except Exception as e:
        flash('Failed to cancel visit.', 'error')
    
    next_url = request.form.get('next') or url_for('main.today')
    return redirect(next_url)


@bp.route('/visits/<visit_id>/reschedule', methods=['GET', 'POST'])
@login_required
def reschedule_visit(visit_id):
    """Reschedule a visit to a different date/time."""
    user_id = get_current_user_id()
    supabase = get_supabase()
    
    # Get visit
    response = supabase.table('visits')\
        .select('*, clients(name)')\
        .eq('id', visit_id)\
        .eq('user_id', user_id)\
        .single()\
        .execute()
    
    if not response.data:
        flash('Visit not found.', 'error')
        return redirect(url_for('main.today'))
    
    visit = response.data
    
    if request.method == 'POST':
        new_date_str = request.form.get('scheduled_date', '').strip()
        new_time_str = request.form.get('scheduled_time', '').strip() or None
        
        try:
            new_date = datetime.strptime(new_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date.', 'error')
            return render_template('visits/reschedule.html', visit=visit)
        
        scheduled_time = None
        if new_time_str:
            try:
                scheduled_time = datetime.strptime(new_time_str, '%H:%M').time()
            except:
                pass
        
        try:
            supabase.table('visits').update({
                'scheduled_date': new_date.isoformat(),
                'scheduled_time': scheduled_time.isoformat() if scheduled_time else None
            }).eq('id', visit_id).eq('user_id', user_id).execute()
            
            flash('Visit rescheduled.', 'success')
            return redirect(url_for('visits.view_visit', visit_id=visit_id))
            
        except Exception as e:
            flash('Failed to reschedule visit.', 'error')
    
    return render_template('visits/reschedule.html', visit=visit)


def get_interval_days(frequency, custom_months=None):
    """Get the number of days between visits based on frequency."""
    if frequency == 'weekly':
        return 7
    elif frequency == 'biweekly':
        return 14
    elif frequency == 'monthly':
        return 30  # Approximate
    elif frequency == 'custom' and custom_months:
        return custom_months * 30  # Approximate
    elif frequency.startswith('custom_'):
        # Parse stored format like "custom_3"
        months = int(frequency.split('_')[1])
        return months * 30
    else:
        return 0


def add_interval(current_date, frequency, custom_months=None):
    """Add the appropriate interval to a date, handling month boundaries properly."""
    if frequency == 'weekly':
        return current_date + timedelta(days=7)
    elif frequency == 'biweekly':
        return current_date + timedelta(days=14)
    elif frequency == 'monthly':
        # Add one month properly
        return add_months(current_date, 1)
    elif frequency == 'custom' and custom_months:
        return add_months(current_date, custom_months)
    elif frequency.startswith('custom_'):
        months = int(frequency.split('_')[1])
        return add_months(current_date, months)
    else:
        return current_date


def add_months(source_date, months):
    """Add months to a date, handling month boundaries."""
    month = source_date.month - 1 + months
    year = source_date.year + month // 12
    month = month % 12 + 1
    day = min(source_date.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
                                  31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return date(year, month, day)


def maintain_rolling_window(supabase, user_id, client_id, estimate_id, frequency, price=None):
    """Ensure there are always enough future visits scheduled for recurring clients."""
    today = date.today()
    
    # Determine target count based on frequency
    # For longer intervals, we don't need as many future visits
    if frequency.startswith('custom_'):
        months = int(frequency.split('_')[1])
        target_count = max(4, 12 // months)  # At least 4, but scale down for longer intervals
    elif frequency == 'monthly':
        target_count = 6
    else:
        target_count = 8
    
    # Count future scheduled recurring visits for this client
    response = supabase.table('visits')\
        .select('scheduled_date, price')\
        .eq('client_id', client_id)\
        .eq('user_id', user_id)\
        .eq('status', 'scheduled')\
        .eq('is_recurring', True)\
        .gte('scheduled_date', today.isoformat())\
        .order('scheduled_date', desc=True)\
        .execute()
    
    future_visits = response.data if response.data else []
    
    if len(future_visits) >= target_count:
        return  # Already have enough
    
    # Find the last scheduled date and get price from existing visits if not provided
    if future_visits:
        last_date = datetime.strptime(future_visits[0]['scheduled_date'], '%Y-%m-%d').date()
        if price is None and future_visits[0].get('price'):
            price = future_visits[0]['price']
    else:
        last_date = today
    
    # Add visits until we have enough
    visits_to_create = []
    
    current_date = add_interval(last_date, frequency)
    while len(future_visits) + len(visits_to_create) < target_count:
        visits_to_create.append({
            'client_id': client_id,
            'user_id': user_id,
            'estimate_id': estimate_id,
            'scheduled_date': current_date.isoformat(),
            'status': 'scheduled',
            'is_recurring': True,
            'recurring_frequency': frequency,
            'price': price
        })
        current_date = add_interval(current_date, frequency)
    
    if visits_to_create:
        supabase.table('visits').insert(visits_to_create).execute()
