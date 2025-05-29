import streamlit as st
import pandas as pd
from auth import login_page, initialize_user_db
from Metric_calculation import user_dashboard, admin_dashboard

def main():
    # Initialize user database and session state
    if "authenticated" not in st.session_state:
        initialize_user_db()
        st.session_state.authenticated = False
        st.session_state.username = ""
        st.session_state.role = ""
        st.session_state.files_uploaded = False
        st.session_state.master_df = None
        st.session_state.device_df = None
        st.session_state.disconnected_df = None

    st.set_page_config(page_title="Farm Dashboard", layout="wide")

    if st.session_state.authenticated:
        if not st.session_state.files_uploaded:
            file_upload_page()
        else:
            if st.session_state.role == "admin":
                # Show sidebar for toggling between dashboards
                panel = st.sidebar.radio("Admin View", ["User Dashboard", "Admin Panel", "Upload Files"])
                if panel == "User Dashboard":
                    from Metric_calculation import user_dashboard
                    user_dashboard()
                elif panel == "Admin Panel":
                    from Metric_calculation import admin_panel
                    admin_panel()
                else:
                    file_upload_page()  # Assuming this is your upload function
            else:
                from Metric_calculation import user_dashboard
                user_dashboard()
    else:
        login_page()

def file_upload_page():
    st.title("Upload Data Files")
    st.session_state.master_df, st.session_state.device_df, st.session_state.disconnected_df = load_data()
    
    if st.session_state.master_df is not None and st.session_state.device_df is not None and st.session_state.disconnected_df is not None:
        if st.button("Proceed to Dashboard"):
            st.session_state.files_uploaded = True
            st.rerun()

def load_data():
    uploaded_master = st.file_uploader("Upload Master File", type=["csv"], key="master")
    uploaded_device_inventory = st.file_uploader("Upload Device Inventory File", type=["csv"], key="device")
    uploaded_disconnected = st.file_uploader("Upload Disconnected Device Output File", type=["csv"], key="disconnected")

    if uploaded_master and uploaded_device_inventory and uploaded_disconnected:
        master_df = pd.read_csv(uploaded_master)
        device_df = pd.read_csv(uploaded_device_inventory)
        disconnected_df = pd.read_csv(uploaded_disconnected)

        # Ensure entry_date is datetime
        if "entry_date" in disconnected_df.columns:
            disconnected_df["entry_date"] = pd.to_datetime(disconnected_df["entry_date"], errors="coerce")

        return master_df, device_df, disconnected_df
    else:
        return None, None, None

if __name__ == "__main__":
    main()