import streamlit as st
import pandas as pd
import base64
import urllib.request
import io
import re
import plotly.graph_objects as go
from plotly.subplots import make_subplots
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

# Core Data Helpers
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

def time_to_minutes(val):
    if pd.isna(val):
        return 0.0
    if isinstance(val, (int, float)):
        return float(val) * 1440.0
    val_str = str(val).strip()
    if not val_str or val_str.lower() in ["nan", "none", "0", "0:00", "00:00:00"]:
        return 0.0
    try:
        parts = val_str.split(":")
        if len(parts) == 3:
            return float(parts[0]) * 60.0 + float(parts[1]) + float(parts[2]) / 60.0
        elif len(parts) == 2:
            return float(parts[0]) * 60.0 + float(parts[1])
    except Exception:
        pass
    try:
        return float(val_str)
    except ValueError:
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

@st.cache_data(ttl=300)
def parse_generic_kpi_sheet(sheet_id, gid):
    df_raw = fetch_raw_csv(sheet_id, gid)
    if df_raw.empty:
        return pd.DataFrame()

    header_idx = 0
    keywords = ["kpi", "metric", "project", "week", "date", "target", "score", "agent", "qa"]
    for i in range(min(15, len(df_raw))):
        row_cells = [str(x).strip().lower() for x in df_raw.iloc[i].fillna("").tolist()]
        if any(any(k in x for k in keywords) for x in row_cells):
            header_idx = i
            break

    headers = [str(c).strip() if str(c).strip() != "nan" else f"Col_{j}" for j, c in enumerate(df_raw.iloc[header_idx].tolist())]
    df_clean = df_raw.iloc[header_idx + 1:].copy()
    df_clean.columns = headers
    return df_clean.dropna(how="all").reset_index(drop=True)

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
        elif any(k in clow for k in ["role", "position"]):
            df_clean = df_clean.rename(columns={c: "role"})

    if "Agent Name" in df_clean.columns:
        df_clean = df_clean[
            ~df_clean["Agent Name"].astype(str).str.lower().str.contains("total|grand total|blank|nan", na=False)
        ]

    if "site" in df_clean.columns:
        df_clean["site"] = df_clean["site"].apply(normalize_site)

    if "role" in df_clean.columns:
        df_clean["role"] = df_clean["role"].astype(str).str.strip().str.upper()

    return df_clean.reset_index(drop=True)

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
    
    if "month" in df_clean.columns:
        df_clean["month_clean"] = df_clean["month"].astype(str).str.strip()
    else:
        df_clean["month_clean"] = "August 2026"

    if "Account" not in df_clean.columns: df_clean["Account"] = "TDS"
    if "role" not in df_clean.columns: 
        df_clean["role"] = "CSA"
    else:
        df_clean["role"] = df_clean["role"].astype(str).str.strip().str.upper()

    if "Total Late Time" in df_clean.columns:
        df_clean["Late_Mins_Numeric"] = df_clean["Total Late Time"].apply(time_to_minutes)
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
    df_clean["role"] = df_data.iloc[:, 4].astype(str).str.strip().str.upper()

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
        combined_df["month_clean"] = parsed_dates.dt.strftime("%B %Y").fillna("August 2026")
    else:
        combined_df["month_clean"] = "August 2026"

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

# Load Operational KPI Sheets
cdmx_kpis_df = parse_generic_kpi_sheet("1RW3LApb5TgMtdtBKqKHfZ3_t3sBQYCuUZqp8owA3ndM", "1978250855")
tj_kpis_df = parse_generic_kpi_sheet("12uF_syUu7enzOjob7di6c2UlPa6-EUgcTUHG7UcIMgk", "517756888")
cdmx_weekly_trends_df = parse_generic_kpi_sheet("1RW3LApb5TgMtdtBKqKHfZ3_t3sBQYCuUZqp8owA3ndM", "1684808847")

# Filters UI
st.subheader("🔍 Filters & Drilldown")
f0, f1, f2, f3, f4 = st.columns(5)

with f0:
    sites = ["All Sites", "CDMX", "Tijuana"]
    selected_site = st.selectbox("Site:", sites, index=1)

site_filtered_raw = df_raw.copy()
site_filtered_att = attendance_raw_df.copy()

