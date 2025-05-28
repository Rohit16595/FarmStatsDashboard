import streamlit as st
import pandas as pd
from auth import load_users, save_users, hash_password
from datetime import datetime, timedelta
from streamlit_option_menu import option_menu
import matplotlib.pyplot as plt

def format_date(dt):
    return dt.strftime("%d-%m-%Y")

def preprocess_disconnected_df(disconnected_df, master_df):
    # Parse entry_date as DD-MM-YYYY and map Cluster
    disconnected_df["entry_date"] = pd.to_datetime(disconnected_df["entry_date"], format="%d-%m-%Y", errors="coerce")
    cluster_map = master_df.set_index("farm_name")["Cluster"].to_dict()
    disconnected_df["Cluster"] = disconnected_df["farm_name"].map(cluster_map)
    return disconnected_df

def calculate_metrics(master_df, device_df, disconnected_df, selected_cluster, selected_farm, selected_date):
    disconnected_df = preprocess_disconnected_df(disconnected_df, master_df)

    # Filter by date and data_quality
    filtered_disconnected = disconnected_df[
        (disconnected_df["entry_date"].dt.date == pd.to_datetime(selected_date, format="%d-%m-%Y").date()) &
        (disconnected_df["data_quality"] == "Disconnected")
    ]

    if selected_cluster != "All":
        filtered_disconnected = filtered_disconnected[filtered_disconnected["Cluster"] == selected_cluster]
        master_df = master_df[master_df["Cluster"] == selected_cluster]

    if selected_farm != "All":
        filtered_disconnected = filtered_disconnected[filtered_disconnected["farm_name"] == selected_farm]
        master_df = master_df[master_df["farm_name"] == selected_farm]

    filtered_device = device_df.copy()
    if selected_farm != "All":
        filtered_device = filtered_device[filtered_device["farm_name"] == selected_farm]
    elif selected_cluster != "All":
        farms = master_df["farm_name"].unique()
        filtered_device = filtered_device[filtered_device["farm_name"].isin(farms)]

    total_devices = len(filtered_device)
    disconnected_devices = len(filtered_disconnected["deviceid"].unique())
    total_farms = master_df["farm_name"].nunique()
    gateway_count = filtered_device["gatewayid"].nunique()
    disconnected_list = filtered_disconnected[["deviceid", "tag_number"]].dropna().drop_duplicates().values.tolist()

    gateway_devices = filtered_device.groupby("gatewayid")["deviceid"].apply(set).to_dict()
    disconnected_set = set(filtered_disconnected["deviceid"])
    gateway_issues = [g for g, devs in gateway_devices.items() if devs.issubset(disconnected_set)]
    gateway_issue_flag = "Yes" if gateway_issues else "No"
    gateway_issue_count = len(gateway_issues)

    return {
        "farm_count": total_farms,
        "total_devices": total_devices,
        "disconnected_devices": disconnected_devices,
        "gateway_issue": gateway_issue_flag,
        "gateway_count": gateway_count,
        "disconnected_list": disconnected_list,
        "disconnected_gateway_count": gateway_issue_count,
    }

def get_trend_data(disconnected_df, device_df, master_df, selected_cluster, selected_farm, selected_device_type, period_days):
    disconnected_df = preprocess_disconnected_df(disconnected_df, master_df)

    end_date = disconnected_df["entry_date"].max().normalize()
    start_date = end_date - timedelta(days=period_days)
    trend_df = disconnected_df[
        (disconnected_df["entry_date"] >= start_date) &
        (disconnected_df["entry_date"] <= end_date) &
        (disconnected_df["data_quality"] == "Disconnected")
    ]

    if selected_cluster != "All":
        trend_df = trend_df[trend_df["Cluster"] == selected_cluster]
    if selected_farm != "All":
        trend_df = trend_df[trend_df["farm_name"] == selected_farm]
    if selected_device_type != "All":
        trend_df = trend_df[trend_df["Device_type"] == selected_device_type]

    device_trend = trend_df.groupby("entry_date")["deviceid"].nunique().reset_index(name="Disconnected Devices")

    gateway_issues = []
    for date in pd.date_range(start=start_date, end=end_date):
        day_data = trend_df[trend_df["entry_date"].dt.date == date.date()]
        disconnected_set = set(day_data["deviceid"])
        filtered_device = device_df.copy()
        if selected_farm != "All":
            filtered_device = filtered_device[filtered_device["farm_name"] == selected_farm]
        gateway_devices = filtered_device.groupby("gatewayid")["deviceid"].apply(set).to_dict()
        gateway_issue_count = sum(1 for devs in gateway_devices.values() if devs.issubset(disconnected_set))
        gateway_issues.append({"entry_date": date, "Disconnected Gateways": gateway_issue_count})
    gateway_trend = pd.DataFrame(gateway_issues)

    return device_trend, gateway_trend

