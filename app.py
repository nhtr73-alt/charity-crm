from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import csv
import io
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from models import db, Contact, ContactNote, Category

app = Flask(__name__)
app.config['SECRET_KEY'] = 'charity-crm-secret-key-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///charity_crm.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255))
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=db.func.now())

class SMTPSettings(db.Model):
    __tablename__ = 'smtp_settings'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True)
    smtp_server = db.Column(db.String(255))
    smtp_port = db.Column(db.Integer, default=587)
    smtp_username = db.Column(db.String(255))
    smtp_password = db.Column(db.String(255))
    smtp_from_email = db.Column(db.String(255))
    use_tls = db.Column(db.Boolean, default=True)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()
    default_categories = ['Trader', 'Supplier', 'Ticket Holder', 'Donor', 'Volunteer', 'General']
    for cat_name in default_categories:
        existing = Category.query.filter_by(name=cat_name).first()
        if not existing:
            cat = Category(name=cat_name, is_default=True)
            db.session.add(cat)

    if not User.query.first():
        admin = User(username='admin', password_hash=generate_password_hash('charity2024'), email='admin@charity.org', is_admin=True)
        db.session.add(admin)
        db.session.commit()
        print('Default admin user created: admin / charity2024')

    db.session.commit()

DEFAULT_CATEGORIES = ['Trader', 'Supplier', 'Ticket Holder', 'Donor', 'Volunteer', 'General']

