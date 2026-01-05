"""
API routes - JSON endpoints for AJAX/mobile.
"""
from flask import Blueprint, jsonify, request
from ..auth import login_required, get_current_user_id
from ..supabase_client import get_supabase
from datetime import date

bp = Blueprint('api', __name__, url_prefix='/api')


@bp.route('/today')
@login_required
def today_visits():
    """Get today's visits as JSON."""
    user_id = get_current_user_id()
    today_date = date.today()
    
    supabase = get_supabase()
    
    response = supabase.table('visits')\
        .select('*, clients(name, phone, address)')\
        .eq('user_id', user_id)\
        .eq('scheduled_date', today_date.isoformat())\
        .neq('status', 'cancelled')\
        .order('scheduled_time', desc=False, nullsfirst=False)\
        .execute()
    
    return jsonify(response.data if response.data else [])


@bp.route('/clients')
@login_required
def list_clients():
    """Get clients as JSON."""
    user_id = get_current_user_id()
    client_type = request.args.get('type')
    
    supabase = get_supabase()
    
    query = supabase.table('clients')\
        .select('*')\
        .eq('user_id', user_id)\
        .order('name')
    
    if client_type:
        query = query.eq('type', client_type)
    
    response = query.execute()
    
    return jsonify(response.data if response.data else [])


@bp.route('/visits/<visit_id>/complete', methods=['POST'])
@login_required
def api_complete_visit(visit_id):
    """Mark visit complete via API."""
    user_id = get_current_user_id()
    supabase = get_supabase()
    
    data = request.get_json() or {}
    notes = data.get('notes')
    
    try:
        from datetime import datetime
        supabase.table('visits').update({
            'status': 'completed',
            'completion_notes': notes,
            'completed_at': datetime.utcnow().isoformat()
        }).eq('id', visit_id).eq('user_id', user_id).execute()
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
