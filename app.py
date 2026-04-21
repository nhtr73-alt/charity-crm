import os
import time
from html import unescape
from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import csv
import io
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from models import db, Contact, ContactNote, Category

ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'png', 'jpg', 'jpeg'}

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'charity-crm-secret-key-2024')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///charity_crm.db')
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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
    mailgun_api_key = db.Column(db.String(255))
    mailgun_domain = db.Column(db.String(255))
    mailgun_enabled = db.Column(db.Boolean, default=False)
    sendgrid_api_key = db.Column(db.String(255))
    sendgrid_enabled = db.Column(db.Boolean, default=False)
    use_shared = db.Column(db.Boolean, default=True)

class Document(db.Model):
    __tablename__ = 'documents'
    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    document_type = db.Column(db.String(100))
    file_data = db.Column(db.LargeBinary)
    content_type = db.Column(db.String(100))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'))

class ActivityLog(db.Model):
    __tablename__ = 'activity_log'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'))
    action = db.Column(db.String(100))
    details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Tag(db.Model):
    __tablename__ = 'tags'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True)
    color = db.Column(db.String(20), default='primary')

class ContactTag(db.Model):
    __tablename__ = 'contact_tags'
    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'))
    tag_id = db.Column(db.Integer, db.ForeignKey('tags.id'))

class Task(db.Model):
    __tablename__ = 'tasks'
    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    title = db.Column(db.String(255))
    due_date = db.Column(db.Date)
    completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class EmailTemplate(db.Model):
    __tablename__ = 'email_templates'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    name = db.Column(db.String(255))
    subject = db.Column(db.String(255))
    body = db.Column(db.Text)

class DeletedContact(db.Model):
    __tablename__ = 'deleted_contacts'
    id = db.Column(db.Integer, primary_key=True)
    original_id = db.Column(db.Integer)
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    email = db.Column(db.String(255))
    phone = db.Column(db.String(50))
    company = db.Column(db.String(255))
    category = db.Column(db.String(100))
    sub_category = db.Column(db.String(100))
    notes = db.Column(db.Text)
    deleted_at = db.Column(db.DateTime, default=datetime.utcnow)
    deleted_by = db.Column(db.Integer, db.ForeignKey('users.id'))

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

    recent_contacts = Contact.query.order_by(Contact.created_at.desc()).limit(5).all()
    recent_activities = ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(10).all()

    my_tasks = Task.query.filter_by(user_id=current_user.id, completed=False).order_by(Task.due_date.asc()).limit(5).all()
    overdue_tasks = Task.query.filter(Task.due_date < datetime.utcnow().date(), Task.completed == False).count()

    return render_template('index.html', total_contacts=total_contacts, category_counts=category_counts,
                         recent_contacts=recent_contacts, recent_activities=recent_activities,
                         my_tasks=my_tasks, overdue_tasks=overdue_tasks)

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

        files = request.files.getlist('documents')
        for file in files:
            if file.filename and allowed_file(file.filename):
                doc = Document(
                    contact_id=contact.id,
                    original_filename=file.filename,
                    document_type=request.form.get('document_type', 'Other'),
                    file_data=file.read(),
                    content_type=file.content_type,
                    uploaded_by=current_user.id
                )
                db.session.add(doc)

        if files and files[0].filename:
            db.session.commit()
            flash('Contact added with documents!', 'success')
        else:
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

        files = request.files.getlist('documents')
        for file in files:
            if file.filename and allowed_file(file.filename):
                doc = Document(
                    contact_id=contact.id,
                    original_filename=file.filename,
                    document_type=request.form.get('document_type', 'Other'),
                    file_data=file.read(),
                    content_type=file.content_type,
                    uploaded_by=current_user.id
                )
                db.session.add(doc)

        db.session.commit()
        flash('Contact updated successfully!', 'success')
        return redirect(url_for('contact_detail', contact_id=contact.id))

    return render_template('contact_form.html', categories=DEFAULT_CATEGORIES, sub_categories=sub_categories, contact=contact)

