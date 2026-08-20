import streamlit as st
import pandas as pd

st.set_page_config(page_title="Google Sheets Connection Test", layout="wide")
st.title("⚡ CCSI Live Operations Data Test")

# Direct CSV export endpoint using your Sheet ID
SHEET_ID = "1RW3LApb5TgMtdtBKqKHfZ3_t3sBQYCuUZqp8owA3ndM"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

@st.cache_data(ttl=5)
def load_data():
    return pd.read_csv(CSV_URL)

try:
    df = load_data()
    st.success("Connected successfully to Google Sheets!")
    st.write(f"**Total rows loaded:** {len(df)}")
    st.dataframe(df, use_container_width=True)
except Exception as e:
    st.error(f"Error fetching data: {e}")
    st.warning("If you see HTTP 401: Verify Step 1 is complete ('Anyone with the link can view').")
