from navigation import make_sidebar
import streamlit as st
import mysql.connector
from mysql.connector import Error
import pandas as pd
from datetime import datetime
from datetime import timedelta
import io
from bs4 import BeautifulSoup
import requests
import time
import plotly.express as px
import plotly.graph_objects as go
from requests.exceptions import Timeout
import logging
import os

# Create LOGS folder if it doesn't exist
if not os.path.exists('LOGS'):
    os.makedirs('LOGS')

# Set up logging
current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = f'LOGS/sharkninja_log_{current_time}.log'

logging.basicConfig(
    level=logging.INFO,  # Changed to INFO to capture more details
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename=log_file,
    filemode='w'
)
logger = logging.getLogger(__name__)

# Custom CSS to enhance the app's appearance
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}
st.set_page_config(layout="wide")
st.markdown("""
<style>
    .stRadio > label {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 5px;
        margin-right: 10px;
    }
    .stRadio > label:hover {
        background-color: #e0e2e6;
    }
            
    .stDataFrame {
        border: 1px solid #e0e2e6;
        border-radius: 5px;
    }
    .main .block-container {
        padding-top: 2rem;
    }
    .stDownloadButton > button {
        background-color: #FFffff;
        color: black;
        width: 300px;
        position: relative;
        right:157px;
        border: 2px;
        border-radius: 5px;
        font-size: 17px;
        font-weight: 400;
        text-align: center;
        cursor: pointer;
        transition: all 0.3s ease;
            }
    .stButton > button:hover {
        background-color: #eeeeff;
        color: #000;
    }
    .stButton > button:active {
        background-color: #ffffff;
        color: white;
    }
    .stButton > button:focus {
        background-color: #eeeeff;
        color: white;
    }
</style>
""", unsafe_allow_html=True)
def extract_id_from_url(url):
    """Extracts the part of the URL that comes after 'zid'."""
    with st.spinner("bezig met extract"):
        try:
            start_index = url.index("zid") + 3
            zid_part = url[start_index:]
            return zid_part
        except ValueError:
            return None
def get_data(country, brand, status):
    conn = create_connection()
    if conn is None:
        return pd.DataFrame()
    
    query = """
    SELECT p.sku, MAX(ps.Date) as LatestDate, ps.status
    FROM products p
    JOIN productstatus ps ON p.productid = ps.productid
    JOIN countries c ON ps.countryid = c.countryid
    JOIN brands b ON ps.brandid = b.brandid
    WHERE c.countrycode = %s AND b.brandname = %s AND ps.status = %s
    GROUP BY p.sku
    ORDER BY MAX(ps.Date) DESC
    """
    
    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(query, (country, brand, status))
            result = cursor.fetchall()
        df = pd.DataFrame(result)
        
        if not df.empty and 'LatestDate' in df.columns:
            df['LatestDate'] = pd.to_datetime(df['LatestDate'])
        
        return df
    except Error as e:
        st.error(f"Error executing query: {e}")
        return pd.DataFrame()
    finally:
        if conn and conn.is_connected():
            conn.close()
def create_connection():
    try:
        connection = mysql.connector.connect(
            host="localhost",
            port=2000,
            user="sharkninja_user",
            password="3m3r4ld0",
            database="sharkninja_prd"
        )
        return connection
    except Error as e:
        st.error(f"Error connecting to MySQL Database: {e}")
        return None

def get_dataframe_init(country, brand):
    conn = create_connection()
    if conn is None:
        return pd.DataFrame()

    query = """
    SELECT p.sku, ps.Date as LatestDate, ps.status
    FROM products p
    JOIN productstatus ps ON p.productid = ps.productid
    JOIN countries c ON ps.countryid = c.countryid
    JOIN brands b ON ps.brandid = b.brandid
    JOIN (
        SELECT ps.productid, MAX(ps.Date) as LatestDate
        FROM productstatus ps
        JOIN countries c ON ps.countryid = c.countryid
        JOIN brands b ON ps.brandid = b.brandid
        WHERE c.countrycode = %s AND b.brandname = %s AND ps.status IN ('IN', 'OUT')
        GROUP BY ps.productid
    ) latest ON ps.productid = latest.productid AND ps.Date = latest.LatestDate
    WHERE c.countrycode = %s AND b.brandname = %s
    ORDER BY ps.Date DESC;
    """
    
    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(query, (country, brand, country, brand))
            result = cursor.fetchall()
        df = pd.DataFrame(result)
        return df
    except Error as e:
        st.error(f"Error executing query: {e}")
        return pd.DataFrame()
    finally:
        if conn and conn.is_connected():
            conn.close()

