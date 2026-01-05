"""
Onboarding/welcome quiz routes.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from ..auth import login_required, get_current_user_id, get_user_profile
from ..supabase_client import get_supabase

bp = Blueprint('onboarding', __name__, url_prefix='/welcome')


@bp.route('/')
@login_required
def start():
    """Start the welcome quiz."""
    return redirect(url_for('onboarding.step1'))


@bp.route('/step1', methods=['GET', 'POST'])
@login_required
def step1():
    """Step 1: Business name."""
    user_id = get_current_user_id()
    profile = get_user_profile()
    
    if request.method == 'POST':
        business_name = request.form.get('business_name', '').strip()
        
        if business_name:
            supabase = get_supabase()
            supabase.table('user_profiles').update({
                'business_name': business_name
            }).eq('id', user_id).execute()
        
        return redirect(url_for('onboarding.step2'))
    
    return render_template('onboarding/step1.html', profile=profile)


@bp.route('/step2', methods=['GET', 'POST'])
@login_required
def step2():
    """Step 2: Business phone."""
    user_id = get_current_user_id()
    profile = get_user_profile()
    
    if request.method == 'POST':
        business_phone = request.form.get('business_phone', '').strip()
        
        if business_phone:
            supabase = get_supabase()
            supabase.table('user_profiles').update({
                'business_phone': business_phone
            }).eq('id', user_id).execute()
        
        return redirect(url_for('onboarding.step3'))
    
    return render_template('onboarding/step2.html', profile=profile)


@bp.route('/step3', methods=['GET', 'POST'])
@login_required
def step3():
    """Step 3: Payment methods."""
    user_id = get_current_user_id()
    profile = get_user_profile()
    
    if request.method == 'POST':
        # Build payment instructions from selections
        methods = request.form.getlist('payment_methods')
        venmo = request.form.get('venmo', '').strip()
        zelle = request.form.get('zelle', '').strip()
        other_info = request.form.get('other_info', '').strip()
        
        instructions = []
        if 'venmo' in methods and venmo:
            instructions.append(f"Venmo: {venmo}")
        if 'zelle' in methods and zelle:
            instructions.append(f"Zelle: {zelle}")
        if 'check' in methods:
            instructions.append("Check: Make payable to your business name")
        if 'cash' in methods:
            instructions.append("Cash accepted")
        if other_info:
            instructions.append(other_info)
        
        payment_instructions = "\n".join(instructions) if instructions else None
        
        supabase = get_supabase()
        supabase.table('user_profiles').update({
            'payment_instructions': payment_instructions
        }).eq('id', user_id).execute()
        
        return redirect(url_for('onboarding.complete'))
    
    return render_template('onboarding/step3.html', profile=profile)


@bp.route('/complete')
@login_required
def complete():
    """Quiz complete - show success and redirect to app."""
    profile = get_user_profile()
    return render_template('onboarding/complete.html', profile=profile)
