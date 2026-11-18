import os

class Config:
    """Central configuration class for the Airline Luggage Tracking System."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'nsuk-csc-2026-luggage-tracking-secret-key')

    # MySQL Database Configuration (Update password if your MySQL root user has one)
    MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
    MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '')
    MYSQL_DATABASE = os.environ.get('MYSQL_DATABASE', 'airline_luggage_db')
    MYSQL_PORT = int(os.environ.get('MYSQL_PORT', 3306))

    # Directory where generated QR code PNG files are saved
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    QR_FOLDER = os.path.join(BASE_DIR, 'static', 'qrcodes')

    # Valid luggage statuses in sequential airline workflow order
    VALID_STATUSES = [
        'Registered',
        'Checked In',
        'At Security Screening',
        'Loaded onto Aircraft',
        'In Transit',
        'Arrived at Destination Airport',
        'Ready for Collection',
        'Delivered'
    ]