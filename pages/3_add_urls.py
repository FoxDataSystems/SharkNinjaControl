import streamlit as st
import mysql.connector
import pandas as pd


def get_database_connection():
    return mysql.connector.connect(
        host="localhost",
        port=2000,
        user="sharkninja_user",
        password="3m3r4ld0",
        database="sharkninja_prd"
    )


def add_url_to_database(url):
    conn = get_database_connection()
    cursor = conn.cursor()
    
    try:
        # Check if the URL already exists
        cursor.execute("SELECT COUNT(*) FROM urls WHERE url = %s", (url,))
        if cursor.fetchone()[0] > 0:
            return False  # URL already exists
        
        # If not, insert the new URL
        cursor.execute("INSERT INTO urls (url) VALUES (%s)", (url,))
        conn.commit()
        return True
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return False
    finally:
        cursor.close()
        conn.close()


def get_all_urls_from_database():
    conn = get_database_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT url FROM urls")
    urls = [row[0] for row in cursor.fetchall()]
    
    cursor.close()
    conn.close()
    return urls


def search_urls(search_term):
    conn = get_database_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT url FROM urls WHERE url LIKE %s", (f'%{search_term}%',))
    urls = [row[0] for row in cursor.fetchall()]
    
    cursor.close()
    conn.close()
    return urls


def remove_url_from_database(url):
    conn = get_database_connection()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM urls WHERE url = %s", (url,))
    conn.commit()
    
    removed = cursor.rowcount > 0
    cursor.close()
    conn.close()
    return removed


def main():
    st.title("URL Database Manager")

    # Ensure the database and table are set up

    tab1, tab2 = st.tabs(["Add URLs", "Search and Remove URLs"])

    with tab1:
        st.subheader("Add Multiple URLs")
        urls_input = st.text_area("Enter URLs (one per line):", height=200)
        
        if st.button("Add URLs"):
            if urls_input:
                urls = urls_input.split('\n')
                success_count = 0
                already_exist_count = 0
                
                for url in urls:
                    url = url.strip()
                    if url:  # Skip empty lines
                        if add_url_to_database(url):
                            success_count += 1
                        else:
                            already_exist_count += 1
                
                st.success(f"Added {success_count} new URL(s) successfully!")
                if already_exist_count > 0:
                    st.warning(f"{already_exist_count} URL(s) already existed in the database.")
            else:
                st.warning("Please enter at least one URL.")

        st.subheader("Current URLs in Database")
        urls = get_all_urls_from_database()
        url_list = []
        if urls:
            for url in urls:
                url_list.append(url)
               #st.text(url)
        else:
            st.info("No URLs in the database yet.")
        st.dataframe(url_list, width=2000)

    with tab2:
        st.subheader("Search and Remove URLs")
        search_term = st.text_input("Enter search term:")
        
        if search_term:
            results = search_urls(search_term)
            if results:
                st.success(f"Found {len(results)} matching URL(s):")
                for url in results:
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.text(url)
                    with col2:
                        if st.button("Remove", key=url):
                            if remove_url_from_database(url):
                                st.success(f"Removed URL: {url}")
                                st.rerun()
                            else:
                                st.error(f"Failed to remove URL: {url}")
            else:
                st.info("No matching URLs found.")

if __name__ == "__main__":
    main()
