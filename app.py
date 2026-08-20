import streamlit as st
import pandas as pd

st.set_page_config(page_title="Google Sheet Test", layout="wide")
st.title("🧪 Google Sheets Live Data Test")

# Test URL for your provided Google Sheet
SHEET_URL = "https://docs.google.com/spreadsheets/d/1RW3LApb5TgMtdtBKqKHfZ3_t3sBQYCuUZqp8owA3ndM/export?format=csv"

@st.cache_data(ttl=5)
def load_data():
    return pd.read_csv(SHEET_URL)

try:
    df = load_data()
    st.success("Successfully connected to Google Sheets!")
    st.write(f"**Total Records Loaded:** {len(df)}")
    st.dataframe(df, use_container_width=True)
except Exception as e:
    st.error(f"Failed to fetch Google Sheet data: {e}")
    st.info("Troubleshooting: Ensure the Google Sheet sharing setting is set to 'Anyone with the link can view'.")
