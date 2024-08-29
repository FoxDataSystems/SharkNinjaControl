import sqlite3
import mysql.connector
from mysql.connector import Error

def transfer_product_status():
    print("Transferring ProductStatus data...")
    # Fetch all data from SQLite
    sqlite_cursor.execute("SELECT ProductID, CountryID, BrandID, Date, Status, Type, CurrentPrice FROM ProductStatus")
    
    # Insert data into MySQL in batches
    insert_query = """
    INSERT INTO productstatus (productid, countryid, brandid, Date, status, Type, currentprice)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    transfer_data(sqlite_cursor, mysql_cursor, insert_query)

def transfer_prices():
    print("Transferring Prices data...")
    # Fetch all product IDs from MySQL
    mysql_cursor.execute("SELECT productid FROM products")
    valid_product_ids = set(row[0] for row in mysql_cursor.fetchall())

    # Fetch all data from SQLite
    sqlite_cursor.execute("SELECT ProductID, CountryID, Price, EntryDate, Reason FROM Prices")
    
    # Insert data into MySQL in batches
    insert_query = """
    INSERT INTO prices (productid, countryid, price, entrydate, reason)
    VALUES (%s, %s, %s, %s, %s)
    """
    
    batch_size = 1000
    total_inserted = 0
    skipped = 0
    
    while True:
        rows = sqlite_cursor.fetchmany(batch_size)
        if not rows:
            break
        
        valid_rows = [row for row in rows if row[0] in valid_product_ids]
        skipped += len(rows) - len(valid_rows)
        
        if valid_rows:
            mysql_cursor.executemany(insert_query, valid_rows)
            mysql_conn.commit()
            total_inserted += len(valid_rows)
        
        print(f"Inserted {total_inserted} rows so far... (Skipped {skipped} invalid rows)")

    print(f"Successfully inserted {total_inserted} rows into MySQL prices table.")
    print(f"Skipped {skipped} rows due to invalid product IDs.")

def transfer_data(sqlite_cursor, mysql_cursor, insert_query):
    batch_size = 1000
    total_inserted = 0
    
    while True:
        rows = sqlite_cursor.fetchmany(batch_size)
        if not rows:
            break
        mysql_cursor.executemany(insert_query, rows)
        mysql_conn.commit()
        total_inserted += len(rows)
        print(f"Inserted {total_inserted} rows so far...")

    print(f"Successfully inserted {total_inserted} rows into MySQL table.")

print("Starting data transfer process...")

# SQLite connection
print("Connecting to SQLite database...")
sqlite_conn = sqlite3.connect('Sharkninja.db')
sqlite_cursor = sqlite_conn.cursor()
print("Connected to SQLite database successfully.")

# MySQL connection
try:
    print("Attempting to connect to MySQL database...")
    mysql_conn = mysql.connector.connect(
        host='localhost',
        port=2000,
        database='sharkninja_prd',
        user='sharkninja_user',
        password='3m3r4ld0'
    )
    mysql_cursor = mysql_conn.cursor()
    print("Connected to MySQL database successfully.")

    while True:
        print("\nChoose an option:")
        print("1. Transfer ProductStatus data")
        print("2. Transfer Prices data")
        print("3. Exit")
        choice = input("Enter your choice (1-3): ")

        if choice == '1':
            transfer_product_status()
        elif choice == '2':
            transfer_prices()
        elif choice == '3':
            print("Exiting...")
            break
        else:
            print("Invalid choice. Please try again.")

except Error as e:
    print(f"Error occurred: {e}")

finally:
    print("Closing database connections...")
    if 'mysql_conn' in locals() and mysql_conn.is_connected():
        mysql_cursor.close()
        mysql_conn.close()
        print("MySQL connection closed.")
    sqlite_conn.close()
    print("SQLite connection closed.")

print("Data transfer process completed.")
