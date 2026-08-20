import streamlit as st
import pandas as pd
import base64
import urllib.request
import io
from streamlit_autorefresh import st_autorefresh

# 1. Page Configuration & Auto-Refresh
st.set_page_config(
    page_title="ACSI & CCSI Operations Command Dashboard", 
    page_icon="⚡", 
    layout="wide"
)
st_autorefresh(interval=1800000, key="combined_refresh")

def get_image_base64(file_path):
    try:
        with open(file_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode()
    except Exception:
        return None

ccsi_b64 = get_image_base64("ccsi_logo.png")
acsi_b64 = get_image_base64("acsi_logo.png")

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
        border-left: 6px solid #007AC1;
        padding-left: 12px;
        font-size: 2rem;
        font-weight: bold;
        color: #111111;
        line-height: 1.2;
    }
    </style>
""", unsafe_allow_html=True)

col_acsi, col_title, col_ccsi = st.columns([1.2, 5, 1.2])

with col_acsi:
    if acsi_b64:
        st.markdown(f'<img src="data:image/png;base64,{acsi_b64}" width="140">', unsafe_allow_html=True)
    else:
        st.markdown("### **ACSI**")

with col_title:
    st.markdown('<div class="header-title">⚡ Master Operations Command Dashboard</div>', unsafe_allow_html=True)
    st.caption("Combined Operations: TDS & TransDev SD/OC | Target: ≥88% Status Adherence")

with col_ccsi:
    if ccsi_b64:
        st.markdown(f'<img src="data:image/png;base64,{ccsi_b64}" width="140">', unsafe_allow_html=True)
    else:
        st.markdown("### **CCSi**")

st.divider()

def parse_adherence_val(val):
    if pd.isna(val):
        return None
    if isinstance(val, (int, float)):
        return float(val) * 100.0 if float(val) <= 1.0 else float(val)
    if isinstance(val, str):
        val_str = val.replace("%", "").strip()
        try:
            parsed = float(val_str)
            return parsed * 100.0 if parsed <= 1.0 and "%" not in val else parsed
        except ValueError:
            return None
    return None

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

def fetch_raw_csv(sheet_id, gid):
    gviz_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&gid={gid}"
    req = urllib.request.Request(
        gviz_url, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    )
    with urllib.request.urlopen(req) as response:
        content = response.read()
    return pd.read_csv(io.BytesIO(content), engine="python", header=None, on_bad_lines="skip").dropna(how="all")

# 2. Dynamic Smart Header Parser
@st.cache_data(ttl=1800)
def parse_sheet_smart(sheet_id, gid, account_name):
    df = fetch_raw_csv(sheet_id, gid)
    
    header_idx = None
    for i in range(min(10, len(df))):
        row_str = df.iloc[i].astype(str).str.lower().tolist()
        if any("agent" in cell or "site" in cell for cell in row_str):
            header_idx = i
            break

    if header_idx is not None:
        headers = df.iloc[header_idx].astype(str).str.strip().str.lower()
        df_data = df.iloc[header_idx + 1:].copy()
        df_data.columns = headers
    else:
        df_data = df.copy()

    df_clean = pd.DataFrame()

    def get_col_data(possible_names, default_val=None):
        for name in possible_names:
            matches = [c for c in df_data.columns if name in str(c).lower()]
            if matches:
                return df_data[matches[0]].astype(str).str.strip()
        return default_val

    df_clean["site"] = get_col_data(["site", "location", "sit"], "MX")
    df_clean["role"] = get_col_data(["role", "position", "title"], "Agent")
    df_clean["week"] = get_col_data(["week", "wk", "period"], "Week 1")
    df_clean["Date"] = get_col_data(["date", "day"], None)
    df_clean["Agent Name"] = get_col_data(["agent name", "agent", "employee", "name"], None)
    
    df_clean["Total Break"] = get_col_data(["total break", "break time", "break"], "0:00")
    df_clean["Total Meal"] = get_col_data(["total meal", "meal time", "meal", "lunch"], "0:00")
    df_clean["Unaccounted"] = get_col_data(["unaccounted", "unapproved", "lost time"], "0:00")
    df_clean["Direct_Adherence"] = get_col_data(["adherence", "direct adherence", "status adherence"], None)

    bad_sites = ["site", "sit", "location", "nan", "none", "", "a"]
    bad_agents = ["agent name", "agent", "name", "employee", "nan", "none", ""]

    df_clean = df_clean[~df_clean["site"].str.lower().isin(bad_sites)]
    df_clean = df_clean[~df_clean["Agent Name"].str.lower().isin(bad_agents)]
    
    df_clean["Account"] = account_name
    return df_clean.dropna(subset=["Agent Name"]).reset_index(drop=True)

@st.cache_data(ttl=1800)
def load_all_combined_data_v4():
    frames = []
    
    try:
        tds_df = parse_sheet_smart("18WdoYyycy71LWCEUesOq6-uLWqtAo52jD4p12ObGi3k", "1537474403", "TDS")
        frames.append(tds_df)
    except Exception as e:
        st.error(f"Error fetching data for TDS: {e}")

    try:
        td_df = parse_sheet_smart("1bp9_e-ML_TVCxkvjsr893nhcJmyw1WILWAsgwdAcjUc", "676189719", "TransDev SD & OC")
        frames.append(td_df)
    except Exception as e:
        st.error(f"Error fetching data for TransDev SD & OC: {e}")

    if not frames:
        return pd.DataFrame()
        
    combined_df = pd.concat(frames, axis=0, ignore_index=True)
    
    # Standardize Month Parsing across both sources
    if "Date" in combined_df.columns:
        combined_df["Parsed_Date"] = pd.to_datetime(combined_df["Date"], errors="coerce")
        formatted_months = combined_df["Parsed_Date"].dt.strftime("%B %Y")
        combined_df["month"] = formatted_months.fillna(combined_df["Date"]).fillna("Unknown")
    else:
        combined_df["month"] = "Unknown"

    time_cols = ["Total Break", "Total Meal", "Unaccounted"]
    for col in time_cols:
        if col in combined_df.columns:
            combined_df[f"{col}_Mins"] = combined_df[col].apply(time_to_minutes)
        else:
            combined_df[f"{col}_Mins"] = 0.0

    if "Direct_Adherence" in combined_df.columns:
        combined_df["Parsed_Adherence"] = combined_df["Direct_Adherence"].apply(parse_adherence_val)
    else:
        combined_df["Parsed_Adherence"] = None

    return combined_df

# 3. Main Operational Logic
try:
    df_raw = load_all_combined_data_v4()

    SHIFT_MINS_PER_DAY = 480.0 
    group_cols = ["Account", "month", "week", "site", "role", "Agent Name"]
    valid_group_cols = [c for c in group_cols if c in df_raw.columns]

    if valid_group_cols and not df_raw.empty:
        adherence_summary = (
            df_raw.groupby(valid_group_cols, as_index=False)
            .agg(
                Days_Logged=("Date", "nunique") if "Date" in df_raw.columns else ("Total Break_Mins", "count"),
                Total_Break_Mins=("Total Break_Mins", "sum"),
                Total_Meal_Mins=("Total Meal_Mins", "sum"),
                Unaccounted_Mins=("Unaccounted_Mins", "sum"),
                Direct_Adherence_Avg=("Parsed_Adherence", "mean")
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
        
        adherence_summary["Adherence_%"] = adherence_summary["Direct_Adherence_Avg"].fillna(
            ((1 - (adherence_summary["Total_Lost_Mins"] / adherence_summary["Scheduled_Mins"])) * 100).clip(lower=0, upper=100)
        )
        
        adherence_summary["Goal_Met"] = adherence_summary["Adherence_%"] >= 88.0
    else:
        adherence_summary = pd.DataFrame()

    # 4. Filters Section
    st.subheader("🔍 Filters & Drilldown")
    f0, f1, f2, f3, f4 = st.columns(5)
    
    with f0:
        accounts = ["All Accounts"] + sorted(df_raw["Account"].dropna().unique().tolist()) if "Account" in df_raw.columns else ["All Accounts"]
        selected_account = st.selectbox("Account / Source:", accounts, index=0)

    with f1:
        months = ["All Months"] + sorted(df_raw["month"].dropna().unique().tolist()) if "month" in df_raw.columns else ["All Months"]
        selected_month = st.selectbox("Month:", months, index=0)

    with f2:
        weeks = ["All Weeks"] + sorted(df_raw["week"].dropna().unique().tolist(), reverse=True) if "week" in df_raw.columns else ["All Weeks"]
        selected_week = st.selectbox("Work Week:", weeks, index=0)
        
    with f3:
        sites = ["All Sites"] + sorted(df_raw["site"].dropna().unique().tolist()) if "site" in df_raw.columns else ["All Sites"]
        selected_site = st.selectbox("Site:", sites, index=0)
        
    with f4:
        roles = ["All Roles"] + sorted(df_raw["role"].dropna().unique().tolist()) if "role" in df_raw.columns else ["All Roles"]
        selected_role = st.selectbox("Role (Position):", roles, index=0)

    filtered_df = adherence_summary.copy()
    if not filtered_df.empty:
        if selected_account != "All Accounts" and "Account" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["Account"] == selected_account]
        if selected_month != "All Months" and "month" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["month"] == selected_month]
        if selected_week != "All Weeks" and "week" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["week"] == selected_week]
        if selected_site != "All Sites" and "site" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["site"] == selected_site]
        if selected_role != "All Roles" and "role" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["role"] == selected_role]

    # 5. Metric Ribbon
    m1, m2, m3, m4 = st.columns(4)
    
    overall_adherence = filtered_df["Adherence_%"].mean() if not filtered_df.empty else 0.0
    non_compliant_count = len(filtered_df[filtered_df["Adherence_%"] < 88.0]) if not filtered_df.empty else 0
    delta_val = overall_adherence - 88.0
    
    with m1:
        st.metric(
            "🎯 Combined Adherence %", 
            f"{overall_adherence:.1f}%", 
            delta=f"{delta_val:+.1f}% vs Goal (88%)",
            delta_color="normal"
        )
    with m2:
        st.metric(
            "🚨 Total Agents Below 88%", 
            f"{non_compliant_count} Agents",
            delta="Needs Attention" if non_compliant_count > 0 else "All Compliant",
            delta_color="inverse" if non_compliant_count > 0 else "normal"
        )
    with m3:
        total_overage = filtered_df["Exceeded_Break_Mins"].sum() if not filtered_df.empty else 0
        st.metric("⏱️ Combined Break Overage", f"{int(total_overage)} Mins")
    with m4:
        st.write("**Direct Sheet Links:**")
        st.markdown("[🔗 TDS Sheet](https://docs.google.com/spreadsheets/d/18WdoYyycy71LWCEUesOq6-uLWqtAo52jD4p12ObGi3k/edit#gid=1537474403)")
        st.markdown("[🔗 TransDev Sheet](https://docs.google.com/spreadsheets/d/1bp9_e-ML_TVCxkvjsr893nhcJmyw1WILWAsgwdAcjUc/edit#gid=676189719)")

    st.divider()

    # 6. Breakdown Tables
    if not filtered_df.empty:
        col_acc, col_site, col_role = st.columns(3)
        
        with col_acc:
            st.markdown("### 📁 Adherence by Account")
            if "Account" in filtered_df.columns:
                acc_summary = (
                    filtered_df.groupby("Account", as_index=False)
                    .agg(
                        Avg_Adherence=("Adherence_%", "mean"),
                        Agents_Below_Goal=("Goal_Met", lambda x: (~x).sum())
                    )
                )
                acc_summary["Avg_Adherence"] = acc_summary["Avg_Adherence"].apply(lambda x: f"{x:.1f}%")
                st.dataframe(acc_summary, use_container_width=True, hide_index=True)

        with col_site:
            st.markdown("### 🏢 Adherence by Site")
            if "site" in filtered_df.columns:
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
            st.markdown("### 👤 Adherence by Role")
            if "role" in filtered_df.columns:
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

    # 7. Matrix
    st.subheader("📊 Combined Agent Adherence Performance Matrix (Target: ≥88%)")

    if not filtered_df.empty:
        display_table = filtered_df.copy()
        display_table["Adherence %"] = display_table["Adherence_%"].apply(lambda x: f"{x:.1f}%")
        display_table["Break Overage"] = display_table["Exceeded_Break_Mins"].apply(lambda x: f"{int(x)} mins")
        display_table["Status Goal"] = display_table["Goal_Met"].apply(lambda x: "🟢 Met Goal" if x else "🔴 Below 88%")
        
        cols_to_show = [c for c in ["Account", "month", "week", "site", "role", "Agent Name", "Days_Logged", "Break Overage", "Adherence %", "Status Goal"] if c in display_table.columns]
        
        st.dataframe(
            display_table[cols_to_show],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No adherence data found for the selected filters.")

    st.divider()

    with st.expander("📋 View Master Raw Combined Data Feed"):
        st.dataframe(df_raw, use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Error merging and calculating operations data: {e}")
