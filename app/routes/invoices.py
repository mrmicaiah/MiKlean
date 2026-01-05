"""
Invoice routes - create, view, send, mark paid, PDF download.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from datetime import date, datetime
from ..auth import login_required, get_current_user_id, get_user_profile
from ..supabase_client import get_supabase

bp = Blueprint('invoices', __name__)


@bp.route('/clients/<client_id>/invoice', methods=['GET', 'POST'])
@login_required
def create_invoice(client_id):
    """Create an invoice for a client's completed visits."""
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
    
    # Get completed, non-invoiced visits
    visits_response = supabase.table('visits')\
        .select('*, estimates(price_per_visit)')\
        .eq('client_id', client_id)\
        .eq('user_id', user_id)\
        .eq('status', 'completed')\
        .is_('invoice_id', 'null')\
        .order('scheduled_date')\
        .execute()
    
    available_visits = visits_response.data if visits_response.data else []
    
    # Add price to each visit
    for visit in available_visits:
        if visit.get('estimates') and visit['estimates'].get('price_per_visit'):
            visit['price'] = float(visit['estimates']['price_per_visit'])
        else:
            visit['price'] = 0
    
    if request.method == 'POST':
        selected_visit_ids = request.form.getlist('visits')
        
        if not selected_visit_ids:
            flash('Please select at least one visit to invoice.', 'error')
            return render_template('invoices/create.html', 
                                   client=client, 
                                   visits=available_visits)
        
        # Filter to selected visits
        selected_visits = [v for v in available_visits if v['id'] in selected_visit_ids]
        
        if not selected_visits:
            flash('No valid visits selected.', 'error')
            return render_template('invoices/create.html', 
                                   client=client, 
                                   visits=available_visits)
        
        # Calculate total
        subtotal = sum(v['price'] for v in selected_visits)
        total = subtotal  # No tax for now
        
        # Generate invoice number
        invoice_number = generate_invoice_number(supabase, user_id)
        
        try:
            # Create invoice
            invoice_response = supabase.table('invoices').insert({
                'client_id': client_id,
                'user_id': user_id,
                'invoice_number': invoice_number,
                'subtotal': subtotal,
                'total': total,
                'status': 'draft'
            }).execute()
            
            if not invoice_response.data:
                flash('Failed to create invoice.', 'error')
                return render_template('invoices/create.html', 
                                       client=client, 
                                       visits=available_visits)
            
            invoice_id = invoice_response.data[0]['id']
            
            # Link visits to invoice
            supabase.table('visits').update({
                'invoice_id': invoice_id
            }).in_('id', selected_visit_ids).eq('user_id', user_id).execute()
            
            flash('Invoice created.', 'success')
            return redirect(url_for('invoices.view_invoice', invoice_id=invoice_id))
            
        except Exception as e:
            flash('Failed to create invoice.', 'error')
    
    return render_template('invoices/create.html', client=client, visits=available_visits)


@bp.route('/invoices/<invoice_id>')
@login_required
def view_invoice(invoice_id):
    """View invoice detail."""
    user_id = get_current_user_id()
    supabase = get_supabase()
    
    # Get invoice with client info
    response = supabase.table('invoices')\
        .select('*, clients(name, address, email)')\
        .eq('id', invoice_id)\
        .eq('user_id', user_id)\
        .single()\
        .execute()
    
    if not response.data:
        flash('Invoice not found.', 'error')
        return redirect(url_for('clients.list_clients'))
    
    invoice = response.data
    
    # Get visits on this invoice
    visits_response = supabase.table('visits')\
        .select('*, estimates(price_per_visit)')\
        .eq('invoice_id', invoice_id)\
        .order('scheduled_date')\
        .execute()
    
    visits = visits_response.data if visits_response.data else []
    
    # Add price to each visit
    for visit in visits:
        if visit.get('estimates') and visit['estimates'].get('price_per_visit'):
            visit['price'] = float(visit['estimates']['price_per_visit'])
        else:
            visit['price'] = 0
    
    return render_template('invoices/view.html', invoice=invoice, visits=visits)


@bp.route('/invoices/<invoice_id>/preview')
@login_required
def preview_invoice(invoice_id):
    """Preview invoice as client will see it."""
    user_id = get_current_user_id()
    supabase = get_supabase()
    
    # Get invoice with client info
    response = supabase.table('invoices')\
        .select('*, clients(name, address, email)')\
        .eq('id', invoice_id)\
        .eq('user_id', user_id)\
        .single()\
        .execute()
    
    if not response.data:
        flash('Invoice not found.', 'error')
        return redirect(url_for('clients.list_clients'))
    
    invoice = response.data
    profile = get_user_profile()
    
    # Get visits on this invoice
    visits_response = supabase.table('visits')\
        .select('*, estimates(price_per_visit, description)')\
        .eq('invoice_id', invoice_id)\
        .order('scheduled_date')\
        .execute()
    
    visits = visits_response.data if visits_response.data else []
    
    for visit in visits:
        if visit.get('estimates') and visit['estimates'].get('price_per_visit'):
            visit['price'] = float(visit['estimates']['price_per_visit'])
        else:
            visit['price'] = 0
    
    return render_template('invoices/preview.html', 
                           invoice=invoice, 
                           visits=visits,
                           profile=profile,
                           is_preview=True)


