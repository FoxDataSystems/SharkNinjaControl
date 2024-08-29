import streamlit as st
import mysql.connector
import pandas as pd
import plotly.express as px
from datetime import date, datetime
import io

st.set_page_config(layout="wide", page_title="SKU Price Manager")
# make_sidebar()
st.markdown(
    """
<style>
    [data-testid="collapsedControl"] {
        display: none
    }
</style>
""",
    unsafe_allow_html=True,
)
class PriceManager:
    def __init__(self):
        self.conn = mysql.connector.connect(
            host="localhost",
            port=2000,
            user="sharkninja_user",
            password="3m3r4ld0",
            database="sharkninja_prd"
        )
        self.cursor = self.conn.cursor(dictionary=True)

    def upsert_price(self, sku, price, entry_date, reason, country):
        # Get ProductID and CountryID
        self.cursor.execute("SELECT productid FROM products WHERE sku = %s", (sku,))
        product_id = self.cursor.fetchone()
        if not product_id:
            self.cursor.execute("INSERT INTO products (sku, productname) VALUES (%s, %s)", (sku, f"Product {sku}"))
            product_id = self.cursor.lastrowid
        else:
            product_id = product_id['productid']

        self.cursor.execute("SELECT countryid FROM countries WHERE countrycode = %s", (country,))
        country_id = self.cursor.fetchone()
        if not country_id:
            self.cursor.execute("INSERT INTO countries (countrycode) VALUES (%s)", (country,))
            country_id = self.cursor.lastrowid
        else:
            country_id = country_id['countryid']

        # Insert or update price
        self.cursor.execute('''
            INSERT INTO prices (productid, countryid, price, entrydate, reason) 
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE price = %s, reason = %s
        ''', (product_id, country_id, price, entry_date, reason, price, reason))
        self.conn.commit()

    def get_price_history(self, sku, country=None, days=None):
        query = '''
            SELECT p.entrydate, p.price, p.reason, c.countrycode as country 
            FROM prices p
            JOIN products pr ON p.productid = pr.productid
            JOIN countries c ON p.countryid = c.countryid
            WHERE pr.sku = %s
        '''
        params = [sku]
        if country:
            query += " AND c.countrycode = %s"
            params.append(country)
        if days:
            query += f" AND p.entrydate >= DATE_SUB(CURDATE(), INTERVAL {days} DAY)"
        query += " ORDER BY p.entrydate DESC"
        
        self.cursor.execute(query, params)
        return pd.DataFrame(self.cursor.fetchall())

    def delete_entry(self, sku, entry_date, country):
        self.cursor.execute('''
            DELETE FROM prices 
            WHERE productid = (SELECT productid FROM products WHERE sku = %s)
            AND countryid = (SELECT countryid FROM countries WHERE countrycode = %s)
            AND entrydate = %s
        ''', (sku, country, entry_date))
        self.conn.commit()
        return self.cursor.rowcount

    def search_skus(self, term):
        self.cursor.execute("SELECT DISTINCT sku FROM products WHERE sku LIKE %s", (f'%{term}%',))
        return [row['sku'] for row in self.cursor.fetchall()]

    def export_data(self):
        query = '''
            SELECT pr.sku, p.price, p.entrydate, p.reason, c.countrycode as Country
            FROM prices p
            JOIN products pr ON p.productid = pr.productid
            JOIN countries c ON p.countryid = c.countryid
        '''
        df = pd.read_sql_query(query, self.conn)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Prices')
        return output.getvalue()

    def get_price_changes_by_date(self, search_date, country):
        query = '''
            SELECT pr.sku, p.price, p.reason
            FROM prices p
            JOIN products pr ON p.productid = pr.productid
            JOIN countries c ON p.countryid = c.countryid
            WHERE p.entrydate = %s AND c.countrycode = %s
        '''
        self.cursor.execute(query, (search_date, country))
        return pd.DataFrame(self.cursor.fetchall())

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
# Call add_logo function


