"""
Help and support routes.
"""
from flask import Blueprint, render_template
from ..auth import login_required

bp = Blueprint('help', __name__, url_prefix='/help')


@bp.route('/')
@login_required
def index():
    """Main help page."""
    return render_template('help/index.html')


@bp.route('/getting-started')
@login_required
def getting_started():
    """Getting started tutorial."""
    return render_template('help/getting_started.html')


@bp.route('/faq')
@login_required
def faq():
    """Frequently asked questions."""
    return render_template('help/faq.html')
