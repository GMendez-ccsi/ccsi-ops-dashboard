import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh

# 1. Page Config & Real-Time Auto Refresh
st.set_page_config(page_title="CCSI Operations Live Dashboard", layout="wide")
st_autorefresh(interval=10000, key="datarefresh")

st.title("⚡ CCSI CDMX & TJ Live Operations Dashboard")
st.caption("Real-Time Tracking: QA, Attendance, Talk Times & Communication Status")

# 2. Source URL
SHEET_OPS_REPORT = "https://docs.google.com/spreadsheets/d/1RW3LApb5TgMtdtBKqKHfZ3_t3sBQYCuUZqp8owA3ndM/export?format=csv&gid=1684808847"
URL_EXEC_DASHBOARD = "https://docs.google.com/spreadsheets/d/1RW3LApb5TgMtdtBKqKHfZ3_t3sBQYCuUZqp8owA3ndM/edit#gid=1684808847"

# 3. Robust Data Loader (Handles uneven rows and header gaps)
@st.cache_data(ttl=5)
def load_data(url):
    # 'python' engine + on_bad_lines='skip' ignores broken row formatting seamlessly
    return pd.read_csv(url, engine="python", on_bad_lines="skip")

try:
    df_ops = load_data(SHEET_OPS_REPORT)
    st.success("Connected successfully to Google Sheets!")
    
    # Clean empty rows/columns if present
    df_ops = df_ops.dropna(how="all")
    
    # Render Data Table
    st.subheader("📊 Live Operations Data")
    st.dataframe(df_ops, use_container_width=True)

except Exception as e:
    st.error(f"Error parsing sheet data: {e}")

st.divider()

# 4. Direct Navigation Links
st.subheader("🔗 Quick Access Links")
st.link_button("📊 Open Executive Dashboard Google Sheet", URL_EXEC_DASHBOARD, use_container_width=True)
