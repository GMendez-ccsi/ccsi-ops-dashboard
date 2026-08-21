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
                proj_options = ["All Projects"] + sorted(trends_df[project_col].dropna().unique().tolist()) if project_col else ["All Projects"]
                sel_proj = st.selectbox("Filter Project:", proj_options, key="trend_proj_filter")
                
            with tf2:
                site_options = ["All Hubs/Sites"] + sorted(trends_df[site_col].dropna().unique().tolist()) if site_col else ["All Hubs/Sites"]
                sel_site = st.selectbox("Filter Hub / Site:", site_options, key="trend_site_filter")
                
            with tf3:
                week_options = ["All Weeks"] + sorted(trends_df[week_col].dropna().unique().tolist()) if week_col else ["All Weeks"]
                sel_week = st.selectbox("Filter Week Label:", week_options, key="trend_week_filter")

            filtered_trends = trends_df.copy()
            if sel_proj != "All Projects" and project_col:
                filtered_trends = filtered_trends[filtered_trends[project_col] == sel_proj]
            if sel_site != "All Hubs/Sites" and site_col:
                filtered_trends = filtered_trends[filtered_trends[site_col] == sel_site]
            if sel_week != "All Weeks" and week_col:
                filtered_trends = filtered_trends[filtered_trends[week_col] == sel_week]

            st.divider()

            if show_rate_col and not filtered_trends.empty:
                filtered_trends["_parsed_show_rate"] = (
                    filtered_trends[show_rate_col]
                    .astype(str)
                    .str.replace("%", "")
                    .str.strip()
                )
                filtered_trends["_parsed_show_rate"] = pd.to_numeric(filtered_trends["_parsed_show_rate"], errors="coerce")

                outlier_col1, outlier_col2 = st.columns(2)

                with outlier_col1:
                    st.markdown("### 🟢 Top 5 Performers (Show Rate)")
                    top_5 = (
                        filtered_trends.sort_values(by="_parsed_show_rate", ascending=False)
                        .dropna(subset=["_parsed_show_rate"])
                        .head(5)
                        .drop(columns=["_parsed_show_rate"])
                    )
                    st.dataframe(top_5, use_container_width=True, hide_index=True)

                with outlier_col2:
                    st.markdown("### 🔴 Bottom 5 Outliers (Show Rate)")
                    bottom_5 = (
                        filtered_trends.sort_values(by="_parsed_show_rate", ascending=True)
                        .dropna(subset=["_parsed_show_rate"])
                        .head(5)
                        .drop(columns=["_parsed_show_rate"])
                    )
                    st.dataframe(bottom_5, use_container_width=True, hide_index=True)

                filtered_trends = filtered_trends.drop(columns=["_parsed_show_rate"])

            st.divider()
            st.markdown("### 📋 Filtered Weekly Trends Log")
            st.dataframe(filtered_trends, use_container_width=True, hide_index=True)
        else:
            st.info("No CDMX Weekly Trends data currently loaded.")