@app.route('/contact/<int:contact_id>/delete', methods=['POST'])
@login_required
def contact_delete(contact_id):
    contact = Contact.query.get_or_404(contact_id)
    deleted = DeletedContact(
        original_id=contact.id,
        first_name=contact.first_name,
        last_name=contact.last_name,
        email=contact.email,
        phone=contact.phone,
        company=contact.company,
        category=contact.category,
        sub_category=contact.sub_category,
        notes=contact.notes,
        deleted_by=current_user.id
    )
    db.session.add(deleted)
    db.session.delete(contact)
    db.session.commit()
    flash('Contact moved to recycle bin!', 'success')
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

@app.route('/email-compose', methods=['GET', 'POST'])
@login_required
def email_compose():
    contacts = Contact.query.all()
    templates = EmailTemplate.query.all()
    templates_json = [{'id': t.id, 'name': t.name, 'subject': t.subject, 'body': t.body} for t in templates]

    if request.method == 'POST':
        recipient_ids = request.form.getlist('recipients')
        recipients = Contact.query.filter(Contact.id.in_(recipient_ids)).all()
        subject = request.form.get('subject', '').strip()
        body = request.form.get('body', '').strip()
        use_smtp = request.form.get('use_smtp') == 'send'

        if not recipients:
            flash('No recipients selected.', 'error')
            return render_template('email_compose.html', contacts=contacts, templates=templates, templates_json=templates_json)

        if not subject or not body:
            flash('Subject and message are required.', 'error')
            return render_template('email_compose.html', contacts=contacts, templates=templates, templates_json=templates_json)

        if use_smtp:
            success_count = 0
            error_count = 0
            for recipient in recipients:
                personalized_body = body
                personalized_body = personalized_body.replace('{first_name}', recipient.first_name or '')
                personalized_body = personalized_body.replace('{last_name}', recipient.last_name or '')
                personalized_body = personalized_body.replace('{email}', recipient.email or '')
                personalized_body = personalized_body.replace('{company}', recipient.company or '')

                personalized_body = unescape(personalized_body)

                ok, msg = send_smtp_email(recipient.email, subject, personalized_body, current_user.id)
                if ok:
                    success_count += 1
                else:
                    error_count += 1
                time.sleep(1)

            flash(f'Sent: {success_count}, Failed: {error_count}', 'success')
        else:
            emails = [r.email for r in recipients]
            session['bulk_emails'] = emails
            session['email_subject'] = subject
            session['email_body'] = body
            flash(f'{len(emails)} ready in email client.', 'success')

        return redirect(url_for('email_compose'))

    return render_template('email_compose.html', contacts=contacts, templates=templates, templates_json=templates_json)

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

    use_smtp = request.form.get('use_smtp') == 'send'

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

        if use_smtp:
            total = len(recipients)
            limit_warning = ""
            if total > 100:
                limit_warning = f"Warning: ISP limits! {total} > 100. Consider Mailgun/SendGrid. Sending first 100... "
                recipients = recipients[:100]

            success_count = 0
            error_count = 0
            import time
            for i, recipient in enumerate(recipients):
                ok, msg = send_smtp_email(recipient.email, subject, body, current_user.id)
                if ok:
                    success_count += 1
                else:
                    error_count += 1
                if i < len(recipients) - 1:
                    time.sleep(1)

            flash(limit_warning + f'Emails sent: {success_count}, Failed: {error_count}', 'success' if not limit_warning else 'warning')
        else:
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
        use_smtp = request.form.get('use_smtp') == 'send'

        if not subject or not body:
            flash('Subject and body are required.', 'error')
            return render_template('email_single.html', contact=contact)

        if use_smtp:
            ok, msg = send_smtp_email(contact.email, subject, body, current_user.id)
            if ok:
                flash(f'Email sent to {contact.email}!', 'success')
            else:
                flash(f'Failed to send: {msg}', 'error')
        else:
            session['single_email'] = contact.email
            session['email_subject'] = subject
            session['email_body'] = body
            flash(f'Email prepared for {contact.email}. Use mailto: link to send.', 'success')

        return redirect(url_for('contact_detail', contact_id=contact_id))

    return render_template('email_single.html', contact=contact)

