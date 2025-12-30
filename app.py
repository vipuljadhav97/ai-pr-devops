import requests
import os
import streamlit as st
import pandas as pd
from dotenv import load_dotenv
import pymysql
from pymysql.cursors import DictCursor

load_dotenv()  # Load variables from .env file

st.set_page_config(page_title="HubSpot Customers", layout="wide")
st.title("🔗 HubSpot Customers")

hubspot_token = os.getenv("HUBSPOT_TOKEN")

# DB credentials
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")

# Initialize session state
if "show_view_dialog" not in st.session_state:
    st.session_state.show_view_dialog = False
if "view_customer_data" not in st.session_state:
    st.session_state.view_customer_data = None
if "customers_df" not in st.session_state:
    st.session_state.customers_df = None

if not hubspot_token:
    st.error("Missing HUBSPOT_TOKEN in .env file")
    st.stop()


def get_db_connection():
    """Get MySQL database connection."""
    try:
        conn = pymysql.connect(
            host=MYSQL_HOST,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE,
            port=MYSQL_PORT,
            cursorclass=DictCursor
        )
        return conn
    except Exception as e:
        st.error(f"Database connection error: {e}")
        return None


def init_db():
    """Initialize database and create customers table if not exists."""
    conn = get_db_connection()
    if not conn:
        return False
    
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
        return True
    except Exception as e:
        st.error(f"Database initialization error: {e}")
        conn.close()
        return False


def sync_customers_to_db(customers_df):
    """Sync customers from HubSpot to database. Only insert new records and remove deleted ones."""
    if customers_df is None or len(customers_df) == 0:
        return {"new": 0, "skipped": 0, "deleted": 0, "errors": 0}
    
    conn = get_db_connection()
    if not conn:
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
                        print(f"Error deleting customer {hubspot_id}: {e}")
            
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
                    print(f"Error inserting customer {row.get('ID')}: {e}")
            
            conn.commit()
        conn.close()
        
        return {"new": new_count, "skipped": skipped_count, "deleted": deleted_count, "errors": error_count}
    
    except Exception as e:
        st.error(f"Database sync error: {e}")
        conn.close()
        return {"new": 0, "skipped": 0, "deleted": 0, "errors": 1}


def fetch_customers():
    """Fetch customers from HubSpot API."""
    url = "https://api.hubapi.com/crm/v3/objects/contacts?limit=100"
    headers = {"Authorization": f"Bearer {hubspot_token}"}

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()

        # Extract contacts
        contacts = data.get("results", [])
        if not contacts:
            st.warning("No customers found.")
            return None

        # Parse contact data
        customers = []
        for contact in contacts:
            customer = {
                "ID": contact.get("id"),
                "Email": contact.get("properties", {}).get("email", "N/A"),
                "First Name": contact.get("properties", {}).get("firstname", "N/A"),
                "Last Name": contact.get("properties", {}).get("lastname", "N/A"),
                "Phone": contact.get("properties", {}).get("phone", "N/A"),
                "Company": contact.get("properties", {}).get("company", "N/A"),
            }
            customers.append(customer)

        return pd.DataFrame(customers)

    except requests.exceptions.HTTPError as e:
        st.error(f"API Error: {response.status_code} - {response.text}")
        return None
    except Exception as e:
        st.error(f"Error fetching customers: {str(e)}")
        return None


