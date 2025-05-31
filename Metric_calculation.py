import streamlit as st
import pandas as pd
from auth import load_users, save_users, hash_password
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import plotly.express as px

def format_date(dt):
    return dt.strftime("%d-%m-%Y")

def preprocess_disconnected_df(disconnected_df, master_df):
    disconnected_df.columns = disconnected_df.columns.str.strip()  # Clean column names
    if "entry_date" not in disconnected_df.columns:
        st.error("Column 'entry_date' not found in disconnected device file.")
        st.stop()

    # Clean and normalize entry_date
    disconnected_df["entry_date"] = (
        disconnected_df["entry_date"]
        .astype(str)
        .str.strip()
        .str.replace(r"\s+", "", regex=True)
    )
    
    disconnected_df["entry_date"] = pd.to_datetime(
        disconnected_df["entry_date"], dayfirst=True, errors="coerce"
    )

    if disconnected_df["entry_date"].isna().all():
        st.error("All dates in 'entry_date' failed to parse. Ensure format is DD-MM-YYYY or clean invisible characters.")
        st.stop()

    cluster_map = master_df.set_index("farm_name")["Cluster"].to_dict()
    disconnected_df["Cluster"] = disconnected_df["farm_name"].map(cluster_map)
    return disconnected_df


def calculate_metrics(master_df, device_df, disconnected_df, selected_cluster, selected_farm, selected_date):
    # Preprocess the disconnected dataframe
    disconnected_df = preprocess_disconnected_df(disconnected_df, master_df)
    
    # Normalize device types and data quality for case-insensitive comparison
    disconnected_df["Device_type_normalized"] = disconnected_df["Device_type"].astype(str).str.strip().str.lower()
    disconnected_df["data_quality_normalized"] = disconnected_df["data_quality"].astype(str).str.strip().str.lower()

    # Filter data by selected date
    selected_date_obj = pd.to_datetime(selected_date, format="%d-%m-%Y").date()
    date_filtered = disconnected_df[
        (disconnected_df["entry_date"].dt.date == selected_date_obj)
    ]
    
    # Filter for disconnected devices only
    filtered_disconnected = date_filtered[
        (date_filtered["data_quality_normalized"] == "disconnected")
    ]

    # Apply cluster filter if specified
    if selected_cluster != "All":
        master_df = master_df[master_df["Cluster"] == selected_cluster]
        device_df = device_df[device_df["farm_name"].isin(master_df["farm_name"])]
        disconnected_df = disconnected_df[disconnected_df["farm_name"].isin(master_df["farm_name"])]
        date_filtered = date_filtered[date_filtered["farm_name"].isin(master_df["farm_name"])]
        filtered_disconnected = filtered_disconnected[filtered_disconnected["farm_name"].isin(master_df["farm_name"])]

    # Apply farm filter if specified
    if selected_farm != "All":
        master_df = master_df[master_df["farm_name"] == selected_farm]
        device_df = device_df[device_df["farm_name"] == selected_farm]
        disconnected_df = disconnected_df[disconnected_df["farm_name"] == selected_farm]
        date_filtered = date_filtered[date_filtered["farm_name"] == selected_farm]
        filtered_disconnected = filtered_disconnected[filtered_disconnected["farm_name"] == selected_farm]

    # Calculate total farms
    total_farms = master_df["farm_name"].nunique()

    # Calculate total devices (all devices on selected date)
    total_devices = date_filtered["deviceid"].nunique()

    # Calculate device type counts (all devices on selected date)
    b_type_count = len(date_filtered[date_filtered["Device_type_normalized"] == "b type"])
    c_type_count = len(date_filtered[date_filtered["Device_type_normalized"] == "c type"])
    a_type_count = total_devices - (b_type_count + c_type_count)

    device_type_counts = {
        "A": a_type_count,
        "B": b_type_count,
        "C": c_type_count
    }

    # Calculate disconnected devices
    disconnected_devices = filtered_disconnected["deviceid"].nunique()
    disconnected_list = filtered_disconnected[["deviceid", "tag_number"]].dropna().drop_duplicates().values.tolist()

    # Calculate disconnected type counts
    b_type_disconnected = len(filtered_disconnected[filtered_disconnected["Device_type_normalized"] == "b type"])
    c_type_disconnected = len(filtered_disconnected[filtered_disconnected["Device_type_normalized"] == "c type"])
    a_type_disconnected = disconnected_devices - (b_type_disconnected + c_type_disconnected)

    disconnected_type_counts = {
        "A": a_type_disconnected,
        "B": b_type_disconnected,
        "C": c_type_disconnected
    }

    # Gateway calculations
    gateway_count = device_df["gatewayid"].nunique()
    gateway_devices = device_df.groupby("gatewayid")["deviceid"].apply(set).to_dict()
    disconnected_set = set(filtered_disconnected["deviceid"])

    gateway_issues = [g for g, devs in gateway_devices.items() if devs.issubset(disconnected_set) and devs]
    gateway_issue_flag = "Yes" if len(gateway_issues) > 0 else "No"
    gateway_issue_count = len(gateway_issues)

    return {
        "farm_count": total_farms,
        "total_devices": total_devices,
        "disconnected_devices": disconnected_devices,
        "gateway_issue": gateway_issue_flag,
        "gateway_count": gateway_count,
        "disconnected_list": disconnected_list,
        "disconnected_gateway_count": gateway_issue_count,
        "device_type_counts": device_type_counts,
        "disconnected_type_counts": disconnected_type_counts,
        "gateway_issues_list": gateway_issues
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
    # Use Plotly for interactive plots
    fig1 = px.line(device_df, x="entry_date", y="Disconnected Devices", 
                  title="Device Disconnection Trend",
                  labels={"entry_date": "Date", "Disconnected Devices": "Devices"})
    fig1.update_traces(mode="markers+lines")
    fig1.update_layout(hovermode="x unified")
    
    fig2 = px.line(gateway_df, x="entry_date", y="Disconnected Gateways", 
                  title="Gateway Disconnection Trend",
                  labels={"entry_date": "Date", "Disconnected Gateways": "Gateways"},
                  color_discrete_sequence=["red"])
    fig2.update_traces(mode="markers+lines")
    fig2.update_layout(hovermode="x unified")
    
    st.plotly_chart(fig1, use_container_width=True)
    st.plotly_chart(fig2, use_container_width=True)

def user_dashboard():
    # Load session state data
    master_df = st.session_state.master_df
    device_df = st.session_state.device_df
    disconnected_df = st.session_state.disconnected_df

    # Farm status filter (BEFORE dropdowns)
    status_list = ["All"] + sorted(master_df["farm_status"].dropna().unique())
    selected_status = st.selectbox("Farm Status", status_list, key="status_select")
    
    if selected_status != "All":
        master_df = master_df[master_df["farm_status"] == selected_status]
    
    # Sync device_df and disconnected_df
    allowed_farms = master_df["farm_name"].unique()
    device_df = device_df[device_df["farm_name"].isin(allowed_farms)]
    disconnected_df = disconnected_df[disconnected_df["farm_name"].isin(allowed_farms)]

    st.title("User Dashboard")

    # Preprocess for date list
    disconnected_df = preprocess_disconnected_df(disconnected_df, master_df)
    date_list = sorted(disconnected_df["entry_date"].dropna().dt.date.unique(), reverse=True)

    # After filtering master_df and disconnected_df (see issue 2 first!)
    date_list = sorted(disconnected_df["entry_date"].dropna().dt.date.unique())

    if date_list:
        col1, col2 = st.columns(2)
        with col1:
            selected_date = st.date_input(
                "Select Date", 
                value=max(date_list), 
                min_value=min(date_list), 
                max_value=max(date_list), 
                key="date_select"
            )
            selected_date = selected_date.strftime("%d-%m-%Y")

        with col2:
            selected_farm = st.selectbox(
                "Select Farm", ["All"] + sorted(master_df["farm_name"].dropna().unique()),
                key="farm_select"
            )

        col3, col4 = st.columns(2)
        with col3:
            selected_cluster = st.selectbox(
                "Select Cluster", ["All"] + sorted(master_df["Cluster"].dropna().unique()),
                key="cluster_select"
            )
      
    else:
        st.error("No valid dates found in disconnected device file. Please check data format.")
        st.stop()

    # Apply filter to master_df and disconnected_df
    if selected_status != "All":
        master_df = master_df[master_df["farm_status"] == selected_status]
    disconnected_df = disconnected_df[disconnected_df["farm_name"].isin(master_df["farm_name"])]

    # Recompute date list post filtering
    disconnected_df = preprocess_disconnected_df(disconnected_df, master_df)
    date_list = sorted(disconnected_df["entry_date"].dropna().dt.date.unique(), reverse=True)

    # Display Farm Info
    st.markdown("### 🏡 Farm Info")
if selected_farm != "All":
    vcm_name = master_df[master_df["farm_name"] == selected_farm]["vcm_name"].values[0]
else:
    vcm_name = "N/A"

st.markdown(
    f"<div style='display: flex; gap: 3rem;'>"
    f"<b>Farm Name:</b> {selected_farm} &nbsp;&nbsp;"
    f"<b>Cluster:</b> {selected_cluster} &nbsp;&nbsp;"
    f"<b>VCM Name:</b> {vcm_name}"
    f"</div>",
    unsafe_allow_html=True
    )

    metrics = calculate_metrics(master_df, device_df, disconnected_df, selected_cluster, selected_farm, selected_date)

    # Device Statistics Section
    st.subheader("📊 Device Statistics")
    cols = st.columns(4)
    cols[0].metric("Total Devices", metrics["total_devices"], help="Total number of devices")

    for i, (dev_type, count) in enumerate(metrics.get("device_type_counts", {}).items(), 1):
        if i < 4:
            cols[i].metric(f"{dev_type} Devices", count, help=f"Total {dev_type} type devices")

    cols = st.columns(4)
    cols[0].metric("Disconnected Devices", metrics["disconnected_devices"], help="Total disconnected devices")
    desired_order = ["C", "B", "A"]
    disconnected_types = metrics.get("disconnected_type_counts", {})
    for idx, dev_type in enumerate(desired_order):
        count = disconnected_types.get(dev_type)
        if count is not None:
            cols[idx + 1].metric(f"Disconnected {dev_type}", count, help=f"Disconnected {dev_type} type devices")

    # Gateway Statistics Section
    st.subheader("📊 Gateway Statistics")
    cols = st.columns(3)
    cols[0].metric("Total Gateways", metrics["gateway_count"], help="Total number of gateways")
    cols[1].metric("Disconnected Gateways", metrics["disconnected_gateway_count"], help="Gateways with all devices disconnected")

    if metrics["gateway_issue"] == "Yes":
        cols[2].markdown(f'<p style="font-size:20px;color:red">Gateway Issue: {metrics["gateway_issue"]}</p>', unsafe_allow_html=True)
    else:
        cols[2].markdown(f'<p style="font-size:20px;color:black">Gateway Issue: {metrics["gateway_issue"]}</p>', unsafe_allow_html=True)

    # Disconnected Devices List
    st.subheader("📋 Disconnected Devices List")
    if metrics["disconnected_list"]:
        df = pd.DataFrame(metrics["disconnected_list"], columns=["Device ID", "Tag Number"])
        st.dataframe(df)
    else:
        st.info("No disconnected devices found.")

    # Trend Analysis Section
    st.subheader("📉 Trend Analysis")
    period_map = {
        "7 days": 7,
        "1 month": 30,
        "3 months": 90,
        "6 months": 180,
        "1 year": 365
    }

    col1, col2 = st.columns(2)
    with col1:
        selected_period = st.selectbox("Trend Duration", list(period_map.keys()))
    with col2:
        selected_device_type = st.selectbox("Device Type", ["All"] + sorted(disconnected_df["Device_type"].dropna().unique().tolist()))

    device_trend, gateway_trend = get_trend_data(
        disconnected_df, device_df, master_df,
        selected_cluster, selected_farm,
        selected_device_type, period_map[selected_period]
    )

    if not device_trend.empty or not gateway_trend.empty:
        plot_trends(device_trend, gateway_trend)
    else:
        st.info("No trend data available.")


def admin_dashboard(show=True):
    # Create tabs for navigation
    tab1, tab2 = st.tabs(["User Dashboard", "Admin Panel"])
    
    with tab1:
        user_dashboard()
    
    with tab2:
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
