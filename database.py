from models import db, Category

def init_db(app):
    with app.app_context():
        db.create_all()

        default_categories = ['Trader', 'Supplier', 'Ticket Holder', 'Donor', 'Volunteer', 'General']

        for cat_name in default_categories:
            existing = Category.query.filter_by(name=cat_name).first()
            if not existing:
                cat = Category(name=cat_name, is_default=True)
                db.session.add(cat)

        db.session.commit()
        print('Database initialized successfully!')