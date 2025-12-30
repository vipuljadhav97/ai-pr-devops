import streamlit as st

st.set_page_config(page_title="Unified Platform", layout="wide", initial_sidebar_state="expanded")

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



        