def fetch_urls_from_database():
    conn = create_connection()
    if conn is None:
        return []
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT url FROM urls")
        urls = cursor.fetchall()
        return [url[0] for url in urls]
    except Error as e:
        st.error(f"Error fetching URLs: {e}")
        return []
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

def categorize_url(url):
    if "ninjakitchen.fr" in url:
        return "FR", "Ninja"
    elif "sharkclean.fr" in url:
        return "FR", "Shark"
    elif "ninjakitchen.nl" in url or "ninjakitchen.be" in url:
        return "NL" if "ninjakitchen.nl" in url else "BE", "Ninja"
    elif "sharkclean.nl" in url or "sharkclean.be" in url:
        return "NL" if "sharkclean.nl" in url else "BE", "Shark"
    else:
        return None, None

def group_urls_by_category(urls):
    grouped_urls = {}
    for url in urls:
        country, brand = categorize_url(url)
        if country and brand:
            key = f"{country}{brand}"
            if key not in grouped_urls:
                grouped_urls[key] = []
            grouped_urls[key].append(url)
    return grouped_urls
##sidebar functions
def save_to_db(df):
    logger.info(f"Saving {len(df)} rows to database")
    conn = create_connection()
    if conn is None:
        return
    
    cursor = conn.cursor()
    
    for _, row in df.iterrows():
        try:
            # Insert or get CountryID
            cursor.execute("INSERT IGNORE INTO countries (countrycode) VALUES (%s)", (row['Country'],))
            cursor.execute("SELECT countryid FROM countries WHERE countrycode = %s", (row['Country'],))
            country_id = cursor.fetchone()[0]

            # Insert or get BrandID
            cursor.execute("INSERT IGNORE INTO brands (brandname) VALUES (%s)", (row['Brand'],))
            cursor.execute("SELECT brandid FROM brands WHERE brandname = %s", (row['Brand'],))
            brand_id = cursor.fetchone()[0]

            # Insert or get ProductID
            cursor.execute("INSERT IGNORE INTO products (sku, productname) VALUES (%s, %s)", (row['SKU'], row['Product Name']))
            cursor.execute("SELECT productid FROM products WHERE sku = %s", (row['SKU'],))
            product_id = cursor.fetchone()[0]

            # Insert or get URL ID
            cursor.execute("INSERT IGNORE INTO urls (url) VALUES (%s)", (row['URL'],))
            cursor.execute("SELECT id FROM urls WHERE url = %s", (row['URL'],))
            url_id = cursor.fetchone()[0]

            # Insert into SKU_URL junction table
            cursor.execute("INSERT IGNORE INTO sku_url (skuid, urlid) VALUES (%s, %s)", (product_id, url_id))

            # Insert into ProductStatus
            cursor.execute("""
            INSERT INTO productstatus 
            (productid, countryid, brandid, Date, status, Type, currentprice)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (product_id, country_id, brand_id, row['Date'], row['Status'], row['Type'], row['Current Price']))

            conn.commit()
            logger.info(f"Successfully saved data for SKU {row['SKU']}")

        except Error as e:
            logger.error(f"Error saving data for SKU {row['SKU']}: {e}")
            conn.rollback()

    cursor.close()
    conn.close()
    logger.info("Database connection closed")

    st.success("All records processed. Check logs for details on any errors.")

def read_from_db(country, brand):
    conn = create_connection()
    if conn is None:
        return pd.DataFrame()
    
    try:
        query = """
        SELECT p.sku, p.productname, ps.Date, u.url, ps.status, ps.Type, ps.currentprice, c.countrycode, b.brandname
        FROM productstatus ps
        JOIN products p ON ps.productid = p.productid
        JOIN countries c ON ps.countryid = c.countryid
        JOIN brands b ON ps.brandid = b.brandid
        JOIN sku_url su ON p.productid = su.skuid
        JOIN urls u ON su.urlid = u.id
        WHERE c.countrycode = %s AND b.brandname = %s
        """
        df = pd.read_sql(query, conn, params=(country, brand))
        return df
    except Error as e:
        st.error(f"Error reading from database: {e}")
        return pd.DataFrame()
    finally:
        if conn.is_connected():
            conn.close()

def export_to_excel(out_of_stock_df, in_stock_df, skipped_df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        out_of_stock_df.to_excel(writer, sheet_name="Out of Stock", index=False)
        in_stock_df.to_excel(writer, sheet_name="In Stock", index=False)
        try:
            skipped_df.to_excel(writer, sheet_name="Skipped URLS", index=False)
        except:
            print("nice")
    return output.getvalue()
def get_out_of_stock_date(country, brand):
    conn = create_connection()
    if conn is None:
        return pd.DataFrame()
    
    query = """
    SELECT t1.sku, t1.Date as OutOfStockDate
    FROM productstatus t1
    INNER JOIN (
        SELECT p.sku, MAX(ps.Date) as MaxDate
        FROM products p
        JOIN productstatus ps ON p.productid = ps.productid
        JOIN countries c ON ps.countryid = c.countryid
        JOIN brands b ON ps.brandid = b.brandid
        WHERE c.countrycode = %s AND b.brandname = %s AND ps.status = 'OUT'
        GROUP BY p.sku
    ) t2 ON t1.sku = t2.sku AND t1.Date = t2.MaxDate
    WHERE t1.status = 'OUT'
    AND NOT EXISTS (
        SELECT 1
        FROM productstatus t3
        JOIN products p ON t3.productid = p.productid
        JOIN countries c ON t3.countryid = c.countryid
        JOIN brands b ON t3.brandid = b.brandid
        WHERE p.sku = t1.sku AND c.countrycode = %s AND b.brandname = %s
        AND t3.Date > t1.Date
        AND t3.status = 'IN'
    )
    ORDER BY t1.Date DESC;
    """
    
    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(query, (country, brand, country, brand))
            result = cursor.fetchall()
        df = pd.DataFrame(result)
        
        if not df.empty:
            df['OutOfStockDate'] = pd.to_datetime(df['OutOfStockDate'])
            current_date = datetime.now()
            df['Days out of stock'] = (current_date - df['OutOfStockDate']).dt.days
        
        return df
    except Error as e:
        st.error(f"Error executing query: {e}")
        return pd.DataFrame()
    finally:
        if conn and conn.is_connected():
            conn.close()
def get_current_out_of_stock(country, brand):
    conn = create_connection()
    if conn is None:
        return pd.DataFrame()
    
    query = """
    WITH ranked_status AS (
        SELECT 
            p.sku, 
            ps.Date, 
            ps.status,
            ROW_NUMBER() OVER (PARTITION BY p.sku ORDER BY ps.Date DESC) as rn,
            SUM(CASE WHEN ps.status = 'IN' THEN 1 ELSE 0 END) OVER (PARTITION BY p.sku ORDER BY ps.Date DESC) as in_stock_count
        FROM products p
        JOIN productstatus ps ON p.productid = ps.productid
        JOIN countries c ON ps.countryid = c.countryid
        JOIN brands b ON ps.brandid = b.brandid
        WHERE c.countrycode = %s AND b.brandname = %s
    ),
    current_status AS (
        SELECT sku, Date, status
        FROM ranked_status
        WHERE rn = 1
    ),
    earliest_out_date AS (
        SELECT 
            sku, 
            MIN(Date) as EarliestOutDate
        FROM ranked_status
        WHERE status = 'OUT' AND in_stock_count = 0
        GROUP BY sku
    )
    SELECT 
        cs.sku, 
        eod.EarliestOutDate as LastOutOfStockDate,
        DATEDIFF(CURDATE(), eod.EarliestOutDate) as DaysOutOfStock
    FROM current_status cs
    JOIN earliest_out_date eod ON cs.sku = eod.sku
    WHERE cs.status = 'OUT'
    ORDER BY DaysOutOfStock DESC
    """
    
    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(query, (country, brand))
            result = cursor.fetchall()
        df = pd.DataFrame(result)
        
        if not df.empty and 'LastOutOfStockDate' in df.columns:
            df['LastOutOfStockDate'] = pd.to_datetime(df['LastOutOfStockDate'])
        
        return df
    except Error as e:
        st.error(f"Error executing query: {e}")
        return pd.DataFrame()
    finally:
        if conn and conn.is_connected():
            conn.close()
def check_availability(urls):
    out_of_stock_products = []
    in_stock_products = []
    skipped_urls = []
    current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total_urls = len(urls)
    timeout_seconds = 5

    with requests.Session() as session:
        progress_placeholder = st.empty()

        for index, url in enumerate(urls, start=1):
            try:
                start_time = time.time()
                response = session.get(url, headers=headers, timeout=timeout_seconds)
                response.raise_for_status()

                soup = BeautifulSoup(response.text, "html.parser")

                out_of_stock_button = soup.find("button", class_="js-btn_out-of-stock", title="Niet op voorraad")
                out_of_stock_button_fr = soup.find("button", class_="js-btn_out-of-stock", title="Stock épuisé")

                add_to_cart_button = soup.find("button", title="Ajouter au panier")
                add_to_cart_button_nl = soup.find("button", title="Toevoegen aan winkelmandje")

                product_name_tag = soup.find("h1", class_="js-product-title js-make-bold")
                
                price_tag = soup.find("div", attrs={"data-testing-id": "current-price"})
                current_price = price_tag.text.strip() if price_tag else "N/A"

                if product_name_tag:
                    product_name = product_name_tag.get_text(strip=True)
                    product_type = "Ninja" if "ninja" in product_name.lower() else "Shark"
                    zid_part = extract_id_from_url(url)

                    if out_of_stock_button or out_of_stock_button_fr:
                        out_of_stock_products.append(
                            (zid_part, product_name, current_date, url, "OUT", product_type, current_price)
                        )
                    elif add_to_cart_button or add_to_cart_button_nl:
                        in_stock_products.append(
                            (zid_part, product_name, current_date, url, "IN", product_type, current_price)
                        )
                    else:
                        in_stock_products.append(
                            (zid_part, product_name, current_date, url, "IN", product_type, current_price)
                        )

            except Timeout:
                skipped_urls.append(url)
            except requests.RequestException as e:
                st.error(f"Error fetching {url}: {e}")

            if time.time() - start_time > timeout_seconds:
                skipped_urls.append(url)

        progress_placeholder.empty()

    return out_of_stock_products, in_stock_products, skipped_urls
def process_urls(urls, existing_products=None):
    if existing_products is None:
        existing_products = set()

    out_of_stock_products = []
    in_stock_products = []
    skipped_urls = []
    total_urls = len(urls)

    progress_bar = st.progress(0)
    status_text = st.empty()

    for index, url in enumerate(urls, start=1):
        progress_bar.progress(index / total_urls)
        status_text.text(f"Processing {index} out of {total_urls}, Skipped: {len(skipped_urls)}")

        result = check_availability([url])
        if result[0]:
            product = result[0][0]
            if product[0] not in existing_products:
                out_of_stock_products.append(product)
                existing_products.add(product[0])
        elif result[1]:
            product = result[1][0]
            if product[0] not in existing_products:
                in_stock_products.append(product)
                existing_products.add(product[0])
        else:
            skipped_urls.append(url)

    progress_bar.empty()
    status_text.empty()

    return out_of_stock_products, in_stock_products, skipped_urls, existing_products
def get_or_create_id(table_name, column_name, value):
    conn = create_connection()
    if conn is None:
        return None
    
    try:
        cursor = conn.cursor()
        
        if table_name == "countries":
            id_column = "countryid"
        elif table_name.endswith('s'):
            id_column = f"{table_name[:-1]}id"
        else:
            id_column = f"{table_name}id"
        
        cursor.execute(f"SELECT {id_column} FROM {table_name} WHERE {column_name} = %s", (value,))
        result = cursor.fetchone()
        
        if result:
            id = result[0]
        else:
            cursor.execute(f"INSERT INTO {table_name} ({column_name}) VALUES (%s)", (value,))
            id = cursor.lastrowid
        
        conn.commit()
        return id
    except Error as e:
        st.error(f"Error in get_or_create_id: {e}")
        return None
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

def get_or_create_product_id(sku, product_name):
    conn = create_connection()
    if conn is None:
        return None
    
    try:
        cursor = conn.cursor()
        
        cursor.execute("SELECT productid FROM products WHERE sku = %s", (sku,))
        result = cursor.fetchone()
        
        if result:
            product_id = result[0]
        else:
            cursor.execute("INSERT INTO products (sku, productname) VALUES (%s, %s)", (sku, product_name))
            product_id = cursor.lastrowid
        
        conn.commit()
        return product_id
    except Error as e:
        st.error(f"Error in get_or_create_product_id: {e}")
        return None
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

def save_prices_to_db(df, language):
    logger.info(f"save_prices_to_db function called with {len(df)} rows")
    conn = create_connection()
    if conn is None:
        return
    
    try:
        cursor = conn.cursor()
        
        logger.info(f"Getting country ID for language: {language}")
        country_id = get_or_create_id("countries", "countrycode", language)
        logger.info(f"Country ID: {country_id}")
        
        for index, row in df.iterrows():
            try:
                logger.info(f"Processing row {index}: SKU={row['SKU']}, Product Name={row['Product Name']}")
                product_id = get_or_create_product_id(row['SKU'], row['Product Name'])
                logger.info(f"Product ID: {product_id}")
                
                date_obj = datetime.strptime(row['Date'], "%Y-%m-%d %H:%M:%S")
                formatted_date = date_obj.strftime("%Y-%m-%d %H:%M:%S")
                
                price_str = row['Current Price'].replace('€', '').strip()
                current_price = float(price_str.replace(',', '.'))
                logger.info(f"Current price: {current_price}")
                
                # Get the last price record for this product and country
                cursor.execute("""
                    SELECT price, entrydate FROM prices
                    WHERE productid = %s AND countryid = %s
                    ORDER BY entrydate DESC LIMIT 1
                """, (product_id, country_id))
                last_price_record = cursor.fetchone()
                
                if last_price_record:
                    last_price, last_date = last_price_record
                    last_date = datetime.strptime(last_date, "%Y-%m-%d %H:%M:%S")
                    logger.info(f"Last price record: Price={last_price}, Date={last_date}")
                    
                    # Check if the price has changed
                    if current_price != last_price:
                        # Insert the last known price with datetime stamp current datetime - 1 hour
                        insert_date = date_obj - timedelta(hours=1)
                        logger.info(f"Price changed. Inserting last known price with date: {insert_date}")
                        cursor.execute("""
                            INSERT INTO prices (productid, countryid, price, entrydate, reason)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (product_id, country_id, last_price, insert_date.strftime("%Y-%m-%d %H:%M:%S"), "Last known price"))
                        
                        # Insert the new price with current datetime
                        logger.info(f"Inserting new price with date: {date_obj}")
                        cursor.execute("""
                            INSERT INTO prices (productid, countryid, price, entrydate, reason)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (product_id, country_id, current_price, formatted_date, "Newly scraped price"))
                    else:
                        logger.info("Price unchanged, no new record inserted")
                else:
                    logger.info("No previous price record, inserting first record")
                    # If there's no previous record, insert the current price
                    cursor.execute("""
                        INSERT INTO prices (productid, countryid, price, entrydate, reason)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (product_id, country_id, current_price, formatted_date, "First recorded price"))
                
                conn.commit()
                logger.info("Price record(s) committed to database")
            except Error as e:
                logger.error(f"Error processing row: {row}")
                logger.error(f"Error details: {str(e)}")
                logger.exception("Detailed error information:")
                conn.rollback()
        
    except Error as e:
        logger.error(f"Error in save_prices_to_db: {str(e)}")
        logger.exception("Detailed error information:")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()
        logger.info("Database connection closed")

