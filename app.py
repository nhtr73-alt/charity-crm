from flask import Flask, render_template, request, redirect, url_for, flash, session, Response
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.encoders import encode_base64
import csv
import io
import smtplib
import json
import urllib.request
import urllib.error
import base64
from datetime import datetime, date
from models import db, Contact, ContactNote, Category, EmailTemplateOld as EmailTemplate, EmailAttachment, Task, Donation, Event, EventRegistration, ActivityLog, Tag, ContactTag, EmailSendLog, EmailSequence, ContactSequence, CustomField, DuplicateGroup

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
    mailjet_api_key = db.Column(db.String(255))
    mailjet_secret_key = db.Column(db.String(255))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()

    try:
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        
        if 'contacts' in inspector.get_table_names():
            contact_columns = [col['name'] for col in inspector.get_columns('contacts')]
            if 'pipeline_stage' not in contact_columns:
                db.session.execute(db.text('ALTER TABLE contacts ADD COLUMN pipeline_stage VARCHAR(50) DEFAULT \'New\''))
            if 'lifecycle_stage' not in contact_columns:
                db.session.execute(db.text('ALTER TABLE contacts ADD COLUMN lifecycle_stage VARCHAR(50) DEFAULT \'Subscriber\''))
            if 'engagement_score' not in contact_columns:
                db.session.execute(db.text('ALTER TABLE contacts ADD COLUMN engagement_score INTEGER DEFAULT 0'))
            if 'last_email_open' not in contact_columns:
                db.session.execute(db.text('ALTER TABLE contacts ADD COLUMN last_email_open DATETIME'))
            if 'last_email_click' not in contact_columns:
                db.session.execute(db.text('ALTER TABLE contacts ADD COLUMN last_email_click DATETIME'))
            if 'total_emails_opened' not in contact_columns:
                db.session.execute(db.text('ALTER TABLE contacts ADD COLUMN total_emails_opened INTEGER DEFAULT 0'))
            if 'total_emails_clicked' not in contact_columns:
                db.session.execute(db.text('ALTER TABLE contacts ADD COLUMN total_emails_clicked INTEGER DEFAULT 0'))
            if 'custom_fields' not in contact_columns:
                db.session.execute(db.text('ALTER TABLE contacts ADD COLUMN custom_fields TEXT'))
            db.session.commit()
        
        smtp_columns = [col['name'] for col in inspector.get_columns('smtp_settings')] if 'smtp_settings' in inspector.get_table_names() else []
        if 'mailjet_api_key' not in smtp_columns:
            try:
                db.session.execute(db.text('ALTER TABLE smtp_settings ADD COLUMN mailjet_api_key VARCHAR(255)'))
                db.session.execute(db.text('ALTER TABLE smtp_settings ADD COLUMN mailjet_secret_key VARCHAR(255)'))
                db.session.commit()
            except:
                pass
    except Exception as e:
        print(f"Migration note: {e}")

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

    if request.args.get('preview'):
        contact = Contact.query.get(request.args.get('preview'))
        if contact:
            subject = request.args.get('subject', '')
            body = request.args.get('body', '')
            body = body.replace('{{first_name}}', contact.first_name)
            body = body.replace('{{last_name}}', contact.last_name)
            body = body.replace('{{full_name}}', f'{contact.first_name} {contact.last_name}')
            body = body.replace('{{email}}', contact.email)
            body = body.replace('{{company}}', contact.company or '')
            subject = subject.replace('{{first_name}}', contact.first_name)
            subject = subject.replace('{{last_name}}', contact.last_name)
            subject = subject.replace('{{full_name}}', f'{contact.first_name} {contact.last_name}')
            return render_template('email_preview.html', contact=contact, subject=subject, body=body)

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

        personalized_emails = []
        for recipient in recipients:
            personalized_body = body
            personalized_body = personalized_body.replace('{{first_name}}', recipient.first_name)
            personalized_body = personalized_body.replace('{{last_name}}', recipient.last_name)
            personalized_body = personalized_body.replace('{{full_name}}', f'{recipient.first_name} {recipient.last_name}')
            personalized_body = personalized_body.replace('{{email}}', recipient.email)
            personalized_body = personalized_body.replace('{{company}}', recipient.company or '')

            personalized_subject = subject
            personalized_subject = personalized_subject.replace('{{first_name}}', recipient.first_name)
            personalized_subject = personalized_subject.replace('{{last_name}}', recipient.last_name)
            personalized_subject = personalized_subject.replace('{{full_name}}', f'{recipient.first_name} {recipient.last_name}')

            add_email_note(recipient.id, f"Subject: {personalized_subject}\n\n{personalized_body}", 'Bulk Email')
            personalized_emails.append({
                'email': recipient.email,
                'name': f'{recipient.first_name} {recipient.last_name}',
                'subject': personalized_subject,
                'body': personalized_body
            })

        session['bulk_emails'] = personalized_emails
        session['email_subject'] = subject
        session['email_body'] = body
        flash(f'{len(personalized_emails)} email(s) prepared with personalization!', 'success')
        return redirect(url_for('email_page'))

    return render_template('email.html', all_contacts=all_contacts, selected_contacts=selected_contacts, selected_ids=[int(r.id) for r in selected_contacts], category_filter=category_filter)

