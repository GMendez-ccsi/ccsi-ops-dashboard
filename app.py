import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh

# 1. Page Config & Real-Time Auto Refresh
st.set_page_config(page_title="CCSI Operations Live Dashboard", layout="wide")
st_autorefresh(interval=10000, key="datarefresh")

st.title("⚡ CCSI CDMX & TJ Live Operations Dashboard")
st.caption("Real-Time Tracking: QA, Attendance, Talk Times & Communication Status")

# 2. Source URL for the new Sheet and Tab
SHEET_ID = "18WdoYyycy71LWCEUesOq6-uLWqtAo52jD4p12ObGi3k"
GID = "1537474403"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"
URL_EXEC_DASHBOARD = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit#gid={GID}"

# 3. Robust Data Loader
@st.cache_data(ttl=5)
def load_data(url):
    return pd.read_csv(url, engine="python", on_bad_lines="skip")

try:
    df_ops = load_data(CSV_URL)
    st.success("Connected successfully to Google Sheets!")
    
    # Clean empty rows
    df_ops = df_ops.dropna(how="all")
    
    # Render Data Table
    st.subheader("📊 Live Operations Data")
    st.dataframe(df_ops, use_container_width=True)

except Exception as e:
    st.error(f"Error fetching sheet data: {e}")

st.divider()

# 4. Direct Navigation Links
st.subheader("🔗 Quick Access Links")
st.link_button("📊 Open Executive Dashboard Google Sheet", URL_EXEC_DASHBOARD, use_container_width=True)