def get_out_of_stock_date(country, brand):
    conn = create_connection()
    if conn is None:
        return pd.DataFrame()
    
    query = """
    SELECT t1.sku, t1.Date as OutOfStockDate
    FROM productstatus t1
    INNER JOIN (
        SELECT p.sku, MAX(ps.Date) as MaxDate
        FROM products p
        JOIN productstatus ps ON p.productid = ps.productid
        JOIN countries c ON ps.countryid = c.countryid
        JOIN brands b ON ps.brandid = b.brandid
        WHERE c.countrycode = %s AND b.brandname = %s AND ps.status = 'OUT'
        GROUP BY p.sku
    ) t2 ON t1.sku = t2.sku AND t1.Date = t2.MaxDate
    WHERE t1.status = 'OUT'
    AND NOT EXISTS (
        SELECT 1
        FROM productstatus t3
        JOIN products p ON t3.productid = p.productid
        JOIN countries c ON t3.countryid = c.countryid
        JOIN brands b ON t3.brandid = b.brandid
        WHERE p.sku = t1.sku AND c.countrycode = %s AND b.brandname = %s
        AND t3.Date > t1.Date
        AND t3.status = 'IN'
    )
    ORDER BY t1.Date DESC;
    """
    
    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(query, (country, brand, country, brand))
            result = cursor.fetchall()
        df = pd.DataFrame(result)
        
        if not df.empty:
            df['OutOfStockDate'] = pd.to_datetime(df['OutOfStockDate'])
            current_date = datetime.now()
            df['Days out of stock'] = (current_date - df['OutOfStockDate']).dt.days
        
        return df
    except Error as e:
        st.error(f"Error executing query: {e}")
        return pd.DataFrame()
    finally:
        if conn and conn.is_connected():
            conn.close()