def main():
    pm = PriceManager()

    st.title('SKU Price Manager')

    col1, col2 = st.columns([1, 3])

    with col1:
        country = st.radio("Select Country:", ["NL", "BE", "FR"])
        if st.button('Export to Excel'):
            st.download_button(
                label="Download Excel file",
                data=pm.export_data(),
                file_name="price_database.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    with col2:
        tab1, tab2, tab3, tab4 = st.tabs(
            ["Manage Prices", "Price History", "Search by Date", "Delete Entries"])

        with tab1:
            st.subheader("Manage Prices")
        
            # Initialize session state
            if 'adding_new_sku' not in st.session_state:
                st.session_state.adding_new_sku = False
        
            # Button to toggle between adding new SKU and selecting existing SKU
            if st.button('Add New SKU' if not st.session_state.adding_new_sku else 'Select Existing SKU'):
                st.session_state.adding_new_sku = not st.session_state.adding_new_sku
        
            # Display either selectbox or text input based on state
            if st.session_state.adding_new_sku:
                sku = st.text_input('Enter new SKU:', key='new_sku_input')
            else:
                sku = st.selectbox('Select SKU:', [''] + pm.search_skus(''), key='manage_sku')
        
            price = st.number_input('Price (€):', min_value=0.0, format='%.2f')
            reason = st.text_input('Reason for change:')
            entry_date = st.date_input("Date:", value=date.today())
        
            if st.button('Submit'):
                if sku and price and reason:
                    pm.upsert_price(sku, price, entry_date, reason, country)
                    st.success(f'Price updated for SKU {sku}: €{price:.2f} on {entry_date}')
                    # Reset to selectbox mode after successful submission
                    st.session_state.adding_new_sku = False
                    st.rerun()
                else:
                    st.error('Please fill all fields.')

        with tab2:
            st.subheader("Price History")

            col1, col2 = st.columns([1, 2])

            with col1:
                lookup_sku = st.selectbox('Select or Enter SKU:', [''] + pm.search_skus(''), key='history_sku')
                show_all = st.checkbox("Show all countries")

            if lookup_sku:
                df = pm.get_price_history(lookup_sku, None if show_all else country)
                df_30_days = pm.get_price_history(lookup_sku, None if show_all else country, days=30)

                if not df.empty:
                    with col2:
                        if not df_30_days.empty:
                            lowest_price_30_days = df_30_days['price'].min()
                            st.metric("Lowest price (last 30 days)", f"€{lowest_price_30_days:.2f}")

                    st.plotly_chart(
                        px.line(df, x='entrydate', y='price', color='country' if show_all else None,
                                title=f'Price History for {lookup_sku}')
                        .update_layout(yaxis_title='Price (€)', xaxis_title='Date'),
                        use_container_width=True
                    )

                    st.dataframe(
                        df.style.format({'price': '€{:.2f}'})
                           .set_properties(**{'text-align': 'left'}),
                        use_container_width=True
                    )
                else:
                    st.info(f"No price history found for {lookup_sku}")

        with tab3:
            st.subheader("Search by Date")
            search_date = st.date_input(
                "Select date to search for price changes:", key='search_date')

            if st.button('Search Price Changes'):
                changes_df = pm.get_price_changes_by_date(search_date, country)
                if not changes_df.empty:
                    st.write(f"Price changes on {search_date}:")
                    st.dataframe(changes_df.style.format({'price': '€{:.2f}'}))
                else:
                    st.info(f"No price changes found on {search_date}")

        with tab4:
            st.subheader("Delete Entries")
            del_sku = st.selectbox('Select SKU:', [''] + pm.search_skus(''), key='delete_sku')
        
            if del_sku:
                df = pm.get_price_history(del_sku, country)
                if not df.empty:
                    st.write(f"Current entries for {del_sku} in {country}:")
        
                    # Add the 'delete' column
                    df['delete'] = False
        
                    # Use st.data_editor for inline editing and row selection
                    edited_df = st.data_editor(
                        df,
                        hide_index=True,
                        column_config={
                            "entrydate": st.column_config.DateColumn("Date"),
                            "price": st.column_config.NumberColumn("Price (€)", format="€%.2f"),
                            "reason": "Reason",
                            "delete": st.column_config.CheckboxColumn("Delete?")
                        },
                        disabled=["entrydate", "price", "reason"],
                        key="editor"
                    )
        
                    # Filter rows marked for deletion
                    rows_to_delete = edited_df[edited_df['delete'] == True]
        
                    if not rows_to_delete.empty:
                        if st.button("Delete Selected Entries"):
                            for _, row in rows_to_delete.iterrows():
                                pm.delete_entry(del_sku, row['entrydate'], country)
                            st.success(f"Deleted {len(rows_to_delete)} entries for SKU {del_sku}")
                            st.rerun()
                    else:
                        st.info("Select entries to delete by checking the 'Delete?' column")
                else:
                    st.info(f"No entries found for SKU {del_sku} in {country}")

if __name__ == "__main__":
    main()