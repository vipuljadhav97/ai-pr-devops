import streamlit as st
from utils.db_service import check_database_status

st.set_page_config(page_title="Unified Platform", layout="wide", initial_sidebar_state="expanded")

# Check database status
db_status, db_error = check_database_status()

# Add sidebar status indicators
with st.sidebar:
    st.markdown("### 📊 Service Status")
    st.divider()
    
    # Database status
    if db_status:
        st.markdown("✅ **Database** - Connected")
    else:
        st.markdown("❌ **Database** - Disconnected")
        if db_error:
            st.caption(f"Error: {db_error}")

# Define pages using st.Page API
home_page = st.Page("pages/home.py", title="Home", icon="🏠")

# Customers section pages
view_customers_page = st.Page("pages/customers/view.py", title="View Customers", icon="👥")

# Configure navigation with sections
pages = {
    "": [home_page],
    "Customers": [view_customers_page],
}

# Create navigation
page = st.navigation(pages)

# Render the page
page.run()



        