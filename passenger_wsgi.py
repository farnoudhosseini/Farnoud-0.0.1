# cPanel / CloudLinux Passenger entry point
# در Setup Python App مسیر Application startup file را روی این فایل بگذارید.

import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from dotenv import load_dotenv
load_dotenv(os.path.join(BASE, ".env"))

from admin_app import app as application
