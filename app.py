import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh

# 1. Page Configuration & Auto-Refresh
st.set_page_config(page_title="CCSI Operations Live Dashboard", page_icon="⚡", layout="wide")
st_autorefresh(interval=15000, key="datarefresh")

st.title("⚡ CCSI CDMX & TJ Live Operations Command Dashboard")
st.caption("Tactical Real-Time Tracking: Exceeded Breaks Breakdown by Site, Role & Agent")

# 2. Source Configuration
SHEET_ID = "18WdoYyycy71LWCEUesOq6-uLWqtAo52jD4p12ObGi3k"
GID = "1537474403"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"
URL_EXEC_DASHBOARD = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit#gid={GID}"

# Helper function to convert HH:MM:SS or MM:SS to total minutes
def time_to_minutes(time_str):
    if pd.isna(time_str) or not isinstance(time_str, str):
        return 0.0
    try:
        parts = time_str.strip().split(":")
        if len(parts) == 3:
            return int(parts[0]) * 60 + int(parts[1]) + int(parts[2]) / 60.0
        elif len(parts) == 2:
            return int(parts[0]) + int(parts[1]) / 60.0
    except Exception:
        return 0.0
    return 0.0

@st.cache_data(ttl=5)
def load_and_process_data(url):
    df = pd.read_csv(url, engine="python", on_bad_lines="skip").dropna(how="all")
    
    # Clean column names
    df.columns = df.columns.str.strip()
    
    # Calculate Break Minutes per entry
    if "Total Break" in df.columns:
        df["Break_Minutes"] = df["Total Break"].apply(time_to_minutes)
    else:
        df["Break_Minutes"] = 0.0
        
    return df

try:
    df_raw = load_and_process_data(CSV_URL)

    # 3. Exceeded Breaks Aggregation Logic (Per Week, Agent Name, Site, and Role)
    if all(col in df_raw.columns for col in ["week", "Agent Name", "site", "role"]):
        break_summary = (
            df_raw.groupby(["week", "site", "role", "Agent Name"], as_index=False)
            .agg(
                Total_Break_Mins=("Break_Minutes", "sum"),
                Days_Logged=("Date", "nunique") if "Date" in df_raw.columns else ("Break_Minutes", "count")
            )
        )
        
        # Calculate weekly threshold: 30 mins per day logged
        break_summary["Weekly_Threshold_Mins"] = break_summary["Days_Logged"] * 30
        break_summary["Exceeded_Mins"] = break_summary["Total_Break_Mins"] - break_summary["Weekly_Threshold_Mins"]
        
        # Filter strictly for agents who EXCEEDED their allowed break time
        exceeded_df = break_summary[break_summary["Exceeded_Mins"] > 0].sort_values(
            by=["week", "Exceeded_Mins"], ascending=[False, False]
        )
    else:
        exceeded_df = pd.DataFrame()

    # 4. Filters Section (Week, Site, Role)
    st.subheader("🔍 Filters & Drilldown")
    f1, f2, f3 = st.columns(3)
    
    with f1:
        weeks = ["All Weeks"] + sorted(df_raw["week"].dropna().unique().tolist(), reverse=True) if "week" in df_raw.columns else ["All Weeks"]
        selected_week = st.selectbox("Work Week:", weeks)
        
    with f2:
        sites = ["All Sites"] + sorted(df_raw["site"].dropna().unique().tolist()) if "site" in df_raw.columns else ["All Sites"]
        selected_site = st.selectbox("Site:", sites)
        
    with f3:
        roles = ["All Roles"] + sorted(df_raw["role"].dropna().unique().tolist()) if "role" in df_raw.columns else ["All Roles"]
        selected_role = st.selectbox("Role:", roles)

    # Apply Filters to Exceeded Breaks Data
    filtered_exceeded = exceeded_df.copy()
    if not filtered_exceeded.empty:
        if selected_week != "All Weeks":
            filtered_exceeded = filtered_exceeded[filtered_exceeded["week"] == selected_week]
        if selected_site != "All Sites":
            filtered_exceeded = filtered_exceeded[filtered_exceeded["site"] == selected_site]
        if selected_role != "All Roles":
            filtered_exceeded = filtered_exceeded[filtered_exceeded["role"] == selected_role]

    # 5. Top KPI Ribbon based on filtered selection
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("🚨 Total Violations", f"{len(filtered_exceeded)} Agents")
    with m2:
        total_exceeded = filtered_exceeded["Exceeded_Mins"].sum() if not filtered_exceeded.empty else 0
        st.metric("⏱️ Total Overage Time", f"{int(total_exceeded)} Mins")
    with m3:
        avg_overage = filtered_exceeded["Exceeded_Mins"].mean() if not filtered_exceeded.empty else 0
        st.metric("📊 Avg Overage / Agent", f"{int(avg_overage)} Mins")
    with m4:
        st.link_button("🔗 Open Master Sheet", URL_EXEC_DASHBOARD, use_container_width=True)

    st.divider()

    # 6. Site & Role Summary Breakdown Cards
    if not filtered_exceeded.empty:
        col_site, col_role = st.columns(2)
        
        with col_site:
            st.markdown("### 🏢 Overage by Site")
            site_summary = (
                filtered_exceeded.groupby("site", as_index=False)
                .agg(Violations=("Agent Name", "count"), Total_Exceeded_Mins=("Exceeded_Mins", "sum"))
            )
            site_summary["Total_Exceeded_Mins"] = site_summary["Total_Exceeded_Mins"].apply(lambda x: f"{int(x)} mins")
            st.dataframe(site_summary, use_container_width=True, hide_index=True)
            
        with col_role:
            st.markdown("### 👤 Overage by Role")
            role_summary = (
                filtered_exceeded.groupby("role", as_index=False)
                .agg(Violations=("Agent Name", "count"), Total_Exceeded_Mins=("Exceeded_Mins", "sum"))
            )
            role_summary["Total_Exceeded_Mins"] = role_summary["Total_Exceeded_Mins"].apply(lambda x: f"{int(x)} mins")
            st.dataframe(role_summary, use_container_width=True, hide_index=True)

    st.divider()

    # 7. Detailed Table View per Site, Role, and Agent Name
    st.subheader("🔴 Exceeded Break Time Table (Per Site, Role & Agent)")

    if not filtered_exceeded.empty:
        formatted_table = filtered_exceeded.copy()
        formatted_table["Total Break Time"] = formatted_table["Total_Break_Mins"].apply(lambda x: f"{int(x)} mins")
        formatted_table["Allowed Time"] = formatted_table["Weekly_Threshold_Mins"].apply(lambda x: f"{int(x)} mins")
        formatted_table["Time Exceeded"] = formatted_table["Exceeded_Mins"].apply(lambda x: f"+{int(x)} mins")
        
        st.dataframe(
            formatted_table[["week", "site", "role", "Agent Name", "Days_Logged", "Total Break Time", "Allowed Time", "Time Exceeded"]],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.success("🎉 No break threshold violations found for the selected Site, Role, and Week filters!")

    st.divider()

    # 8. Raw Activity Feed
    with st.expander("📋 View Full Raw Activity Feed"):
        st.dataframe(df_raw, use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Error processing break calculations: {e}")
