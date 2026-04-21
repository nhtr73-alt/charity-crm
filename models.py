from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date

db = SQLAlchemy()

class Contact(db.Model):
    __tablename__ = 'contacts'

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(50))
    company = db.Column(db.String(255))
    category = db.Column(db.String(100), default='General')
    sub_category = db.Column(db.String(100))
    notes = db.Column(db.Text)
    pipeline_stage = db.Column(db.String(50), default='New')
    lifecycle_stage = db.Column(db.String(50), default='Subscriber')
    engagement_score = db.Column(db.Integer, default=0)
    custom_fields = db.Column(db.Text)
    last_email_open = db.Column(db.DateTime)
    last_email_click = db.Column(db.DateTime)
    total_emails_opened = db.Column(db.Integer, default=0)
    total_emails_clicked = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    contact_notes = db.relationship('ContactNote', backref='contact', lazy='dynamic', cascade='all, delete-orphan')
    tasks = db.relationship('Task', backref='contact', lazy='dynamic', cascade='all, delete-orphan')
    donations = db.relationship('Donation', backref='contact', lazy='dynamic', cascade='all, delete-orphan')
    event_registrations = db.relationship('EventRegistration', backref='contact', lazy='dynamic', cascade='all, delete-orphan')
    activity_logs = db.relationship('ActivityLog', backref='contact', lazy='dynamic', cascade='all, delete-orphan')
    email_sends = db.relationship('EmailSendLog', backref='contact', lazy='dynamic', cascade='all, delete-orphan')
    sequences = db.relationship('ContactSequence', backref='contact', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Contact {self.first_name} {self.last_name}>'

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'


class ContactNote(db.Model):
    __tablename__ = 'contact_notes'

    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Note {self.id} for Contact {self.contact_id}>'


class Category(db.Model):
    __tablename__ = 'categories'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    is_default = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f'<Category {self.name}>'


class EmailTemplateOld(db.Model):
    __tablename__ = 'email_templates'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    subject = db.Column(db.String(255))
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50))
    is_public = db.Column(db.Boolean, default=True)
    usage_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<EmailTemplate {self.name}>'


class EmailAttachment(db.Model):
    __tablename__ = 'email_attachments'

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    filepath = db.Column(db.String(500), nullable=False)
    content_type = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<EmailAttachment {self.filename}>'


class Task(db.Model):
    __tablename__ = 'tasks'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'))
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'))
    due_date = db.Column(db.Date)
    completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)

    user = db.relationship('User', backref='tasks')

    def __repr__(self):
        return f'<Task {self.title}>'


class Donation(db.Model):
    __tablename__ = 'donations'

    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    donation_date = db.Column(db.Date, default=date.today)
    payment_method = db.Column(db.String(50))
    payment_reference = db.Column(db.String(100))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Donation ${self.amount} by {self.contact_id}>'


class Event(db.Model):
    __tablename__ = 'events'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    event_date = db.Column(db.DateTime)
    location = db.Column(db.String(255))
    event_type = db.Column(db.String(50))
    capacity = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    registrations = db.relationship('EventRegistration', backref='event', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Event {self.name}>'


class EventRegistration(db.Model):
    __tablename__ = 'event_registrations'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=False)
    registered_at = db.Column(db.DateTime, default=datetime.utcnow)
    attended = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f'<Registration {self.id}>'


class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'

    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='activity_logs')

    def __repr__(self):
        return f'<ActivityLog {self.action}>'


class Tag(db.Model):
    __tablename__ = 'tags'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    color = db.Column(db.String(20), default='primary')

    contact_tags = db.relationship('ContactTag', backref='tag', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Tag {self.name}>'


class ContactTag(db.Model):
    __tablename__ = 'contact_tags'

    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=False)
    tag_id = db.Column(db.Integer, db.ForeignKey('tags.id'), nullable=False)

    __table_args__ = (db.UniqueConstraint('contact_id', 'tag_id', name='unique_contact_tag'),)


class EmailSendLog(db.Model):
    __tablename__ = 'email_send_log'

    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'))
    subject = db.Column(db.String(255))
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    opened_at = db.Column(db.DateTime)
    clicked_at = db.Column(db.DateTime)
    bounced = db.Column(db.Boolean, default=False)
    bounced_reason = db.Column(db.String(255))
    message_id = db.Column(db.String(255))

    def __repr__(self):
        return f'<EmailSendLog {self.id}>'


class EmailSequence(db.Model):
    __tablename__ = 'email_sequences'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    trigger_type = db.Column(db.String(50))
    steps = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<EmailSequence {self.name}>'


class ContactSequence(db.Model):
    __tablename__ = 'contact_sequences'

    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=False)
    sequence_id = db.Column(db.Integer, db.ForeignKey('email_sequences.id'), nullable=False)
    current_step = db.Column(db.Integer, default=0)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    paused = db.Column(db.Boolean, default=False)

    sequence = db.relationship('EmailSequence', backref='contacts')

    def __repr__(self):
        return f'<ContactSequence {self.id}>'


class CustomField(db.Model):
    __tablename__ = 'contact_custom_fields'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    field_type = db.Column(db.String(20), default='text')
    options = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<CustomField {self.name}>'


class DuplicateGroup(db.Model):
    __tablename__ = 'duplicate_groups'

    id = db.Column(db.Integer, primary_key=True)
    canonical_contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'))
    duplicate_of = db.Column(db.Integer, db.ForeignKey('contacts.id'))
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)