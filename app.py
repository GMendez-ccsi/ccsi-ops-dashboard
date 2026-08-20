import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh

# 1. Page Configuration & Auto-Refresh
st.set_page_config(page_title="CCSI Operations Live Dashboard", page_icon="⚡", layout="wide")
st_autorefresh(interval=15000, key="datarefresh")

st.title("⚡ CCSI CDMX & TJ Live Operations Command Dashboard")
st.caption("Tactical Real-Time Tracking: Weekly Break Compliance & Tactical Metrics")

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

    # 3. Exceeded Breaks Aggregation Logic
    # Group by 'week' and 'Agent Name'
    if "week" in df_raw.columns and "Agent Name" in df_raw.columns:
        break_summary = (
            df_raw.groupby(["week", "Agent Name", "site", "role"], as_index=False)
            .agg(
                Total_Break_Mins=("Break_Minutes", "sum"),
                Days_Logged=("Date", "nunique")
            )
        )
        
        # Calculate weekly threshold: 30 mins per day logged (or default 150 mins for 5-day week)
        break_summary["Weekly_Threshold_Mins"] = break_summary["Days_Logged"] * 30
        break_summary["Exceeded_Mins"] = break_summary["Total_Break_Mins"] - break_summary["Weekly_Threshold_Mins"]
        
        # Filter strictly for agents who EXCEEDED their allowed break time
        exceeded_df = break_summary[break_summary["Exceeded_Mins"] > 0].sort_values(
            by=["week", "Exceeded_Mins"], ascending=[False, False]
        )
    else:
        exceeded_df = pd.DataFrame()

    # 4. Top KPI Ribbon
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("🚨 Total Break Violations", f"{len(exceeded_df)} Incidents")
    with m2:
        total_exceeded = exceeded_df["Exceeded_Mins"].sum() if not exceeded_df.empty else 0
        st.metric("⏱️ Total Overage Time", f"{int(total_exceeded)} Mins")
    with m3:
        st.metric("🟢 System Sync", "Active")
    with m4:
        st.link_button("🔗 Open Master Sheet", URL_EXEC_DASHBOARD, use_container_width=True)

    st.divider()

    # 5. Dedicated Exceeded Break Matrix Section
    st.subheader("🔴 Exceeded Break Time Per Week / Per Agent")
    
    # Week Filter Dropdown
    if "week" in df_raw.columns:
        weeks_list = ["All Weeks"] + sorted(df_raw["week"].dropna().unique().tolist(), reverse=True)
        selected_week = st.selectbox("Filter by Work Week:", weeks_list)
        
        if selected_week != "All Weeks":
            display_exceeded = exceeded_df[exceeded_df["week"] == selected_week]
        else:
            display_exceeded = exceeded_df
    else:
        display_exceeded = exceeded_df

    # Display Clean Exceeded Breaks Table
    if not display_exceeded.empty:
        # Format table for executive presentation
        formatted_table = display_exceeded.copy()
        formatted_table["Total Break Time"] = formatted_table["Total_Break_Mins"].apply(lambda x: f"{int(x)} mins")
        formatted_table["Allowed Time"] = formatted_table["Weekly_Threshold_Mins"].apply(lambda x: f"{int(x)} mins")
        formatted_table["Time Exceeded"] = formatted_table["Exceeded_Mins"].apply(lambda x: f"+{int(x)} mins")
        
        st.dataframe(
            formatted_table[["week", "Agent Name", "site", "role", "Days_Logged", "Total Break Time", "Allowed Time", "Time Exceeded"]],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.success("🎉 No break threshold violations found for the selected view!")

    st.divider()

    # 6. Full Raw Data Feed Tab
    with st.expander("📋 View Full Raw Activity Feed"):
        st.dataframe(df_raw, use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Error processing break calculations: {e}")
