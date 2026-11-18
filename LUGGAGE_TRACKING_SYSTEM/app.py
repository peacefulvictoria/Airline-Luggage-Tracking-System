import os
import random
import string
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, send_from_directory, jsonify
)
from werkzeug.security import generate_password_hash, check_password_hash
import qrcode

from config import Config
from database import execute_query, get_db_connection

app = Flask(__name__)
app.config.from_object(Config)

# Ensure QR code storage directory exists
os.makedirs(app.config['QR_FOLDER'], exist_ok=True)


# ============================================================================
# HELPER FUNCTIONS & ACCESS CONTROL DECORATORS
# ============================================================================

def generate_tracking_code():
    """Generates a unique, non-sensitive luggage reference ID (e.g., TRK-2026-48291)."""
    year = datetime.now().year
    while True:
        digits = ''.join(random.choices(string.digits, k=5))
        letters = ''.join(random.choices(string.ascii_uppercase, k=2))
        code = f"TRK-{year}-{digits}{letters}"
        existing = execute_query(
            "SELECT Luggage_ID FROM Luggage WHERE Tracking_Code = %s",
            (code,),
            fetch_one=True
        )
        if not existing:
            return code


def create_qr_image(tracking_code):
    """
    Generates a high-error-correction QR code PNG containing ONLY the tracking_code.
    Sensitive passenger data (name, phone, email) is never exposed in the QR payload.
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # 30% damage tolerance
        box_size=10,
        border=4,
    )
    qr.add_data(tracking_code)
    qr.make(fit=True)

    img = qr.make_image(fill_color="#0a2540", back_color="white")
    filename = f"{tracking_code}.png"
    filepath = os.path.join(app.config['QR_FOLDER'], filename)
    img.save(filepath)
    return filename


def login_required(f):
    """Ensures a user is logged into an active session."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access that page.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def role_required(*allowed_roles):
    """Restricts route access strictly to authorized roles ('Admin' or 'Staff')."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash("Authentication required.", "warning")
                return redirect(url_for('login'))
            if session.get('role') not in allowed_roles:
                flash("Unauthorized access: You do not have permission to view this resource.", "danger")
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def bootstrap_demo_accounts():
    """
    Ensures default demo accounts exist with valid password hashes and sample luggage
    has generated QR images on disk for smooth project demonstration.
    """
    conn = get_db_connection()
    if not conn:
        return
    conn.close()

    default_hash = generate_password_hash("password123")
    demo_users = [
        ("admin", "admin@skytrackair.com", default_hash, "Admin"),
        ("staff_abv", "staff.abv@skytrackair.com", default_hash, "Staff")
    ]
    for username, email, pwd_hash, role in demo_users:
        user = execute_query("SELECT User_ID FROM Users WHERE Username = %s", (username,), fetch_one=True)
        if not user:
            execute_query(
                "INSERT INTO Users (Username, Email, Password, Role) VALUES (%s, %s, %s, %s)",
                (username, email, pwd_hash, role),
                commit=True
            )
        else:
            execute_query(
                "UPDATE Users SET Password = %s WHERE Username = %s",
                (pwd_hash, username),
                commit=True
            )

    # Seed one demo luggage item if Luggage table is empty
    count_row = execute_query("SELECT COUNT(*) AS total FROM Luggage", fetch_one=True)
    if count_row and count_row['total'] == 0:
        passenger = execute_query("SELECT Passenger_ID FROM Passengers LIMIT 1", fetch_one=True)
        if passenger:
            code = "TRK-2026-10001NG"
            qr_file = create_qr_image(code)
            luggage_id = execute_query(
                """INSERT INTO Luggage (Passenger_ID, Tracking_Code, QR_Code, Weight, Destination, Status)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (passenger['Passenger_ID'], code, qr_file, 23.50, "Lagos (LOS) - Murtala Muhammed Intl", "Checked In"),
                commit=True
            )
            execute_query(
                """INSERT INTO Tracking (Luggage_ID, Location, Scan_Time, Status, Updated_By)
                   VALUES (%s, %s, %s, %s, %s)""",
                (luggage_id, "Abuja (ABV) - Check-in Counter 04", datetime.now(), "Checked In", "staff_abv"),
                commit=True
            )


# ============================================================================
# PUBLIC & PASSENGER ROUTES
# ============================================================================