def admin_required(f):
    from functools import wraps
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            flash('Admin access required.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            flash('Invalid username or password.', 'error')

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/users')
@login_required
def users():
    if not current_user.is_admin:
        flash('Admin access required.', 'error')
        return redirect(url_for('index'))
    all_users = User.query.all()
    return render_template('users.html', users=all_users)

@app.route('/user/<int:user_id>/toggle_admin', methods=['POST'])
@login_required
def toggle_admin(user_id):
    if not current_user.is_admin:
        flash('Admin access required.', 'error')
        return redirect(url_for('index'))
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('Cannot change your own admin status.', 'error')
        return redirect(url_for('users'))
    user.is_admin = not user.is_admin
    db.session.commit()
    flash(f'Admin status updated for {user.username}.', 'success')
    return redirect(url_for('users'))

@app.route('/user/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    if not current_user.is_admin:
        flash('Admin access required.', 'error')
        return redirect(url_for('index'))
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('Cannot delete your own account.', 'error')
        return redirect(url_for('users'))
    db.session.delete(user)
    db.session.commit()
    flash(f'User {user.username} deleted.', 'success')
    return redirect(url_for('users'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        email = request.form.get('email', '').strip()

        if not username or not password:
            flash('Username and password are required.', 'error')
            return render_template('register.html')

        existing = User.query.filter_by(username=username).first()
        if existing:
            flash('Username already exists.', 'error')
            return render_template('register.html')

        user = User(username=username, password_hash=generate_password_hash(password), email=email)
        db.session.add(user)
        db.session.commit()
        flash('Account created! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/')
@login_required
def index():
    total_contacts = Contact.query.count()
    category_counts = {}
    for cat in DEFAULT_CATEGORIES:
        category_counts[cat] = Contact.query.filter_by(category=cat).count()
    return render_template('index.html', total_contacts=total_contacts, category_counts=category_counts)

@app.route('/contacts')
@login_required
def contacts_list():
    search = request.args.get('search', '')
    category_filter = request.args.get('category', '')
    sub_category_filter = request.args.get('sub_category', '')
    sort = request.args.get('sort', 'name')
    page = request.args.get('page', 1, type=int)
    per_page = 20

    query = Contact.query

    if search:
        search_term = f'%{search}%'
        query = query.filter(
            (Contact.first_name.ilike(search_term)) |
            (Contact.last_name.ilike(search_term)) |
            (Contact.email.ilike(search_term)) |
            (Contact.company.ilike(search_term))
        )

    if category_filter:
        query = query.filter_by(category=category_filter)

    if sub_category_filter:
        query = query.filter_by(sub_category=sub_category_filter)

    if sort == 'date':
        query = query.order_by(Contact.created_at.desc())
    else:
        query = query.order_by(Contact.last_name.asc(), Contact.first_name.asc())

    contacts = query.paginate(page=page, per_page=per_page, error_out=False)
    return render_template('contacts_list.html', contacts=contacts, search=search, category_filter=category_filter,
                         sub_category_filter=sub_category_filter, sort=sort)

@app.route('/contact/add', methods=['GET', 'POST'])
@login_required
def contact_add():
    sub_categories = get_unique_sub_categories()

    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        company = request.form.get('company', '').strip()
        category = request.form.get('category', 'General')
        sub_category = request.form.get('sub_category', '').strip()
        notes = request.form.get('notes', '').strip()

        if not first_name or not last_name or not email:
            flash('First name, last name, and email are required.', 'error')
            return render_template('contact_form.html', categories=DEFAULT_CATEGORIES, sub_categories=sub_categories, contact={})

        existing = Contact.query.filter_by(email=email).first()
        if existing:
            flash('A contact with this email already exists.', 'error')
            return render_template('contact_form.html', categories=DEFAULT_CATEGORIES, sub_categories=sub_categories, contact={})

        contact = Contact(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            company=company,
            category=category,
            sub_category=sub_category,
            notes=notes
        )
        db.session.add(contact)
        db.session.commit()
        flash('Contact added successfully!', 'success')
        return redirect(url_for('contacts_list'))

    return render_template('contact_form.html', categories=DEFAULT_CATEGORIES, sub_categories=sub_categories, contact={})

@app.route('/contact/<int:contact_id>')
@login_required
def contact_detail(contact_id):
    contact = Contact.query.get_or_404(contact_id)
    notes = ContactNote.query.filter_by(contact_id=contact_id).order_by(ContactNote.created_at.desc()).all()
    return render_template('contact_detail.html', contact=contact, notes=notes)

@app.route('/contact/<int:contact_id>/edit', methods=['GET', 'POST'])
@login_required
def contact_edit(contact_id):
    contact = Contact.query.get_or_404(contact_id)
    sub_categories = get_unique_sub_categories()

    if request.method == 'POST':
        contact.first_name = request.form.get('first_name', '').strip()
        contact.last_name = request.form.get('last_name', '').strip()
        contact.email = request.form.get('email', '').strip()
        contact.phone = request.form.get('phone', '').strip()
        contact.company = request.form.get('company', '').strip()
        contact.category = request.form.get('category', 'General')
        contact.sub_category = request.form.get('sub_category', '').strip()
        contact.notes = request.form.get('notes', '').strip()

        db.session.commit()
        flash('Contact updated successfully!', 'success')
        return redirect(url_for('contact_detail', contact_id=contact.id))

    return render_template('contact_form.html', categories=DEFAULT_CATEGORIES, sub_categories=sub_categories, contact=contact)

@app.route('/contact/<int:contact_id>/delete', methods=['POST'])
@login_required
def contact_delete(contact_id):
    contact = Contact.query.get_or_404(contact_id)
    db.session.delete(contact)
    db.session.commit()
    flash('Contact deleted successfully!', 'success')
    return redirect(url_for('contacts_list'))

@app.route('/contact/<int:contact_id>/note/add', methods=['POST'])
@login_required
def note_add(contact_id):
    contact = Contact.query.get_or_404(contact_id)
    content = request.form.get('content', '').strip()

    if not content:
        flash('Note content is required.', 'error')
        return redirect(url_for('contact_detail', contact_id=contact_id))

    note = ContactNote(contact_id=contact_id, content=content)
    db.session.add(note)
    db.session.commit()
    flash('Note added successfully!', 'success')
    return redirect(url_for('contact_detail', contact_id=contact_id))

@app.route('/contact/<int:contact_id>/note/<int:note_id>/delete', methods=['POST'])
@login_required
def note_delete(contact_id, note_id):
    note = ContactNote.query.get_or_404(note_id)
    db.session.delete(note)
    db.session.commit()
    flash('Note deleted successfully!', 'success')
    return redirect(url_for('contact_detail', contact_id=contact_id))

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_csv():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected.', 'error')
            return redirect(request.url)

        file = request.files['file']
        if file.filename == '':
            flash('No file selected.', 'error')
            return redirect(request.url)

        if file:
            stream = io.StringIO(file.stream.read().decode('UTF-8'), newline=None)
            csv_reader = csv.DictReader(stream)

            added = 0
            errors = []
            for row_num, row in enumerate(csv_reader, start=2):
                first_name = row.get('first_name', '').strip()
                last_name = row.get('last_name', '').strip()
                email = row.get('email', '').strip()

                if not email:
                    errors.append(f'Row {row_num}: Email is required')
                    continue

                existing = Contact.query.filter_by(email=email).first()
                if existing:
                    errors.append(f'Row {row_num}: Contact with email {email} already exists')
                    continue

                if not first_name or not last_name:
                    errors.append(f'Row {row_num}: First name and last name are required')
                    continue

                contact = Contact(
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    phone=row.get('phone', '').strip(),
                    company=row.get('company', '').strip(),
                    category=row.get('category', 'General').strip() or 'General',
                    sub_category=row.get('sub_category', '').strip()
                )
                db.session.add(contact)
                added += 1

            db.session.commit()
            if added > 0:
                flash(f'Successfully imported {added} contacts!', 'success')
            if errors:
                for error in errors[:10]:
                    flash(error, 'warning')
            return redirect(url_for('contacts_list'))

    return render_template('upload.html')

@app.route('/categories', methods=['GET', 'POST'])
@login_required
def categories():
    sub_categories = get_unique_sub_categories()

    if request.method == 'POST':
        new_category = request.form.get('new_category', '').strip()
        new_sub_category = request.form.get('new_sub_category', '').strip()

        if new_category:
            if new_category in DEFAULT_CATEGORIES:
                flash(f'Category {new_category} already exists.', 'error')
            else:
                DEFAULT_CATEGORIES.append(new_category)
                flash(f'Category {new_category} added!', 'success')

        if new_sub_category:
            if new_sub_category in sub_categories:
                flash(f'Sub-category {new_sub_category} already exists.', 'error')
            else:
                flash(f'Sub-category {new_sub_category} added!', 'success')

        return redirect(url_for('categories'))

    category_counts = {cat: Contact.query.filter_by(category=cat).count() for cat in DEFAULT_CATEGORIES}
    return render_template('categories.html', categories=DEFAULT_CATEGORIES, sub_categories=sub_categories, category_counts=category_counts)

@app.route('/email', methods=['GET', 'POST'])
@login_required
def email_page():
    selected_ids = request.args.getlist('contacts')
    selected_contacts = []

    if selected_ids:
        selected_contacts = Contact.query.filter(Contact.id.in_(selected_ids)).all()

    category_filter = request.args.get('category', '')

    if category_filter:
        all_contacts = Contact.query.filter_by(category=category_filter).all()
    else:
        all_contacts = Contact.query.all()

    if request.method == 'POST':
        recipient_ids = request.form.getlist('recipients')
        recipients = Contact.query.filter(Contact.id.in_(recipient_ids)).all()
        subject = request.form.get('subject', '').strip()
        body = request.form.get('body', '').strip()

        if not recipients:
            flash('No recipients selected.', 'error')
            return render_template('email.html', all_contacts=all_contacts, selected_ids=[int(r.id) for r in selected_contacts], category_filter=category_filter)

        if not subject or not body:
            flash('Subject and body are required.', 'error')
            return redirect(url_for('email_page'))

        emails = [r.email for r in recipients]
        session['bulk_emails'] = emails
        session['email_subject'] = subject
        session['email_body'] = body
        flash(f'{len(emails)} email(s) queued. Use your email client to send.', 'success')
        return redirect(url_for('email_page'))

    return render_template('email.html', all_contacts=all_contacts, selected_contacts=selected_contacts, selected_ids=[int(r.id) for r in selected_contacts], category_filter=category_filter)

@app.route('/contact/<int:contact_id>/send_email', methods=['GET', 'POST'])
@login_required
def send_single_email(contact_id):
    contact = Contact.query.get_or_404(contact_id)

    if request.method == 'POST':
        subject = request.form.get('subject', '').strip()
        body = request.form.get('body', '').strip()

        if not subject or not body:
            flash('Subject and body are required.', 'error')
            return render_template('email_single.html', contact=contact)

        use_smtp = request.form.get('use_smtp') == 'send'

        if use_smtp:
            ok, msg = send_smtp_email(contact.email, subject, body, current_user.id)
            if ok:
                flash(f'Email sent to {contact.email}!', 'success')
            else:
                flash(f'Send failed: {msg}. Use mailto instead.', 'error')
        else:
            mailto_url = f"mailto:{contact.email}?subject={subject}&body={body}"
            flash(f'Email ready. <a href="{mailto_url}" class="btn btn-primary">Open Email App</a>', 'success')

        return redirect(url_for('contact_detail', contact_id=contact_id))

    return render_template('email_single.html', contact=contact)

def get_unique_sub_categories():
    sub_categories = set()
    contacts = Contact.query.all()
    for contact in contacts:
        if contact.sub_category:
            sub_categories.add(contact.sub_category)
    return sorted(list(sub_categories))

def send_smtp_email(recipient_email, subject, body, user_id):
    settings = None
    try:
        settings = SMTPSettings.query.filter_by(user_id=user_id).first()

        admin_user = User.query.filter_by(is_admin=True).first()
        if not settings and admin_user:
            settings = SMTPSettings.query.filter_by(user_id=admin_user.id).first()

        if not settings or not settings.smtp_server:
            return False, "SMTP not configured - go to Settings"

        msg = MIMEMultipart()
        from_addr = settings.smtp_from_email or settings.smtp_username
        msg['From'] = from_addr
        msg['To'] = recipient_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(settings.smtp_server, settings.smtp_port, timeout=30)
        if settings.use_tls:
            server.starttls()
        server.login(settings.smtp_username, settings.smtp_password)
        server.sendmail(from_addr, recipient_email, msg.as_string())
        server.quit()
        return True, "Sent"
    except Exception as e:
        import traceback
        return False, f"Error: {str(e)}"

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    smtp = SMTPSettings.query.filter_by(user_id=current_user.id).first()
    if not smtp:
        smtp = SMTPSettings(user_id=current_user.id)
        db.session.add(smtp)
        db.session.commit()

    if request.method == 'POST':
        smtp.smtp_server = request.form.get('smtp_server', '').strip()
        smtp.smtp_port = request.form.get('smtp_port', '587').strip()
        smtp.smtp_username = request.form.get('smtp_username', '').strip()
        smtp.smtp_password = request.form.get('smtp_password', '').strip()
        smtp.smtp_from_email = request.form.get('smtp_from_email', '').strip()
        smtp.use_tls = 'use_tls' in request.form
        db.session.commit()
        flash('SMTP settings saved!', 'success')
        return redirect(url_for('settings'))

    return render_template('settings.html', smtp=smtp)

@app.context_processor
def inject_categories():
    from flask_login import current_user
    return dict(categories_list=DEFAULT_CATEGORIES, current_user=current_user)

if __name__ == '__main__':
    app.run(debug=True, port=5000)