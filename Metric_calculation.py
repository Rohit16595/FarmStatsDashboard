import streamlit as st
import pandas as pd
from auth import load_users, save_users, hash_password
from datetime import datetime, timedelta
import plotly.express as px

def format_date(dt):
    return dt.strftime("%d-%m-%Y")

def preprocess_disconnected_df(disconnected_df, master_df):
    disconnected_df["entry_date"] = pd.to_datetime(disconnected_df["entry_date"], format="%d-%m-%Y", errors="coerce")
    cluster_map = master_df.set_index("farm_name")["Cluster"].to_dict()
    disconnected_df["Cluster"] = disconnected_df["farm_name"].map(cluster_map)
    return disconnected_df

def calculate_metrics(master_df, device_df, disconnected_df, selected_cluster, selected_farm, selected_date):
    disconnected_df = preprocess_disconnected_df(disconnected_df, master_df)

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

    # Device type count (for selected date only)
    all_devices_on_date = disconnected_df[
        disconnected_df["entry_date"].dt.date == pd.to_datetime(selected_date, format="%d-%m-%Y").date()
    ]
    if selected_cluster != "All":
        all_devices_on_date = all_devices_on_date[all_devices_on_date["Cluster"] == selected_cluster]
    if selected_farm != "All":
        all_devices_on_date = all_devices_on_date[all_devices_on_date["farm_name"] == selected_farm]

    device_type_counts = all_devices_on_date["Device_type"].value_counts().to_dict()
    disconnected_type_counts = filtered_disconnected["Device_type"].value_counts().to_dict()

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
