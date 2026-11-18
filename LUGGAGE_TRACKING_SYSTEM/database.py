import mysql.connector
from mysql.connector import Error
from config import Config


def get_db_connection():
    """Establishes and returns a connection to the MySQL database."""
    try:
        connection = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DATABASE,
            port=Config.MYSQL_PORT
        )
        return connection
    except Error as e:
        print(f"[Database Connection Error]: {e}")
        return None


def execute_query(query, params=None, fetch_one=False, fetch_all=False, commit=False):
    """
    Executes parameterized SQL queries safely to prevent SQL injection.
    Returns fetched rows (as dictionaries), lastrowid on commit, or None on error.
    """
    conn = get_db_connection()
    if conn is None:
        return None

    cursor = conn.cursor(dictionary=True)
    result = None
    try:
        cursor.execute(query, params or ())
        if commit:
            conn.commit()
            result = cursor.lastrowid
        elif fetch_one:
            result = cursor.fetchone()
        elif fetch_all:
            result = cursor.fetchall()
    except Error as e:
        if commit:
            conn.rollback()
        print(f"[SQL Execution Error]: {e}")
        raise e
    finally:
        cursor.close()
        conn.close()

    return result