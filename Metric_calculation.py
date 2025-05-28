
import streamlit as st
import pandas as pd
from auth import load_users, save_users, hash_password
from datetime import datetime
from streamlit_option_menu import option_menu

def format_date(dt):
    return dt.strftime("%d-%m-%Y")

def calculate_metrics(master_df, device_df, disconnected_df, selected_cluster, selected_farm, selected_date):
    if selected_cluster != "All":
        master_df = master_df[master_df["Cluster"] == selected_cluster]
    if selected_farm != "All":
        master_df = master_df[master_df["farm_name"] == selected_farm]

    if selected_date:
        disconnected_df = disconnected_df[disconnected_df["entry_date"] == pd.to_datetime(selected_date)]

    merged_df = pd.merge(master_df, device_df, on="farm_name", how="left")
    merged_df = pd.merge(merged_df, disconnected_df, on="farm_name", how="left")

    total_devices = len(merged_df)
    disconnected_devices = merged_df["disconnection_flag"].sum() if "disconnection_flag" in merged_df else 0
    disconnected_percent = round((disconnected_devices / total_devices) * 100, 2) if total_devices > 0 else 0

    return total_devices, disconnected_devices, disconnected_percent

def user_dashboard():
    st.title("User Dashboard")
    master_df = st.session_state.master_df
    device_df = st.session_state.device_df
    disconnected_df = st.session_state.disconnected_df

    default_date = format_date(disconnected_df["entry_date"].max())

    cluster_list = ["All"] + sorted(master_df["Cluster"].dropna().unique().tolist())
    selected_cluster = st.selectbox("Select Cluster", cluster_list)

    farm_list = ["All"] + sorted(master_df["farm_name"].dropna().unique().tolist())
    selected_farm = st.selectbox("Select Farm", farm_list)

    date_list = [format_date(dt) for dt in disconnected_df["entry_date"].dropna().dt.date.unique()]
    selected_date = st.selectbox("Select Entry Date", sorted(date_list, reverse=True), index=0)

    total, disconnected, percent = calculate_metrics(master_df, device_df, disconnected_df,
                                                     selected_cluster, selected_farm, selected_date)

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Devices", total)
    col2.metric("Disconnected Devices", disconnected)
    col3.metric("Disconnection %", f"{percent}%")

def admin_dashboard():
    selected = option_menu(
        menu_title=None,
        options=["User Dashboard", "Admin Panel"],
        icons=["speedometer", "gear"],
        menu_icon="cast",
        default_index=0,
        orientation="horizontal"
    )

    if selected == "User Dashboard":
        user_dashboard()
    else:
        admin_panel()

def admin_panel():
    st.title("Admin Panel")
    master_df = st.session_state.master_df
    device_df = st.session_state.device_df
    disconnected_df = st.session_state.disconnected_df

    default_date = format_date(disconnected_df["entry_date"].max())

    cluster_list = ["All"] + sorted(master_df["Cluster"].dropna().unique().tolist())
    selected_cluster = st.selectbox("Select Cluster", cluster_list, key="admin_cluster")

    farm_list = ["All"] + sorted(master_df["farm_name"].dropna().unique().tolist())
    selected_farm = st.selectbox("Select Farm", farm_list, key="admin_farm")

    date_list = [format_date(dt) for dt in disconnected_df["entry_date"].dropna().dt.date.unique()]
    selected_date = st.selectbox("Select Entry Date", sorted(date_list, reverse=True), index=0, key="admin_date")

    total, disconnected, percent = calculate_metrics(master_df, device_df, disconnected_df,
                                                     selected_cluster, selected_farm, selected_date)

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Devices", total)
    col2.metric("Disconnected Devices", disconnected)
    col3.metric("Disconnection %", f"{percent}%")

    with st.expander("User Management"):
        users = load_users()
        st.subheader("Existing Users")
        for username, details in users.items():
            col1, col2, col3 = st.columns(3)
            col1.write(username)
            col2.write(details["role"])
            if col3.button(f"Delete {username}"):
                del users[username]
                save_users(users)
                st.experimental_rerun()

        st.subheader("Add New User")
        new_username = st.text_input("New Username")
        new_password = st.text_input("New Password", type="password")
        new_role = st.selectbox("Role", ["admin", "user"])
        if st.button("Add User"):
            users = load_users()
            if new_username in users:
                st.error("Username already exists")
            else:
                users[new_username] = {
                    "password": hash_password(new_password),
                    "role": new_role
                }
                save_users(users)
                st.success("User added successfully")