def get_unique_sub_categories():
    sub_categories = set()
    contacts = Contact.query.all()
    for contact in contacts:
        if contact.sub_category:
            sub_categories.add(contact.sub_category)
    return sorted(list(sub_categories))

def log_activity(contact_id, action, details=''):
    if hasattr(current_user, 'id'):
        log = ActivityLog(user_id=current_user.id, contact_id=contact_id, action=action, details=details)
        db.session.add(log)
        db.session.commit()

@app.route('/activity')
@login_required
def activity_log():
    logs = ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(100).all()
    return render_template('activity_log.html', logs=logs)

@app.route('/recycle-bin')
@login_required
def recycle_bin():
    deleted = DeletedContact.query.order_by(DeletedContact.deleted_at.desc()).all()
    return render_template('recycle_bin.html', deleted=deleted)

@app.route('/recycle-bin/<int:id>/restore', methods=['POST'])
@login_required
def restore_contact(id):
    deleted = DeletedContact.query.get_or_404(id)
    contact = Contact(
        first_name=deleted.first_name,
        last_name=deleted.last_name,
        email=deleted.email,
        phone=deleted.phone,
        company=deleted.company,
        category=deleted.category,
        sub_category=deleted.sub_category,
        notes=deleted.notes
    )
    db.session.add(contact)
    db.session.delete(deleted)
    db.session.commit()
    flash('Contact restored!', 'success')
    return redirect(url_for('contacts_list'))

@app.route('/tags', methods=['GET', 'POST'])
@login_required
def manage_tags():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        color = request.form.get('color', 'primary')
        if name:
            existing = Tag.query.filter_by(name=name).first()
            if not existing:
                tag = Tag(name=name, color=color)
                db.session.add(tag)
                db.session.commit()
                flash('Tag created!', 'success')
            else:
                flash('Tag already exists.', 'error')
        return redirect(url_for('manage_tags'))

    tags = Tag.query.all()
    return render_template('tags.html', tags=tags)

@app.route('/contact/<int:contact_id>/tags', methods=['GET', 'POST'])
@login_required
def contact_tags(contact_id):
    contact = Contact.query.get_or_404(contact_id)
    all_tags = Tag.query.all()

    if request.method == 'POST':
        selected_tags = request.form.getlist('tags')
        ContactTag.query.filter_by(contact_id=contact_id).delete()
        for tag_id in selected_tags:
            ct = ContactTag(contact_id=contact_id, tag_id=tag_id)
            db.session.add(ct)
        db.session.commit()
        flash('Tags updated!', 'success')
        return redirect(url_for('contact_detail', contact_id=contact_id))

    contact_tags = [ct.tag_id for ct in ContactTag.query.filter_by(contact_id=contact_id).all()]
    return render_template('contact_tags.html', contact=contact, all_tags=all_tags, contact_tags=contact_tags)

@app.route('/contact/<int:contact_id>/tasks', methods=['GET', 'POST'])
@login_required
def contact_tasks(contact_id):
    contact = Contact.query.get_or_404(contact_id)

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        due_date = request.form.get('due_date')
        if title:
            task = Task(contact_id=contact_id, user_id=current_user.id, title=title, due_date=datetime.strptime(due_date, '%Y-%m-%d') if due_date else None)
            db.session.add(task)
            db.session.commit()
            flash('Task added!', 'success')
        return redirect(url_for('contact_tasks', contact_id=contact_id))

    tasks = Task.query.filter_by(contact_id=contact_id).order_by(Task.due_date.asc()).all()
    return render_template('contact_tasks.html', contact=contact, tasks=tasks)