def get_out_of_stock_duration(country, brand):
    conn = create_connection()
    if conn is None:
        return pd.DataFrame()
    
    query = """
    WITH status_changes AS (
        SELECT 
            p.sku, 
            ps.Date, 
            ps.status,
            LAG(ps.status) OVER (PARTITION BY p.sku ORDER BY ps.Date) AS prev_status,
            LAG(ps.Date) OVER (PARTITION BY p.sku ORDER BY ps.Date) AS prev_date
        FROM products p
        JOIN productstatus ps ON p.productid = ps.productid
        JOIN countries c ON ps.countryid = c.countryid
        JOIN brands b ON ps.brandid = b.brandid
        WHERE c.countrycode = %s AND b.brandname = %s
    )
    SELECT 
        sku, 
        Date AS BackInStockDate, 
        prev_date AS OutOfStockDate,
        DATEDIFF(Date, prev_date) AS DaysOutOfStock
    FROM status_changes
    WHERE status = 'IN' AND prev_status = 'OUT'
    ORDER BY Date DESC
    """
    
    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(query, (country, brand))
            result = cursor.fetchall()
        df = pd.DataFrame(result)
        
        if not df.empty:
            df['BackInStockDate'] = pd.to_datetime(df['BackInStockDate'])
            df['OutOfStockDate'] = pd.to_datetime(df['OutOfStockDate'])
        
        return df
    except Error as e:
        st.error(f"Error executing query: {e}")
        return pd.DataFrame()
    finally:
        if conn and conn.is_connected():
            conn.close()

