import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh

# 1. Page Config & Real-Time Auto Refresh (Every 10 seconds)
st.set_page_config(page_title="CCSI Operations Live Dashboard", layout="wide")
st_autorefresh(interval=10000, key="datarefresh")

st.title("⚡ CCSI CDMX & TJ Live Operations Dashboard")
st.caption("Real-Time Tracking: QA, Attendance, Talk Times & Communication Status")

# 2. Source URLs & Direct Sheet Deep Links
# Direct CSV Export Link derived from your provided Google Sheet
SHEET_OPS_REPORT = "https://docs.google.com/spreadsheets/d/1RW3LApb5TgMtdtBKqKHfZ3_t3sBQYCuUZqp8owA3ndM/export?format=csv&gid=1684808847"

URL_EXEC_DASHBOARD = "https://docs.google.com/spreadsheets/d/1RW3LApb5TgMtdtBKqKHfZ3_t3sBQYCuUZqp8owA3ndM/edit#gid=1684808847"

# 3. Data Loading Engine with Fallback Handling
@st.cache_data(ttl=5)
def load_data(url):
    return pd.read_csv(url)

try:
    df_ops = load_data(SHEET_OPS_REPORT)
    st.success("Connected successfully to Google Sheets!")
    
    # Render Main Data Table
    st.subheader("📊 Live Operations Data")
    st.dataframe(df_ops, use_container_width=True)

except Exception as e:
    st.error(f"Failed to fetch live data from Google Sheets. Error: {e}")
    st.warning("⚠️ **Why is this happening?** Your Google Workspace domain security is blocking automated server access (HTTP 401: Unauthorized).")
    
    st.markdown("""
    ### How to resolve this in 30 seconds:
    1. Open your Google Sheet: [Click Here to Open Sheet](https://docs.google.com/spreadsheets/d/1RW3LApb5TgMtdtBKqKHfZ3_t3sBQYCuUZqp8owA3ndM/edit?usp=sharing)
    2. Click **File** (top left menu) $\\rightarrow$ **Share** $\\rightarrow$ **Publish to web**.
    3. Change **Web page** to **Comma-separated values (.csv)**.
    4. Click **Publish** and copy the generated link.
    5. Replace `SHEET_OPS_REPORT` in `app.py` with your new published link.
    """)

st.divider()

# 4. Direct Navigation Links
st.subheader("🔗 Quick Access Links")
st.link_button("📊 Open Executive Dashboard Google Sheet", URL_EXEC_DASHBOARD, use_container_width=True)