@app.route('/task/<int:task_id>/toggle', methods=['POST'])
@login_required
def toggle_task(task_id):
    task = Task.query.get_or_404(task_id)
    task.completed = not task.completed
    db.session.commit()
    return redirect(url_for('contact_tasks', contact_id=task.contact_id))

@app.route('/task/<int:task_id>/delete', methods=['POST'])
@login_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    contact_id = task.contact_id
    db.session.delete(task)
    db.session.commit()
    flash('Task deleted.', 'success')
    return redirect(url_for('contact_tasks', contact_id=contact_id))

@app.route('/email-templates', methods=['GET', 'POST'])
@login_required
def email_templates():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        subject = request.form.get('subject', '').strip()
        body = request.form.get('body', '').strip()
        if name:
            template = EmailTemplate(user_id=current_user.id, name=name, subject=subject, body=body)
            db.session.add(template)
            db.session.commit()
            flash('Template saved!', 'success')
        return redirect(url_for('email_templates'))

    templates = EmailTemplate.query.filter_by(user_id=current_user.id).all()
    return render_template('email_templates.html', templates=templates)

@app.route('/email-templates/<int:id>/use')
@login_required
def use_template(id):
    template = EmailTemplate.query.get_or_404(id)
    session['email_subject'] = template.subject
    session['email_body'] = template.body
    flash(f'Template "{template.name}" loaded. Go to Email to select recipients.', 'success')
    return redirect(url_for('email_page'))

@app.route('/email-templates/<int:id>/delete', methods=['POST'])
@login_required
def delete_template(id):
    template = EmailTemplate.query.get_or_404(id)
    db.session.delete(template)
    db.session.commit()
    flash('Template deleted.', 'success')
    return redirect(url_for('email_templates'))

@app.route('/pipeline')
@login_required
def pipeline():
    contacts = Contact.query.all()
    stages = {
        'New': [],
        'Contacted': [],
        'In Progress': [],
        'Completed': [],
        'Lost': []
    }
    for c in contacts:
        stage = getattr(c, 'pipeline_stage', None) or 'New'
        if stage in stages:
            stages[stage].append(c)
    return render_template('pipeline.html', stages=stages)

@app.route('/contact/<int:contact_id>/set_stage', methods=['POST'])
@login_required
def set_pipeline_stage(contact_id):
    stage = request.form.get('stage')
    contact = Contact.query.get_or_404(contact_id)
    contact.pipeline_stage = stage
    db.session.commit()
    flash(f'Moved to {stage}', 'success')
    return redirect(url_for('pipeline'))

@app.route('/quick-add', methods=['POST'])
@login_required
def quick_add():
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    category = request.form.get('category', 'General')

    if not first_name or not last_name or not email:
        flash('Name and email required.', 'error')
        return redirect(url_for('index'))

    existing = Contact.query.filter_by(email=email).first()
    if existing:
        flash('Contact already exists.', 'error')
        return redirect(url_for('index'))

    contact = Contact(first_name=first_name, last_name=last_name, email=email, phone=phone, category=category)
    db.session.add(contact)
    db.session.commit()
    log_activity(contact.id, 'Created', f'Quick add by {current_user.username}')
    flash('Contact added!', 'success')
    return redirect(url_for('index'))

@app.route('/merge-duplicates')
@login_required
def merge_duplicates():
    emails = db.session.query(Contact.email).filter(Contact.email != '').group_by(Contact.email).having(db.func.count(Contact.id) > 1).all()
    duplicates = []
    for (email,) in emails:
        contacts = Contact.query.filter_by(email=email).all()
        duplicates.append(contacts)
    return render_template('merge_duplicates.html', duplicates=duplicates)

