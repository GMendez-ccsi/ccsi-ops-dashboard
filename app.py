import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh

# 1. Page Configuration & Auto-Refresh (Every 15 Seconds)
st.set_page_config(
    page_title="CCSI Operations Live Dashboard",
    page_icon="⚡",
    layout="wide"
)
st_autorefresh(interval=15000, key="datarefresh")

# Custom Styling for Clean Metrics & Card Layout
st.markdown("""
    <style>
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 15px;
        border-left: 5px solid #0066cc;
    }
    div[data-testid="stMetricValue"] {
        font-size: 28px;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

st.title("⚡ CCSI CDMX & TJ Live Operations Command Dashboard")
st.caption("Tactical Real-Time Tracking: Operational Metrics, Compliance & Deep Sheet Links")

# 2. Source Configuration
SHEET_ID = "18WdoYyycy71LWCEUesOq6-uLWqtAo52jD4p12ObGi3k"
GID = "1537474403"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"
URL_EXEC_DASHBOARD = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit#gid={GID}"

# 3. Data Engine
@st.cache_data(ttl=5)
def load_data(url):
    df = pd.read_csv(url, engine="python", on_bad_lines="skip")
    return df.dropna(how="all")

try:
    df_raw = load_data(CSV_URL)
    
    # 4. Top-Level Metric Summary Cards
    m1, m2, m3, m4 = st.columns(4)
    
    total_records = len(df_raw)
    total_cols = len(df_raw.columns)
    
    with m1:
        st.metric(label="📋 Active Records Loaded", value=f"{total_records} Rows")
    with m2:
        st.metric(label="📊 Tracked Data Columns", value=f"{total_cols} Fields")
    with m3:
        st.metric(label="🟢 System Status", value="Online / Syncing")
    with m4:
        st.link_button("🔗 Open Master Google Sheet", URL_EXEC_DASHBOARD, use_container_width=True)

    st.divider()

    # 5. Search Bar & Interactive Multi-Tab Interface
    st.subheader("🔍 Operations Data Explorer")
    
    search_query = st.text_input("Filter across all records (Search Agent, Status, Subject, or Date):", "")
    
    # Filter dataset dynamically based on search
    if search_query:
        mask = df_raw.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)
        df_display = df_raw[mask]
    else:
        df_display = df_raw

    # Organize Views into Navigable Tabs
    tab1, tab2, tab3 = st.tabs(["📊 Full Active Feed", "🎯 Filtered View", "ℹ️ Data Structure"])

    with tab1:
        st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True,
            height=450
        )

    with tab2:
        st.caption("Use column selectors to drill down into specific operational metrics:")
        selected_cols = st.multiselect("Select columns to display:", df_raw.columns.tolist(), default=df_raw.columns.tolist()[:5])
        if selected_cols:
            st.dataframe(df_display[selected_cols], use_container_width=True, hide_index=True)

    with tab3:
        col_a, col_b = st.columns(2)
        with col_a:
            st.write("**Column Data Types:**")
            st.json(df_raw.dtypes.astype(str).to_dict())
        with col_b:
            st.write("**Summary Statistics:**")
            st.write(df_raw.describe(include="all").fillna(""))

except Exception as e:
    st.error(f"Error rendering dashboard view: {e}")
