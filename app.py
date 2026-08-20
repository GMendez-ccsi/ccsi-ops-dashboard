import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh

# 1. Page Configuration & Auto-Refresh
st.set_page_config(page_title="CCSI Operations Live Dashboard", page_icon="⚡", layout="wide")
st_autorefresh(interval=15000, key="datarefresh")

st.title("⚡ CCSI CDMX & TJ Live Operations Command Dashboard")
st.caption("Tactical Real-Time Tracking: Status Adherence % (Target: ≥88%) & Break Overages")

# 2. Source Configuration
SHEET_ID = "18WdoYyycy71LWCEUesOq6-uLWqtAo52jD4p12ObGi3k"
GID = "1537474403"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"
URL_EXEC_DASHBOARD = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit#gid={GID}"

# Helper function to convert duration strings to total minutes
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
    df.columns = df.columns.str.strip()
    
    # Duration Columns Conversion
    time_cols = [
        "Total Break", "Total Meal", "Total EM/TA/Tow", "Total Meeting", 
        "Total Supervisor", "Total Tech Issue", "Total Training", "Unaccounted"
    ]
    
    for col in time_cols:
        if col in df.columns:
            df[f"{col}_Mins"] = df[col].apply(time_to_minutes)
        else:
            df[f"{col}_Mins"] = 0.0

    return df

try:
    df_raw = load_and_process_data(CSV_URL)

    # 3. Adherence and Break Calculations
    # Expected shift duration base (480 mins / 8 hrs active shift)
    SHIFT_MINS_PER_DAY = 480.0 

    if all(col in df_raw.columns for col in ["week", "Agent Name", "site", "role"]):
        adherence_summary = (
            df_raw.groupby(["week", "site", "role", "Agent Name"], as_index=False)
            .agg(
                Days_Logged=("Date", "nunique") if "Date" in df_raw.columns else ("Total Break_Mins", "count"),
                Total_Break_Mins=("Total Break_Mins", "sum"),
                Total_Meal_Mins=("Total Meal_Mins", "sum"),
                Unaccounted_Mins=("Unaccounted_Mins", "sum"),
                Non_Adherent_Mins=("Total Tech Issue_Mins", "sum")
            )
        )
        
        # Calculate Total Shift Time and Adherence %
        adherence_summary["Scheduled_Mins"] = adherence_summary["Days_Logged"] * SHIFT_MINS_PER_DAY
        
        # Break Overages (Beyond 30 mins/day)
        adherence_summary["Allowed_Break_Mins"] = adherence_summary["Days_Logged"] * 30.0
        adherence_summary["Exceeded_Break_Mins"] = (
            adherence_summary["Total_Break_Mins"] - adherence_summary["Allowed_Break_Mins"]
        ).clip(lower=0)
        
        # Total Non-Adherent Minutes (Unaccounted + Break Overages)
        adherence_summary["Total_Lost_Mins"] = (
            adherence_summary["Unaccounted_Mins"] + adherence_summary["Exceeded_Break_Mins"]
        )
        
        # Calculate Adherence %
        adherence_summary["Adherence_%"] = (
            (1 - (adherence_summary["Total_Lost_Mins"] / adherence_summary["Scheduled_Mins"])) * 100
        ).clip(lower=0, upper=100)
        
        adherence_summary["Goal_Met"] = adherence_summary["Adherence_%"] >= 88.0
    else:
        adherence_summary = pd.DataFrame()

    # 4. Filters Section
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

    # Filter Application
    filtered_df = adherence_summary.copy()
    if not filtered_df.empty:
        if selected_week != "All Weeks":
            filtered_df = filtered_df[filtered_df["week"] == selected_week]
        if selected_site != "All Sites":
            filtered_df = filtered_df[filtered_df["site"] == selected_site]
        if selected_role != "All Roles":
            filtered_df = filtered_df[filtered_df["role"] == selected_role]

    # 5. Top KPI Ribbon
    m1, m2, m3, m4 = st.columns(4)
    
    overall_adherence = filtered_df["Adherence_%"].mean() if not filtered_df.empty else 0.0
    non_compliant_count = len(filtered_df[filtered_df["Adherence_%"] < 88.0]) if not filtered_df.empty else 0
    
    with m1:
        st.metric(
            "🎯 Overall Adherence %", 
            f"{overall_adherence:.1f}%", 
            delta=f"{overall_adherence - 88.0:.1f}% vs Goal (88%)"
        )
    with m2:
        st.metric("🚨 Agents Below 88% Goal", f"{non_compliant_count} Agents")
    with m3:
        total_overage = filtered_df["Exceeded_Break_Mins"].sum() if not filtered_df.empty else 0
        st.metric("⏱️ Total Break Overage", f"{int(total_overage)} Mins")
    with m4:
        st.link_button("🔗 Open Master Sheet", URL_EXEC_DASHBOARD, use_container_width=True)

    st.divider()

    # 6. Site & Role Status Adherence Benchmarks
    if not filtered_df.empty:
        col_site, col_role = st.columns(2)
        
        with col_site:
            st.markdown("### 🏢 Adherence % by Site")
            site_summary = (
                filtered_df.groupby("site", as_index=False)
                .agg(
                    Avg_Adherence=("Adherence_%", "mean"),
                    Agents_Below_Goal=("Goal_Met", lambda x: (~x).sum())
                )
            )
            site_summary["Avg_Adherence"] = site_summary["Avg_Adherence"].apply(lambda x: f"{x:.1f}%")
            st.dataframe(site_summary, use_container_width=True, hide_index=True)
            
        with col_role:
            st.markdown("### 👤 Adherence % by Role")
            role_summary = (
                filtered_df.groupby("role", as_index=False)
                .agg(
                    Avg_Adherence=("Adherence_%", "mean"),
                    Agents_Below_Goal=("Goal_Met", lambda x: (~x).sum())
                )
            )
            role_summary["Avg_Adherence"] = role_summary["Avg_Adherence"].apply(lambda x: f"{x:.1f}%")
            st.dataframe(role_summary, use_container_width=True, hide_index=True)

    st.divider()

    # 7. Main Performance Table with Highlighted Goal Compliance
    st.subheader("📊 Agent Status Adherence Performance Matrix (Target: ≥88%)")

    if not filtered_df.empty:
        display_table = filtered_df.copy()
        display_table["Adherence %"] = display_table["Adherence_%"].apply(lambda x: f"{x:.1f}%")
        display_table["Break Overage"] = display_table["Exceeded_Break_Mins"].apply(lambda x: f"{int(x)} mins")
        display_table["Status Goal"] = display_table["Goal_Met"].apply(lambda x: "🟢 Met Goal" if x else "🔴 Below 88%")
        
        st.dataframe(
            display_table[["week", "site", "role", "Agent Name", "Days_Logged", "Break Overage", "Adherence %", "Status Goal"]],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No adherence data found for the selected filters.")

    st.divider()

    # 8. Raw Activity Feed
    with st.expander("📋 View Full Raw Activity Feed"):
        st.dataframe(df_raw, use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Error processing status adherence calculations: {e}")