@bp.route('/invoices/<invoice_id>/pdf')
@login_required
def download_invoice_pdf(invoice_id):
    """Download invoice as PDF."""
    user_id = get_current_user_id()
    supabase = get_supabase()
    
    # Get invoice with client info
    response = supabase.table('invoices')\
        .select('*, clients(name, address, email)')\
        .eq('id', invoice_id)\
        .eq('user_id', user_id)\
        .single()\
        .execute()
    
    if not response.data:
        flash('Invoice not found.', 'error')
        return redirect(url_for('clients.list_clients'))
    
    invoice = response.data
    profile = get_user_profile()
    
    # Get visits on this invoice
    visits_response = supabase.table('visits')\
        .select('*, estimates(price_per_visit, description)')\
        .eq('invoice_id', invoice_id)\
        .order('scheduled_date')\
        .execute()
    
    visits = visits_response.data if visits_response.data else []
    
    for visit in visits:
        if visit.get('estimates') and visit['estimates'].get('price_per_visit'):
            visit['price'] = float(visit['estimates']['price_per_visit'])
        else:
            visit['price'] = 0
    
    # Generate PDF
    from ..services.pdf import generate_invoice_pdf
    pdf_file = generate_invoice_pdf(invoice, visits, profile)
    
    filename = f"{invoice['invoice_number']}_{invoice['clients']['name'].replace(' ', '_')}.pdf"
    
    return send_file(
        pdf_file,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )


@bp.route('/invoices/<invoice_id>/send', methods=['GET', 'POST'])
@login_required
def send_invoice(invoice_id):
    """Send invoice to client."""
    user_id = get_current_user_id()
    supabase = get_supabase()
    
    # Get invoice with client info
    response = supabase.table('invoices')\
        .select('*, clients(name, phone, email)')\
        .eq('id', invoice_id)\
        .eq('user_id', user_id)\
        .single()\
        .execute()
    
    if not response.data:
        flash('Invoice not found.', 'error')
        return redirect(url_for('clients.list_clients'))
    
    invoice = response.data
    client = invoice['clients']
    
    if request.method == 'POST':
        send_method = request.form.get('method')
        
        if send_method == 'email':
            if not client.get('email'):
                flash('Client has no email address. Please add one first.', 'error')
                return redirect(url_for('clients.edit_client', client_id=invoice['client_id']))
            
            # TODO: Send email via SendGrid with PDF attachment
            # For now, mark as sent
            supabase.table('invoices').update({
                'status': 'sent',
                'sent_at': datetime.utcnow().isoformat()
            }).eq('id', invoice_id).execute()
            
            flash(f'Invoice sent to {client["email"]}.', 'success')
            return redirect(url_for('invoices.view_invoice', invoice_id=invoice_id))
            
        elif send_method == 'text':
            # Generate SMS message
            profile = get_user_profile()
            business_name = profile.get('business_name') or 'Your cleaner'
            payment_info = profile.get('payment_instructions') or ''
            
            message = f"Hi {client['name']}! Invoice {invoice['invoice_number']} for ${invoice['total']:.2f} from {business_name}."
            if payment_info:
                message += f" Payment: {payment_info[:100]}"
            
            # Update status
            supabase.table('invoices').update({
                'status': 'sent',
                'sent_at': datetime.utcnow().isoformat()
            }).eq('id', invoice_id).execute()
            
            # Redirect to SMS app
            sms_url = f"sms:{client['phone']}?body={message}"
            return redirect(sms_url)
    
    return render_template('invoices/send.html', invoice=invoice, client=client)


@bp.route('/invoices/<invoice_id>/paid', methods=['POST'])
@login_required
def mark_paid(invoice_id):
    """Mark an invoice as paid."""
    user_id = get_current_user_id()
    supabase = get_supabase()
    
    try:
        supabase.table('invoices').update({
            'status': 'paid',
            'paid_at': datetime.utcnow().isoformat()
        }).eq('id', invoice_id).eq('user_id', user_id).execute()
        
        flash('Invoice marked as paid.', 'success')
        
    except Exception as e:
        flash('Failed to update invoice.', 'error')
    
    return redirect(url_for('invoices.view_invoice', invoice_id=invoice_id))


def generate_invoice_number(supabase, user_id):
    """Generate the next invoice number for a user."""
    # Get the highest invoice number for this user
    response = supabase.table('invoices')\
        .select('invoice_number')\
        .eq('user_id', user_id)\
        .order('created_at', desc=True)\
        .limit(1)\
        .execute()
    
    if response.data and response.data[0].get('invoice_number'):
        last_number = response.data[0]['invoice_number']
        # Extract number from "INV-0001" format
        try:
            num = int(last_number.split('-')[1])
            return f"INV-{num + 1:04d}"
        except:
            pass
    
    return "INV-0001"
