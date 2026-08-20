import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh

# 1. Page Config & Real-Time Auto Refresh (Every 10 seconds)
st.set_page_config(page_title="CCSI Operations Live Dashboard", layout="wide")
st_autorefresh(interval=10000, key="datarefresh")

st.title("⚡ CCSI CDMX & TJ Live Operations Dashboard")
st.caption("Real-Time Tracking: QA, Attendance, Talk Times & Communication Status")

# 2. Google Sheets Configuration & Direct Deep Links
SHEET_OPS_REPORT = "https://docs.google.com/spreadsheets/d/1RW3LApb5TgMtdtBKqKHfZ3_t3sBQYCuUZqp8owA3ndM/export?format=csv&gid=1684808847"
SHEET_BREAK_ARCHIVE = "https://docs.google.com/spreadsheets/d/18WdoYyycy71LWCEUesOq6-uLWqtAo52jD4p12ObGi3k/export?format=csv&gid=1537474403"
SHEET_EMAILS = "https://docs.google.com/spreadsheets/d/1bp9_e-ML_TVCxkvjsr893nhcJmyw1WILWAsgwdAcjUc/export?format=csv&gid=90525846"

URL_EXEC_DASHBOARD = "https://docs.google.com/spreadsheets/d/1RW3LApb5TgMtdtBKqKHfZ3_t3sBQYCuUZqp8owA3ndM/edit#gid=1684808847"
URL_KPIS = "https://docs.google.com/spreadsheets/d/1RW3LApb5TgMtdtBKqKHfZ3_t3sBQYCuUZqp8owA3ndM/edit#gid=90525846"
URL_BREAKS = "https://docs.google.com/spreadsheets/d/18WdoYyycy71LWCEUesOq6-uLWqtAo52jD4p12ObGi3k/edit#gid=1537474403"
URL_EMAILS = "https://docs.google.com/spreadsheets/d/1bp9_e-ML_TVCxkvjsr893nhcJmyw1WILWAsgwdAcjUc/edit#gid=90525846"

# 3. Data Loading Engine
@st.cache_data(ttl=5)
def load_all_data():
    df_ops = pd.read_csv(SHEET_OPS_REPORT)
    df_breaks = pd.read_csv(SHEET_BREAK_ARCHIVE)
    df_emails = pd.read_csv(SHEET_EMAILS)
    return df_ops, df_breaks, df_emails

try:
    df_ops, df_breaks, df_emails = load_all_data()
except Exception as e:
    st.error("Error reading live data from Google Sheets. Ensure sheets are set to 'Anyone with the link can view'.")
    st.stop()

# 4. Top Real-Time KPI Cards
df_ops["Schedule Adherence Clean"] = df_ops["Schedule Adherence"].str.rstrip("%").astype(float)
df_ops["Status Adherence Clean"] = df_ops["Status Adherence %"].str.rstrip("%").astype(float)

avg_adherence = df_ops["Status Adherence Clean"].mean()
total_absences = df_ops["Unexcused Absences"].sum()
total_lateness = df_ops["Lateness >than 5 mins"].sum()
pending_emails = len(df_emails[df_emails["Status"] == "Awaiting Reply"])

m1, m2, m3, m4 = st.columns(4)
m1.metric("Avg Status Adherence", f"{avg_adherence:.2f}%", delta=f"{avg_adherence - 88.0:.2f}% vs 88% Target")
m2.metric("Total Unexcused Absences", f"{int(total_absences)}", delta="Goal: < 1", delta_color="inverse")
m3.metric("Lateness Incidents (>5m)", f"{int(total_lateness)}", delta="Goal: < 2", delta_color="inverse")
m4.metric("Emails Awaiting Reply", f"{pending_emails} Pending", delta_color="off")

st.divider()

# 5. Agent Coaching & Performance Action Matrix
col_left, col_right = st.columns([2, 1])

with col_left:
    st.subheader("🔴 Agents Requiring Immediate Intervention")
    critical_agents = df_ops[
        (df_ops["Status Adherence Clean"] < 88.0) | 
        (df_ops["Unexcused Absences"] > 0) | 
        (df_ops["Lateness >than 5 mins"] >= 2) |
        (df_ops["Coaching Priority"].notna())
    ][["Agent Name", "Status Adherence %", "Unexcused Absences", "Lateness >than 5 mins", "Coaching Priority"]]

    st.dataframe(critical_agents, use_container_width=True, hide_index=True)

with col_right:
    st.subheader("🔗 Direct Sheet Navigation")
    st.write("Jump straight to the underlying source data tabs:")
    st.link_button("📊 Executive Dashboard Sheet", URL_EXEC_DASHBOARD, use_container_width=True)
    st.link_button("🎯 Operational KPIs Sheet", URL_KPIS, use_container_width=True)
    st.link_button("⏱️ Historical Breaks & Meals Log", URL_BREAKS, use_container_width=True)
    st.link_button("✉️ Individual Email View", URL_EMAILS, use_container_width=True)

st.divider()

# 6. Operational Email & Communication Tracker
st.subheader("✉️ Action Required: Communication & Inbox Bounces")
tab1, tab2 = st.tabs(["Awaiting Reply", "Full Log / Delivery Bounces"])

with tab1:
    st.dataframe(
        df_emails[df_emails["Status"] == "Awaiting Reply"][["Email Address", "Date Sent", "Subject", "Latest Message / Context"]],
        use_container_width=True, hide_index=True
    )

with tab2:
    st.dataframe(df_emails, use_container_width=True, hide_index=True)