@app.route('/email/send_all', methods=['POST'])
@login_required
def send_all_emails():
    from datetime import datetime
    
    attachment_ids = request.form.getlist('attachments')
    attachments = []
    if attachment_ids:
        attachments = [{'id': a.id, 'filepath': a.filepath, 'filename': a.filename, 'content_type': a.content_type} 
                     for a in EmailAttachment.query.filter(EmailAttachment.id.in_(attachment_ids)).all()]
    
    bulk_emails = session.get('bulk_emails', [])
    if not bulk_emails:
        flash('No emails prepared. Please compose emails first.', 'error')
        return redirect(url_for('email_page'))

    sent_count = 0
    failed_count = 0
    failed_emails = []

    for email_data in bulk_emails:
        ok, msg = send_smtp_email(email_data['email'], email_data['subject'], email_data['body'], current_user.id, attachments)
        if ok:
            sent_count += 1
            for recipient in Contact.query.filter_by(email=email_data['email']).all():
                add_email_note(recipient.id, email_data['subject'], email_data['body'], 'Bulk Email')
        else:
            failed_count += 1
            failed_emails.append(f"{email_data['email']}: {msg}")

    session.pop('bulk_emails', None)
    session.pop('email_subject', None)
    session.pop('email_body', None)

    if sent_count > 0:
        flash(f'Successfully sent {sent_count} email(s)!', 'success')
    if failed_count > 0:
        for err in failed_emails:
            flash(f'Failed: {err}', 'error')

    return redirect(url_for('email_page'))

@app.route('/email/test', methods=['POST'])
@login_required
def test_email():
    test_email_addr = request.form.get('test_email', '').strip()
    
    if not test_email_addr:
        flash('Please provide a test email address.', 'error')
        return redirect(url_for('settings'))
    
    ok, msg = send_smtp_email(test_email_addr, "Test Email from Charity CRM", 
                             "This is a test email to verify your email settings are configured correctly.", 
                             current_user.id)
    
    if ok:
        flash(f'Test email sent to {test_email_addr}!', 'success')
    else:
        flash(f'Test failed: {msg}', 'error')
    
    return redirect(url_for('settings'))

@app.route('/email/clear_prepared', methods=['POST'])
@login_required
def clear_prepared_emails():
    session.pop('bulk_emails', None)
    session.pop('email_subject', None)
    session.pop('email_body', None)
    return {'success': True}


@app.route('/email/track/open/<int:contact_id>/<message_id>')
def track_email_open(contact_id, message_id):
    contact = Contact.query.get(contact_id)
    if contact:
        contact.last_email_open = datetime.utcnow()
        contact.total_emails_opened = (contact.total_emails_opened or 0) + 1
        contact.engagement_score = (contact.engagement_score or 0) + 5
        db.session.commit()

        log = EmailSendLog.query.filter_by(contact_id=contact_id, message_id=message_id).first()
        if log:
            log.opened_at = datetime.utcnow()
            db.session.commit()

    pixel = b'R0lGODlhAQABAIAAAAAAAP///yH5BAEAAEALAAAAAABAAEAAAICTAEAOw=='
    return Response(base64.b64decode(pixel), mimetype='image/gif')


@app.route('/email/track/click/<int:contact_id>/<message_id>')
def track_email_click(contact_id, message_id):
    contact = Contact.query.get(contact_id)
    if contact:
        contact.last_email_click = datetime.utcnow()
        contact.total_emails_clicked = (contact.total_emails_clicked or 0) + 1
        contact.engagement_score = (contact.engagement_score or 0) + 10
        db.session.commit()

        log = EmailSendLog.query.filter_by(contact_id=contact_id, message_id=message_id).first()
        if log:
            log.clicked_at = datetime.utcnow()
            db.session.commit()

    return '', 204


