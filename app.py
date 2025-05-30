import streamlit as st
import pandas as pd
from auth import login_page, initialize_user_db
from Metric_calculation import user_dashboard, admin_dashboard
import chardet

def safe_read_file(uploaded_file):
    import io
    import chardet

    file_name = uploaded_file.name.lower()
    try:
        raw_data = uploaded_file.read()
        result = chardet.detect(raw_data)
        encoding = result['encoding'] or 'utf-8'
        uploaded_file.seek(0)

        if file_name.endswith('.csv'):
            return pd.read_csv(uploaded_file, encoding=encoding)
        elif file_name.endswith(('.xls', '.xlsx')):
            return pd.read_excel(uploaded_file)
        else:
            st.error(f"Unsupported file format: {file_name}. Upload .csv, .xls, or .xlsx only.")
            return None
    except Exception as e:
        st.error(f"Failed to read {file_name}: {e}")
        return None

def main():
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
                # ✅ This line must be indented INSIDE the admin role block
                panel = st.sidebar.radio("Navigation", ["User Dashboard", "Admin Panel", "Upload Files"])

                if panel == "User Dashboard":
                    from Metric_calculation import user_dashboard
                    user_dashboard()

                elif panel == "Admin Panel":
                    from Metric_calculation import admin_panel
                    admin_panel()

                elif panel == "Upload Files":
                    file_upload_page()

            else:
                from Metric_calculation import user_dashboard
                user_dashboard()
    else:
        login_page()

def file_upload_page():
    st.title("📁 Upload Files (Admin Only)")

    st.markdown("Please upload the following files to proceed:")

    master_file = st.file_uploader("Upload Master File", type=["csv", "xls", "xlsx"])
    device_file = st.file_uploader("Upload Device Inventory File", type=["csv", "xls", "xlsx"])
    disconnected_file = st.file_uploader("Upload Disconnected Device Output File", type=["csv", "xls", "xlsx"])

    if st.button("📊 Load Dashboard"):
        if not (master_file and device_file and disconnected_file):
            st.warning("Please upload all required files.")
            return

        master_df = safe_read_file(master_file)
        device_df = safe_read_file(device_file)
        disconnected_df = safe_read_file(disconnected_file)

        if master_df is not None and device_df is not None and disconnected_df is not None:
            st.session_state.master_df = master_df
            st.session_state.device_df = device_df
            st.session_state.disconnected_df = disconnected_df
            st.session_state.files_uploaded = True
            st.success("Files successfully loaded. Please proceed.")
        else:
            st.error("Failed to load one or more files. Please check format and try again.")


def load_data():
    uploaded_master = st.file_uploader("Upload Master File", type=["csv"], key="master")
    uploaded_device_inventory = st.file_uploader("Upload Device Inventory File", type=["csv"], key="device")
    uploaded_disconnected = st.file_uploader("Upload Disconnected Device Output File", type=["csv"], key="disconnected")

    if uploaded_master and uploaded_device_inventory and uploaded_disconnected:
        master_df = safe_read_file(uploaded_master)
        device_df = safe_read_file(uploaded_device_inventory)
        disconnected_df = safe_read_file(uploaded_disconnected)

        # Ensure entry_date is datetime
        if "entry_date" in disconnected_df.columns:
            disconnected_df["entry_date"] = pd.to_datetime(disconnected_df["entry_date"], errors="coerce")

        return master_df, device_df, disconnected_df
    else:
        return None, None, None

if __name__ == "__main__":
    main()
