"""
Invoice routes - create, view, send, mark paid, PDF download.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from datetime import date, datetime
import secrets
import urllib.parse
from ..auth import login_required, get_current_user_id, get_user_profile
from ..supabase_client import get_supabase

bp = Blueprint('invoices', __name__)


def get_visit_price(visit):
    """Get the price for a visit - use visit.price first, fall back to estimate."""
    # First check if visit has its own price
    if visit.get('price') is not None:
        return float(visit['price'])
    # Fall back to estimate price
    if visit.get('estimates') and visit['estimates'].get('price_per_visit'):
        return float(visit['estimates']['price_per_visit'])
    return 0


def generate_public_token():
    """Generate a unique token for public invoice access."""
    return secrets.token_urlsafe(16)


@bp.route('/clients/<client_id>/invoice', methods=['GET', 'POST'])
@login_required
def create_invoice(client_id):
    """Create an invoice for a client's completed visits."""
    user_id = get_current_user_id()
    supabase = get_supabase()
    
    # Check if coming from a specific visit
    from_visit_id = request.args.get('from_visit')
    
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
    
    # Add price to each visit (visit price takes precedence over estimate)
    for visit in available_visits:
        visit['price'] = get_visit_price(visit)
    
    if request.method == 'POST':
        selected_visit_ids = request.form.getlist('visits')
        
        if not selected_visit_ids:
            flash('Please select at least one visit to invoice.', 'error')
            return render_template('invoices/create.html', 
                                   client=client, 
                                   visits=available_visits,
                                   from_visit_id=from_visit_id)
        
        # Filter to selected visits
        selected_visits = [v for v in available_visits if v['id'] in selected_visit_ids]
        
        if not selected_visits:
            flash('No valid visits selected.', 'error')
            return render_template('invoices/create.html', 
                                   client=client, 
                                   visits=available_visits,
                                   from_visit_id=from_visit_id)
        
        # Calculate total
        subtotal = sum(v['price'] for v in selected_visits)
        total = subtotal  # No tax for now
        
        # Generate invoice number and public token
        invoice_number = generate_invoice_number(supabase, user_id)
        public_token = generate_public_token()
        
        try:
            # Create invoice
            invoice_response = supabase.table('invoices').insert({
                'client_id': client_id,
                'user_id': user_id,
                'invoice_number': invoice_number,
                'subtotal': subtotal,
                'total': total,
                'status': 'draft',
                'public_token': public_token
            }).execute()
            
            if not invoice_response.data:
                flash('Failed to create invoice.', 'error')
                return render_template('invoices/create.html', 
                                       client=client, 
                                       visits=available_visits,
                                       from_visit_id=from_visit_id)
            
            invoice_id = invoice_response.data[0]['id']
            
            # Link visits to invoice
            supabase.table('visits').update({
                'invoice_id': invoice_id
            }).in_('id', selected_visit_ids).eq('user_id', user_id).execute()
            
            flash('Invoice created.', 'success')
            return redirect(url_for('invoices.view_invoice', invoice_id=invoice_id))
            
        except Exception as e:
            flash('Failed to create invoice.', 'error')
    
    return render_template('invoices/create.html', 
                           client=client, 
                           visits=available_visits,
                           from_visit_id=from_visit_id)


@bp.route('/invoices/<invoice_id>')
@login_required
def view_invoice(invoice_id):
    """View invoice detail."""
    user_id = get_current_user_id()
    supabase = get_supabase()
    
    # Get invoice with client info
    response = supabase.table('invoices')\
        .select('*, clients(name, address, email, phone)')\
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
        visit['price'] = get_visit_price(visit)
    
    # Generate public URL
    public_url = None
    if invoice.get('public_token'):
        public_url = url_for('invoices.public_invoice', token=invoice['public_token'], _external=True)
    
    return render_template('invoices/view.html', invoice=invoice, visits=visits, public_url=public_url)