@app.route('/sequences')
@login_required
def email_sequences():
    sequences = EmailSequence.query.order_by(EmailSequence.created_at.desc()).all()
    return render_template('sequences.html', sequences=sequences)


@app.route('/sequences/new', methods=['GET', 'POST'])
@login_required
def create_sequence():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        trigger_type = request.form.get('trigger_type', '').strip()

        if not name:
            flash('Sequence name is required.', 'error')
            return redirect(url_for('create_sequence'))

        steps_json = []
        step_count = int(request.form.get('step_count', 0))
        for i in range(step_count):
            step = {
                'delay_days': int(request.form.get(f'step_{i}_delay', 0)),
                'subject': request.form.get(f'step_{i}_subject', ''),
                'body': request.form.get(f'step_{i}_body', '')
            }
            if step['subject']:
                steps_json.append(step)

        sequence = EmailSequence(
            name=name,
            description=description,
            trigger_type=trigger_type,
            steps=json.dumps(steps_json),
            is_active='is_active' in request.form
        )
        db.session.add(sequence)
        db.session.commit()
        flash('Email sequence created!', 'success')
        return redirect(url_for('email_sequences'))

    return render_template('sequence_form.html', sequence=None)


@app.route('/sequences/<int:sequence_id>/enroll', methods=['POST'])
@login_required
def enroll_sequence(sequence_id):
    contact_ids = request.form.getlist('contacts')
    sequence = EmailSequence.query.get_or_404(sequence_id)

    for cid in contact_ids:
        existing = ContactSequence.query.filter_by(contact_id=cid, sequence_id=sequence_id).first()
        if not existing:
            cs = ContactSequence(contact_id=cid, sequence_id=sequence_id)
            db.session.add(cs)

    db.session.commit()
    flash(f'Enrolled {len(contact_ids)} contacts in {sequence.name}', 'success')
    return redirect(url_for('email_sequences'))


@app.route('/sequences/run')
@login_required
def run_sequences():
    now = datetime.utcnow()

    active_sequences = EmailSequence.query.filter_by(is_active=True).all()
    enrolled = ContactSequence.query.filter_by(paused=False).all()

    results = {'processed': 0, 'sent': 0}

    for cs in enrolled:
        if not cs.sequence or not cs.sequence.is_active:
            continue

        steps = json.loads(cs.sequence.steps or '[]')
        if cs.current_step >= len(steps):
            cs.completed_at = now
            cs.paused = True
            results['processed'] += 1
            continue

        step = steps[cs.current_step]
        contact = Contact.query.get(cs.contact_id)

        if not contact:
            continue

        delay = step.get('delay_days', 0)
        step_started = cs.started_at or now

        if (now - step_started).days >= delay:
            personalized_body = step.get('body', '').replace('{{first_name}}', contact.first_name)
            personalized_body = personalized_body.replace('{{last_name}}', contact.last_name)
            personalized_body = personalized_body.replace('{{full_name}}', f'{contact.first_name} {contact.last_name}')

            personalized_subject = step.get('subject', '').replace('{{first_name}}', contact.first_name)

            ok, msg = send_smtp_email(contact.email, personalized_subject, personalized_body, current_user.id)

            log = EmailSendLog(contact_id=contact.id, subject=personalized_subject, message_id=f"{cs.id}_{cs.current_step}")
            db.session.add(log)

            cs.current_step += 1
            results['processed'] += 1
            if ok:
                results['sent'] += 1

    db.session.commit()
    flash(f'Sequence processor: {results["sent"]} emails sent, {results["processed"]} processed', 'success')
    return redirect(url_for('email_sequences'))


@app.route('/duplicates')
@login_required
def duplicates():
    potential_dups = []
    contacts = Contact.query.all()

    for i, c1 in enumerate(contacts):
        for c2 in contacts[i+1:]:
            score = 0
            if c1.email.lower() == c2.email.lower():
                score += 100
            if c1.first_name.lower() == c2.first_name.lower() and c1.last_name.lower() == c2.last_name.lower():
                score += 80
            if c1.phone and c2.phone and c1.phone == c2.phone:
                score += 50

            if score >= 80:
                potential_dups.append({'contact1': c1, 'contact2': c2, 'score': score})

    return render_template('duplicates.html', duplicates=potential_dups)


