

DB: SQLite file at app.db by default; tests use a temp DB per run.
Import/export: Export downloads a JSON array; Import supports overwrite (default) or merge via checkbox, matched on unique_id.
Session handling: Configured SQLAlchemy sessions to not expire on commit to avoid DetachedInstanceError when rendering templates.
Search: Case-sensitive LIKE on unique_id, prefix, chassis, type; we can switch to case-insensitive if you want.
Follow-ups you might want later

Case-insensitive search and column indexes for larger inventories.
A direct “get_by_id” in the service for edit fetch instead of scanning.
CSRF protection and basic form validation (WTForms or flask-wtf).
Switch to a WSGI server like Gunicorn when you’re ready.