@app.route('/contact/<int:id>/merge_into/<int:target_id>', methods=['POST'])
@login_required
def merge_contacts(id, target_id):
    source = Contact.query.get_or_404(id)
    target = Contact.query.get_or_404(target_id)

    if source.phone and not target.phone:
        target.phone = source.phone
    if source.company and not target.company:
        target.company = source.company
    if source.notes and not target.notes:
        target.notes = source.notes
    elif source.notes and target.notes:
        target.notes = f"{target.notes}\n\n-- Merged from {source.full_name} --\n{source.notes}"

    docs = Document.query.filter_by(contact_id=id).all()
    for doc in docs:
        doc.contact_id = target_id

    notes = ContactNote.query.filter_by(contact_id=id).all()
    for note in notes:
        note.contact_id = target_id

    db.session.delete(source)
    db.session.commit()
    flash(f'Merged into {target.full_name}', 'success')
    return redirect(url_for('contacts_list'))

@app.route('/contact/bulk-delete', methods=['POST'])
@login_required
def bulk_delete():
    ids = request.form.getlist('contact_ids')
    if not ids:
        flash('No contacts selected.', 'error')
        return redirect(url_for('contacts_list'))

    for cid in ids:
        contact = Contact.query.get(int(cid))
        if contact:
            deleted = DeletedContact(
                original_id=contact.id,
                first_name=contact.first_name,
                last_name=contact.last_name,
                email=contact.email,
                phone=contact.phone,
                company=contact.company,
                category=contact.category,
                sub_category=contact.sub_category,
                notes=contact.notes,
                deleted_by=current_user.id
            )
            db.session.add(deleted)
            db.session.delete(contact)

    db.session.commit()
    flash(f'{len(ids)} contacts moved to recycle bin.', 'success')
    return redirect(url_for('contacts_list'))

@app.route('/my-tasks')
@login_required
def my_tasks():
    tasks = Task.query.filter_by(user_id=current_user.id, completed=False).order_by(Task.due_date.asc()).all()
    return render_template('my_tasks.html', tasks=tasks)

def send_smtp_email(recipient_email, subject, body, user_id):
    user_settings = SMTPSettings.query.filter_by(user_id=user_id).first()

    admin_settings = None
    if current_user.is_admin:
        admin_settings = user_settings
    else:
        admin_user = User.query.filter_by(is_admin=True).first()
        if admin_user:
            admin_settings = SMTPSettings.query.filter_by(user_id=admin_user.id).first()

    settings = user_settings or admin_settings

    if not settings:
        return False, "SMTP not configured. Ask admin to set up email in Settings."

    if settings.sendgrid_enabled and settings.sendgrid_api_key:
        return send_sendgrid_email(recipient_email, subject, body, settings)

    if settings.mailgun_enabled and settings.mailgun_api_key and settings.mailgun_domain:
        return send_mailgun_email(recipient_email, subject, body, settings)

    if not settings.smtp_server:
        return False, "SMTP not configured. Ask admin to set up email in Settings."

    try:
        from_email = settings.smtp_from_email or settings.smtp_username

        user_settings = SMTPSettings.query.filter_by(user_id=user_id).first()
        if user_settings and user_settings.smtp_from_email and not user_settings.use_shared:
            from_email = user_settings.smtp_from_email

        msg = MIMEMultipart()
        msg['From'] = from_email
        msg['To'] = recipient_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(settings.smtp_server, settings.smtp_port)
        if settings.use_tls:
            server.starttls()
        server.login(settings.smtp_username, settings.smtp_password)
        server.sendmail(from_email, recipient_email, msg.as_string())
        server.quit()
        return True, "Sent"
    except Exception as e:
        return False, str(e)

def send_mailgun_email(recipient_email, subject, body, settings):
    import requests
    try:
        response = requests.post(
            f"https://api.mailgun.net/v3/{settings.mailgun_domain}/messages",
            auth=("api", settings.mailgun_api_key),
            data={
                "from": f"{settings.smtp_from_email or 'True Butterflies Foundation'} <noreply@{settings.mailgun_domain}>",
                "to": recipient_email,
                "subject": subject,
                "text": body
            }
        )
        if response.status_code == 200:
            return True, "Sent via Mailgun"
        else:
            return False, f"Mailgun error: {response.text}"
    except Exception as e:
        return False, str(e)