@app.route('/duplicates/merge', methods=['POST'])
@login_required
def merge_duplicates():
    keep_id = request.form.get('keep_id', type=int)
    merge_id = request.form.get('merge_id', type=int)

    keep = Contact.query.get_or_404(keep_id)
    merge = Contact.query.get_or_404(merge_id)

    notes = ContactNote.query.filter_by(contact_id=merge_id).all()
    for note in notes:
        note.contact_id = keep_id
        db.session.add(note)

    tasks = Task.query.filter_by(contact_id=merge_id).all()
    for task in tasks:
        task.contact_id = keep_id
        db.session.add(task)

    donations = Donation.query.filter_by(contact_id=merge_id).all()
    for donation in donations:
        donation.contact_id = keep_id
        db.session.add(donation)

    db.session.delete(merge)
    db.session.commit()

    flash(f'Merged into {keep.full_name}', 'success')
    return redirect(url_for('duplicates'))


@app.route('/contact/<int:contact_id>/convert', methods=['POST'])
@login_required
def convert_contact_to_donor(contact_id):
    contact = Contact.query.get_or_404(contact_id)
    contact.category = 'Donor'
    if contact.lifecycle_stage == 'Subscriber':
        contact.lifecycle_stage = 'Lead'
    elif contact.lifecycle_stage == 'Lead':
        contact.lifecycle_stage = 'Donor'
    contact.pipeline_stage = 'Completed'
    contact.engagement_score = (contact.engagement_score or 0) + 50
    db.session.commit()
    log_activity(contact_id, 'Converted to Donor')
    flash(f'{contact.full_name} converted to Donor', 'success')
    return redirect(url_for('contact_detail', contact_id=contact_id))


@app.route('/custom-fields')
@login_required
def custom_fields_list():
    fields = CustomField.query.all()
    return render_template('custom_fields.html', fields=fields)


@app.route('/custom-fields/new', methods=['POST'])
@login_required
def create_custom_field():
    name = request.form.get('name', '').strip()
    field_type = request.form.get('field_type', 'text')
    options = request.form.get('options', '').strip()

    if not name:
        flash('Field name is required.', 'error')
        return redirect(url_for('custom_fields_list'))

    field = CustomField(name=name, field_type=field_type, options=options)
    db.session.add(field)
    db.session.commit()
    flash(f'Custom field {name} created!', 'success')
    return redirect(url_for('custom_fields_list'))


@app.route('/score/update', methods=['POST'])
@login_required
def update_engagement_scores():
    for contact in Contact.query.all():
        score = 0

        score += (contact.total_emails_opened or 0) * 5
        score += (contact.total_emails_clicked or 0) * 10

        notes_count = contact.contact_notes.count()
        score += notes_count * 10

        donations = contact.donations.all()
        total_donated = sum(d.amount for d in donations)
        if total_donated > 0:
            score += min(int(total_donated / 10), 100)

        tasks_completed = Task.query.filter_by(contact_id=contact.id, completed=True).count()
        score += tasks_completed * 20

        contact.engagement_score = score

        if total_donated >= 1000:
            contact.lifecycle_stage = 'Major Donor'
        elif total_donated > 0:
            contact.lifecycle_stage = 'Recurring' if contact.lifecycle_stage in ['Donor', 'Recurring'] else 'Donor'
        elif score > 100:
            contact.lifecycle_stage = 'Lead'
        elif score > 0:
            contact.lifecycle_stage = 'Subscriber'

    db.session.commit()
    flash('Engagement scores updated!', 'success')
    return redirect(url_for('contacts_list'))


@app.route('/email/templates/library')
@login_required
def email_template_library():
    category = request.args.get('category', '')
    if category:
        templates = EmailTemplate.query.filter_by(category=category).order_by(EmailTemplate.usage_count.desc()).all()
    else:
        templates = EmailTemplate.query.order_by(EmailTemplate.usage_count.desc()).all()
    return render_template('email_templates.html', templates=templates, library=True)

@app.route('/email/builder')
@login_required
def email_builder():
    category_filter = request.args.get('category', '')
    if category_filter:
        all_contacts = Contact.query.filter_by(category=category_filter).all()
    else:
        all_contacts = Contact.query.all()
    
    contacts_data = [{'id': c.id, 'first_name': c.first_name, 'last_name': c.last_name, 'email': c.email, 'company': c.company} for c in all_contacts]
    return render_template('email_builder.html', all_contacts=contacts_data, category_filter=category_filter)

@app.route('/email/rich')
@login_required
def email_compose():
    category_filter = request.args.get('category', '')
    if category_filter:
        all_contacts = Contact.query.filter_by(category=category_filter).all()
    else:
        all_contacts = Contact.query.all()
    contacts_data = [{'id': c.id, 'first_name': c.first_name, 'last_name': c.last_name, 'email': c.email, 'company': c.company} for c in all_contacts]
    return render_template('email_compose.html', all_contacts=contacts_data, category_filter=category_filter)


