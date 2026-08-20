import streamlit as st
import pandas as pd
import base64
from streamlit_autorefresh import st_autorefresh

# 1. Page Configuration & Auto-Refresh (30 Minutes = 1,800,000 ms)
st.set_page_config(
    page_title="TransDev SD & OC Operations Dashboard", 
    page_icon="🚌", 
    layout="wide"
)
st_autorefresh(interval=1800000, key="transdev_refresh")

# Base64 helper to convert local images to embeddable strings
def get_image_base64(file_path):
    try:
        with open(file_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode()
    except Exception:
        return None

# Load local images
ccsi_b64 = get_image_base64("ccsi_logo.png")
acsi_b64 = get_image_base64("acsi_logo.png")

# Custom Styling
st.markdown("""
    <style>
    div[data-testid="stLinkButton"]>a {
        background-color: #007AC1 !important;
        color: white !important;
        border-radius: 6px;
        border: none;
        font-weight: bold;
    }
    .header-title {
        border-left: 6px solid #E31B23;
        padding-left: 12px;
        font-size: 2rem;
        font-weight: bold;
        color: #111111;
        line-height: 1.2;
    }
    </style>
""", unsafe_allow_html=True)

# Branding Header Section: ACSI (Left) -> Title (Center) -> CCSI (Right)
col_acsi, col_title, col_ccsi = st.columns([1.2, 5, 1.2])

with col_acsi:
    if acsi_b64:
        st.markdown(f'<img src="data:image/png;base64,{acsi_b64}" width="140">', unsafe_allow_html=True)
    else:
        st.markdown("### **ACSI**")

with col_title:
    st.markdown('<div class="header-title">🚌 TransDev SD & OC Operations Dashboard</div>', unsafe_allow_html=True)
    st.caption("San Diego & Orange County Teams | Target: ≥88% Status Adherence")

with col_ccsi:
    if ccsi_b64:
        st.markdown(f'<img src="data:image/png;base64,{ccsi_b64}" width="140">', unsafe_allow_html=True)
    else:
        st.markdown("### **CCSi**")

st.divider()

# 2. Source Configuration for TransDev SD & OC Sheet
SHEET_ID = "1bp9_e-ML_TVCxkvjsr893nhcJmyw1WILWAsgwdAcjUc"
GID = "676189719"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"
URL_TRANSDEV_DASHBOARD = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit#gid={GID}"

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

@st.cache_data(ttl=1800)
def load_and_process_data(url):
    df = pd.read_csv(url, engine="python", on_bad_lines="skip").dropna(how="all")
    df.columns = df.columns.str.strip()
    
    # Month parsing logic from Date column
    if "Date" in df.columns:
        df["Parsed_Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df["month"] = df["Parsed_Date"].dt.strftime("%B %Y")
    else:
        df["month"] = "Unknown"

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

    # 3. Status Adherence Calculations
    SHIFT_MINS_PER_DAY = 480.0 

    group_cols = ["month", "week", "site", "role", "Agent Name"]
    valid_group_cols = [c for c in group_cols if c in df_raw.columns]

    if valid_group_cols:
        adherence_summary = (
            df_raw.groupby(valid_group_cols, as_index=False)
            .agg(
                Days_Logged=("Date", "nunique") if "Date" in df_raw.columns else ("Total Break_Mins", "count"),
                Total_Break_Mins=("Total Break_Mins", "sum"),
                Total_Meal_Mins=("Total Meal_Mins", "sum"),
                Unaccounted_Mins=("Unaccounted_Mins", "sum"),
                Non_Adherent_Mins=("Total Tech Issue_Mins", "sum")
            )
        )
        
        adherence_summary["Scheduled_Mins"] = adherence_summary["Days_Logged"] * SHIFT_MINS_PER_DAY
        adherence_summary["Allowed_Break_Mins"] = adherence_summary["Days_Logged"] * 30.0
        adherence_summary["Exceeded_Break_Mins"] = (
            adherence_summary["Total_Break_Mins"] - adherence_summary["Allowed_Break_Mins"]
        ).clip(lower=0)
        
        adherence_summary["Total_Lost_Mins"] = (
            adherence_summary["Unaccounted_Mins"] + adherence_summary["Exceeded_Break_Mins"]
        )
        
        adherence_summary["Adherence_%"] = (
            (1 - (adherence_summary["Total_Lost_Mins"] / adherence_summary["Scheduled_Mins"])) * 100
        ).clip(lower=0, upper=100)
        
        adherence_summary["Goal_Met"] = adherence_summary["Adherence_%"] >= 88.0
    else:
        adherence_summary = pd.DataFrame()

    # 4. Filters Section
    st.subheader("🔍 Filters & Drilldown")
    f1, f2, f3, f4 = st.columns(4)
    
    with f1:
        months = ["All Months"] + sorted(df_raw["month"].dropna().unique().tolist()) if "month" in df_raw.columns else ["All Months"]
        selected_month = st.selectbox("Month:", months)

    with f2:
        weeks = ["All Weeks"] + sorted(df_raw["week"].dropna().unique().tolist(), reverse=True) if "week" in df_raw.columns else ["All Weeks"]
        selected_week = st.selectbox("Work Week:", weeks)
        
    with f3:
        sites = ["All Sites"] + sorted(df_raw["site"].dropna().unique().tolist()) if "site" in df_raw.columns else ["All Sites"]
        selected_site = st.selectbox("Site:", sites)
        
    with f4:
        roles = ["All Roles"] + sorted(df_raw["role"].dropna().unique().tolist()) if "role" in df_raw.columns else ["All Roles"]
        selected_role = st.selectbox("Role:", roles)

    # Apply Selected Filters
    filtered_df = adherence_summary.copy()
    if not filtered_df.empty:
        if selected_month != "All Months" and "month" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["month"] == selected_month]
        if selected_week != "All Weeks" and "week" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["week"] == selected_week]
        if selected_site != "All Sites" and "site" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["site"] == selected_site]
        if selected_role != "All Roles" and "role" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["role"] == selected_role]

    # 5. Top Metric Ribbon
    m1, m2, m3, m4 = st.columns(4)
    
    overall_adherence = filtered_df["Adherence_%"].mean() if not filtered_df.empty else 0.0
    non_compliant_count = len(filtered_df[filtered_df["Adherence_%"] < 88.0]) if not filtered_df.empty else 0
    delta_val = overall_adherence - 88.0
    
    with m1:
        st.metric(
            "🎯 Overall Adherence %", 
            f"{overall_adherence:.1f}%", 
            delta=f"{delta_val:+.1f}% vs Goal (88%)",
            delta_color="normal"
        )
    with m2:
        st.metric(
            "🚨 Agents Below 88% Goal", 
            f"{non_compliant_count} Agents",
            delta="Needs Attention" if non_compliant_count > 0 else "All Compliant",
            delta_color="inverse" if non_compliant_count > 0 else "normal"
        )
    with m3:
        total_overage = filtered_df["Exceeded_Break_Mins"].sum() if not filtered_df.empty else 0
        st.metric("⏱️ Total Break Overage", f"{int(total_overage)} Mins")
    with m4:
        st.link_button("🔗 Open TransDev Master Sheet", URL_TRANSDEV_DASHBOARD, use_container_width=True)

    st.divider()

    # 6. Site & Role Summary Benchmarks
    if not filtered_df.empty:
        col_site, col_role = st.columns(2)
        
        with col_site:
            st.markdown("### 🏢 Adherence % by Site (SD / OC)")
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

    # 7. Agent Performance Table
    st.subheader("📊 TransDev Agent Adherence Performance Matrix (Target: ≥88%)")

    if not filtered_df.empty:
        display_table = filtered_df.copy()
        display_table["Adherence %"] = display_table["Adherence_%"].apply(lambda x: f"{x:.1f}%")
        display_table["Break Overage"] = display_table["Exceeded_Break_Mins"].apply(lambda x: f"{int(x)} mins")
        display_table["Status Goal"] = display_table["Goal_Met"].apply(lambda x: "🟢 Met Goal" if x else "🔴 Below 88%")
        
        cols_to_show = [c for c in ["month", "week", "site", "role", "Agent Name", "Days_Logged", "Break Overage", "Adherence %", "Status Goal"] if c in display_table.columns]
        
        st.dataframe(
            display_table[cols_to_show],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No adherence data found for the selected TransDev filters.")

    st.divider()

    # 8. TransDev Raw Feed
    with st.expander("📋 View TransDev Raw Feed"):
        st.dataframe(df_raw, use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Error processing TransDev adherence data: {e}")
