# PythonAnywhere WSGI config
import sys
path = '/var/www/charity_crm'
if path not in sys.path:
    sys.path.append(path)

from app import app as application