# MiKlean

Simple tools for small cleaning businesses. Manage prospects, estimates, visits, and invoices from your phone.

## Features

- **Client Management** - Track prospects and clients with contact info and notes
- **Estimates** - Create and send professional estimates with accept links
- **Scheduling** - Rolling 8-week visit schedule with automatic renewal
- **Invoicing** - Invoice completed visits and track payments
- **Mobile-First** - Designed for use in the field on any phone

## Tech Stack

- **Backend:** Python/Flask
- **Database:** Supabase (PostgreSQL)
- **Auth:** Supabase Auth
- **Frontend:** Jinja2 templates + Tailwind CSS
- **Email:** SendGrid
- **Calendar:** Google Calendar API (optional)

## Setup

1. Clone the repository
2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # or `venv\Scripts\activate` on Windows
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Copy `.env.example` to `.env` and fill in your credentials
5. Run the SQL setup script in your Supabase project
6. Start the development server:
   ```bash
   python run.py
   ```

## Environment Variables

See `.env.example` for all required environment variables.

## Development

The app runs on `http://localhost:5000` by default.

## License

Proprietary - Untitled Publishers