# TAB 4: AGENT SCOPE
with tab_agent_scope:
    st.subheader("👤 Agent Scope & Performance Drilldown")

    if not filtered_raw_df.empty:
        scope_df = filtered_raw_df.copy()

        scope_group_cols = ["Agent Name", "Account", "site", "role", "month_clean", "week"]
        valid_scope_cols = [c for c in scope_group_cols if c in scope_df.columns]

        agent_perf = (
            scope_df.groupby(valid_scope_cols, as_index=False)
            .agg(
                Days_Logged=("Date", "nunique") if "Date" in scope_df.columns else ("Total Break_Mins", "count"),
                Total_Break_Mins=("Total Break_Mins", "sum"),
                Exceeded_Break_Mins=("Exceeded_Break_Raw_Mins", "sum"),
                Total_Meal_Mins=("Total Meal_Mins", "sum"),
                Unaccounted_Mins=("Unaccounted_Mins", "sum"),
                Direct_Adherence_Avg=("Parsed_Adherence", "mean")
            )
        )

        agent_perf["Scheduled_Mins"] = agent_perf["Days_Logged"] * SHIFT_MINS_PER_DAY
        agent_perf["Total_Lost_Mins"] = agent_perf["Unaccounted_Mins"] + agent_perf["Exceeded_Break_Mins"]
        agent_perf["Adherence_%"] = agent_perf["Direct_Adherence_Avg"]

        missing_adh = agent_perf["Adherence_%"].isna()
        if missing_adh.any():
            calc_adh = (
                (1 - (agent_perf.loc[missing_adh, "Total_Lost_Mins"] / agent_perf.loc[missing_adh, "Scheduled_Mins"])) * 100
            ).clip(lower=0, upper=100)
            agent_perf.loc[missing_adh, "Adherence_%"] = calc_adh

        st.markdown("#### ⏱️ Outlier Time Period Selection")
        scope_col1, scope_col2 = st.columns(2)

        with scope_col1:
            group_by_period = st.radio(
                "View Outliers By:", 
                ["By Week", "By Month"], 
                horizontal=True, 
                key="agent_scope_period_type"
            )

        with scope_col2:
            if group_by_period == "By Week":
                week_opts = ["All Filtered Weeks"] + sorted(agent_perf["week"].dropna().unique().tolist())
                selected_scope_time = st.selectbox("Select Week:", week_opts, key="agent_scope_week_sel")
            else:
                month_opts = ["All Filtered Months"] + sorted(agent_perf["month_clean"].dropna().unique().tolist())
                selected_scope_time = st.selectbox("Select Month:", month_opts, key="agent_scope_month_sel")

        outlier_filtered = agent_perf.copy()
        if group_by_period == "By Week" and selected_scope_time != "All Filtered Weeks":
            outlier_filtered = outlier_filtered[outlier_filtered["week"] == selected_scope_time]
        elif group_by_period == "By Month" and selected_scope_time != "All Filtered Months":
            outlier_filtered = outlier_filtered[outlier_filtered["month_clean"] == selected_scope_time]

        st.divider()

        out_col1, out_col2 = st.columns(2)

        with out_col1:
            st.markdown("### 🟢 Top 5 Performers (Adherence %)")
            top_5_agents = (
                outlier_filtered.sort_values(by="Adherence_%", ascending=False)
                .head(5)
                .copy()
            )
            top_5_agents["Adherence %"] = top_5_agents["Adherence_%"].apply(lambda x: f"{x:.1f}%")
            top_5_agents["Break Overage"] = top_5_agents["Exceeded_Break_Mins"].apply(lambda x: f"{int(x)} mins")
            
            display_cols = [c for c in ["Agent Name", "site", "role", "month_clean", "week", "Adherence %", "Break Overage"] if c in top_5_agents.columns]
            st.dataframe(top_5_agents[display_cols], use_container_width=True, hide_index=True)

        with out_col2:
            st.markdown("### 🔴 Bottom 5 Outliers (Adherence %)")
            bottom_5_agents = (
                outlier_filtered.sort_values(by="Adherence_%", ascending=True)
                .head(5)
                .copy()
            )
            bottom_5_agents["Adherence %"] = bottom_5_agents["Adherence_%"].apply(lambda x: f"{x:.1f}%")
            bottom_5_agents["Break Overage"] = bottom_5_agents["Exceeded_Break_Mins"].apply(lambda x: f"{int(x)} mins")
            
            display_cols = [c for c in ["Agent Name", "site", "role", "month_clean", "week", "Adherence %", "Break Overage"] if c in bottom_5_agents.columns]
            st.dataframe(bottom_5_agents[display_cols], use_container_width=True, hide_index=True)

        st.divider()

        st.markdown("### 🔍 Individual Agent Log Search")
        agent_list = sorted(filtered_raw_df["Agent Name"].dropna().unique().tolist())
        selected_agent = st.selectbox("Select Agent for Granular Log View:", agent_list, key="agent_scope_select")
        st.dataframe(filtered_raw_df[filtered_raw_df["Agent Name"] == selected_agent], use_container_width=True, hide_index=True)
    else:
        st.info("No raw log data available for the active global filters.")

