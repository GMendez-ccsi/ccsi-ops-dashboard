import streamlit as st
import pandas as pd
import base64
import urllib.request
import io
import re
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
    .badge-green {
        background-color: #D1FAE5; color: #065F46; padding: 4px 8px; border-radius: 4px; font-weight: bold;
    }
    .badge-yellow {
        background-color: #FEF3C7; color: #92400E; padding: 4px 8px; border-radius: 4px; font-weight: bold;
    }
    .badge-red {
        background-color: #FEE2E2; color: #991B1B; padding: 4px 8px; border-radius: 4px; font-weight: bold;
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

def normalize_site(val):
    if pd.isna(val) or not str(val).strip():
        return "Unknown"
    s = str(val).strip().upper()
    if s in ["TJ", "TIJUANA", "TIJ"] or "TJ" in s or "TIJUANA" in s:
        return "Tijuana"
    if s in ["MX", "CDMX", "MEXICO"] or "MX" in s or "CDMX" in s:
        return "CDMX"
    return str(val).strip().title()

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
    val = time_str.strip()
    if not val or val.lower() == "nan" or val == "0":
        return 0.0
    try:
        parts = val.split(":")
        if len(parts) == 3:
            return float(parts[0]) * 60.0 + float(parts[1]) + float(parts[2]) / 60.0
        elif len(parts) == 2:
            return float(parts[0]) * 60.0 + float(parts[1])
    except Exception:
        try:
            return float(val)
        except ValueError:
            return 0.0
    return 0.0

def clean_week_str(val):
    if pd.isna(val) or not str(val).strip():
        return "Week 1"
    val_str = str(val).strip()
    
    w_match = re.search(r'[Ww](\d+)', val_str)
    if w_match:
        return f"Week {int(w_match.group(1))}"
    
    match = re.search(r'(\d+)', val_str)
    if match:
        num = int(match.group(1))
        return f"Week {num}" if num < 100 else "Week 1"
        
    return val_str

def fetch_raw_csv(sheet_id, gid):
    gviz_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&gid={gid}"
    req = urllib.request.Request(
        gviz_url, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    )
    with urllib.request.urlopen(req) as response:
        content = response.read()
    return pd.read_csv(io.BytesIO(content), engine="python", header=None, on_bad_lines="skip").dropna(how="all")

# Parser for 60-day Independent Pivot Summary Sheet
@st.cache_data(ttl=300)
def parse_pivot_attendance_sheet_raw(sheet_id, gid):
    df_raw = fetch_raw_csv(sheet_id, gid)
    if df_raw.empty:
        return pd.DataFrame()

    header_idx = None
    for i in range(min(15, len(df_raw))):
        row_cells = [str(x).strip().lower() for x in df_raw.iloc[i].fillna("").tolist()]
        if any("agent" in x or "site" in x or "name" in x for x in row_cells):
            header_idx = i
            break

    if header_idx is not None:
        headers = [str(c).strip() if str(c).strip() != "nan" else f"Col_{j}" for j, c in enumerate(df_raw.iloc[header_idx].tolist())]
        df_clean = df_raw.iloc[header_idx + 1:].copy()
        df_clean.columns = headers
    else:
        df_clean = df_raw.copy()

    df_clean = df_clean.dropna(how="all")

    for c in df_clean.columns:
        clow = str(c).lower().strip()
        if "site" in clow or "location" in clow:
            df_clean = df_clean.rename(columns={c: "site"})
        elif any(k in clow for k in ["agent", "employee"]) and "name" in clow:
            df_clean = df_clean.rename(columns={c: "Agent Name"})

    if "Agent Name" in df_clean.columns:
        df_clean = df_clean[
            ~df_clean["Agent Name"].astype(str).str.lower().str.contains("total|grand total|blank|nan", na=False)
        ]

    if "site" in df_clean.columns:
        df_clean["site"] = df_clean["site"].apply(normalize_site)

    return df_clean.reset_index(drop=True)

# Main Attendance Sheet Parser with strict date normalization
@st.cache_data(ttl=300)
def parse_primary_attendance_sheet(sheet_id, gid):
    df_raw = fetch_raw_csv(sheet_id, gid)
    if df_raw.empty:
        return pd.DataFrame()

    header_idx = None
    for i in range(min(15, len(df_raw))):
        row_cells = [str(x).strip().lower() for x in df_raw.iloc[i].fillna("").tolist()]
        if any("agent" in x or "name" in x or "site" in x for x in row_cells):
            header_idx = i
            break

    if header_idx is not None:
        headers = [str(c).strip() for c in df_raw.iloc[header_idx].tolist()]
        df_clean = df_raw.iloc[header_idx + 1:].copy()
        df_clean.columns = headers
    else:
        df_clean = df_raw.copy()

    df_clean = df_clean.loc[:, ~df_clean.columns.duplicated()].dropna(how="all")

    col_map = {}
    for c in df_clean.columns:
        clow = str(c).lower().strip()
        if "site" in clow or "location" in clow: col_map[c] = "site"
        elif "week" in clow: col_map[c] = "week"
        elif "account" in clow: col_map[c] = "Account"
        elif "month" in clow or "date" in clow: col_map[c] = "month"
        elif any(k in clow for k in ["role", "position", "title"]): col_map[c] = "role"
        elif any(k in clow for k in ["agent", "employee", "name"]): col_map[c] = "Agent Name"
        elif "unjustified" in clow: col_map[c] = "Unjustified Absences"
        elif "justified" in clow: col_map[c] = "Justified Absences"
        elif "late" in clow or "lateness" in clow: col_map[c] = "Total Late Time"

    df_clean = df_clean.rename(columns=col_map)

    if "Agent Name" in df_clean.columns:
        df_clean = df_clean[
            ~df_clean["Agent Name"].astype(str).str.lower().str.contains("total|grand total|blank|nan", na=False)
        ]

    if "site" in df_clean.columns:
        df_clean["site"] = df_clean["site"].apply(normalize_site)
    else:
        df_clean["site"] = "CDMX"

    df_clean["week"] = df_clean["week"].apply(clean_week_str) if "week" in df_clean.columns else "Week 1"
    
    # Strictly bind row to Month
    if "month" in df_clean.columns:
        parsed_dates = pd.to_datetime(df_clean["month"], errors="coerce", format="mixed")
        df_clean["parsed_date"] = parsed_dates
        df_clean["month"] = parsed_dates.dt.strftime("%B %Y").fillna(df_clean["month"].astype(str).str.strip())
    else:
        df_clean["month"] = "August 2026"

    if "Account" not in df_clean.columns: df_clean["Account"] = "TDS"
    if "role" not in df_clean.columns: df_clean["role"] = "CSA"

    if "Total Late Time" in df_clean.columns:
        df_clean["Late_Mins_Numeric"] = df_clean["Total Late Time"].astype(str).apply(time_to_minutes)
    else:
        df_clean["Late_Mins_Numeric"] = 0.0

    df_clean["Total Late Instances"] = (df_clean["Late_Mins_Numeric"] > 0).astype(int)

    return df_clean.reset_index(drop=True)

@st.cache_data(ttl=1800)
def parse_sheet_by_structure(sheet_id, gid, account_label):
    df_raw = fetch_raw_csv(sheet_id, gid)
    if df_raw.empty:
        return pd.DataFrame()

    header_idx = None
    for i in range(min(20, len(df_raw))):
        row_cells = [str(x).strip().lower() for x in df_raw.iloc[i].fillna("").tolist()]
        if "date" in row_cells or "week" in row_cells or "agent name" in row_cells or "site" in row_cells:
            header_idx = i
            break

    df_data = df_raw.iloc[header_idx + 1:].copy() if header_idx is not None else df_raw.copy()

    df_clean = pd.DataFrame()
    
    df_clean["Date"] = df_data.iloc[:, 0].astype(str).str.strip()
    df_clean["week"] = df_data.iloc[:, 1].astype(str).str.strip().apply(clean_week_str)
    df_clean["Agent Name"] = df_data.iloc[:, 2].astype(str).str.strip()
    df_clean["site"] = df_data.iloc[:, 3].astype(str).str.strip().apply(normalize_site)
    df_clean["role"] = df_data.iloc[:, 4].astype(str).str.strip()

    df_clean["Total Break"] = df_data.iloc[:, 9].astype(str).str.strip() if df_data.shape[1] > 9 else "0:00"
    df_clean["Total Meal"] = df_data.iloc[:, 10].astype(str).str.strip() if df_data.shape[1] > 10 else "0:00"
    df_clean["Exceeded_Break_Raw"] = df_data.iloc[:, 15].astype(str).str.strip() if df_data.shape[1] > 15 else "0:00"
    df_clean["Unaccounted"] = df_data.iloc[:, 16].astype(str).str.strip() if df_data.shape[1] > 16 else "0:00"
    df_clean["Direct_Adherence"] = df_data.iloc[:, 17].astype(str).str.strip() if df_data.shape[1] > 17 else None

    invalid_mask = (
        df_clean["Agent Name"].isna() |
        df_clean["Agent Name"].str.lower().isin(["none", "nan", "", "agent name", "agent", "employee", "name", "site"])
    )
    df_clean = df_clean[~invalid_mask].copy()
    df_clean["Account"] = account_label
    return df_clean.reset_index(drop=True)

@st.cache_data(ttl=1800)
def load_all_combined_data_v15():
    frames = []
    
    try:
        tds_df = parse_sheet_by_structure("18WdoYyycy71LWCEUesOq6-uLWqtAo52jD4p12ObGi3k", "1537474403", "TDS")
        frames.append(tds_df)
    except Exception as e:
        st.error(f"Error fetching data for TDS: {e}")

    try:
        td_df = parse_sheet_by_structure("1bp9_e-ML_TVCxkvjsr893nhcJmyw1WILWAsgwdAcjUc", "676189719", "TransDev SD & OC")
        frames.append(td_df)
    except Exception as e:
        st.error(f"Error fetching data for TransDev SD & OC: {e}")

    if not frames:
        return pd.DataFrame()
        
    combined_df = pd.concat(frames, axis=0, ignore_index=True)

    if "Date" in combined_df.columns:
        parsed_dates = pd.to_datetime(combined_df["Date"], errors="coerce", format="mixed")
        combined_df["parsed_date"] = parsed_dates
        combined_df["month"] = parsed_dates.dt.strftime("%B %Y").fillna("August 2026")
    else:
        combined_df["month"] = "August 2026"

    time_cols = ["Total Break", "Total Meal", "Unaccounted", "Exceeded_Break_Raw"]
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

# Load Datasets
attendance_raw_df = parse_primary_attendance_sheet("1PUerkTX4iCaFUP27FXV34azza6L5LpFYsb1nHVKrH-c", "601856217")
pivot_attendance_df = parse_pivot_attendance_sheet_raw("1kzXr88ueah-Gg0gVI4bhl1peFdWYgy0nIFRkZOl0RK0", "243149129")
df_raw = load_all_combined_data_v15()

# Filters UI
st.subheader("🔍 Filters & Drilldown")
f0, f1, f2, f3, f4 = st.columns(5)

with f0:
    sites = ["All Sites", "CDMX", "Tijuana"]
    selected_site = st.selectbox("Site:", sites, index=0)

with f1:
    accounts = ["All Accounts"]
    all_acc = set()
    if "Account" in attendance_raw_df.columns: all_acc.update(attendance_raw_df["Account"].dropna().unique())
    if "Account" in df_raw.columns: all_acc.update(df_raw["Account"].dropna().unique())
    accounts += sorted([a for a in all_acc if a and str(a).lower() != "nan"])
    selected_account = st.selectbox("Account / Source:", accounts, index=0)

with f2:
    months = ["All Months"]
    all_months = set()
    if "month" in attendance_raw_df.columns: all_months.update(attendance_raw_df["month"].dropna().unique())
    if "month" in df_raw.columns: all_months.update(df_raw["month"].dropna().unique())
    
    clean_months = sorted([m for m in all_months if m and str(m).lower() != "nan"])
    months += clean_months
    
    aug_idx = months.index("August 2026") if "August 2026" in months else 0
    selected_month = st.selectbox("Month:", months, index=aug_idx)

with f3:
    all_weeks = set()
    if "week" in attendance_raw_df.columns: all_weeks.update(attendance_raw_df["week"].dropna().unique())
    if "week" in df_raw.columns: all_weeks.update(df_raw["week"].dropna().unique())
    available_weeks = sorted(
        [w for w in all_weeks if w and str(w).lower() != "nan"], 
        key=lambda x: int(re.search(r'\d+', str(x)).group()) if re.search(r'\d+', str(x)) else 0
    )
    selected_weeks = st.multiselect("Work Week (Multi-Select Allowed):", options=available_weeks, default=[])

with f4:
    all_roles = set()
    if "role" in df_raw.columns:
        all_roles.update(df_raw["role"].dropna().astype(str).str.strip().unique())
    if "role" in attendance_raw_df.columns:
        all_roles.update(attendance_raw_df["role"].dropna().astype(str).str.strip().unique())
    
    roles_available = sorted([r for r in all_roles if r and r.lower() not in ["nan", "none", "role", "position"]])
    selected_roles = st.multiselect("Role (Position):", options=roles_available, default=[])

# Filter enforcing strict calendar month capping across weeks
def apply_common_filters(df, strict_month=True):
    if df.empty:
        return df
    dff = df.copy()
    
    if selected_site != "All Sites" and "site" in dff.columns:
        if selected_site == "Tijuana":
            dff = dff[dff["site"].astype(str).str.lower().isin(["tijuana", "tj"])]
        elif selected_site == "CDMX":
            dff = dff[dff["site"].astype(str).str.lower().isin(["cdmx", "mx", "mexico"])]

    if selected_account != "All Accounts" and "Account" in dff.columns:
        dff = dff[dff["Account"].astype(str).str.strip().str.lower() == selected_account.strip().lower()]

    # STRICT MONTH CAP: Match on exact YYYY-MM / Month Name to prevent cross-month week leakage
    if strict_month and selected_month != "All Months" and "month" in dff.columns:
        target_month = selected_month.strip().lower()
        dff = dff[dff["month"].astype(str).str.strip().str.lower() == target_month]

        if "parsed_date" in dff.columns:
            sel_dt = pd.to_datetime(selected_month, errors="coerce")
            if pd.notna(sel_dt):
                dff = dff[
                    (dff["parsed_date"].dt.year == sel_dt.year) & 
                    (dff["parsed_date"].dt.month == sel_dt.month)
                ]

    # WEEK FILTER: Multi-week selection within month bounds
    if selected_weeks and "week" in dff.columns:
        selected_weeks_lower = [w.lower().strip() for w in selected_weeks]
        dff = dff[dff["week"].astype(str).str.strip().str.lower().isin(selected_weeks_lower)]

    if "role" in dff.columns and selected_roles:
        selected_roles_lower = [r.lower().strip() for r in selected_roles]
        dff = dff[dff["role"].astype(str).str.strip().str.lower().isin(selected_roles_lower)]
        
    return dff

# Primary datasets filtered strictly by month and weeks
filtered_attendance_df = apply_common_filters(attendance_raw_df, strict_month=True)
filtered_raw_df = apply_common_filters(df_raw, strict_month=True)

# 60-Day Pivot Tracker: Filters BY SITE/ROLE ONLY, NOT MONTH/WEEK (60-day rolling rule)
def apply_pivot_filters(df):
    if df.empty:
        return df
    dff = df.copy()
    if selected_site != "All Sites" and "site" in dff.columns:
        if selected_site == "Tijuana":
            dff = dff[dff["site"].astype(str).str.lower().isin(["tijuana", "tj"])]
        elif selected_site == "CDMX":
            dff = dff[dff["site"].astype(str).str.lower().isin(["cdmx", "mx", "mexico"])]
    if "role" in dff.columns and selected_roles:
        selected_roles_lower = [r.lower().strip() for r in selected_roles]
        dff = dff[dff["role"].astype(str).str.strip().str.lower().isin(selected_roles_lower)]
    return dff

independent_pivot_df = apply_pivot_filters(pivot_attendance_df)

# Calculations on month-capped data
SHIFT_MINS_PER_DAY = 480.0 
group_cols = ["Account", "month", "week", "site", "role", "Agent Name"]
valid_group_cols = [c for c in group_cols if c in filtered_raw_df.columns]

if valid_group_cols and not filtered_raw_df.empty:
    adherence_summary = (
        filtered_raw_df.groupby(valid_group_cols, as_index=False)
        .agg(
            Days_Logged=("Date", "nunique") if "Date" in filtered_raw_df.columns else ("Total Break_Mins", "count"),
            Total_Break_Mins=("Total Break_Mins", "sum"),
            Exceeded_Break_Mins=("Exceeded_Break_Raw_Mins", "sum"),
            Total_Meal_Mins=("Total Meal_Mins", "sum"),
            Unaccounted_Mins=("Unaccounted_Mins", "sum"),
            Direct_Adherence_Avg=("Parsed_Adherence", "mean")
        )
    )
    
    adherence_summary["Scheduled_Mins"] = adherence_summary["Days_Logged"] * SHIFT_MINS_PER_DAY
    adherence_summary["Total_Lost_Mins"] = (
        adherence_summary["Unaccounted_Mins"] + adherence_summary["Exceeded_Break_Mins"]
    )
    
    adherence_summary["Adherence_%"] = adherence_summary["Direct_Adherence_Avg"]
    
    missing_mask = adherence_summary["Adherence_%"].isna()
    if missing_mask.any():
        calc_vals = (
            (1 - (adherence_summary.loc[missing_mask, "Total_Lost_Mins"] / adherence_summary.loc[missing_mask, "Scheduled_Mins"])) * 100
        ).clip(lower=0, upper=100)
        adherence_summary.loc[missing_mask, "Adherence_%"] = calc_vals

    adherence_summary["Goal_Met"] = adherence_summary["Adherence_%"] >= 88.0
    filtered_df = adherence_summary
else:
    filtered_df = pd.DataFrame()

# Dashboard Tabs
tab_attendance, tab_adherence, tab_ops_kpi, tab_agent_scope, tab_service_hours = st.tabs([
    "📅 Attendance", 
    "🎯 Status Adherence", 
    "📊 Operational KPI View", 
    "👤 Agent Scope", 
    "⏱️ Service Hours per Campaign"
])

# TAB 1: ATTENDANCE
with tab_attendance:
    a_col1, a_col2 = st.columns([2.5, 1.5])
    with a_col1:
        st.subheader("📅 Attendance Tracker & Pivot Summary")
    with a_col2:
        st.markdown("[🔗 Open Main Attendance Sheet](https://docs.google.com/spreadsheets/d/1PUerkTX4iCaFUP27FXV34azza6L5LpFYsb1nHVKrH-c/edit#gid=601856217)")
        st.markdown("[🔗 Open Pivot Attendance Summary Sheet](https://docs.google.com/spreadsheets/d/1kzXr88ueah-Gg0gVI4bhl1peFdWYgy0nIFRkZOl0RK0/edit#gid=243149129)")

    if not filtered_attendance_df.empty:
        distinct_attendance_df = filtered_attendance_df.drop_duplicates(subset=["Agent Name"]) if "Agent Name" in filtered_attendance_df.columns else filtered_attendance_df

        active_headcount = len(distinct_attendance_df)
        unjustified_absences = int(pd.to_numeric(filtered_attendance_df.get('Unjustified Absences', 0), errors='coerce').fillna(0).sum())
        justified_absences = int(pd.to_numeric(filtered_attendance_df.get('Justified Absences', 0), errors='coerce').fillna(0).sum())
        
        late_instances = int(filtered_attendance_df.get('Total Late Instances', pd.Series([0])).sum())
        total_late_mins = float(filtered_attendance_df.get('Late_Mins_Numeric', pd.Series([0])).sum())
        
        late_hours = int(total_late_mins // 60)
        remaining_mins = int(total_late_mins % 60)
        late_time_str = f"{late_hours}h {remaining_mins}m" if late_hours > 0 else f"{int(total_late_mins)} Mins"

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("👥 Active Roster Headcount", f"{active_headcount}")
        m2.metric("⚠️ Unjustified Absences", f"{unjustified_absences}")
        m3.metric("📋 Justified Absences", f"{justified_absences}")
        m4.metric("⏱️ Total Late Instances", f"{late_instances}")
        m5.metric("⏳ Total Lateness Time", late_time_str)

        st.divider()

        # Visual Independent 60-Day Pivot Tracker (Compatible with all Pandas versions)
        st.write("### 📌 Attendance Point Infractions (Rolling 60-Day Pivot Tracker)")
        st.caption("ℹ️ Unfiltered by Month/Week filters as infractions operate on a 60-day running window.")
        
        if not independent_pivot_df.empty:
            def style_escalation(val):
                s = str(val).lower()
                if any(x in s for x in ["written", "warning", "4", "escalated", "final", "termination"]):
                    return "background-color: #FEE2E2; color: #991B1B; font-weight: bold;"
                elif any(x in s for x in ["review", "verbal", "2", "3", "coaching"]):
                    return "background-color: #FEF3C7; color: #92400E; font-weight: bold;"
                return "background-color: #D1FAE5; color: #065F46; font-weight: bold;"

            target_cols = [c for c in independent_pivot_df.columns if any(k in str(c).lower() for k in ["escalation", "points", "infraction"])]
            
            styler = independent_pivot_df.style
            if hasattr(styler, "map"):
                styled_pivot = styler.map(style_escalation, subset=target_cols if target_cols else None)
            else:
                styled_pivot = styler.applymap(style_escalation, subset=target_cols if target_cols else None)

            st.dataframe(styled_pivot, use_container_width=True, hide_index=True)
        else:
            st.info("No 60-day point infractions logged.")

        st.divider()

        st.write("### 📊 Agent Absence & Lateness Duration Breakdown")
        chart_cols = [c for c in ["Unjustified Absences", "Justified Absences", "Total Late Instances", "Late_Mins_Numeric"] if c in filtered_attendance_df.columns]
        if chart_cols and "Agent Name" in filtered_attendance_df.columns:
            plot_df = filtered_attendance_df.groupby("Agent Name")[chart_cols].sum(numeric_only=True).fillna(0)
            plot_df = plot_df.rename(columns={"Late_Mins_Numeric": "Late Duration (Mins)"})
            st.bar_chart(plot_df)

        st.divider()
        st.write("### 📋 Primary Attendance Log")
        st.dataframe(filtered_attendance_df, use_container_width=True, hide_index=True)
    else:
        st.info("No attendance data found for the selected filter combination.")

# TAB 2: STATUS ADHERENCE
with tab_adherence:
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

    st.markdown("### 🚨 Bottom 5 Adherence Outliers")
    if not filtered_df.empty:
        bottom_5 = filtered_df.sort_values(by="Adherence_%", ascending=True).head(5).copy()
        bottom_5["Adherence %"] = bottom_5["Adherence_%"].apply(lambda x: f"{x:.1f}%")
        bottom_5["Break Overage"] = bottom_5["Exceeded_Break_Mins"].apply(lambda x: f"{int(x)} mins")
        bottom_5["Unaccounted Mins"] = bottom_5["Unaccounted_Mins"].apply(lambda x: f"{int(x)} mins")
        bottom_5["Status Goal"] = bottom_5["Goal_Met"].apply(lambda x: "🟢 Met Goal" if x else "🔴 Below 88%")
        
        outlier_cols = [c for c in ["Account", "site", "role", "Agent Name", "month", "week", "Break Overage", "Unaccounted Mins", "Adherence %", "Status Goal"] if c in bottom_5.columns]
        st.dataframe(bottom_5[outlier_cols], use_container_width=True, hide_index=True)
    else:
        st.info("No outlier data available for the selected filters.")

    st.divider()

    st.subheader("📊 Combined Agent Adherence Performance Matrix (Target: ≥88%)")
    if not filtered_df.empty:
        display_table = filtered_df.copy()
        display_table["Adherence %"] = display_table["Adherence_%"].apply(lambda x: f"{x:.1f}%")
        display_table["Break Overage"] = display_table["Exceeded_Break_Mins"].apply(lambda x: f"{int(x)} mins")
        display_table["Status Goal"] = display_table["Goal_Met"].apply(lambda x: "🟢 Met Goal" if x else "🔴 Below 88%")
        
        cols_to_show = [c for c in ["Account", "month", "week", "site", "role", "Agent Name", "Days_Logged", "Break Overage", "Adherence %", "Status Goal"] if c in display_table.columns]
        st.dataframe(display_table[cols_to_show], use_container_width=True, hide_index=True)
    else:
        st.info("No adherence data found for the selected filters.")

# TAB 3: OPERATIONAL KPI VIEW
with tab_ops_kpi:
    st.subheader("📊 Hub & Site Level KPI Breakdown")
    kpi_cdmx, kpi_tj, kpi_bench = st.tabs(["🇲🇽 CDMX", "🇲🇽 Tijuana", "🎯 KPI Benchmarks"])
    with kpi_cdmx:
        cdmx_df = filtered_raw_df[filtered_raw_df["site"].astype(str).str.lower().isin(["cdmx", "mx", "mexico"])] if "site" in filtered_raw_df.columns else pd.DataFrame()
        st.dataframe(cdmx_df, use_container_width=True, hide_index=True) if not cdmx_df.empty else st.info("No CDMX data found.")
    with kpi_tj:
        tj_df = filtered_raw_df[filtered_raw_df["site"].astype(str).str.lower().isin(["tijuana", "tj"])] if "site" in filtered_raw_df.columns else pd.DataFrame()
        st.dataframe(tj_df, use_container_width=True, hide_index=True) if not tj_df.empty else st.info("No Tijuana data found.")
    with kpi_bench:
        st.table(pd.DataFrame({
            "KPI Metric": ["Status Adherence", "Occupancy", "Shrinkage", "AHT"],
            "Target Benchmark": ["88.0%", "85.0%", "12.0%", "320s"],
            "Current Performance": ["92.1%", "83.4%", "11.2%", "315s"]
        }))

# TAB 4: AGENT SCOPE
with tab_agent_scope:
    st.subheader("👤 Agent Scope & Performance Drilldown")
    if not filtered_raw_df.empty and "Agent Name" in filtered_raw_df.columns:
        agent_list = sorted(filtered_raw_df["Agent Name"].dropna().unique().tolist())
        selected_agent = st.selectbox("Select Agent:", agent_list)
        st.dataframe(filtered_raw_df[filtered_raw_df["Agent Name"] == selected_agent], use_container_width=True, hide_index=True)

# TAB 5: SERVICE HOURS
with tab_service_hours:
    sk1, sk2, sk3, sk4 = st.columns(4)
    with sk1:
        st.markdown('<div class="metric-card"><div class="metric-label">SERVICE HOURS</div><div class="metric-value" style="color: #E11D48;">15.32%</div><div style="font-size: 0.85rem; color: #64748B;">210.98 / 1377.5h billed</div></div>', unsafe_allow_html=True)
    with sk2:
        st.markdown('<div class="metric-card"><div class="metric-label">GAP A TARGET</div><div class="metric-value">1166.52<span style="font-size: 1rem;">h</span></div></div>', unsafe_allow_html=True)
    with sk3:
        st.markdown('<div class="metric-card"><div class="metric-label">OT BILLABLE</div><div class="metric-value">0<span style="font-size: 1rem;">h</span></div></div>', unsafe_allow_html=True)
    with sk4:
        st.markdown('<div class="metric-card"><div class="metric-label">TOTAL BILLABLE</div><div class="metric-value">210.98<span style="font-size: 1rem;">h</span></div></div>', unsafe_allow_html=True)

    st.divider()
    col_rank, col_fact = st.columns([1.3, 1])
    with col_rank:
        st.markdown("### 🏆 Ranking Supervisores")
        st.dataframe(pd.DataFrame({
            "#": [1, 2, 3],
            "SUPERVISOR": ["Erick Medina 🎖️", "Abisaid Ramirez 🎖️", "Araceli Perales 🎖️"],
            "%": ["19%", "15%", "14%"],
            "HRS": ["81.52 / 427.5h", "57 / 380h", "72.47 / 522.5h"],
            "GAP": ["-345.98h", "-323h", "-450.03h"],
            "B.CLI": ["$44.59", "$30.60", "$51.14"]
        }), use_container_width=True, hide_index=True)
    with col_fact:
        st.markdown("### FACTURABILIDAD")
        st.dataframe(pd.DataFrame({
            "Estatus": ["Facturable", "Parcial", "No Facturable"],
            "Agentes": [24, 1, 0],
            "Porcentaje": [96, 4, 0]
        }), use_container_width=True, hide_index=True)

st.divider()
with st.expander("📋 View Master Raw Combined Data Feed"):
    st.dataframe(df_raw, use_container_width=True, hide_index=True)
