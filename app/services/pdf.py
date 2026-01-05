"""
PDF generation service using fpdf2 (no system dependencies).
"""
from fpdf import FPDF
import io


class EstimatePDF(FPDF):
    def __init__(self, profile):
        super().__init__()
        self.profile = profile
        
    def header(self):
        # Yellow header bar
        self.set_fill_color(255, 193, 7)  # Yellow
        self.rect(0, 0, 210, 35, 'F')
        
        # Business name
        self.set_font('Helvetica', 'B', 20)
        self.set_text_color(26, 26, 26)
        self.set_xy(15, 12)
        business_name = self.profile.get('business_name') or 'Your Business'
        self.cell(0, 10, business_name, 0, 0, 'L')
        
        # ESTIMATE title
        self.set_xy(15, 12)
        self.cell(0, 10, 'ESTIMATE', 0, 0, 'R')
        
        # Business phone
        if self.profile.get('business_phone'):
            self.set_font('Helvetica', '', 10)
            self.set_xy(15, 22)
            self.cell(0, 5, self.profile['business_phone'], 0, 0, 'L')
        
        # Valid for 30 days
        self.set_font('Helvetica', '', 9)
        self.set_text_color(100, 100, 100)
        self.set_xy(15, 22)
        self.cell(0, 5, 'Valid for 30 days', 0, 0, 'R')
        
        self.ln(30)

    def footer(self):
        self.set_y(-25)
        self.set_font('Helvetica', '', 9)
        self.set_text_color(128, 128, 128)
        phone = self.profile.get('business_phone') or 'your phone'
        self.cell(0, 10, f'Questions? Contact us at {phone}', 0, 0, 'C')
        self.ln(5)
        self.cell(0, 10, 'Thank you for considering our services!', 0, 0, 'C')


class InvoicePDF(FPDF):
    def __init__(self, profile, invoice_number):
        super().__init__()
        self.profile = profile
        self.invoice_number = invoice_number
        
    def header(self):
        # Yellow header bar
        self.set_fill_color(255, 193, 7)
        self.rect(0, 0, 210, 35, 'F')
        
        # Business name
        self.set_font('Helvetica', 'B', 20)
        self.set_text_color(26, 26, 26)
        self.set_xy(15, 12)
        business_name = self.profile.get('business_name') or 'Your Business'
        self.cell(0, 10, business_name, 0, 0, 'L')
        
        # INVOICE title
        self.set_xy(15, 12)
        self.cell(0, 10, 'INVOICE', 0, 0, 'R')
        
        # Business phone
        if self.profile.get('business_phone'):
            self.set_font('Helvetica', '', 10)
            self.set_xy(15, 22)
            self.cell(0, 5, self.profile['business_phone'], 0, 0, 'L')
        
        # Invoice number
        self.set_font('Helvetica', 'B', 11)
        self.set_text_color(255, 193, 7)
        self.set_fill_color(26, 26, 26)
        self.set_xy(155, 20)
        self.cell(40, 8, self.invoice_number, 0, 0, 'C', True)
        
        self.ln(30)

    def footer(self):
        self.set_y(-25)
        self.set_font('Helvetica', 'B', 11)
        self.set_text_color(26, 26, 26)
        self.cell(0, 10, 'Thank you for your business!', 0, 0, 'C')
        self.ln(5)
        self.set_font('Helvetica', '', 9)
        self.set_text_color(128, 128, 128)
        phone = self.profile.get('business_phone') or 'your phone'
        self.cell(0, 10, f'Questions? Contact us at {phone}', 0, 0, 'C')


