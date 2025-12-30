import os
import pymysql
from pymysql.cursors import DictCursor
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# DB credentials
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")

# Log file path
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
DB_ERROR_LOG = os.path.join(LOG_DIR, "db_error.txt")

# Ensure log directory exists
os.makedirs(LOG_DIR, exist_ok=True)


def log_error(error_message: str, context: str = "Database Operation"):
    """Log error to db_error.txt file"""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(DB_ERROR_LOG, "a") as log_file:
            log_file.write(f"\n[{timestamp}] {context}\n")
            log_file.write(f"Error: {error_message}\n")
            log_file.write("-" * 60 + "\n")
    except Exception as e:
        print(f"Failed to log error: {e}")


def get_db_connection():
    """Get MySQL database connection."""
    try:
        conn = pymysql.connect(
            host=MYSQL_HOST,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE,
            port=MYSQL_PORT,
            cursorclass=DictCursor,
            connect_timeout=5
        )
        return conn
    except Exception as e:
        error_msg = f"Database connection error: {str(e)}"
        log_error(error_msg, "Connection Attempt")
        return None


def check_database_status():
    """Check if database is connected and initialized. Returns (status, error_msg)"""
    
    # Check if credentials are configured
    if not MYSQL_DATABASE or not MYSQL_USER:
        return False, "Database credentials not configured in .env"
    
    # Try to connect
    conn = get_db_connection()
    if not conn:
        error_msg = "Failed to connect to MySQL database"
        return False, error_msg
    
    # Try to check if table exists
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) as count FROM information_schema.TABLES 
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'customer_entity'
            """, (MYSQL_DATABASE,))
            result = cursor.fetchone()
            conn.close()
            
            if result and result['count'] > 0:
                return True, None
            else:
                error_msg = "customer_entity table not found. Database not initialized."
                return False, error_msg
                
    except Exception as e:
        error_msg = f"Database check error: {str(e)}"
        log_error(error_msg, "Database Status Check")
        conn.close()
        return False, error_msg


def init_db():
    """Initialize database and create customers table if not exists."""
    conn = get_db_connection()
    if not conn:
        error_msg = "Cannot connect to database for initialization"
        log_error(error_msg, "Database Initialization")
        return False, error_msg
    
    try:
        with conn.cursor() as cursor:
            # Create customers table with unique constraint on hubspot_id
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS customer_entity (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    hubspot_id VARCHAR(255) NOT NULL UNIQUE,
                    email VARCHAR(255),
                    firstname VARCHAR(255),
                    lastname VARCHAR(255),
                    phone VARCHAR(100),
                    company VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_hubspot_id (hubspot_id),
                    INDEX idx_email (email)
                )
            """)
            conn.commit()
        conn.close()
        return True, None
    except Exception as e:
        error_msg = f"Database initialization error: {str(e)}"
        log_error(error_msg, "Database Initialization")
        conn.close()
        return False, error_msg


def sync_customers_to_db(customers_df):
    """Sync customers from HubSpot to database. Only insert new records and remove deleted ones."""
    if customers_df is None or len(customers_df) == 0:
        return {"new": 0, "skipped": 0, "deleted": 0, "errors": 0}
    
    conn = get_db_connection()
    if not conn:
        error_msg = "Cannot connect to database for sync"
        log_error(error_msg, "Customer Sync")
        return {"new": 0, "skipped": 0, "deleted": 0, "errors": 1}
    
    new_count = 0
    skipped_count = 0
    deleted_count = 0
    error_count = 0
    
    try:
        with conn.cursor() as cursor:
            # Get all existing hubspot_ids from database
            cursor.execute("SELECT hubspot_id FROM customer_entity")
            db_records = cursor.fetchall()
            db_hubspot_ids = set(str(record['hubspot_id']) for record in db_records)
            
            # Get all hubspot_ids from API response
            api_hubspot_ids = set(str(row['ID']) for _, row in customers_df.iterrows())
            
            # Find records to delete (in DB but not in API response)
            ids_to_delete = db_hubspot_ids - api_hubspot_ids
            
            # Delete records that are no longer in HubSpot
            if ids_to_delete:
                for hubspot_id in ids_to_delete:
                    try:
                        cursor.execute(
                            "DELETE FROM customer_entity WHERE hubspot_id = %s",
                            (hubspot_id,)
                        )
                        deleted_count += 1
                    except Exception as e:
                        error_count += 1
                        log_error(f"Error deleting customer {hubspot_id}: {str(e)}", "Customer Deletion")
            
            # Insert or skip existing records
            for _, row in customers_df.iterrows():
                try:
                    # Check if customer already exists
                    cursor.execute(
                        "SELECT hubspot_id FROM customer_entity WHERE hubspot_id = %s",
                        (str(row['ID']),)
                    )
                    existing = cursor.fetchone()
                    
                    if existing:
                        skipped_count += 1
                        continue
                    
                    # Insert new customer
                    cursor.execute("""
                        INSERT INTO customer_entity 
                        (hubspot_id, email, firstname, lastname, phone, company)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        str(row['ID']),
                        row.get('Email', 'N/A'),
                        row.get('First Name', 'N/A'),
                        row.get('Last Name', 'N/A'),
                        row.get('Phone', 'N/A'),
                        row.get('Company', 'N/A')
                    ))
                    new_count += 1
                    
                except pymysql.IntegrityError:
                    # Duplicate key - skip
                    skipped_count += 1
                except Exception as e:
                    error_count += 1
                    log_error(f"Error inserting customer {row.get('ID')}: {str(e)}", "Customer Insertion")
            
            conn.commit()
        conn.close()
        
        return {"new": new_count, "skipped": skipped_count, "deleted": deleted_count, "errors": error_count}
    
    except Exception as e:
        error_msg = f"Database sync error: {str(e)}"
        log_error(error_msg, "Customer Sync Operation")
        conn.close()
        return {"new": 0, "skipped": 0, "deleted": 0, "errors": 1}