# TAB 5: SERVICE HOURS PER CAMPAIGN
with tab_service_hours:
    head_col1, head_col2 = st.columns([3, 1])
    with head_col1:
        st.subheader("⏱️ Service Hours & Facturabilidad per Campaign")
    with head_col2:
        st.markdown("[🔗 Open Live Service Hours Sheet](https://docs.google.com/spreadsheets/d/1PEybVFo8uL4jfasxJfrvWtEFHyk1EYGmsjLnMgk1Qt4/edit#gid=1459025310)")

    months = ["Jan-26", "Feb-26", "Mar-26", "Apr-26", "May-26", "Jun-26", "Jul-26", "Aug-26", "Sep-26", "Oct-26", "Nov-26", "Dec-26"]
    
    # Complete dataset including FTE, Target, Accrued, %, and MoM
    data_matrix = {
        "Month": months,
        # CDMX Metrics
        "CDMX_FTE": [32, 32, 31, 30, 31, 31, 31, 31, 31, 31, 31, 31],
        "CDMX_Target": [6678.5, 6080.0, 6526.0, 6374.5, 6222.5, 6080.0, 6051.5, 5652.5, 5529.0, 5652.5, 5491.0, 5747.5],
        "CDMX_Accrued": [5330.338, 5673.986, 5986.862, 5475.0, 5768.27, 5617.34, 5626.0, 5500.0, 0.0, 0.0, 0.0, 0.0],
        "CDMX_Pct": [79.81, 93.32, 91.74, 85.89, 92.70, 92.39, 92.97, 97.30, 0.0, 0.0, 0.0, 0.0],
        "CDMX_MoM": [None, 13.51, -1.58, -5.85, 6.81, -0.31, 0.58, 4.33, None, None, None, None],
        
        # TJ Metrics
        "TJ_FTE": [7, 7, 7, 7, 6, 6, 6, 6, 6, 6, 6, 6],
        "TJ_Target": [1463.0, 1330.0, 1463.0, 1463.0, 1206.5, 1244.5, 1292.0, 1216.0, 1254.0, 1244.5, 1206.5, 1311.0],
        "TJ_Accrued": [1335.85, 1228.586, 1307.67, 1358.5, 1095.53, 1084.25, 907.6, 1004.0, 0.0, 0.0, 0.0, 0.0],
        "TJ_Pct": [91.31, 92.37, 89.38, 92.86, 90.80, 87.12, 70.25, 82.57, 0.0, 0.0, 0.0, 0.0],
        "TJ_MoM": [None, 1.07, -2.99, 3.47, -2.05, -3.68, -16.88, 12.32, None, None, None, None],
    }

    # Plotly Chart Generator
    def create_site_chart(site_name, target_vals, accrued_vals, pct_vals):
        fig = make_subplots(specs=[[{"secondary_y": True}]])

        # Target Hours Bar
        fig.add_trace(
            go.Bar(
                x=months, 
                y=target_vals, 
                name="Target Hours", 
                marker_color="#4B9CD3",
                text=[f"{v:g}" for v in target_vals],
                textposition="auto"
            ),
            secondary_y=False,
        )

        # Accrued Hours Bar
        fig.add_trace(
            go.Bar(
                x=months, 
                y=accrued_vals, 
                name="Accrued", 
                marker_color="#52B788",
                text=[f"{v:g}" if v > 0 else "0" for v in accrued_vals],
                textposition="auto"
            ),
            secondary_y=False,
        )

        # % Line Trace
        fig.add_trace(
            go.Scatter(
                x=months, 
                y=pct_vals, 
                name="%", 
                mode="lines+markers+text",
                line=dict(color="#FF9F1C", width=2, dash="dash"),
                marker=dict(symbol="star", size=9, color="#FF9F1C"),
                text=[f"{v:.2f}%" if v > 0 else "" for v in pct_vals],
                textposition="top center",
                textfont=dict(color="#FF9F1C", size=11)
            ),
            secondary_y=True,
        )

        fig.update_layout(
            title=dict(text=f"<b>{site_name} Performance</b>", font=dict(size=18, color="#333")),
            barmode="group",
            bargap=0.2,
            bargroupgap=0.05,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
            margin=dict(l=20, r=20, t=50, b=20),
            height=350,
            paper_bgcolor="white",
            plot_bgcolor="#F9F9F9"
        )

        fig.update_yaxes(title_text="", secondary_y=False, showgrid=True, gridcolor="#E5E5E5")
        fig.update_yaxes(title_text="", secondary_y=True, range=[0, 125], showgrid=False, ticksuffix="%")
        
        return fig

    # 1. Render Dual-Axis Charts
    st.plotly_chart(create_site_chart("TJ", data_matrix["TJ_Target"], data_matrix["TJ_Accrued"], data_matrix["TJ_Pct"]), use_container_width=True)
    st.plotly_chart(create_site_chart("CDMX", data_matrix["CDMX_Target"], data_matrix["CDMX_Accrued"], data_matrix["CDMX_Pct"]), use_container_width=True)

    st.divider()

    # 2. Month-over-Month Data Table
    st.markdown("### 📈 Month over Month (MoM) Trend & Performance Summary")
    
    # Format DataFrame for UI
    df_mom = pd.DataFrame({
        "CDMX Month": data_matrix["Month"],
        "CDMX FTE": data_matrix["CDMX_FTE"],
        "CDMX Target": data_matrix["CDMX_Target"],
        "CDMX Accrued": data_matrix["CDMX_Accrued"],
        "CDMX %": [f"{v:.2f}%" for v in data_matrix["CDMX_Pct"]],
        "CDMX MoM": [f"{v:+.2f}%" if v is not None else "" for v in data_matrix["CDMX_MoM"]],
        "TJ Month": data_matrix["Month"],
        "TJ FTE": data_matrix["TJ_FTE"],
        "TJ Target": data_matrix["TJ_Target"],
        "TJ Accrued": data_matrix["TJ_Accrued"],
        "TJ %": [f"{v:.2f}%" for v in data_matrix["TJ_Pct"]],
        "TJ MoM": [f"{v:+.2f}%" if v is not None else "" for v in data_matrix["TJ_MoM"]],
    })

    st.dataframe(df_mom, use_container_width=True, hide_index=True)