def generate_estimate_pdf(estimate, profile, monthly_rate):
    """Generate a professional PDF for an estimate."""
    pdf = EstimatePDF(profile or {})
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=30)
    
    # Prepared For section
    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 8, 'PREPARED FOR', 0, 1, 'L')
    
    pdf.set_font('Helvetica', 'B', 14)
    pdf.set_text_color(26, 26, 26)
    client_name = estimate.get('clients', {}).get('name', 'Client')
    pdf.cell(0, 8, client_name, 0, 1, 'L')
    
    pdf.set_font('Helvetica', '', 11)
    pdf.set_text_color(100, 100, 100)
    client_address = estimate.get('clients', {}).get('address', '')
    pdf.cell(0, 6, client_address, 0, 1, 'L')
    
    pdf.ln(8)
    
    # Service Description section
    pdf.set_fill_color(245, 245, 245)
    pdf.rect(15, pdf.get_y(), 180, 50, 'F')
    
    pdf.set_xy(20, pdf.get_y() + 5)
    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 6, 'SERVICE DESCRIPTION', 0, 1, 'L')
    
    pdf.set_x(20)
    pdf.set_font('Helvetica', '', 11)
    pdf.set_text_color(50, 50, 50)
    description = estimate.get('description', '')
    pdf.multi_cell(170, 6, description, 0, 'L')
    
    pdf.ln(15)
    
    # Pricing section - yellow box
    y_start = pdf.get_y()
    pdf.set_fill_color(255, 193, 7)
    pdf.rect(15, y_start, 180, 40, 'F')
    
    pdf.set_xy(20, y_start + 8)
    pdf.set_font('Helvetica', '', 12)
    pdf.set_text_color(26, 26, 26)
    frequency = estimate.get('frequency', 'Service').replace('_', ' ').title()
    pdf.cell(90, 8, f'{frequency} Service', 0, 0, 'L')
    
    pdf.set_font('Helvetica', 'B', 24)
    price = estimate.get('price_per_visit', 0)
    pdf.cell(80, 8, f'${price:.2f}', 0, 1, 'R')
    
    pdf.set_x(20)
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(90, 6, 'per visit', 0, 0, 'L')
    
    # Monthly rate if applicable
    if monthly_rate and estimate.get('show_monthly_rate'):
        pdf.set_xy(20, y_start + 28)
        pdf.set_font('Helvetica', '', 11)
        pdf.cell(90, 6, 'Estimated Monthly', 0, 0, 'L')
        pdf.set_font('Helvetica', 'B', 16)
        pdf.cell(80, 6, f'${monthly_rate:.2f}', 0, 0, 'R')
    
    pdf.ln(25)
    
    # Schedule preference
    preferred_day = estimate.get('preferred_day')
    preferred_time = estimate.get('preferred_time')
    
    if preferred_day or preferred_time:
        pdf.set_y(pdf.get_y() + 10)
        pdf.set_font('Helvetica', 'B', 9)
        pdf.set_text_color(150, 150, 150)
        pdf.cell(0, 6, 'PREFERRED SCHEDULE', 0, 1, 'L')
        
        pdf.set_font('Helvetica', '', 12)
        pdf.set_text_color(26, 26, 26)
        schedule = []
        if preferred_day:
            schedule.append(f'{preferred_day.title()}s')
        if preferred_time:
            schedule.append(preferred_time)
        pdf.cell(0, 8, ' - '.join(schedule), 0, 1, 'L')
    
    # Output
    pdf_bytes = pdf.output()
    pdf_file = io.BytesIO(pdf_bytes)
    pdf_file.seek(0)
    return pdf_file


def generate_invoice_pdf(invoice, visits, profile):
    """Generate a professional PDF for an invoice."""
    invoice_number = invoice.get('invoice_number', 'INV-0000')
    pdf = InvoicePDF(profile or {}, invoice_number)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=30)
    
    # Bill To and Invoice Date row
    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(95, 6, 'BILL TO', 0, 0, 'L')
    pdf.cell(95, 6, 'INVOICE DATE', 0, 1, 'R')
    
    pdf.set_font('Helvetica', 'B', 12)
    pdf.set_text_color(26, 26, 26)
    client_name = invoice.get('clients', {}).get('name', 'Client')
    created_at = invoice.get('created_at', '')[:10]
    pdf.cell(95, 7, client_name, 0, 0, 'L')
    pdf.set_font('Helvetica', '', 11)
    pdf.cell(95, 7, created_at, 0, 1, 'R')
    
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(100, 100, 100)
    client_address = invoice.get('clients', {}).get('address', '')
    pdf.cell(0, 6, client_address, 0, 1, 'L')
    
    pdf.ln(10)
    
    # Table header
    pdf.set_fill_color(245, 245, 245)
    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(40, 10, 'DATE', 0, 0, 'L', True)
    pdf.cell(110, 10, 'DESCRIPTION', 0, 0, 'L', True)
    pdf.cell(40, 10, 'AMOUNT', 0, 1, 'R', True)
    
    # Table rows
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(26, 26, 26)
    
    for visit in visits:
        pdf.cell(40, 10, visit.get('scheduled_date', ''), 0, 0, 'L')
        
        desc = 'Cleaning Service'
        if visit.get('completion_notes'):
            desc += f" - {visit['completion_notes'][:40]}"
        pdf.cell(110, 10, desc, 0, 0, 'L')
        
        price = visit.get('price', 0)
        pdf.cell(40, 10, f'${price:.2f}', 0, 1, 'R')
        
        # Light border
        pdf.set_draw_color(230, 230, 230)
        pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    
    pdf.ln(5)
    
    # Total box
    y_start = pdf.get_y()
    pdf.set_fill_color(255, 193, 7)
    pdf.rect(15, y_start, 180, 20, 'F')
    
    pdf.set_xy(20, y_start + 6)
    pdf.set_font('Helvetica', 'B', 14)
    pdf.set_text_color(26, 26, 26)
    pdf.cell(80, 8, 'Total Due', 0, 0, 'L')
    
    pdf.set_font('Helvetica', 'B', 20)
    total = invoice.get('total', 0)
    pdf.cell(90, 8, f'${total:.2f}', 0, 0, 'R')
    
    pdf.ln(25)
    
    # Payment instructions
    if profile and profile.get('payment_instructions'):
        pdf.set_y(pdf.get_y() + 5)
        pdf.set_fill_color(245, 245, 245)
        
        pdf.set_font('Helvetica', 'B', 9)
        pdf.set_text_color(150, 150, 150)
        pdf.cell(0, 8, 'PAYMENT METHODS', 0, 1, 'L')
        
        pdf.set_font('Helvetica', '', 10)
        pdf.set_text_color(50, 50, 50)
        pdf.multi_cell(0, 6, profile['payment_instructions'], 0, 'L')
    
    # Output
    pdf_bytes = pdf.output()
    pdf_file = io.BytesIO(pdf_bytes)
    pdf_file.seek(0)
    return pdf_file