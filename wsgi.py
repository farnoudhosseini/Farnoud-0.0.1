# WSGI entry point — برای gunicorn / uWSGI / aaPanel / cPanel Passenger
# استفاده:
#   gunicorn -w 1 -b 0.0.0.0:5000 wsgi:application
#   یا در Passenger: passenger_wsgi.py این فایل را import می‌کند

import os
import sys

# اطمینان از اینکه مسیر پروژه در PYTHONPATH است
BASE = os.path.dirname(os.path.abspath(__file__))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

# بارگذاری .env قبل از import اپ
from dotenv import load_dotenv
load_dotenv(os.path.join(BASE, ".env"))

from admin_app import app as application

# برای سازگاری با بعضی پنل‌ها
app = application
