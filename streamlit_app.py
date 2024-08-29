import streamlit as st
from time import sleep

import mysql.connector
from datetime import datetime

# MySQL connection configuration
db_config = {
    'host': 'localhost',
    'port': 2000,
    'user': 'sharkninja_user',
    'password': '3m3r4ld0',
    'database': 'sharkninja_prd'
}

def get_db_connection():
    return mysql.connector.connect(**db_config)

def check_credentials(username, password):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM swaggers WHERE username = %s AND password = %s", (username, password))
    result = cursor.fetchone()
    
    # Log the login attempt
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    success = result is not None
    cursor.execute("INSERT INTO login_logs (username, timestamp, success) VALUES (%s, %s, %s)", (username, timestamp, success))
    conn.commit()
    
    cursor.close()
    conn.close()
    return success

def username_exists(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM swaggers WHERE username = %s", (username,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result is not None

def create_user(username, password):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO swaggers (username, password) VALUES (%s, %s)", (username, password))
    conn.commit()
    cursor.close()
    conn.close()

# The login_logs table is already created in the MySQL database, so we don't need this function
# def create_login_logs_table():
#     ...

st.title("Welcome")

tab1, tab2 = st.tabs(["Login", "Create User"])

with tab1:
    st.write("Please log in to continue.")

    username = st.text_input("Username", key="login_username")
    password = st.text_input("Password", type="password", key="login_password")

    if st.button("Log in", type="primary"):
        if check_credentials(username, password):
            st.session_state.logged_in = True
            st.success("Logged in successfully!")
            sleep(0.5)
            st.switch_page("pages/page1.py")
        else:
            st.error("Incorrect username or password")

with tab2:
    st.write("Create a new user account.")

    new_username = st.text_input("New Username", key="new_username")
    new_password = st.text_input("New Password", type="password", key="new_password")
    special_key = st.text_input("Special Key", type="password")

    if st.button("Create User", type="primary"):
        if special_key == "ralphsendme":
            if new_username and new_password:
                if not username_exists(new_username):
                    create_user(new_username, new_password)
                    st.success("User created successfully! You can now log in.")
                else:
                    st.error("Username already exists. Please choose a different username.")
            else:
                st.error("Please provide both username and password.")
        else:
            st.error("Incorrect special key. User creation failed.")