def rich_email():
    category_filter = request.args.get('category', '')
    if category_filter:
        all_contacts = Contact.query.filter_by(category=category_filter).all()
    else:
        all_contacts = Contact.query.all()
    
    contacts_data = [{'id': c.id, 'first_name': c.first_name, 'last_name': c.last_name, 'email': c.email, 'company': c.company} for c in all_contacts]
    templates = EmailTemplate.query.order_by(EmailTemplate.updated_at.desc()).all()
    return render_template('rich_email.html', all_contacts=contacts_data, category_filter=category_filter, email_templates=templates)

@app.route('/email/template/save', methods=['POST'])
@login_required
def save_email_template():
    name = request.form.get('name', '').strip()
    subject = request.form.get('subject', '').strip()
    content = request.form.get('content', '').strip()
    
    if not name or not content:
        return {'success': False, 'message': 'Name and content are required'}
    
    template_id = request.form.get('id')
    
    if template_id:
        template = EmailTemplate.query.get(template_id)
        if template:
            template.name = name
            template.subject = subject
            template.content = content
        else:
            return {'success': False, 'message': 'Template not found'}
    else:
        template = EmailTemplate(name=name, subject=subject, content=content)
        db.session.add(template)
    
    db.session.commit()
    return {'success': True, 'message': 'Template saved!'}

@app.route('/email/template/delete/<int:template_id>', methods=['POST'])
@login_required
def delete_email_template(template_id):
    template = EmailTemplate.query.get_or_404(template_id)
    db.session.delete(template)
    db.session.commit()
    flash('Template deleted.', 'success')
    return redirect(url_for('rich_email'))

@app.route('/email/templates')
@login_required
def list_email_templates():
    templates = EmailTemplate.query.order_by(EmailTemplate.updated_at.desc()).all()
    return {'templates': [{'id': t.id, 'name': t.name, 'subject': t.subject, 'content': t.content} for t in templates]}

@app.route('/email/attachment/upload', methods=['POST'])
@login_required
def upload_attachment():
    if 'file' not in request.files:
        return {'success': False, 'message': 'No file selected'}
    
    file = request.files['file']
    if file.filename == '':
        return {'success': False, 'message': 'No file selected'}
    
    import os
    from werkzeug.utils import secure_filename
    
    filename = secure_filename(file.filename)
    upload_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads', 'attachments')
    os.makedirs(upload_folder, exist_ok=True)
    
    filepath = os.path.join(upload_folder, filename)
    file.save(filepath)
    
    attachment = EmailAttachment(filename=filename, filepath=filepath, content_type=file.content_type)
    db.session.add(attachment)
    db.session.commit()
    
    return {'success': True, 'id': attachment.id, 'filename': filename}

@app.route('/email/attachments')
@login_required
def list_attachments():
    attachments = EmailAttachment.query.order_by(EmailAttachment.created_at.desc()).all()
    return {'attachments': [{'id': a.id, 'filename': a.filename, 'created_at': a.created_at.isoformat()} for a in attachments]}

@app.route('/email/attachment/<int:attachment_id>/delete', methods=['POST'])
@login_required
def delete_attachment(attachment_id):
    import os
    attachment = EmailAttachment.query.get_or_404(attachment_id)
    if os.path.exists(attachment.filepath):
        os.remove(attachment.filepath)
    db.session.delete(attachment)
    db.session.commit()
    return {'success': True}

@app.route('/uploads/attachments/<filename>')
@login_required
def serve_attachment(filename):
    from flask import send_from_directory
    import os
    upload_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads', 'attachments')
    return send_from_directory(upload_folder, filename)

def add_email_note(contact_id, subject, body, sent_via='SMTP'):
    from datetime import datetime
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    note_content = f"[{timestamp}] EMAIL SENT ({sent_via})\nSubject: {subject}\n\n{body}"
    note = ContactNote(contact_id=contact_id, content=note_content)
    db.session.add(note)
    db.session.commit()

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
                add_email_note(contact_id, subject, body, 'SMTP')
                flash(f'Email sent to {contact.email}!', 'success')
            else:
                flash(f'Send failed: {msg}. Use mailto instead.', 'error')
        else:
            add_email_note(contact_id, subject, body, 'Mailto')
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