if selected_site != "All Sites":
    if "site" in site_filtered_raw.columns:
        site_filtered_raw = site_filtered_raw[site_filtered_raw["site"].astype(str).str.strip().str.lower() == selected_site.lower()]
    if "site" in site_filtered_att.columns:
        site_filtered_att = site_filtered_att[site_filtered_att["site"].astype(str).str.strip().str.lower() == selected_site.lower()]

with f1:
    accounts = ["All Accounts"]
    all_acc = set()
    if "Account" in site_filtered_att.columns: all_acc.update(site_filtered_att["Account"].dropna().unique())
    if "Account" in site_filtered_raw.columns: all_acc.update(site_filtered_raw["Account"].dropna().unique())
    accounts += sorted([a for a in all_acc if a and str(a).lower() != "nan"])
    selected_account = st.selectbox("Account / Source:", accounts, index=0)

with f2:
    months = ["All Months"]
    all_months = set()
    if "month_clean" in site_filtered_att.columns: all_months.update(site_filtered_att["month_clean"].dropna().unique())
    if "month_clean" in site_filtered_raw.columns: all_months.update(site_filtered_raw["month_clean"].dropna().unique())
    
    clean_months = sorted([m for m in all_months if m and str(m).lower() != "nan"])
    months += clean_months
    
    aug_idx = months.index("August 2026") if "August 2026" in months else 0
    selected_month = st.selectbox("Month:", months, index=aug_idx)

with f3:
    all_weeks = set()
    if "week" in site_filtered_att.columns: all_weeks.update(site_filtered_att["week"].dropna().unique())
    if "week" in site_filtered_raw.columns: all_weeks.update(site_filtered_raw["week"].dropna().unique())
    available_weeks = sorted(
        [w for w in all_weeks if w and str(w).lower() != "nan"], 
        key=lambda x: int(re.search(r'\d+', str(x)).group()) if re.search(r'\d+', str(x)) else 0
    )
    selected_weeks = st.multiselect("Work Week (Leave empty for ALL weeks):", options=available_weeks, default=[])

with f4:
    all_roles = set()
    if "role" in site_filtered_raw.columns:
        all_roles.update(site_filtered_raw["role"].dropna().astype(str).str.strip().str.upper().unique())
    if "role" in site_filtered_att.columns:
        all_roles.update(site_filtered_att["role"].dropna().astype(str).str.strip().str.upper().unique())
    
    roles_available = sorted([r for r in all_roles if r and r not in ["NAN", "NONE", "ROLE", "POSITION", "UNKNOWN ROLE"]])
    selected_roles = st.multiselect("Role (Position) (Leave empty for ALL roles):", options=roles_available, default=[])

def apply_common_filters(df, strict_month=True):
    if df.empty:
        return df
    dff = df.copy()
    
    if selected_site != "All Sites" and "site" in dff.columns:
        dff = dff[dff["site"].astype(str).str.strip().str.lower() == selected_site.lower()]

    if selected_account != "All Accounts" and "Account" in dff.columns:
        dff = dff[dff["Account"].astype(str).str.strip().str.lower() == selected_account.strip().lower()]

    if strict_month and selected_month != "All Months":
        target_month = selected_month.strip().lower()
        if "month_clean" in dff.columns:
            dff = dff[dff["month_clean"].astype(str).str.strip().str.lower() == target_month]

    if len(selected_weeks) > 0 and "week" in dff.columns:
        selected_weeks_lower = [w.lower().strip() for w in selected_weeks]
        dff = dff[dff["week"].astype(str).str.strip().str.lower().isin(selected_weeks_lower)]

    if len(selected_roles) > 0 and "role" in dff.columns:
        active_roles_upper = [r.upper().strip() for r in selected_roles]
        dff = dff[dff["role"].astype(str).str.strip().str.upper().isin(active_roles_upper)]
        
    return dff

filtered_attendance_df = apply_common_filters(attendance_raw_df, strict_month=True)
filtered_raw_df = apply_common_filters(df_raw, strict_month=True)

