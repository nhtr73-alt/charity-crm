# Charity Event CRM - Specification

## 1. Project Overview
- **Project Name**: Charity CRM
- **Type**: Web-based CRM application
- **Core Functionality**: Contact management system for charity events with categorization, notes, and email integration
- **Target Users**: Charity event organizers and volunteers

## 2. Technology Stack
- **Backend**: Python/Flask
- **Database**: SQLite (simple, portable)
- **Frontend**: HTML/CSS/JavaScript (Bootstrap 5)
- **Email**: SMTP integration

## 3. Data Model

### Contact Fields
| Field | Type | Required |
|-------|------|----------|
| id | Integer | Auto |
| first_name | String(100) | Yes |
| last_name | String(100) | Yes |
| email | String(255) | Yes |
| phone | String(50) | No |
| company | String(255) | No |
| category | String(100) | Default |
| sub_category | String(100) | No |
| notes | Text | No |
| created_at | DateTime | Auto |
| updated_at | DateTime | Auto |

### Categories (Default)
- Trader
- Supplier
- Ticket Holder
- Donor
- Volunteer
- General

### Notes Table
| Field | Type |
|-------|------|
| id | Integer |
| contact_id | Integer (FK) |
| content | Text |
| created_at | DateTime |

## 4. Features

### 4.1 Contact Management
- **Add Single Contact**: Form with all fields
- **CSV Upload**: Import contacts with columns: first_name, last_name, email, phone, company, category, sub_category
- **Edit Contact**: Update any field
- **Delete Contact**: Soft delete option
- **View Contact**: Detailed view with notes history

### 4.2 Search & Filter
- Global search across name, email, company
- Filter by category
- Filter by sub_category
- Sort by name, date created

### 4.3 Notes System
- Add timestamped notes to any contact
- View note history
- Edit/delete notes

### 4.4 Category Management
- View all categories
- Add new categories
- Add sub-categories per contact

### 4.5 Email Integration
- Send single email from contact record
- Bulk email to filtered contacts
- Use SMTP configuration

## 5. UI/UX Specification

### Layout
- **Sidebar**: Navigation (Contacts, Categories, Email, Settings)
- **Main Area**: Content display
- **Header**: Search bar, user info

### Color Scheme
- **Primary**: #2E7D32 (Green - charity feel)
- **Secondary**: #1565C0 (Blue)
- **Background**: #F5F5F5
- **Cards**: #FFFFFF

### Typography
- **Font**: Inter, sans-serif
- **Headings**: Bold, #333

## 6. Acceptance Criteria

### Must Have
- [ ] Add single contact with all fields
- [ ] CSV upload works correctly
- [ ] Search returns relevant results
- [ ] Notes can be added/viewed per contact
- [ ] Categories can be filtered
- [ ] Can add custom sub-categories
- [ ] Single email send via mailto:
- [ ] Bulk email selection works
- [ ] Data persists in database

### Should Have
- [ ] Contact list pagination
- [ ] Export to CSV

### Nice to Have
- [ ] Email templates
- [ ] Activity logging

## 7. File Structure
```
charity_crm/
├── app.py              # Main Flask application
├── database.py        # Database initialization
├── models.py         # SQLAlchemy models
├── requirements.txt  # Dependencies
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── contact_form.html
│   ├── contact_detail.html
│   ├── contacts_list.html
│   ├── categories.html
│   ├── email.html
│   └── upload.html
└── static/
    └── style.css
```