def send_smtp_email(recipient_email, subject, body, user_id, attachments=None):
    settings = None
    try:
        settings = SMTPSettings.query.filter_by(user_id=user_id).first()

        admin_user = User.query.filter_by(is_admin=True).first()
        if not settings and admin_user:
            settings = SMTPSettings.query.filter_by(user_id=admin_user.id).first()

        if not settings:
            return False, "SMTP not configured - go to Settings"

        if settings.mailjet_api_key and settings.mailjet_secret_key:
            return send_mailjet_email(recipient_email, subject, body, settings, attachments)

        if not settings.smtp_server:
            return False, "SMTP not configured - go to Settings"

        msg = MIMEMultipart()
        from_addr = settings.smtp_from_email or settings.smtp_username
        msg['From'] = from_addr
        msg['To'] = recipient_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        if attachments:
            import os
            from email.encoders import encode_base64
            for att in attachments:
                if os.path.exists(att.get('filepath', '')):
                    with open(att['filepath'], 'rb') as f:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(f.read())
                        encode_base64(part)
                        part.add_header('Content-Disposition', f'attachment; filename="{att.get("filename", "attachment")}"')
                        msg.attach(part)

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

def send_mailjet_email(recipient_email, subject, body, settings, attachments=None):
    try:
        api_key = settings.mailjet_api_key
        secret_key = settings.mailjet_secret_key
        from_email = settings.smtp_from_email or settings.smtp_username

        import base64
        auth = base64.b64encode(f"{api_key}:{secret_key}".encode()).decode()

        message = {
            "From": {"Email": from_email, "Name": "Charity CRM"},
            "To": recipient_email if isinstance(recipient_email, str) else ",".join(recipient_email),
            "Subject": subject,
            "TextPart": body,
            "HTMLPart": body.replace('\n', '<br>')
        }

        if attachments:
            import os
            import base64
            attachment_list = []
            for att in attachments:
                if os.path.exists(att.get('filepath', '')):
                    with open(att['filepath'], 'rb') as f:
                        attachment_list.append({
                            "ContentType": att.get('content_type', 'application/octet-stream'),
                            "Filename": att.get('filename', 'attachment'),
                            "Base64Content": base64.b64encode(f.read()).decode()
                        })
            if attachment_list:
                message["Attachments"] = attachment_list

        data = json.dumps({
            "Messages": [message]
        }).encode('utf-8')

        req = urllib.request.Request(
            "https://api.mailjet.com/v3.1/send",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Basic {auth}"
            },
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode())
            if result.get("Messages", [{}])[0].get("Status") == "success":
                return True, "Sent via Mailjet"
            else:
                return False, f"Mailjet error: {result}"

    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        return False, f"Mailjet HTTP {e.code}: {error_body}"
    except Exception as e:
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
        smtp.mailjet_api_key = request.form.get('mailjet_api_key', '').strip()
        smtp.mailjet_secret_key = request.form.get('mailjet_secret_key', '').strip()
        smtp.smtp_server = request.form.get('smtp_server', '').strip()
        smtp.smtp_port = request.form.get('smtp_port', '587').strip()
        smtp.smtp_username = request.form.get('smtp_username', '').strip()
        smtp.smtp_password = request.form.get('smtp_password', '').strip()
        smtp.smtp_from_email = request.form.get('smtp_from_email', '').strip()
        smtp.use_tls = 'use_tls' in request.form
        db.session.commit()
        flash('Settings saved!', 'success')
        return redirect(url_for('settings'))

    return render_template('settings.html', smtp=smtp)


@app.route('/pipeline')
@login_required
def show_pipeline():
    stages = {
        'New': Contact.query.filter_by(pipeline_stage='New').all(),
        'Contacted': Contact.query.filter_by(pipeline_stage='Contacted').all(),
        'In Progress': Contact.query.filter_by(pipeline_stage='In Progress').all(),
        'Completed': Contact.query.filter_by(pipeline_stage='Completed').all(),
        'Lost': Contact.query.filter_by(pipeline_stage='Lost').all()
    }
    return render_template('pipeline.html', stages=stages)


@app.route('/contact/<int:contact_id>/pipeline', methods=['POST'])
@login_required
def set_pipeline_stage(contact_id):
    contact = Contact.query.get_or_404(contact_id)
    new_stage = request.form.get('stage', 'New')
    old_stage = contact.pipeline_stage
    contact.pipeline_stage = new_stage
    db.session.commit()
    log_activity(contact_id, f"Pipeline stage changed from {old_stage} to {new_stage}")
    flash(f'Stage updated to {new_stage}', 'success')
    return redirect(url_for('show_pipeline'))


@app.route('/tasks')
@login_required
def my_tasks():
    tasks = Task.query.filter_by(assigned_to=current_user.id).order_by(Task.due_date.asc()).all()
    return render_template('my_tasks.html', tasks=tasks)