def apply_pivot_filters(df):
    if df.empty:
        return df
    dff = df.copy()
    if selected_site != "All Sites" and "site" in dff.columns:
        dff = dff[dff["site"].astype(str).str.strip().str.lower() == selected_site.lower()]
    if len(selected_roles) > 0 and "role" in dff.columns:
        active_roles_upper = [r.upper().strip() for r in selected_roles]
        dff = dff[dff["role"].astype(str).str.strip().str.upper().isin(active_roles_upper)]
    return dff

independent_pivot_df = apply_pivot_filters(pivot_attendance_df)

# Metrics & Aggregations
SHIFT_MINS_PER_DAY = 480.0 
group_cols = ["Account", "month_clean", "week", "site", "role", "Agent Name"]
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
tab_attendance, tab_adherence, tab_ops_kpi, tab_agent_scope, tab_service_hours, tab_qa = st.tabs([
    "📅 Attendance", 
    "🎯 Status Adherence", 
    "📊 Operational KPI View", 
    "👤 Agent Scope", 
    "⏱️ Service Hours per Campaign",
    "🛡️ Quality Assurance"
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
        working_att = filtered_attendance_df.copy()
        working_att["Unjustified Absences"] = pd.to_numeric(working_att.get("Unjustified Absences", 0), errors='coerce').fillna(0)
        working_att["Justified Absences"] = pd.to_numeric(working_att.get("Justified Absences", 0), errors='coerce').fillna(0)
        working_att["Late_Mins_Numeric"] = pd.to_numeric(working_att.get("Late_Mins_Numeric", 0), errors='coerce').fillna(0)
        working_att["Total Late Instances"] = pd.to_numeric(working_att.get("Total Late Instances", 0), errors='coerce').fillna(0)

        agent_totals = working_att.groupby("Agent Name", as_index=False).agg({
            "Unjustified Absences": "sum",
            "Justified Absences": "sum",
            "Total Late Instances": "sum",
            "Late_Mins_Numeric": "sum"
        })

        active_headcount = agent_totals["Agent Name"].nunique()
        unjustified_absences = int(agent_totals["Unjustified Absences"].sum())
        justified_absences = int(agent_totals["Justified Absences"].sum())
        late_instances = int(agent_totals["Total Late Instances"].sum())
        total_late_mins = float(agent_totals["Late_Mins_Numeric"].sum())

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

        st.write("### 📌 Attendance Point Infractions (Rolling 60-Day Pivot Tracker)")
        st.caption("ℹ️ Unfiltered by Month/Week filters as infractions operate on a 60-day running window.")
        
        if not independent_pivot_df.empty:
            def style_escalation_status(val):
                s = str(val).strip().lower()
                if "terminate" in s:
                    return "background-color: #7F1D1D; color: #FFFFFF; font-weight: bold;"
                elif "probation" in s:
                    return "background-color: #F97316; color: #FFFFFF; font-weight: bold;"
                elif "written warning" in s or "final" in s:
                    return "background-color: #FEE2E2; color: #991B1B; font-weight: bold;"
                elif "verbal warning" in s or "coaching" in s or "review" in s:
                    return "background-color: #FEF3C7; color: #92400E; font-weight: bold;"
                elif "safe" in s or "0" in s or "none" in s:
                    return "background-color: #D1FAE5; color: #065F46; font-weight: bold;"
                return ""

            esc_cols = [c for c in independent_pivot_df.columns if "escalation" in str(c).lower()]
            styler = independent_pivot_df.style
            if esc_cols:
                styled_pivot = styler.map(style_escalation_status, subset=esc_cols) if hasattr(styler, "map") else styler.applymap(style_escalation_status, subset=esc_cols)
            else:
                styled_pivot = styler

            st.dataframe(styled_pivot, use_container_width=True, hide_index=True)
        else:
            st.info("No 60-day point infractions logged.")

        st.divider()

        st.write("### 📊 Agent Absence & Lateness Duration Breakdown")
        if not agent_totals.empty:
            plot_df = agent_totals.set_index("Agent Name").rename(columns={"Late_Mins_Numeric": "Late Duration (Mins)"})
            st.bar_chart(plot_df[["Unjustified Absences", "Justified Absences", "Total Late Instances", "Late Duration (Mins)"]])

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
        
        outlier_cols = [c for c in ["Account", "site", "role", "Agent Name", "month_clean", "week", "Break Overage", "Unaccounted Mins", "Adherence %", "Status Goal"] if c in bottom_5.columns]
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
        
        cols_to_show = [c for c in ["Account", "month_clean", "week", "site", "role", "Agent Name", "Days_Logged", "Break Overage", "Adherence %", "Status Goal"] if c in display_table.columns]
        st.dataframe(display_table[cols_to_show], use_container_width=True, hide_index=True)
    else:
        st.info("No adherence data found for the selected filters.")

# TAB 3: OPERATIONAL KPI VIEW
with tab_ops_kpi:
    st.subheader("📊 Operational Hub & Site-Level KPI Breakdown")
    kpi_cdmx, kpi_tj, kpi_trends = st.tabs([
        "🇲🇽 CDMX Operational KPIs", 
        "🇲🇽 Tijuana Operational KPIs", 
        "📈 CDMX Master Weekly Trends (By Project)"
    ])
    
    with kpi_cdmx:
        st.markdown("[🔗 Open Live CDMX KPI Sheet](https://docs.google.com/spreadsheets/d/1RW3LApb5TgMtdtBKqKHfZ3_t3sBQYCuUZqp8owA3ndM/edit#gid=1978250855)")
        if not cdmx_kpis_df.empty:
            st.dataframe(cdmx_kpis_df, use_container_width=True, hide_index=True)
        else:
            st.info("No CDMX KPI data currently loaded.")

    with kpi_tj:
        st.markdown("[🔗 Open Live Tijuana KPI Sheet](https://docs.google.com/spreadsheets/d/12uF_syUu7enzOjob7di6c2UlPa6-EUgcTUHG7UcIMgk/edit#gid=517756888)")
        if not tj_kpis_df.empty:
            st.dataframe(tj_kpis_df, use_container_width=True, hide_index=True)
        else:
            st.info("No Tijuana KPI data currently loaded.")

    with kpi_trends:
        st.markdown("[🔗 Open Live CDMX Master Log Sheet](https://docs.google.com/spreadsheets/d/1RW3LApb5TgMtdtBKqKHfZ3_t3sBQYCuUZqp8owA3ndM/edit#gid=1684808847)")
        
        if not cdmx_weekly_trends_df.empty:
            trends_df = cdmx_weekly_trends_df.copy()
            
            col_mapping = {c: c.strip() for c in trends_df.columns}
            trends_df = trends_df.rename(columns=col_mapping)
            
            project_col = next((c for c in trends_df.columns if "project" in c.lower()), None)
            site_col = next((c for c in trends_df.columns if c.lower() in ["site", "hub"]), None)
            week_col = next((c for c in trends_df.columns if "week label" in c.lower() or "week" in c.lower()), None)
            show_rate_col = next((c for c in trends_df.columns if "show rate" in c.lower() or "wtd show" in c.lower()), None)

            tf1, tf2, tf3 = st.columns(3)
            
            with tf1:
                proj_options = ["All Projects"]
                if project_col:
                    proj_options += sorted(trends_df[project_col].dropna().unique().tolist())
                sel_proj = st.selectbox("Filter Project:", proj_options)

            with tf2:
                site_options = ["All Sites"]
                if site_col:
                    site_options += sorted(trends_df[site_col].dropna().unique().tolist())
                sel_trend_site = st.selectbox("Filter Hub Site:", site_options)

            with tf3:
                week_options = ["All Weeks"]
                if week_col:
                    week_options += sorted(trends_df[week_col].dropna().unique().tolist())
                sel_trend_week = st.selectbox("Filter Trend Week:", week_options)

            filtered_trends = trends_df.copy()
            if sel_proj != "All Projects" and project_col:
                filtered_trends = filtered_trends[filtered_trends[project_col] == sel_proj]
            if sel_trend_site != "All Sites" and site_col:
                filtered_trends = filtered_trends[filtered_trends[site_col] == sel_trend_site]
            if sel_trend_week != "All Weeks" and week_col:
                filtered_trends = filtered_trends[filtered_trends[week_col] == sel_trend_week]

            st.dataframe(filtered_trends, use_container_width=True, hide_index=True)
        else:
            st.info("No Weekly Trend data found.")

# TAB 4: AGENT SCOPE
with tab_agent_scope:
    st.subheader("👤 Individual Agent Deep-Dive & Profile")
    
    available_agents = []
    if not filtered_raw_df.empty and "Agent Name" in filtered_raw_df.columns:
        available_agents = sorted(filtered_raw_df["Agent Name"].dropna().unique().tolist())
    
    if available_agents:
        selected_agent = st.selectbox("Select Agent for Detailed Inspection:", available_agents)
        
        agent_raw = filtered_raw_df[filtered_raw_df["Agent Name"] == selected_agent]
        agent_att = filtered_attendance_df[filtered_attendance_df["Agent Name"] == selected_agent] if not filtered_attendance_df.empty else pd.DataFrame()
        agent_pivot = independent_pivot_df[independent_pivot_df["Agent Name"] == selected_agent] if not independent_pivot_df.empty else pd.DataFrame()

        ag1, ag2, ag3, ag4 = st.columns(4)
        
        avg_adh = agent_raw["Parsed_Adherence"].mean() if "Parsed_Adherence" in agent_raw.columns and not agent_raw["Parsed_Adherence"].isna().all() else 0.0
        tot_overage = agent_raw["Exceeded_Break_Raw_Mins"].sum() if "Exceeded_Break_Raw_Mins" in agent_raw.columns else 0.0
        tot_unaccounted = agent_raw["Unaccounted_Mins"].sum() if "Unaccounted_Mins" in agent_raw.columns else 0.0
        
        unjustified = int(agent_att["Unjustified Absences"].sum()) if not agent_att.empty and "Unjustified Absences" in agent_att.columns else 0

        ag1.metric("🎯 Avg Adherence", f"{avg_adh:.1f}%")
        ag2.metric("⏱️ Break Overage", f"{int(tot_overage)} Mins")
        ag3.metric("❓ Unaccounted Time", f"{int(tot_unaccounted)} Mins")
        ag4.metric("⚠️ Unjustified Absences", f"{unjustified}")

        st.divider()

        st.write("### 📜 Agent Daily Log History")
        log_cols = [c for c in ["Date", "week", "site", "role", "Total Break", "Total Meal", "Exceeded_Break_Raw", "Unaccounted", "Direct_Adherence"] if c in agent_raw.columns]
        st.dataframe(agent_raw[log_cols], use_container_width=True, hide_index=True)

        if not agent_pivot.empty:
            st.divider()
            st.write("### 📌 Active Infraction & Escalation Status (60-Day Window)")
            st.dataframe(agent_pivot, use_container_width=True, hide_index=True)
    else:
        st.info("No agent data available under current filters.")

# TAB 5: SERVICE HOURS PER CAMPAIGN
with tab_service_hours:
    st.subheader("⏱️ Service Hours Delivered per Campaign")
    
    if not filtered_raw_df.empty:
        hours_df = filtered_raw_df.copy()
        
        hours_df["Break_Hours"] = hours_df["Total Break_Mins"] / 60.0
        hours_df["Meal_Hours"] = hours_df["Total Meal_Mins"] / 60.0
        
        campaign_summary = hours_df.groupby(["Account", "site"], as_index=False).agg(
            Total_Records=("Agent Name", "count"),
            Total_Break_Hours=("Break_Hours", "sum"),
            Total_Meal_Hours=("Meal_Hours", "sum"),
            Avg_Adherence=("Parsed_Adherence", "mean")
        )
        
        campaign_summary["Avg_Adherence"] = campaign_summary["Avg_Adherence"].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else "N/A")
        campaign_summary["Total_Break_Hours"] = campaign_summary["Total_Break_Hours"].apply(lambda x: f"{x:.1f} hrs")
        campaign_summary["Total_Meal_Hours"] = campaign_summary["Total_Meal_Hours"].apply(lambda x: f"{x:.1f} hrs")

        st.dataframe(campaign_summary, use_container_width=True, hide_index=True)
    else:
        st.info("No service hour data available.")

# TAB 6: QUALITY ASSURANCE
with tab_qa:
    st.subheader("🛡️ Quality Assurance Overview")
    st.info("Integration point for QA Audit sheets, Scorecards, and Evaluation Metrics.")