def send_sendgrid_email(recipient_email, subject, body, settings):
    import requests
    try:
        response = requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={
                "Authorization": f"Bearer {settings.sendgrid_api_key}",
                "Content-Type": "application/json"
            },
            json={
                "personalizations": [{"to": [{"email": recipient_email}]}],
                "from": {"email": settings.smtp_from_email or settings.smtp_username},
                "subject": subject,
                "content": [{"type": "text/plain", "value": body}]
            }
        )
        if response.status_code in [200, 202]:
            return True, "Sent via SendGrid"
        else:
            return False, f"SendGrid error: {response.status_code}"
    except Exception as e:
        return False, str(e)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/contact/<int:contact_id>/documents', methods=['GET', 'POST'])
@login_required
def contact_documents(contact_id):
    contact = Contact.query.get_or_404(contact_id)

    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected.', 'error')
            return redirect(url_for('contact_documents', contact_id=contact_id))

        file = request.files['file']
        doc_type = request.form.get('document_type', '').strip()

        if file.filename == '':
            flash('No file selected.', 'error')
            return redirect(url_for('contact_documents', contact_id=contact_id))

        if file and allowed_file(file.filename):
            file_data = file.read()
            doc = Document(
                contact_id=contact_id,
                original_filename=file.filename,
                document_type=doc_type,
                file_data=file_data,
                content_type=file.content_type,
                uploaded_by=current_user.id
            )
            db.session.add(doc)
            db.session.commit()
            flash('Document uploaded!', 'success')
        else:
            flash('Invalid file type. Allowed: PDF, DOC, DOCX, XLS, XLSX, PNG, JPG', 'error')

        return redirect(url_for('contact_documents', contact_id=contact_id))

    documents = Document.query.filter_by(contact_id=contact_id).order_by(Document.uploaded_at.desc()).all()
    return render_template('contact_documents.html', contact=contact, documents=documents)

@app.route('/contact/<int:contact_id>/document/<int:doc_id>/delete', methods=['POST'])
@login_required
def delete_document(contact_id, doc_id):
    doc = Document.query.get_or_404(doc_id)
    if doc.contact_id != contact_id:
        flash('Document not found.', 'error')
        return redirect(url_for('contacts_list'))

    db.session.delete(doc)
    db.session.commit()
    flash('Document deleted.', 'success')
    return redirect(url_for('contact_documents', contact_id=contact_id))

@app.route('/document/<int:doc_id>/download')
@login_required
def download_file(doc_id):
    doc = Document.query.get_or_404(doc_id)
    from flask import make_response
    response = make_response(doc.file_data)
    response.headers['Content-Type'] = doc.content_type or 'application/octet-stream'
    response.headers['Content-Disposition'] = f'attachment; filename={doc.original_filename}'
    return response

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
        smtp.use_shared = 'use_shared' in request.form
        db.session.commit()
        flash('SMTP settings saved!', 'success')
        return redirect(url_for('settings'))

    return render_template('settings.html', smtp=smtp)

@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        user = User.query.get(current_user.id)

        if not check_password_hash(user.password_hash, current_password):
            flash('Current password is incorrect.', 'error')
        elif new_password != confirm_password:
            flash('New passwords do not match.', 'error')
        elif len(new_password) < 4:
            flash('Password must be at least 4 characters.', 'error')
        else:
            user.password_hash = generate_password_hash(new_password)
            db.session.commit()
            flash('Password changed successfully!', 'success')
            return redirect(url_for('index'))

    return render_template('change_password.html')

@app.context_processor
def inject_categories():
    from flask_login import current_user
    return dict(categories_list=DEFAULT_CATEGORIES, current_user=current_user)

if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    app.run(debug=True, port=5000)