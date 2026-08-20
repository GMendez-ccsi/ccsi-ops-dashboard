import streamlit as st
import pandas as pd

st.set_page_config(page_title="Google Sheet Tab Test", layout="wide")
st.title("🧪 Google Sheets Live Data Test (Specific Tab)")

# URL pointing directly to tab gid=1684808847
SHEET_URL = "https://docs.google.com/spreadsheets/d/1RW3LApb5TgMtdtBKqKHfZ3_t3sBQYCuUZqp8owA3ndM/export?format=csv&gid=1684808847"

@st.cache_data(ttl=5)
def load_data():
    return pd.read_csv(SHEET_URL)

try:
    df = load_data()
    st.success("Successfully connected to the specific Google Sheet tab!")
    st.write(f"**Total Records Loaded:** {len(df)}")
    st.dataframe(df, use_container_width=True)
except Exception as e:
    st.error(f"Failed to fetch Google Sheet tab data: {e}")
