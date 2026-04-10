
# Next steps and notes
  
Search: Case-sensitive LIKE on unique_id, prefix, chassis, type; we can switch to case-insensitive if you want.
Follow-ups you might want later

Case-insensitive search and column indexes for larger inventories.
A direct “get_by_id” in the service for edit fetch instead of scanning.
CSRF protection and basic form validation (WTForms or flask-wtf).
Switch to a WSGI server like Gunicorn when you’re ready.