import requests
import os
import streamlit as st
import pandas as pd
from dotenv import load_dotenv
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from utils.db_service import (
    check_database_status, 
    check_hubspot_api_status,
    init_db, 
    sync_customers_to_db,
    get_db_connection,
    log_error,
    log_hubspot_error
)

load_dotenv()  # Load variables from .env file

st.title("👥 View Customers")

hubspot_token = os.getenv("HUBSPOT_TOKEN")

if not hubspot_token:
    st.error("Missing HUBSPOT_TOKEN in .env file")
    st.stop()


def fetch_customers():
    """Fetch customers from HubSpot API."""
    url = "https://api.hubapi.com/crm/v3/objects/contacts?limit=100"
    headers = {"Authorization": f"Bearer {hubspot_token}"}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        # Extract contacts
        contacts = data.get("results", [])
        if not contacts:
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

    except requests.exceptions.Timeout:
        error_msg = "HubSpot API timeout - request took too long"
        log_hubspot_error(error_msg, "Fetch Customers Timeout")
        st.error(f"API Error: {error_msg}")
        return None
    except requests.exceptions.HTTPError as e:
        error_msg = f"API HTTP Error {response.status_code}: {response.text}"
        log_hubspot_error(error_msg, "Fetch Customers HTTP Error")
        st.error(f"API Error: {error_msg}")
        return None
    except Exception as e:
        error_msg = f"Error fetching customers: {str(e)}"
        log_hubspot_error(error_msg, "Fetch Customers Exception")
        st.error(f"API Error: {error_msg}")
        return None


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
# Check and initialize database
db_status, db_error = check_database_status()

if not db_status:
    if db_error:
        st.warning(f"⚠️ Database Status: {db_error}")
        st.info("Attempting to initialize database...")
        success, init_error = init_db()
        if not success and init_error:
            st.error(f"Database initialization failed: {init_error}")
    else:
        st.error("Database is not available")

with st.spinner("Fetching customers from HubSpot..."):
    df = fetch_customers()
    if df is not None:
        # Sync to database
        if db_status:
            with st.spinner("Syncing to database..."):
                sync_result = sync_customers_to_db(df)
                if sync_result["errors"] > 0:
                    st.warning(f"⚠️ {sync_result['errors']} sync errors occurred. Check logs for details.")
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