# TAB 6: QUALITY ASSURANCE
with tab_qa:
    st.subheader("🛡️ Quality Assurance Overview")
    st.markdown("[🔗 Open QA Audit Google Sheet](https://docs.google.com/spreadsheets/d/17blbXU8PWciUJrU0PMTj1iMydQOqPQyGRUYVf3LhbNk/edit#gid=0)")

    @st.cache_data(ttl=300)
    def load_qa_raw_monitoring():
        try:
            sheet_id = "17blbXU8PWciUJrU0PMTj1iMydQOqPQyGRUYVf3LhbNk"
            url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet=MONITORING"
            df = pd.read_csv(url, low_memory=False)
            df.columns = [str(c).strip() for c in df.columns]
            
            if 'week' in df.columns:
                df = df[df['week'].notna() & (df['week'].astype(str).str.strip() != "")]
            return df
        except Exception as e:
            st.error(f"Error loading MONITORING sheet tab: {e}")
            return pd.DataFrame()

    qa_df = load_qa_raw_monitoring()

    if qa_df is not None and not qa_df.empty:
        col_map = {c.lower(): c for c in qa_df.columns}
        
        week_col = col_map.get('week', 'week')
        month_col = col_map.get('month', 'MONTH')
        lead_col = col_map.get('lead', 'LEAD')
        role_col = col_map.get('role', 'ROLE')
        queue_col = col_map.get('queue', 'QUEUE')
        feedback_col = col_map.get('feedback', 'FEEDBACK')
        comment_col = col_map.get('comment', 'COMMENT')

        filtered_qa = qa_df.copy()

        # -------------------------------------------------------------
        # ACCURATE GLOBAL FILTER MATCHING
        # -------------------------------------------------------------

        # 1. Site Filter: Bypassed (All records belong to MX/CDMX)

        # 2. Account / Source Filter -> Maps directly to Column L (QUEUE)
        if 'selected_account' in locals() and selected_account and selected_account != "All Accounts":
            if queue_col in filtered_qa.columns:
                filtered_qa = filtered_qa[
                    filtered_qa[queue_col].astype(str).str.strip().str.upper() == str(selected_account).strip().upper()
                ]

        # 3. Month Filter -> Maps to Column B (MONTH)
        if 'selected_month' in locals() and selected_month and selected_month != "All Months":
            if month_col in filtered_qa.columns:
                # Extract month name (e.g. "August 2026" -> "August")
                clean_month = str(selected_month).split()[0].strip().upper()
                filtered_qa = filtered_qa[
                    filtered_qa[month_col].astype(str).str.strip().str.upper() == clean_month
                ]

        # 4. Work Week Filter -> Extracts digits to match Column A (e.g. "Week 34" -> 34)
        if 'selected_weeks' in locals() and len(selected_weeks) > 0:
            if week_col in filtered_qa.columns:
                target_weeks = [
                    ''.join(filter(str.isdigit, str(w))) 
                    for w in selected_weeks if ''.join(filter(str.isdigit, str(w))) != ""
                ]
                if target_weeks:
                    raw_weeks_clean = (
                        filtered_qa[week_col]
                        .astype(str)
                        .apply(lambda x: ''.join(filter(str.isdigit, x)))
                    )
                    filtered_qa = filtered_qa[raw_weeks_clean.isin(target_weeks)]

        # 5. Role Filter -> Maps dashboard selection to Column J (ROLE)
        if 'selected_roles' in locals() and len(selected_roles) > 0:
            if role_col in filtered_qa.columns:
                role_keywords = []
                for r in selected_roles:
                    r_str = str(r).lower()
                    if "reservation" in r_str:
                        role_keywords.append("reservationist")
                    elif "csa" in r_str:
                        role_keywords.append("csa")
                    elif "hybrid" in r_str:
                        role_keywords.append("hybrid")
                    elif "leader" in r_str or "lead" in r_str:
                        role_keywords.append("team leader")

                if role_keywords:
                    pattern = "|".join(role_keywords)
                    role_series = filtered_qa[role_col].astype(str).str.strip().str.lower()
                    filtered_qa = filtered_qa[role_series.str.contains(pattern, na=False)]

        qa_tab1, qa_tab2, qa_tab3 = st.tabs([
            "📌 Weekly Areas of Opportunity", 
            "📊 TL Virtual Monitoring Pivot", 
            "📋 Master QA Dataset"
        ])

        # -------------------------------------------------------------
        # SUB-TAB 1: MAJOR AREAS OF OPPORTUNITY
        # -------------------------------------------------------------
        with qa_tab1:
            st.markdown("### 💡 Major Areas of Opportunity Summary")
            
            target_opp_col = feedback_col if feedback_col in filtered_qa.columns else comment_col

            if target_opp_col in filtered_qa.columns and week_col in filtered_qa.columns:
                opp_df = filtered_qa[[week_col, target_opp_col]].dropna(subset=[target_opp_col]).copy()
                opp_df[target_opp_col] = opp_df[target_opp_col].astype(str).str.strip()
                opp_df = opp_df[opp_df[target_opp_col] != ""]

                positive_keywords = ["good interaction", "positive and effective", "great job", "no areas for improvement", "perfect call"]
                opp_only_df = opp_df[~opp_df[target_opp_col].str.lower().str.contains("|".join(positive_keywords))]

                if not opp_only_df.empty:
                    def categorize_opportunity(text):
                        t = text.lower()
                        if "script order" in t or "sequence" in t:
                            return "Script Order & Sequence Adherence"
                        elif "greeting" in t or "opening" in t:
                            return "Mandatory Greeting / Script Opening"
                        elif "closing" in t or "call exit" in t:
                            return "Mandatory Closing Script"
                        elif "identity" in t or "verification" in t or "first and last name" in t:
                            return "Customer Identity Verification"
                        elif "reservation" in t or "trip details" in t:
                            return "Trip & Reservation Data Collection"
                        else:
                            return "General Script & Policy Adherence"

                    opp_only_df['Category'] = opp_only_df[target_opp_col].apply(categorize_opportunity)
                    
                    top_category = opp_only_df['Category'].value_counts().idxmax()
                    st.info(f"🎯 **Top Area of Opportunity:** {top_category}")

                    cat_summary = (
                        opp_only_df.groupby([week_col, 'Category'])
                        .size()
                        .reset_index(name="Frequency Count")
                        .sort_values(by=[week_col, "Frequency Count"], ascending=[True, False])
                    )
                    
                    st.markdown("**Opportunities Categorized by Week**")
                    st.dataframe(cat_summary, use_container_width=True, hide_index=True)

                    st.divider()
                    st.markdown("**Detailed Feedback Log**")
                    st.dataframe(opp_only_df[[week_col, target_opp_col]], use_container_width=True, hide_index=True)
                else:
                    st.warning("No improvement areas logged for the selected filter combination.")
            else:
                st.warning("Could not find feedback or week columns.")

        # -------------------------------------------------------------
        # SUB-TAB 2: TL VIRTUAL MONITORED SESSIONS PIVOT
        # -------------------------------------------------------------
        with qa_tab2:
            st.markdown("### 🔍 TL Virtual Monitored Sessions Pivot")

            if lead_col in filtered_qa.columns and week_col in filtered_qa.columns:
                m1, m2, m3 = st.columns(3)
                m1.metric("🎧 Total Monitored Sessions", f"{len(filtered_qa):,}")
                m2.metric("👥 Active Team Leads", filtered_qa[lead_col].nunique())
                m3.metric("📅 Weeks Covered", filtered_qa[week_col].nunique())

                st.divider()

                st.markdown("**Matrix View: Monitored Sessions (Team Lead vs Week)**")
                tl_week_matrix = pd.crosstab(
                    index=filtered_qa[lead_col],
                    columns=filtered_qa[week_col],
                    margins=True,
                    margins_name="Total Monitored"
                )
                st.dataframe(tl_week_matrix, use_container_width=True)

                st.divider()

                st.markdown("**Detailed Breakdown by Role & Team Lead**")
                pivot_cols = [lead_col]
                if role_col in filtered_qa.columns:
                    pivot_cols.append(role_col)
                pivot_cols.append(week_col)

                tl_breakdown = (
                    filtered_qa.groupby(pivot_cols)
                    .size()
                    .reset_index(name="Total Monitored Sessions")
                    .sort_values(by=[lead_col, week_col], ascending=[True, True])
                )
                st.dataframe(tl_breakdown, use_container_width=True, hide_index=True)
            else:
                st.warning("Unable to identify 'LEAD' or 'week' columns required to build the pivot.")

        # -------------------------------------------------------------
        # SUB-TAB 3: RAW DATASET
        # -------------------------------------------------------------
        with qa_tab3:
            st.markdown("### 📋 Full Raw QA Record Log (`MONITORING` Sheet Tab)")
            st.dataframe(filtered_qa, use_container_width=True, hide_index=True)

    else:
        st.info("No QA data returned from Google Sheets. Check access permissions or filter selections.")
st.divider()
with st.expander("📋 View Master Raw Combined Data Feed"):
    st.dataframe(df_raw, use_container_width=True, hide_index=True)
