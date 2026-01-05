"""
Main routes - today view, calendar, home.
"""
from flask import Blueprint, render_template, redirect, url_for, session
from datetime import date, datetime, timedelta
from ..auth import login_required, get_current_user_id
from ..supabase_client import get_supabase

bp = Blueprint('main', __name__)


@bp.route('/')
def index():
    """Home page - redirect based on auth status."""
    if 'access_token' in session:
        return redirect(url_for('main.today'))
    return redirect(url_for('auth.login'))


@bp.route('/today')
@login_required
def today():
    """Today's visits - the home screen."""
    user_id = get_current_user_id()
    today_date = date.today()
    
    supabase = get_supabase()
    
    # Get today's visits with client info
    response = supabase.table('visits')\
        .select('*, clients(name, phone, address)')\
        .eq('user_id', user_id)\
        .eq('scheduled_date', today_date.isoformat())\
        .neq('status', 'cancelled')\
        .order('scheduled_time', desc=False, nullsfirst=False)\
        .execute()
    
    visits = response.data if response.data else []
    
    return render_template('main/today.html', 
                           visits=visits, 
                           today=today_date)


@bp.route('/calendar')
@bp.route('/calendar/<date_str>')
@login_required
def calendar(date_str=None):
    """Calendar view of visits."""
    user_id = get_current_user_id()
    
    # Parse selected date or use today
    if date_str:
        try:
            selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            selected_date = date.today()
    else:
        selected_date = date.today()
    
    # Get start and end of the month
    first_of_month = selected_date.replace(day=1)
    if selected_date.month == 12:
        last_of_month = selected_date.replace(year=selected_date.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        last_of_month = selected_date.replace(month=selected_date.month + 1, day=1) - timedelta(days=1)
    
    # Calculate prev/next month dates
    prev_month = first_of_month - timedelta(days=1)
    if selected_date.month == 12:
        next_month = selected_date.replace(year=selected_date.year + 1, month=1, day=1)
    else:
        next_month = selected_date.replace(month=selected_date.month + 1, day=1)
    
    supabase = get_supabase()
    
    # Get all visits for the month
    response = supabase.table('visits')\
        .select('*, clients(name)')\
        .eq('user_id', user_id)\
        .gte('scheduled_date', first_of_month.isoformat())\
        .lte('scheduled_date', last_of_month.isoformat())\
        .neq('status', 'cancelled')\
        .order('scheduled_date')\
        .order('scheduled_time', desc=False, nullsfirst=False)\
        .execute()
    
    visits = response.data if response.data else []
    
    # Group visits by date for easy template access
    visits_by_date = {}
    for visit in visits:
        visit_date = visit['scheduled_date']
        if visit_date not in visits_by_date:
            visits_by_date[visit_date] = []
        visits_by_date[visit_date].append(visit)
    
    # Get visits for selected date
    selected_visits = visits_by_date.get(selected_date.isoformat(), [])
    
    # Calculate calendar grid info
    # What day of week does the 1st fall on? (0=Monday, 6=Sunday in Python)
    # But we want Sunday=0, so adjust
    first_weekday = (first_of_month.weekday() + 1) % 7
    days_in_month = (last_of_month - first_of_month).days + 1
    
    return render_template('main/calendar.html',
                           selected_date=selected_date,
                           first_of_month=first_of_month,
                           last_of_month=last_of_month,
                           prev_month=prev_month,
                           next_month=next_month,
                           first_weekday=first_weekday,
                           days_in_month=days_in_month,
                           visits_by_date=visits_by_date,
                           selected_visits=selected_visits,
                           today=date.today())