def plot_trends(device_df, gateway_df):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))

    ax1.plot(device_df["entry_date"], device_df["Disconnected Devices"], marker="o")
    ax1.set_title("Device Disconnection Trend")
    ax1.set_xlabel("Date")
    ax1.set_ylabel("Devices")

    ax2.plot(gateway_df["entry_date"], gateway_df["Disconnected Gateways"], marker="o", color="red")
    ax2.set_title("Gateway Disconnection Trend")
    ax2.set_xlabel("Date")
    ax2.set_ylabel("Gateways")

    st.pyplot(fig)

def user_dashboard():
    st.title("User Dashboard")
    master_df = st.session_state.master_df
    device_df = st.session_state.device_df
    disconnected_df = st.session_state.disconnected_df

    cluster_list = ["All"] + sorted(master_df["Cluster"].dropna().unique().tolist())
    selected_cluster = st.selectbox("Select Cluster", cluster_list)

    farm_list = ["All"] + sorted(master_df["farm_name"].dropna().unique().tolist())
    selected_farm = st.selectbox("Select Farm", farm_list)

    disconnected_df = preprocess_disconnected_df(disconnected_df, master_df)
    date_list = sorted(disconnected_df["entry_date"].dropna().dt.date.unique(), reverse=True)
    selected_date = st.selectbox("Select Date", [d.strftime("%d-%m-%Y") for d in date_list])

    metrics = calculate_metrics(master_df, device_df, disconnected_df, selected_cluster, selected_farm, selected_date)

    st.subheader("📊 Key Metrics")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Farms", metrics["farm_count"])
    col2.metric("Total Devices", metrics["total_devices"])
    col3.metric("Disconnected Devices", metrics["disconnected_devices"])
    col4.metric("Gateways", metrics["gateway_count"])

    col5, col6 = st.columns(2)
    col5.metric("Disconnected Gateways", metrics["disconnected_gateway_count"])
    col6.metric("Gateway Issue", metrics["gateway_issue"])

    st.subheader("📋 Disconnected Devices List")
    if metrics["disconnected_list"]:
        df = pd.DataFrame(metrics["disconnected_list"], columns=["Device ID", "Tag Number"])
        st.dataframe(df)
    else:
        st.info("No disconnected devices found.")

    st.subheader("📉 Disconnection Trends")
    period_map = {
        "7 days": 7,
        "1 month": 30,
        "3 months": 90,
        "6 months": 180,
        "1 year": 365
    }

    selected_period = st.selectbox("Trend Duration", list(period_map.keys()))
    selected_device_type = st.selectbox("Device Type", ["All"] + sorted(disconnected_df["Device_type"].dropna().unique().tolist()))

    device_trend, gateway_trend = get_trend_data(disconnected_df, device_df, master_df, selected_cluster, selected_farm, selected_device_type, period_map[selected_period])

    if not device_trend.empty or not gateway_trend.empty:
        plot_trends(device_trend, gateway_trend)
    else:
        st.info("No trend data available.")

def admin_dashboard():
    selected = option_menu(
        menu_title=None,
        options=["User Dashboard", "Admin Panel"],
        icons=["graph-up", "tools"],
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
    users = load_users()
    st.subheader("User Management")
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
        if new_username in users:
            st.error("Username already exists")
        else:
            users[new_username] = {
                "password": hash_password(new_password),
                "role": new_role
            }
            save_users(users)
            st.success("User added successfully")