def add_customer(email: str, firstname: str, lastname: str, phone: str = None, company: str = None):
    """Add a new customer to HubSpot."""
    url = "https://api.hubapi.com/crm/v3/objects/contacts"
    
    # Build properties object
    properties = {
        "email": email,
        "firstname": firstname,
        "lastname": lastname,
    }
    
    if phone:
        properties["phone"] = phone
    if company:
        properties["company"] = company
    
    payload = {
        "properties": properties
    }
    
    headers = {
        "Authorization": f"Bearer {hubspot_token}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        return {"success": True, "id": data.get("id"), "data": data}
    except requests.exceptions.HTTPError as e:
        return {"success": False, "error": f"API Error: {response.status_code} - {response.text}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def update_customer(contact_id: str, email: str = None, firstname: str = None, lastname: str = None, phone: str = None, company: str = None):
    """Update an existing customer in HubSpot."""
    url = f"https://api.hubapi.com/crm/v3/objects/contacts/{contact_id}"
    
    # Build properties object - only include fields that are provided
    properties = {}
    
    if email:
        properties["email"] = email
    if firstname:
        properties["firstname"] = firstname
    if lastname:
        properties["lastname"] = lastname
    if phone:
        properties["phone"] = phone
    if company:
        properties["company"] = company
    
    if not properties:
        return {"success": False, "error": "No properties provided to update"}
    
    payload = {
        "properties": properties
    }
    
    headers = {
        "Authorization": f"Bearer {hubspot_token}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.patch(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        return {"success": True, "id": data.get("id"), "data": data}
    except requests.exceptions.HTTPError as e:
        return {"success": False, "error": f"API Error: {response.status_code} - {response.text}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def delete_customer(contact_id: str, email: str = None):
    """Delete a customer from HubSpot using GDPR delete."""
    url = "https://api.hubapi.com/crm/v3/objects/contacts/gdpr-delete"
    
    payload = {
        "objectId": email if email else contact_id,
        "idProperty": "email" if email else "hs_object_id"
    }
    
    headers = {
        "Authorization": f"Bearer {hubspot_token}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return {"success": True, "message": f"Customer {contact_id} deleted successfully"}
    except requests.exceptions.HTTPError as e:
        return {"success": False, "error": f"API Error: {response.status_code} - {response.text}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@st.dialog("👤 Customer Details")
def view_customer_dialog(customer):
    """Display customer details in a non-editable dialog."""
    st.markdown("### Customer Information")
    
    col1, col2 = st.columns(2)
    with col1:
        st.text_input("ID", value=customer['ID'], disabled=True)
        st.text_input("Email", value=customer['Email'], disabled=True)
        st.text_input("First Name", value=customer['First Name'], disabled=True)
    
    with col2:
        st.text_input("Last Name", value=customer['Last Name'], disabled=True)
        st.text_input("Phone", value=customer['Phone'], disabled=True)
        st.text_input("Company", value=customer['Company'], disabled=True)


@st.dialog("✏️ Update Customer")
def update_customer_dialog(customer):
    """Display update form in a dialog with pre-populated data."""
    st.markdown("### Update Customer Information")
    
    col1, col2 = st.columns(2)
    with col1:
        st.text_input("ID", value=customer['ID'], disabled=True)
        new_email = st.text_input("Email", value=customer['Email'])
        new_firstname = st.text_input("First Name", value=customer['First Name'])
    
    with col2:
        st.write("")  # Spacing
        new_lastname = st.text_input("Last Name", value=customer['Last Name'])
        new_phone = st.text_input("Phone", value=customer['Phone'])
        new_company = st.text_input("Company", value=customer['Company'])
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Update Customer", use_container_width=True):
            with st.spinner("Updating customer..."):
                result = update_customer(
                    contact_id=str(customer['ID']),
                    email=new_email if new_email != customer['Email'] else None,
                    firstname=new_firstname if new_firstname != customer['First Name'] else None,
                    lastname=new_lastname if new_lastname != customer['Last Name'] else None,
                    phone=new_phone if new_phone != customer['Phone'] else None,
                    company=new_company if new_company != customer['Company'] else None
                )
                
                if result["success"]:
                    st.success("✅ Customer updated successfully!")
                    st.rerun()
                else:
                    st.error(f"❌ {result['error']}")
    
    with col2:
        if st.button("❌ Cancel", use_container_width=True):
            pass


@st.dialog("🗑️ Delete Customer")
def delete_customer_dialog(customer):
    """Display delete confirmation dialog."""
    st.error(f"⚠️ Are you sure you want to permanently delete this customer?")
    
    st.markdown("### Customer Information")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**ID:** {customer['ID']}")
        st.markdown(f"**Email:** {customer['Email']}")
        st.markdown(f"**First Name:** {customer['First Name']}")
    
    with col2:
        st.markdown(f"**Last Name:** {customer['Last Name']}")
        st.markdown(f"**Phone:** {customer['Phone']}")
        st.markdown(f"**Company:** {customer['Company']}")
    
    st.warning("⚠️ This action cannot be undone!")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Confirm Delete", use_container_width=True, type="primary"):
            with st.spinner("Deleting customer..."):
                result = delete_customer(str(customer['ID']), email=customer['Email'])
                
                if result["success"]:
                    st.success("✅ Customer deleted successfully!")
                    st.rerun()
                else:
                    st.error(f"❌ {result['error']}")
    
    with col2:
        if st.button("❌ Cancel", use_container_width=True):
            pass


# Fetch and display customers automatically
st.subheader("📋 Customers List")

# Initialize database
if MYSQL_DATABASE and MYSQL_USER:
    if init_db():
        st.success("✅ Database connected and initialized")
    else:
        st.warning("⚠️ Database initialization failed - running without DB sync")

with st.spinner("Fetching customers from HubSpot..."):
    df = fetch_customers()
    if df is not None:
        st.success(f"✅ Found {len(df)} customers from HubSpot")
        
        # Sync to database
        if MYSQL_DATABASE and MYSQL_USER:
            with st.spinner("Syncing to database..."):
                sync_result = sync_customers_to_db(df)
                if sync_result["new"] > 0 or sync_result["skipped"] > 0 or sync_result["deleted"] > 0:
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("🆕 New Records", sync_result["new"])
                    with col2:
                        st.metric("⏭️ Skipped (Duplicates)", sync_result["skipped"])
                    with col3:
                        st.metric("🗑️ Deleted", sync_result["deleted"])
                    with col4:
                        st.metric("❌ Errors", sync_result["errors"])
        
        # Store in session state
        st.session_state.customers_df = df
        
        st.divider()
        
        # Display customers table with action buttons
        st.markdown("### 📊 Customer Records")
        
        # Create header row
        col1, col2, col3, col4, col5, col6 = st.columns([1, 2, 2, 2, 2, 2])
        with col1:
            st.markdown("**#**")
        with col2:
            st.markdown("**ID**")
        with col3:
            st.markdown("**Email**")
        with col4:
            st.markdown("**Name**")
        with col5:
            st.markdown("**Company**")
        with col6:
            st.markdown("**Actions**")
        
        st.divider()
        
        # Display each customer row with action buttons
        for idx, row in df.iterrows():
            col1, col2, col3, col4, col5, col6 = st.columns([1, 2, 2, 2, 2, 2])
            
            with col1:
                st.write(f"#{idx+1}")
            with col2:
                st.write(row["ID"])
            with col3:
                st.write(row["Email"])
            with col4:
                st.write(f"{row['First Name']} {row['Last Name']}")
            with col5:
                st.write(row["Company"])
            with col6:
                # Display actions as simple clickable text using markdown style
                # Using columns to simulate text links
                link_col1, link_col2, link_col3, link_col4, link_col5 = st.columns([1, 0.8, 0.3, 0.8, 0.5])
                
                with link_col1:
                    if st.write("[View](javascript:void(0))") or st.session_state.get(f"clicked_view_{idx}_{row['ID']}"):
                        if st.link_button("View", "#", help="View customer details"):
                            pass
                
                # Use a hidden selectbox approach
                action = st.selectbox(
                    "action",
                    ["---", "View", "Update", "Delete"],
                    key=f"action_{idx}_{row['ID']}",
                    label_visibility="collapsed"
                )
                
                if action == "View":
                    view_customer_dialog(row)
                elif action == "Update":
                    update_customer_dialog(row)
                elif action == "Delete":
                    delete_customer_dialog(row)
    else:
        st.info("No customers to display")


# Divider
st.divider()

# Add new customer section
st.subheader("➕ Add New Customer")

with st.form("add_customer_form"):
    col1, col2 = st.columns(2)
    
    with col1:
        email = st.text_input("Email *", placeholder="customer@example.com")
        firstname = st.text_input("First Name *", placeholder="John")
        phone = st.text_input("Phone", placeholder="+1 (555) 123-4567")
    
    with col2:
        lastname = st.text_input("Last Name *", placeholder="Doe")
        company = st.text_input("Company", placeholder="Acme Corp")
    
    submit_btn = st.form_submit_button("Add Customer", use_container_width=True)
    
    if submit_btn:
        # Validate required fields
        if not email or not firstname or not lastname:
            st.error("Please fill in all required fields (Email, First Name, Last Name)")
        else:
            with st.spinner("Adding customer..."):
                result = add_customer(
                    email=email,
                    firstname=firstname,
                    lastname=lastname,
                    phone=phone if phone else None,
                    company=company if company else None
                )
                
                if result["success"]:
                    st.success(f"✅ Customer added successfully! ID: {result['id']}")
                else:
                    st.error(f"❌ Failed to add customer: {result['error']}")


# Divider
st.divider()

# Update customer section
st.subheader("✏️ Update Customer")

with st.form("update_customer_form"):
    col1, col2 = st.columns(2)
    
    with col1:
        contact_id = st.text_input("Contact ID *", placeholder="123456789")
        email = st.text_input("Email", placeholder="newemail@example.com")
        firstname = st.text_input("First Name", placeholder="John")
        phone = st.text_input("Phone", placeholder="+1 (555) 123-4567")
    
    with col2:
        st.write("")  # Spacing
        lastname = st.text_input("Last Name", placeholder="Doe")
        company = st.text_input("Company", placeholder="Acme Corp")
    
    submit_btn = st.form_submit_button("Update Customer", use_container_width=True)
    
    if submit_btn:
        # Validate contact ID
        if not contact_id:
            st.error("Please enter a Contact ID")
        elif not any([email, firstname, lastname, phone, company]):
            st.error("Please fill in at least one field to update")
        else:
            with st.spinner("Updating customer..."):
                result = update_customer(
                    contact_id=contact_id,
                    email=email if email else None,
                    firstname=firstname if firstname else None,
                    lastname=lastname if lastname else None,
                    phone=phone if phone else None,
                    company=company if company else None
                )
                
                if result["success"]:
                    st.success(f"✅ Customer updated successfully! ID: {result['id']}")
                else:
                    st.error(f"❌ Failed to update customer: {result['error']}")


# Divider
st.divider()

# Delete customer section
st.subheader("🗑️ Delete Customer")
st.warning("⚠️ This action will permanently delete the customer and cannot be undone.")

with st.form("delete_customer_form"):
    contact_id = st.text_input("Contact ID *", placeholder="123456789")
    confirm = st.checkbox("I confirm I want to delete this customer permanently")
    
    submit_btn = st.form_submit_button("Delete Customer", use_container_width=True)
    
    if submit_btn:
        # Validate contact ID
        if not contact_id:
            st.error("Please enter a Contact ID")
        elif not confirm:
            st.error("Please confirm deletion by checking the checkbox")
        else:
            with st.spinner("Deleting customer..."):
                result = delete_customer(contact_id=contact_id, email=None)
                
                if result["success"]:
                    st.success(f"✅ {result['message']}")
                else:
                    st.error(f"❌ Failed to delete customer: {result['error']}")

        