@bp.route('/invoice/view/<token>')
def public_invoice(token):
    """Public view of invoice - no login required."""
    supabase = get_supabase()
    
    # Get invoice by token
    response = supabase.table('invoices')\
        .select('*, clients(name, address, email)')\
        .eq('public_token', token)\
        .single()\
        .execute()
    
    if not response.data:
        return render_template('invoices/not_found.html'), 404
    
    invoice = response.data
    
    # Get user profile for business info
    profile_response = supabase.table('profiles')\
        .select('*')\
        .eq('id', invoice['user_id'])\
        .single()\
        .execute()
    
    profile = profile_response.data if profile_response.data else {}
    
    # Get visits on this invoice
    visits_response = supabase.table('visits')\
        .select('*, estimates(price_per_visit, description)')\
        .eq('invoice_id', invoice['id'])\
        .order('scheduled_date')\
        .execute()
    
    visits = visits_response.data if visits_response.data else []
    
    for visit in visits:
        visit['price'] = get_visit_price(visit)
    
    return render_template('invoices/public.html', 
                           invoice=invoice, 
                           visits=visits,
                           profile=profile)


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
        visit['price'] = get_visit_price(visit)
    
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
    
    try:
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
            visit['price'] = get_visit_price(visit)
        
        # Generate PDF
        from ..services.pdf import generate_invoice_pdf
        pdf_file = generate_invoice_pdf(invoice, visits, profile)
        
        # Sanitize filename - remove special characters
        client_name = invoice.get('clients', {}).get('name', 'Client')
        safe_name = ''.join(c if c.isalnum() or c in ' -_' else '' for c in client_name).replace(' ', '_')
        filename = f"{invoice['invoice_number']}_{safe_name}.pdf"
        
        return send_file(
            pdf_file,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        flash(f'Error generating PDF: {str(e)}', 'error')
        return redirect(url_for('invoices.view_invoice', invoice_id=invoice_id))


@bp.route('/invoices/<invoice_id>/send', methods=['GET', 'POST'])
@login_required
def send_invoice(invoice_id):
    """Send invoice to client - opens email or SMS app."""
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
    
    # Ensure invoice has a public token
    if not invoice.get('public_token'):
        public_token = generate_public_token()
        supabase.table('invoices').update({
            'public_token': public_token
        }).eq('id', invoice_id).execute()
        invoice['public_token'] = public_token
    
    # Generate public URL
    public_url = url_for('invoices.public_invoice', token=invoice['public_token'], _external=True)
    
    # Get business info for message
    profile = get_user_profile()
    business_name = profile.get('business_name') or 'Your cleaner'
    
    if request.method == 'POST':
        send_method = request.form.get('method')
        
        # Update status to sent
        supabase.table('invoices').update({
            'status': 'sent',
            'sent_at': datetime.utcnow().isoformat()
        }).eq('id', invoice_id).execute()
        
        if send_method == 'email':
            # Build email
            subject = f"Invoice {invoice['invoice_number']} from {business_name}"
            body = f"""Hi {client['name']},

Here's your invoice for ${invoice['total']:.2f} from {business_name}.

View your invoice: {public_url}

Thank you for your business!

{business_name}"""
            
            # URL encode for mailto
            encoded_subject = urllib.parse.quote(subject)
            encoded_body = urllib.parse.quote(body)
            mailto_url = f"mailto:{client['email']}?subject={encoded_subject}&body={encoded_body}"
            
            return redirect(mailto_url)
            
        elif send_method == 'text':
            # Build SMS message
            message = f"Hi {client['name']}! Here's your invoice for ${invoice['total']:.2f} from {business_name}: {public_url}"
            
            encoded_message = urllib.parse.quote(message)
            sms_url = f"sms:{client['phone']}?body={encoded_message}"
            
            return redirect(sms_url)
    
    return render_template('invoices/send.html', 
                           invoice=invoice, 
                           client=client, 
                           public_url=public_url,
                           business_name=business_name)


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
