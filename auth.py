
import streamlit as st
import json
import hashlib
import os

USER_DB_FILE = "user_db.json"
DEFAULT_ADMIN = {"username": "admin", "password": "admin123", "role": "admin"}

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def load_users():
    if os.path.exists(USER_DB_FILE):
        with open(USER_DB_FILE, "r") as file:
            return json.load(file)
    return {}

def save_users(users):
    with open(USER_DB_FILE, "w") as file:
        json.dump(users, file)

def initialize_user_db():
    users = load_users()
    if DEFAULT_ADMIN["username"] not in users:
        users[DEFAULT_ADMIN["username"]] = {
            "password": hash_password(DEFAULT_ADMIN["password"]),
            "role": DEFAULT_ADMIN["role"]
        }
        save_users(users)

def login_page():
    st.title("Farm Dashboard Login")

    tab1, tab2 = st.tabs(["Admin Login", "User Login"])

    with tab1:
        username = st.text_input("Username", key="admin_user")
        password = st.text_input("Password", type="password", key="admin_pass")
        if st.button("Login as Admin", key="admin_login"):
            authenticate_user(username, password, "admin")

    with tab2:
        username = st.text_input("Username", key="user_user")
        password = st.text_input("Password", type="password", key="user_pass")
        if st.button("Login as User", key="user_login"):
            authenticate_user(username, password, "user")

def authenticate_user(username, password, expected_role):
    users = load_users()
    if username in users and users[username]["password"] == hash_password(password) and users[username]["role"] == expected_role:
        st.success("Login successful")
        st.session_state.authenticated = True
        st.session_state.username = username
        st.session_state.role = users[username]["role"]
        st.rerun()
    else:
        st.error(f"Invalid credentials or not an {expected_role} account")