@app.route('/tasks/new', methods=['GET', 'POST'])
@login_required
def create_task():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            flash('Task title is required.', 'error')
            return redirect(url_for('create_task'))

        task = Task(
            title=title,
            description=request.form.get('description', '').strip(),
            contact_id=request.form.get('contact_id') or None,
            assigned_to=request.form.get('assigned_to') or current_user.id,
            due_date=parse_date(request.form.get('due_date', ''))
        )
        db.session.add(task)
        db.session.commit()
        flash('Task created!', 'success')
        return redirect(url_for('my_tasks'))

    contacts = Contact.query.all()
    users = User.query.all()
    return render_template('task_form.html', task=None, contacts=contacts, users=users)


@app.route('/tasks/<int:task_id>/toggle', methods=['POST'])
@login_required
def toggle_task(task_id):
    task = Task.query.get_or_404(task_id)
    task.completed = not task.completed
    if task.completed:
        from datetime import datetime
        task.completed_at = datetime.utcnow()
    else:
        task.completed_at = None
    db.session.commit()
    flash(f'Task {"completed" if task.completed else " reopened"}!', 'success')
    return redirect(url_for('my_tasks'))


@app.route('/tasks/<int:task_id>/delete', methods=['POST'])
@login_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    db.session.delete(task)
    db.session.commit()
    flash('Task deleted.', 'success')
    return redirect(url_for('my_tasks'))


@app.route('/donations')
@login_required
def donations_list():
    filter_status = request.args.get('filter', 'all')
    if filter_status == 'year':
        from datetime import date
        year = date.today().year
        dons = Donation.query.filter(db.func.strftime('%Y', Donation.donation_date) == str(year)).all()
    else:
        dons = Donation.query.order_by(Donation.donation_date.desc()).all()

    total = sum(d.amount for d in dons)
    return render_template('donations.html', donations=dons, total=total, filter_status=filter_status)


@app.route('/contact/<int:contact_id>/donations/add', methods=['GET', 'POST'])
@login_required
def add_donation(contact_id):
    contact = Contact.query.get_or_404(contact_id)
    if request.method == 'POST':
        amount = request.form.get('amount', type=float)
        if not amount or amount <= 0:
            flash('Valid amount is required.', 'error')
            return redirect(url_for('add_donation', contact_id=contact_id))

        donation = Donation(
            contact_id=contact_id,
            amount=amount,
            donation_date=parse_date(request.form.get('donation_date', '')),
            payment_method=request.form.get('payment_method', '').strip(),
            payment_reference=request.form.get('payment_reference', '').strip(),
            notes=request.form.get('notes', '').strip()
        )
        db.session.add(donation)
        db.session.commit()
        log_activity(contact_id, f"Donation of ${amount} recorded")
        flash(f'Donation of ${amount} recorded!', 'success')
        return redirect(url_for('contact_detail', contact_id=contact_id))

    return render_template('donation_form.html', contact=contact)


@app.route('/donations/<int:donation_id>/delete', methods=['POST'])
@login_required
def delete_donation(donation_id):
    donation = Donation.query.get_or_404(donation_id)
    contact_id = donation.contact_id
    db.session.delete(donation)
    db.session.commit()
    flash('Donation deleted.', 'success')
    return redirect(url_for('contact_detail', contact_id=contact_id))


@app.route('/events')
@login_required
def events_list():
    upcoming = Event.query.filter(Event.event_date >= datetime.utcnow()).order_by(Event.event_date.asc()).all()
    past = Event.query.filter(Event.event_date < datetime.utcnow()).order_by(Event.event_date.desc()).all()
    return render_template('events.html', upcoming=upcoming, past=past)


@app.route('/events/new', methods=['GET', 'POST'])
@login_required
def create_event():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Event name is required.', 'error')
            return redirect(url_for('create_event'))

        event = Event(
            name=name,
            description=request.form.get('description', '').strip(),
            event_date=parse_datetime(request.form.get('event_date', '')),
            location=request.form.get('location', '').strip(),
            event_type=request.form.get('event_type', '').strip(),
            capacity=request.form.get('capacity', type=int) or None
        )
        db.session.add(event)
        db.session.commit()
        flash('Event created!', 'success')
        return redirect(url_for('events_list'))

    return render_template('event_form.html', event=None)


@app.route('/events/<int:event_id>')
@login_required
def event_detail(event_id):
    event = Event.query.get_or_404(event_id)
    registrations = EventRegistration.query.filter_by(event_id=event_id).all()
    contacts = Contact.query.order_by(Contact.last_name.asc()).all()
    return render_template('event_detail.html', event=event, registrations=registrations, contacts=contacts)