@app.route('/')
def index():
    """Home page featuring quick passenger luggage search and role portals."""
    return render_template('index.html')


@app.route('/track', methods=['GET', 'POST'])
def track_luggage():
    """Public passenger tracking page to view status and chronological checkpoint history."""
    tracking_code = request.args.get('code', '').strip().upper()
    if request.method == 'POST':
        tracking_code = request.form.get('tracking_code', '').strip().upper()

    luggage = None
    history = []

    if tracking_code:
        luggage = execute_query(
            """SELECT l.*, p.Full_Name, p.Phone_Number, p.Email
               FROM Luggage l
               JOIN Passengers p ON l.Passenger_ID = p.Passenger_ID
               WHERE l.Tracking_Code = %s OR CAST(l.Luggage_ID AS CHAR) = %s""",
            (tracking_code, tracking_code),
            fetch_one=True
        )
        if luggage:
            history = execute_query(
                """SELECT Tracking_ID, Location, Scan_Time, Status, Updated_By
                   FROM Tracking
                   WHERE Luggage_ID = %s
                   ORDER BY Scan_Time ASC, Tracking_ID ASC""",
                (luggage['Luggage_ID'],),
                fetch_all=True
            )
        else:
            flash(f"No luggage record found matching reference '{tracking_code}'. Please verify your tag ID.", "danger")

    return render_template(
        'track.html',
        luggage=luggage,
        history=history,
        searched_code=tracking_code,
        statuses=app.config['VALID_STATUSES']
    )


