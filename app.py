import streamlit as st
import pandas as pd
import base64
from streamlit_autorefresh import st_autorefresh

# 1. Page Configuration & Auto-Refresh
st.set_page_config(
    page_title="CCSI & ACSI Operations Dashboard", 
    page_icon="⚡", 
    layout="wide"
)
st_autorefresh(interval=15000, key="datarefresh")

# Base64 helper to convert local images to embeddable strings
def get_image_base64(file_path):
    try:
        with open(file_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode()
    except Exception:
        return None

# Convert local files to base64
ccsi_b64 = get_image_base64("ccsi_logo.png")
acsi_b64 = get_image_base64("acsi_logo.png")

# Custom Styling
st.markdown("""
    <style>
    [data-testid="stMetricValue"] { color: #E31B23 !important; font-weight: bold; }
    .stButton>button, div[data-testid="stLinkButton"]>a {
        background-color: #E31B23 !important; color: white !important; border-radius: 6px; border: none; font-weight: bold;
    }
    .header-title {
        border-left: 6px solid #007AC1;
        padding-left: 12px;
        font-size: 2rem;
        font-weight: bold;
        color: #111111;
    }
    </style>
""", unsafe_allow_html=True)

# Layout Columns
col_ccsi, col_acsi, col_title = st.columns([1.2, 1.2, 5])

with col_ccsi:
    if ccsi_b64:
        st.markdown(f'<img src="data:image/png;base64,{ccsi_b64}" width="140">', unsafe_allow_html=True)
    else:
        st.markdown("### **CCSi**")

with col_acsi:
    if acsi_b64:
        st.markdown(f'<img src="data:image/png;base64,{acsi_b64}" width="140">', unsafe_allow_html=True)
    else:
        st.markdown("### **ACSI**")

with col_title:
    st.markdown('<div class="header-title">⚡ Operations Command Dashboard</div>', unsafe_allow_html=True)
    st.caption("Call Center Services International & Allied Customer Solutions | Target: ≥88% Adherence")

st.divider()
