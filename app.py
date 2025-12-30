import streamlit as st

st.set_page_config(page_title="Unified Platform", layout="wide")
st.title("🏠 Welcome to Unified Platform ecommerce system")

st.markdown("""
## 📊 Overview

Welcome to the Unified Platform ecommerce system. This platform integrates with HubSpot to manage customer data, orders, and more.

### 🎯 Key Features

- **👥 Customer Management**: View, add, update, and delete customers from HubSpot
- **📈 Analytics & Reporting**: Track customer data and interactions
- **🔗 Integrations**: Seamless HubSpot integration for CRM operations
- **💾 Database Sync**: Automatic synchronization with MySQL database

### 🚀 Getting Started

Navigate using the sidebar to access different features:
- **Customers** → View and manage all your customer data
- More features coming soon!

### 📚 Documentation

For more information, visit the documentation or contact support.

---

**Version**: 1.0.0 | **Last Updated**: December 30, 2025
""")

st.divider()

# Display statistics if customers are available
st.subheader("📊 Quick Stats")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("👥 Total Customers", "—", help="View customers page to see details")

with col2:
    st.metric("🆕 New This Month", "—")

with col3:
    st.metric("📈 Growth Rate", "—")

with col4:
    st.metric("✅ Active", "—")

st.divider()

st.info("👈 Use the sidebar to navigate to different sections of the platform.")


        