def get_out_of_stock_history(country, brand):
    conn = create_connection()
    if conn is None:
        return pd.DataFrame()
    
    query = """
    WITH status_changes AS (
        SELECT 
            p.sku, 
            ps.Date AS DateTime,
            ps.status,
            LAG(ps.status) OVER (PARTITION BY p.sku ORDER BY ps.Date) AS prev_status
        FROM products p
        JOIN productstatus ps ON p.productid = ps.productid
        JOIN countries c ON ps.countryid = c.countryid
        JOIN brands b ON ps.brandid = b.brandid
        WHERE c.countrycode = %s AND b.brandname = %s
    ),
    out_of_stock_periods AS (
        SELECT 
            a.sku, 
            a.DateTime AS OutOfStockDate,
            MIN(b.DateTime) AS BackInStockDate
        FROM status_changes a
        LEFT JOIN status_changes b ON a.sku = b.sku 
            AND b.DateTime > a.DateTime 
            AND b.status = 'IN'
        WHERE a.status = 'OUT' AND (a.prev_status IS NULL OR a.prev_status = 'IN')
        GROUP BY a.sku, a.DateTime
    )
    SELECT 
        sku, 
        OutOfStockDate,
        BackInStockDate,
        CASE 
            WHEN BackInStockDate IS NOT NULL THEN 
                GREATEST(1, DATEDIFF(BackInStockDate, OutOfStockDate))
            ELSE 
                DATEDIFF(CURDATE(), OutOfStockDate)
        END AS DaysOutOfStock
    FROM out_of_stock_periods
    ORDER BY sku, OutOfStockDate DESC
    """
    
    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(query, (country, brand))
            result = cursor.fetchall()
        df = pd.DataFrame(result)
        
        if not df.empty:
            df['OutOfStockDate'] = pd.to_datetime(df['OutOfStockDate'])
            df['BackInStockDate'] = pd.to_datetime(df['BackInStockDate'])
        
        # Calculate the current out-of-stock duration for 'Current' status
        df['Status'] = df['BackInStockDate'].apply(lambda x: 'Historical' if pd.notnull(x) else 'Currently out of stock')
        
        return df
    except Error as e:
        st.error(f"Error executing query: {e}")
        return pd.DataFrame()
    finally:
        if conn and conn.is_connected():
            conn.close()