@app.route('/events/<int:event_id>/register', methods=['POST'])
@login_required
def register_event(event_id):
    event = Event.query.get_or_404(event_id)
    contact_id = request.form.get('contact_id', type=int)

    existing = EventRegistration.query.filter_by(event_id=event_id, contact_id=contact_id).first()
    if existing:
        flash('Contact already registered.', 'warning')
        return redirect(url_for('event_detail', event_id=event_id))

    reg = EventRegistration(event_id=event_id, contact_id=contact_id)
    db.session.add(reg)
    db.session.commit()
    log_activity(contact_id, f"Registered for event: {event.name}")
    flash('Contact registered for event!', 'success')
    return redirect(url_for('event_detail', event_id=event_id))


@app.route('/events/<int:event_id>/unregister', methods=['POST'])
@login_required
def unregister_event(event_id):
    contact_id = request.form.get('contact_id', type=int)
    reg = EventRegistration.query.filter_by(event_id=event_id, contact_id=contact_id).first()
    if reg:
        db.session.delete(reg)
        db.session.commit()
        flash('Registration removed.', 'success')
    return redirect(url_for('event_detail', event_id=event_id))


@app.route('/activity')
@login_required
def activity_log():
    filter_type = request.args.get('type', '')
    page = request.args.get('page', 1, type=int)

    query = ActivityLog.query
    if filter_type:
        query = query.filter_by(action=filter_type)

    logs = query.order_by(ActivityLog.created_at.desc()).paginate(page=page, per_page=50, error_out=False)
    return render_template('activity_log.html', logs=logs, filter_type=filter_type)


@app.route('/tags')
@login_required
def tags_list():
    tags = Tag.query.all()
    return render_template('tags.html', tags=tags)


@app.route('/tags/new', methods=['POST'])
@login_required
def create_tag():
    name = request.form.get('name', '').strip()
    color = request.form.get('color', 'primary')
    if not name:
        flash('Tag name is required.', 'error')
    else:
        existing = Tag.query.filter_by(name=name).first()
        if existing:
            flash(f'Tag {name} already exists.', 'warning')
        else:
            tag = Tag(name=name, color=color)
            db.session.add(tag)
            db.session.commit()
            flash(f'Tag {name} created!', 'success')
    return redirect(url_for('tags_list'))


@app.route('/contact/<int:contact_id>/tags', methods=['GET', 'POST'])
@login_required
def contact_tags(contact_id):
    contact = Contact.query.get_or_404(contact_id)
    if request.method == 'POST':
        tag_id = request.form.get('tag_id', type=int)
        existing = ContactTag.query.filter_by(contact_id=contact_id, tag_id=tag_id).first()
        if not existing:
            ct = ContactTag(contact_id=contact_id, tag_id=tag_id)
            db.session.add(ct)
            db.session.commit()
            flash('Tag added!', 'success')
        return redirect(url_for('contact_tags', contact_id=contact_id))

    all_tags = Tag.query.all()
    contact_tag_ids = [ct.tag_id for ct in ContactTag.query.filter_by(contact_id=contact_id).all()]
    return render_template('contact_tags.html', contact=contact, all_tags=all_tags, contact_tag_ids=contact_tag_ids)


@app.route('/contact/<int:contact_id>/tag/<int:tag_id>/remove', methods=['POST'])
@login_required
def remove_contact_tag(contact_id, tag_id):
    ct = ContactTag.query.filter_by(contact_id=contact_id, tag_id=tag_id).first()
    if ct:
        db.session.delete(ct)
        db.session.commit()
        flash('Tag removed.', 'success')
    return redirect(url_for('contact_tags', contact_id=contact_id))


def log_activity(contact_id, action, details=None):
    log = ActivityLog(contact_id=contact_id, user_id=current_user.id, action=action, details=details)
    db.session.add(log)
    db.session.commit()


def parse_date(date_str):
    if not date_str:
        return None
    from datetime import datetime
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except:
        return None


def parse_datetime(dt_str):
    if not dt_str:
        return None
    from datetime import datetime
    try:
        return datetime.strptime(dt_str, '%Y-%m-%dT%H:%M')
    except:
        try:
            return datetime.strptime(dt_str, '%Y-%m-%d')
        except:
            return None


@app.context_processor
def inject_categories():
    from flask_login import current_user
    return dict(categories_list=DEFAULT_CATEGORIES, current_user=current_user)

if __name__ == '__main__':
    app.run(debug=True, port=5000)