# ============================================================================
# AUTHENTICATION ROUTES
# ============================================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles secure login for System Administrators and Airline Staff."""
    if 'user_id' in session:
        return redirect(url_for('admin_dashboard' if session.get('role') == 'Admin' else 'staff_dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash("Both username and password are required.", "danger")
            return render_template('login.html')

        user = execute_query(
            "SELECT * FROM Users WHERE Username = %s",
            (username,),
            fetch_one=True
        )

        if user and check_password_hash(user['Password'], password):
            session.clear()
            session['user_id'] = user['User_ID']
            session['username'] = user['Username']
            session['role'] = user['Role']
            flash(f"Welcome back, {user['Username']} ({user['Role']})!", "success")

            if user['Role'] == 'Admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('staff_dashboard'))
        else:
            flash("Invalid username or password. Please try again.", "danger")

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    """Clears the active session and logs out the user."""
    session.clear()
    flash("You have been securely logged out.", "info")
    return redirect(url_for('login'))


# ============================================================================
# SYSTEM ADMINISTRATOR ROUTES
# ============================================================================

@app.route('/admin/dashboard')
@role_required('Admin')
def admin_dashboard():
    """Displays executive KPI cards, system-wide luggage records, and recent tracking scans."""
    stats = {
        'total_passengers': execute_query("SELECT COUNT(*) AS c FROM Passengers", fetch_one=True)['c'],
        'total_luggage': execute_query("SELECT COUNT(*) AS c FROM Luggage", fetch_one=True)['c'],
        'registered_staff': execute_query("SELECT COUNT(*) AS c FROM Users WHERE Role = 'Staff'", fetch_one=True)['c'],
        'delivered_luggage': execute_query("SELECT COUNT(*) AS c FROM Luggage WHERE Status = 'Delivered'", fetch_one=True)['c'],
        'pending_luggage': execute_query("SELECT COUNT(*) AS c FROM Luggage WHERE Status != 'Delivered'", fetch_one=True)['c'],
    }

    all_luggage = execute_query(
        """SELECT l.*, p.Full_Name, p.Phone_Number
           FROM Luggage l
           JOIN Passengers p ON l.Passenger_ID = p.Passenger_ID
           ORDER BY l.Created_At DESC""",
        fetch_all=True
    )

    recent_tracking = execute_query(
        """SELECT t.*, l.Tracking_Code, l.Destination, p.Full_Name
           FROM Tracking t
           JOIN Luggage l ON t.Luggage_ID = l.Luggage_ID
           JOIN Passengers p ON l.Passenger_ID = p.Passenger_ID
           ORDER BY t.Scan_Time DESC, t.Tracking_ID DESC
           LIMIT 15""",
        fetch_all=True
    )

    passengers = execute_query("SELECT * FROM Passengers ORDER BY Created_At DESC", fetch_all=True)

    return render_template(
        'admin_dashboard.html',
        stats=stats,
        all_luggage=all_luggage,
        recent_tracking=recent_tracking,
        passengers=passengers
    )


@app.route('/admin/users', methods=['GET', 'POST'])
@role_required('Admin')
def manage_users():
    """Allows Administrators to view, create, and remove Airline Staff and Admin accounts."""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        role = request.form.get('role', 'Staff')

        if not username or not email or not password or role not in ('Admin', 'Staff'):
            flash("All fields are required and role must be Admin or Staff.", "danger")
        elif len(password) < 6:
            flash("Password must be at least 6 characters long.", "danger")
        else:
            existing = execute_query(
                "SELECT User_ID FROM Users WHERE Username = %s OR Email = %s",
                (username, email),
                fetch_one=True
            )
            if existing:
                flash("Username or email already exists in the system.", "danger")
            else:
                hashed_pw = generate_password_hash(password)
                execute_query(
                    "INSERT INTO Users (Username, Email, Password, Role) VALUES (%s, %s, %s, %s)",
                    (username, email, hashed_pw, role),
                    commit=True
                )
                flash(f"User '{username}' ({role}) created successfully.", "success")
                return redirect(url_for('manage_users'))

    users = execute_query("SELECT User_ID, Username, Email, Role, Created_At FROM Users ORDER BY User_ID ASC", fetch_all=True)
    return render_template('manage_users.html', users=users)


@app.route('/admin/users/delete/<int:user_id>', methods=['POST'])
@role_required('Admin')
def delete_user(user_id):
    """Deletes a user account while preventing an administrator from deleting themselves."""
    if user_id == session.get('user_id'):
        flash("You cannot delete your own active administrator account.", "danger")
        return redirect(url_for('manage_users'))

    execute_query("DELETE FROM Users WHERE User_ID = %s", (user_id,), commit=True)
    flash("User account removed.", "info")
    return redirect(url_for('manage_users'))


@app.route('/admin/reports')
@role_required('Admin')
def reports():
    """Generates summary analytical reports grouped by luggage status and destination."""
    status_breakdown = execute_query(
        """SELECT Status, COUNT(*) AS Count
           FROM Luggage
           GROUP BY Status
           ORDER BY Count DESC""",
        fetch_all=True
    )

    destination_breakdown = execute_query(
        """SELECT Destination, COUNT(*) AS Total_Bags,
                  SUM(CASE WHEN Status = 'Delivered' THEN 1 ELSE 0 END) AS Delivered_Count
           FROM Luggage
           GROUP BY Destination
           ORDER BY Total_Bags DESC""",
        fetch_all=True
    )

    detailed_records = execute_query(
        """SELECT l.Tracking_Code, p.Full_Name, p.Phone_Number, l.Weight,
                  l.Destination, l.Status, l.Created_At
           FROM Luggage l
           JOIN Passengers p ON l.Passenger_ID = p.Passenger_ID
           ORDER BY l.Created_At DESC""",
        fetch_all=True
    )

    return render_template(
        'reports.html',
        status_breakdown=status_breakdown,
        destination_breakdown=destination_breakdown,
        detailed_records=detailed_records,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )


# ============================================================================
# AIRLINE STAFF ROUTES (AND SHARED OPERATIONAL ACCESS FOR ADMIN)
# ============================================================================

@app.route('/staff/dashboard')
@role_required('Staff', 'Admin')
def staff_dashboard():
    """Airline Staff workspace showing registered luggage items, search, and quick actions."""
    luggage_list = execute_query(
        """SELECT l.*, p.Full_Name, p.Phone_Number, p.Email
           FROM Luggage l
           JOIN Passengers p ON l.Passenger_ID = p.Passenger_ID
           ORDER BY l.Created_At DESC""",
        fetch_all=True
    )
    passenger_count = execute_query("SELECT COUNT(*) AS c FROM Passengers", fetch_one=True)['c']
    in_transit_count = execute_query(
        "SELECT COUNT(*) AS c FROM Luggage WHERE Status != 'Delivered'", fetch_one=True
    )['c']
    delivered_count = execute_query(
        "SELECT COUNT(*) AS c FROM Luggage WHERE Status = 'Delivered'", fetch_one=True
    )['c']

    return render_template(
        'staff_dashboard.html',
        luggage_list=luggage_list,
        passenger_count=passenger_count,
        in_transit_count=in_transit_count,
        delivered_count=delivered_count
    )


@app.route('/staff/register-passenger', methods=['GET', 'POST'])
@role_required('Staff', 'Admin')
def register_passenger():
    """Registers a new airline passenger into the Passengers table."""
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        phone_number = request.form.get('phone_number', '').strip()
        email = request.form.get('email', '').strip()

        if not full_name or not phone_number or not email:
            flash("All passenger fields (Full Name, Phone Number, Email) are required.", "danger")
        else:
            passenger_id = execute_query(
                "INSERT INTO Passengers (Full_Name, Phone_Number, Email) VALUES (%s, %s, %s)",
                (full_name, phone_number, email),
                commit=True
            )
            flash(f"Passenger '{full_name}' registered (ID: {passenger_id}). You can now register their luggage.", "success")
            return redirect(url_for('register_luggage', passenger_id=passenger_id))

    passengers = execute_query("SELECT * FROM Passengers ORDER BY Passenger_ID DESC LIMIT 10", fetch_all=True)
    return render_template('register_passenger.html', passengers=passengers)


@app.route('/staff/register-luggage', methods=['GET', 'POST'])
@role_required('Staff', 'Admin')
def register_luggage():
    """
    Registers a passenger's luggage item, generates a unique QR code image,
    and inserts the initial 'Registered' checkpoint event into the Tracking table.
    """
    selected_passenger_id = request.args.get('passenger_id', type=int)
    passengers = execute_query("SELECT Passenger_ID, Full_Name, Phone_Number FROM Passengers ORDER BY Full_Name ASC", fetch_all=True)

    if request.method == 'POST':
        passenger_id = request.form.get('passenger_id', type=int)
        destination = request.form.get('destination', '').strip()
        origin_checkpoint = request.form.get('origin_checkpoint', '').strip()
        weight = request.form.get('weight', '0').strip()

        if not passenger_id or not destination or not origin_checkpoint:
            flash("Passenger, Destination, and Initial Check-In Location are required.", "danger")
        else:
            try:
                weight_val = float(weight) if weight else 0.0
                if weight_val < 0 or weight_val > 100:
                    raise ValueError("Invalid weight")
            except ValueError:
                flash("Please enter a valid luggage weight between 0 and 100 kg.", "danger")
                return render_template('register_luggage.html', passengers=passengers, selected_passenger_id=passenger_id)

            tracking_code = generate_tracking_code()
            qr_filename = create_qr_image(tracking_code)
            initial_status = 'Registered'

            luggage_id = execute_query(
                """INSERT INTO Luggage (Passenger_ID, Tracking_Code, QR_Code, Weight, Destination, Status)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (passenger_id, tracking_code, qr_filename, weight_val, destination, initial_status),
                commit=True
            )

            execute_query(
                """INSERT INTO Tracking (Luggage_ID, Location, Scan_Time, Status, Updated_By)
                   VALUES (%s, %s, %s, %s, %s)""",
                (luggage_id, origin_checkpoint, datetime.now(), initial_status, session.get('username')),
                commit=True
            )

            flash(f"Luggage registered successfully! Tracking ID: {tracking_code}", "success")
            return redirect(url_for('luggage_details', luggage_id=luggage_id))

    return render_template(
        'register_luggage.html',
        passengers=passengers,
        selected_passenger_id=selected_passenger_id
    )


@app.route('/staff/luggage/<int:luggage_id>')
@role_required('Staff', 'Admin')
def luggage_details(luggage_id):
    """Displays full luggage record, printable QR code tag, and chronological tracking timeline."""
    luggage = execute_query(
        """SELECT l.*, p.Full_Name, p.Phone_Number, p.Email
           FROM Luggage l
           JOIN Passengers p ON l.Passenger_ID = p.Passenger_ID
           WHERE l.Luggage_ID = %s""",
        (luggage_id,),
        fetch_one=True
    )
    if not luggage:
        flash("Luggage record not found.", "danger")
        return redirect(url_for('staff_dashboard'))

    # Ensure QR image exists on disk
    qr_path = os.path.join(app.config['QR_FOLDER'], luggage['QR_Code'])
    if not os.path.exists(qr_path):
        create_qr_image(luggage['Tracking_Code'])

    history = execute_query(
        """SELECT * FROM Tracking
           WHERE Luggage_ID = %s
           ORDER BY Scan_Time ASC, Tracking_ID ASC""",
        (luggage_id,),
        fetch_all=True
    )

    return render_template(
        'luggage_details.html',
        luggage=luggage,
        history=history,
        statuses=app.config['VALID_STATUSES']
    )


@app.route('/staff/download-qr/<filename>')
@role_required('Staff', 'Admin')
def download_qr(filename):
    """Allows Airline Staff to download the QR code PNG file for printing/attaching."""
    safe_name = os.path.basename(filename)
    return send_from_directory(app.config['QR_FOLDER'], safe_name, as_attachment=True)


@app.route('/staff/scan', methods=['GET', 'POST'])
@role_required('Staff', 'Admin')
def scan_qr():
    """
    Camera-based QR scanning and checkpoint update page.
    Handles POST submissions to record a new location and status in the Tracking table.
    """
    prefill_code = request.args.get('code', '').strip().upper()

    if request.method == 'POST':
        tracking_code = request.form.get('tracking_code', '').strip().upper()
        location = request.form.get('location', '').strip()
        new_status = request.form.get('status', '').strip()

        if not tracking_code or not location or not new_status:
            flash("Tracking ID, Checkpoint Location, and New Status are all required.", "danger")
            return redirect(url_for('scan_qr', code=tracking_code))

        if new_status not in app.config['VALID_STATUSES']:
            flash("Invalid luggage status selected.", "danger")
            return redirect(url_for('scan_qr', code=tracking_code))

        luggage = execute_query(
            "SELECT * FROM Luggage WHERE Tracking_Code = %s OR CAST(Luggage_ID AS CHAR) = %s",
            (tracking_code, tracking_code),
            fetch_one=True
        )

        if not luggage:
            flash(f"No luggage found with code '{tracking_code}'.", "danger")
            return redirect(url_for('scan_qr'))

        # Update current status on Luggage table
        execute_query(
            "UPDATE Luggage SET Status = %s WHERE Luggage_ID = %s",
            (new_status, luggage['Luggage_ID']),
            commit=True
        )

        # Insert immutable checkpoint audit log into Tracking table
        execute_query(
            """INSERT INTO Tracking (Luggage_ID, Location, Scan_Time, Status, Updated_By)
               VALUES (%s, %s, %s, %s, %s)""",
            (luggage['Luggage_ID'], location, datetime.now(), new_status, session.get('username')),
            commit=True
        )

        flash(f"Checkpoint logged! {luggage['Tracking_Code']} updated to '{new_status}' at {location}.", "success")
        return redirect(url_for('luggage_details', luggage_id=luggage['Luggage_ID']))

    return render_template(
        'scan_qr.html',
        statuses=app.config['VALID_STATUSES'],
        prefill_code=prefill_code
    )


@app.route('/api/luggage/<tracking_code>')
@role_required('Staff', 'Admin')
def api_lookup_luggage(tracking_code):
    """JSON endpoint called by scanner.js immediately when a QR code is detected by camera."""
    clean_code = tracking_code.strip().upper()
    luggage = execute_query(
        """SELECT l.Luggage_ID, l.Tracking_Code, l.Destination, l.Status, l.Weight,
                  p.Full_Name
           FROM Luggage l
           JOIN Passengers p ON l.Passenger_ID = p.Passenger_ID
           WHERE l.Tracking_Code = %s OR CAST(l.Luggage_ID AS CHAR) = %s""",
        (clean_code, clean_code),
        fetch_one=True
    )
    if not luggage:
        return jsonify({'found': False, 'message': f'No luggage matches code: {clean_code}'}), 404

    return jsonify({
        'found': True,
        'luggage_id': luggage['Luggage_ID'],
        'tracking_code': luggage['Tracking_Code'],
        'passenger_name': luggage['Full_Name'],
        'destination': luggage['Destination'],
        'current_status': luggage['Status'],
        'weight': float(luggage['Weight'] or 0)
    })


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def page_not_found(e):
    flash("The requested page was not found.", "warning")
    return redirect(url_for('index'))


@app.errorhandler(500)
def internal_server_error(e):
    flash("An unexpected server error occurred. Please check your database connection.", "danger")
    return redirect(url_for('index'))


if __name__ == '__main__':
    bootstrap_demo_accounts()
    app.run(debug=True, host='0.0.0.0', port=5000)