def add_logo():
        st.markdown(
            """
        <style>
            [data-testid="stSidebarContent"] {
                background-image: url(https://lever-client-logos.s3.amazonaws.com/5d04777b-cdde-4bc0-9cee-a61a406921c7-1528214915992.png);
                background-repeat: no-repeat;
                background-size: 80%;
                background-position: 20px 80px;
                padding-top: 100px;
            }
        </style>
        """,
            unsafe_allow_html=True,
        )
# add_logo()
st.title("Product Status Dashboard")
# Consolidated radio buttons
#st.markdown(f"### Actions for {brand} ({country})")

col1, col2, col3 = st.columns(3)
with col1:
    country = st.radio("Select Country", ["NL", "BE", "FR"])
    country_code = country.split()[0][:2].upper()
    language = country_code
with col2:
    brand = st.radio("Select Brand", ["Shark", "Ninja"])
    brand_name = brand.split()[0]
# col1, col2 = st.columns(2)
with col3:
    # st.radio("Select Brands", [""])
    st.markdown( f"""
        <div style="
            background-color: #f0f2f6;
            padding: 10px;
            border-radius: 5px;
            margin-right: 10px;
        ">
            Actions for {country}{brand}
        </div>
        """, unsafe_allow_html=True)
    
# Render the HTML in Streamlit
    
    
with col3:
    check_stock_button = st.button("Check Stock", key="check_stock")
    if st.button("Export to Excel", key="export_excel"):
        try:
            out_of_stock_df = read_from_db(country_code, brand_name)
            in_stock_df = read_from_db(country_code, brand_name)
            try:
                skipped_df = read_from_db(f"skipped_urls_{country_code}_{brand_name}")
            except Exception as e:
                skipped_df = pd.DataFrame()

            excel_data = export_to_excel(out_of_stock_df, in_stock_df, skipped_df)

            st.download_button(
                label="Download Excel file",
                data=excel_data,
                file_name=f"products_availability{language}{brand}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        except Exception as e:
            st.error(f"An error occurred while exporting to Excel: {e}")



# Stock checking logic
if check_stock_button:
    try:
        urls = fetch_urls_from_database()
        grouped_urls = group_urls_by_category(urls)

        # Filter URLs based on selected country and brand
        selected_category = f"{country_code}{brand_name}"
        if selected_category in grouped_urls:
            category_urls = grouped_urls[selected_category]
            
            # Initialize empty DataFrames
            out_of_stock_df = pd.DataFrame(columns=["SKU", "Product Name", "Date", "URL", "Status", "Type", "Current Price"])
            in_stock_df = pd.DataFrame(columns=["SKU", "Product Name", "Date", "URL", "Status", "Type", "Current Price"])

            with st.spinner(f"Processing URLs for {country_code} {brand_name}..."):
                (out_of_stock_products, in_stock_products, skipped_urls, processed_products,) = process_urls(category_urls)

            if skipped_urls:
                st.warning(f"Rerunning {len(skipped_urls)} skipped URLs for {country_code} {brand_name}...")
                with st.spinner("Reprocessing skipped URLs..."):
                    (additional_out_of_stock, additional_in_stock, remaining_skipped, processed_products,) = process_urls(skipped_urls, processed_products)

                out_of_stock_products.extend(additional_out_of_stock)
                in_stock_products.extend(additional_in_stock)
                skipped_urls = remaining_skipped

            try:
                if out_of_stock_products:
                    out_of_stock_df = pd.DataFrame(
                        out_of_stock_products,
                        columns=["SKU", "Product Name", "Date", "URL", "Status", "Type", "Current Price"],
                    )
                    out_of_stock_df["Country"] = country_code
                    out_of_stock_df["Brand"] = brand_name
                    save_to_db(out_of_stock_df)
                    st.success(f"Updated {len(out_of_stock_products)} out-of-stock products for {country_code} {brand_name}")
                else:
                    st.write(f"All products are in stock for {country_code} {brand_name}.")

                if in_stock_products:
                    in_stock_df = pd.DataFrame(
                        in_stock_products,
                        columns=["SKU", "Product Name", "Date", "URL", "Status", "Type", "Current Price"],
                    )
                    in_stock_df["Country"] = country_code
                    in_stock_df["Brand"] = brand_name
                    save_to_db(in_stock_df)
                    st.success(f"Updated {len(in_stock_products)} in-stock products for {country_code} {brand_name}")
                else:
                    st.write(f"No products are in stock for {country_code} {brand_name}.")

                # Combine DataFrames and save prices
                all_products_df = pd.concat([out_of_stock_df, in_stock_df], ignore_index=True)
                st.write(f"Total products to update prices: {len(all_products_df)}")
                if not all_products_df.empty:
                    logger.info("Attempting to save prices to database")
                    try:
                        save_prices_to_db(all_products_df, country_code)
                        success_message = f"Prices saved successfully for {country_code} {brand_name}."
                        st.success(success_message)
                        logger.info(success_message)
                    except Exception as e:
                        error_message = f"An error occurred while saving prices: {str(e)}"
                        st.error(error_message)
                        logger.error(error_message)
                        logger.exception("Detailed error information:")
                else:
                    warning_message = f"No products found to save prices for {country_code} {brand_name}."
                    st.warning(warning_message)
                    logger.warning(warning_message)
                
                if skipped_urls:
                    skipped_df = pd.DataFrame(skipped_urls, columns=["URL"])
                    skipped_df["Country"] = country_code
                    skipped_df["Brand"] = brand_name
                    save_to_db(skipped_df, f"skipped_urls_{country_code}_{brand_name}")
                    st.warning(f"{len(skipped_urls)} URLs were skipped after retrying for {country_code} {brand_name}.")
                else:
                    st.success(f"No URLs were skipped in the end for {country_code} {brand_name}.")
            except Exception as e:
                st.error(f"An error occurred while saving products to the database: {e}")
        else:
            st.warning(f"No URLs found for the selected country ({country_code}) and brand ({brand_name}).")

    except Exception as e:
        st.error(f"An error occurred: {e}")
    st.rerun()


col1, col2 = st.columns(2)

with col1:
    country = language #st.radio("Select Country", ["NL", "BE", "FR"])
    country_code = country.split()[0][:2].upper()

with col2:
    brand = brand #st.radio("Select Brand", ["Shark", "Ninja"])
    brand_name = brand.split()[0]

st.markdown("---")

# Create tabs
tab1, tab2, tab3 = st.tabs(["Current Status","Currently Out of Stock", "Out of Stock History"])

with tab1:
        df_outstock = get_dataframe_init(country_code, brand_name)
        df_instock = get_dataframe_init(country_code, brand_name)

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Out of Stock")
            filtered_df_out = df_outstock[df_outstock['status']== 'OUT']
            st.dataframe(filtered_df_out, width=2000)
           

        with col2:
            st.subheader("In Stock")
            filtered_df_in = df_outstock[df_outstock['status']== 'IN']
            st.dataframe(filtered_df_in, width=2000)
   

        st.markdown("---")

        # Display summary statistics
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Total SKUs", len(filtered_df_out) + len(filtered_df_in))

        with col2:
            st.metric("Out of Stock", len(filtered_df_out))

        with col3:
            st.metric("In Stock", len(filtered_df_in))

with tab2:
    # Fetch and display current out of stock dataframe
    df_current_out_of_stock = get_current_out_of_stock(country_code, brand_name)

    st.subheader("📅 Currently Out of Stock")
    edited_df_current_out_of_stock = st.data_editor(
        df_current_out_of_stock,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "LastOutOfStockDate": st.column_config.DatetimeColumn(
                "Last Out of Stock Date",
                format="DD-MM-YYYY",
                step=60,
            ),
        },
    )

    st.markdown("---")

    # Display summary statistics for current out of stock
    col1, col2 = st.columns(2)

    with col1:
        st.metric("Total Currently Out of Stock SKUs", len(df_current_out_of_stock))

    with col2:
        if not df_current_out_of_stock.empty:
            latest_out_of_stock = df_current_out_of_stock['LastOutOfStockDate'].max().strftime('%d-%m-%Y')
            st.metric("Latest Out of Stock Date", latest_out_of_stock)
        else:
            st.metric("Latest Out of Stock Date", "N/A")

with tab3:
    st.subheader("Out of Stock History Analysis")

    df_history = get_out_of_stock_history(country_code, brand_name)

    # 1. Summary metrics


    # 2. Time series of out-of-stock incidents
    
    
    #st.subheader("Detailed Out of Stock History")
    st.dataframe(df_history.sort_values('OutOfStockDate', ascending=False), use_container_width=True)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        total_incidents = len(df_history)
        st.metric("Total Out of Stock Incidents", total_incidents)
    with col2:
        current_out_of_stock = df_history['Status'].value_counts().get('Currently out of stock', 0)
        st.metric("Currently Out of Stock", current_out_of_stock)
    with col3:
        avg_duration = df_history['DaysOutOfStock'].mean()
        st.metric("Average Duration (Days)", f"{avg_duration:.1f}")
    with col4:
        max_duration = df_history['DaysOutOfStock'].max()
        st.metric("Max Duration (Days)", max_duration)


# Add a footer
st.markdown("---")
