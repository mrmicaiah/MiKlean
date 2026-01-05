"""
Visit routes - view, complete, schedule, cancel.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from datetime import date, datetime, timedelta
from ..auth import login_required, get_current_user_id
from ..supabase_client import get_supabase

bp = Blueprint('visits', __name__)


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
        preferred_time_str = request.form.get('preferred_time', '').strip() or None
        
        # Validation
        errors = []
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except ValueError:
            errors.append('Invalid start date.')
            start_date = None
        
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
                'is_recurring': False
            })
        else:
            # Recurring visits - 8 weeks worth
            current_date = start_date
            interval = get_interval_days(recurring_frequency)
            
            for _ in range(8):
                visits_to_create.append({
                    'client_id': client_id,
                    'user_id': user_id,
                    'estimate_id': estimate_id,
                    'scheduled_date': current_date.isoformat(),
                    'scheduled_time': scheduled_time.isoformat() if scheduled_time else None,
                    'status': 'scheduled',
                    'is_recurring': True,
                    'recurring_frequency': recurring_frequency
                })
                current_date = current_date + timedelta(days=interval)
        
        try:
            supabase.table('visits').insert(visits_to_create).execute()
            
            if schedule_type == 'one_time':
                flash(f'Visit scheduled for {client["name"]} on {start_date.strftime("%b %d")}.', 'success')
            else:
                flash(f'{len(visits_to_create)} visits scheduled for {client["name"]}.', 'success')
            return redirect(url_for('clients.view_client', client_id=client_id))
            
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
                visit['recurring_frequency']
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


def get_interval_days(frequency):
    """Get the number of days between visits based on frequency."""
    if frequency == 'weekly':
        return 7
    elif frequency == 'biweekly':
        return 14
    elif frequency == 'monthly':
        return 30  # Approximate
    else:
        return 0


def maintain_rolling_window(supabase, user_id, client_id, estimate_id, frequency):
    """Ensure there are always 8 weeks of future visits scheduled for recurring clients."""
    today = date.today()
    
    # Count future scheduled recurring visits for this client
    response = supabase.table('visits')\
        .select('scheduled_date')\
        .eq('client_id', client_id)\
        .eq('user_id', user_id)\
        .eq('status', 'scheduled')\
        .eq('is_recurring', True)\
        .gte('scheduled_date', today.isoformat())\
        .order('scheduled_date', desc=True)\
        .execute()
    
    future_visits = response.data if response.data else []
    
    if len(future_visits) >= 8:
        return  # Already have enough
    
    # Find the last scheduled date
    if future_visits:
        last_date = datetime.strptime(future_visits[0]['scheduled_date'], '%Y-%m-%d').date()
    else:
        last_date = today
    
    # Add visits until we have 8 weeks covered
    interval = get_interval_days(frequency)
    visits_to_create = []
    
    current_date = last_date + timedelta(days=interval)
    while len(future_visits) + len(visits_to_create) < 8:
        visits_to_create.append({
            'client_id': client_id,
            'user_id': user_id,
            'estimate_id': estimate_id,
            'scheduled_date': current_date.isoformat(),
            'status': 'scheduled',
            'is_recurring': True,
            'recurring_frequency': frequency
        })
        current_date = current_date + timedelta(days=interval)
    
    if visits_to_create:
        supabase.table('visits').insert(visits_to_create).execute()
