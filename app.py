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
    .metric-card {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .metric-value {
        font-size: 2.2rem;
        font-weight: 700;
        color: #0F172A;
    }
    .metric-label {
        font-size: 0.85rem;
        font-weight: 600;
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 0.05em;
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

# Corrected Site Mapping Logic
def normalize_site(val):
    if pd.isna(val) or not str(val).strip():
        return "Unknown"
    s = str(val).strip().upper()
    if s in ["TJ", "TIJUANA"]:
        return "Tijuana"
    if s in ["MX", "CDMX", "MEXICO CITY", "MEXICO"]:
        return "CDMX"
    return str(val).strip()

def fetch_raw_csv(sheet_id, gid):
    gviz_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&gid={gid}"
    req = urllib.request.Request(
        gviz_url, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    )
    try:
        with urllib.request.urlopen(req) as response:
            content = response.read()
        return pd.read_csv(io.BytesIO(content), engine="python", header=None, on_bad_lines="skip").dropna(how="all")
    except Exception as e:
        return pd.DataFrame()

# Parser for Attendance Sheet
@st.cache_data(ttl=1800)
def parse_attendance_sheet(sheet_id, gid):
    df_raw = fetch_raw_csv(sheet_id, gid)
    if df_raw.empty:
        return pd.DataFrame()
    
    header_idx = None
    for i in range(min(20, len(df_raw))):
        row_cells = [str(x).strip().lower() for x in df_raw.iloc[i].fillna("").tolist()]
        if any(k in row_cells for k in ["agent", "name", "employee", "site", "account", "status"]):
            header_idx = i
            break

    if header_idx is not None:
        headers = [str(c).strip() for c in df_raw.iloc[header_idx].tolist()]
        df_data = df_raw.iloc[header_idx + 1:].copy()
        df_data.columns = headers
    else:
        df_data = df_raw.copy()

    df_data = df_data.loc[:, ~df_data.columns.duplicated()].copy()
    df_data = df_data.dropna(how="all")

    for col in df_data.columns:
        df_data[col] = df_data[col].astype(str).str.strip()

    col_map = {}
    for c in df_data.columns:
        if c.lower() in ["site", "location"]: col_map[c] = "site"
        elif c.lower() in ["week", "work week"]: col_map[c] = "week"
        elif c.lower() in ["account"]: col_map[c] = "Account"
        elif c.lower() in ["month"]: col_map[c] = "month"
        elif c.lower() in ["agent name", "agent", "employee"]: col_map[c] = "Agent Name"
    df_data = df_data.rename(columns=col_map)

    if "site" in df_data.columns:
        df_data["site"] = df_data["site"].apply(normalize_site)
    else:
        df_data["site"] = "Unknown"

    if "week" in df_data.columns:
        df_data["week"] = df_data["week"].apply(clean_week_str)
    else:
        df_data["week"] = "Week 1"

    if "month" not in df_data.columns:
        df_data["month"] = "August 2026"
    if "Account" not in df_data.columns:
        df_data["Account"] = "TDS"

    return df_data.reset_index(drop=True)

# Parser for TransDev Sheet
@st.cache_data(ttl=1800)
def parse_transdev_sheet(sheet_id, gid):
    df_raw = fetch_raw_csv(sheet_id, gid)
    if df_raw.empty:
        return pd.DataFrame()
    
    header_idx = None
    for i in range(min(20, len(df_raw))):
        row_cells = [str(x).strip().lower() for x in df_raw.iloc[i].fillna("").tolist()]
        if "site" in row_cells or "position" in row_cells:
            header_idx = i
            break

    df_data = df_raw.iloc[header_idx + 1:].copy() if header_idx is not None else df_raw.copy()
    df_clean = pd.DataFrame()
    
    df_clean["site"] = df_data.iloc[:, 0].astype(str).str.strip().apply(normalize_site)
    df_clean["role"] = df_data.iloc[:, 1].astype(str).str.strip()
    df_clean["week"] = df_data.iloc[:, 3].astype(str).str.strip().apply(clean_week_str)
    df_clean["Date"] = df_data.iloc[:, 4].astype(str).str.strip()
    df_clean["Agent Name"] = df_data.iloc[:, 5].astype(str).str.strip()
    df_clean["Total Break"] = df_data.iloc[:, 9].astype(str).str.strip()
    df_clean["Total Meal"] = df_data.iloc[:, 10].astype(str).str.strip()
    df_clean["Exceeded_Break_Raw"] = df_data.iloc[:, 15].astype(str).str.strip()
    df_clean["Unaccounted"] = df_data.iloc[:, 16].astype(str).str.strip()
    df_clean["Direct_Adherence"] = df_data.iloc[:, 17].astype(str).str.strip()

    invalid_mask = (
        df_clean["Agent Name"].isna() |
        df_clean["Agent Name"].str.lower().isin(["none", "nan", "", "agent name", "agent", "employee", "name", "site"])
    )
    df_clean = df_clean[~invalid_mask].copy()
    df_clean["Account"] = "TransDev SD & OC"
    return df_clean.reset_index(drop=True)

# Parser for TDS Sheet
@st.cache_data(ttl=1800)
def parse_tds_sheet(sheet_id, gid):
    df_raw = fetch_raw_csv(sheet_id, gid)
    if df_raw.empty:
        return pd.DataFrame()
    
    header_idx = None
    for i in range(min(20, len(df_raw))):
        row_cells = [str(x).strip().lower() for x in df_raw.iloc[i].fillna("").tolist()]
        if any(term in cell for cell in row_cells for term in ["agent", "employee", "name", "site", "position"]):
            header_idx = i
            break

    df_data = df_raw.iloc[header_idx + 1:].copy() if header_idx is not None else df_raw.copy()
    df_clean = pd.DataFrame()

    def extract_by_names(names, default="Unknown"):
        cols = [str(c).strip().lower() for c in df_data.columns]
        for name in names:
            for idx, c in enumerate(cols):
                if name in c:
                    return df_data.iloc[:, idx].astype(str).str.strip()
        return pd.Series([default] * len(df_data), index=df_data.index)

    df_clean["Date"] = df_data.iloc[:, 0].astype(str).str.strip()
    df_clean["week"] = df_data.iloc[:, 1].astype(str).str.strip().apply(clean_week_str)
    df_clean["Agent Name"] = df_data.iloc[:, 2].astype(str).str.strip()
    df_clean["site"] = extract_by_names(["site", "loc"], "MX").apply(normalize_site)
    df_clean["role"] = extract_by_names(["position", "role", "title"], "Csa")
    
    df_clean["Total Break"] = extract_by_names(["total break", "breaks"], "0:00")
    df_clean["Total Meal"] = extract_by_names(["total meal", "meal"], "0:00")
    df_clean["Exceeded_Break_Raw"] = df_data.iloc[:, 15].astype(str).str.strip() if df_data.shape[1] > 15 else "0:00"
    df_clean["Unaccounted"] = extract_by_names(["unaccounted", "unaccou"], "0:00")
    df_clean["Direct_Adherence"] = df_data.iloc[:, 18].astype(str).str.strip() if df_data.shape[1] > 18 else None

    invalid_mask = (
        df_clean["Agent Name"].isna() |
        df_clean["Agent Name"].str.lower().isin(["none", "nan", "", "agent name", "agent", "employee", "name"])
    )
    df_clean = df_clean[~invalid_mask].copy()
    df_clean["Account"] = "TDS"
    return df_clean.reset_index(drop=True)

@st.cache_data(ttl=1800)
def load_all_combined_data_v15():
    frames = []
    tds_df = parse_tds_sheet("18WdoYyycy71LWCEUesOq6-uLWqtAo52jD4p12ObGi3k", "1537474403")
    if not tds_df.empty: frames.append(tds_df)

    td_df = parse_transdev_sheet("1bp9_e-ML_TVCxkvjsr893nhcJmyw1WILWAsgwdAcjUc", "676189719")
    if not td_df.empty: frames.append(td_df)

    if not frames:
        return pd.DataFrame()
        
    combined_df = pd.concat(frames, axis=0, ignore_index=True)

    if "Date" in combined_df.columns:
        parsed_dates = pd.to_datetime(combined_df["Date"], errors="coerce", format="mixed")
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

# Load Sheets
attendance_raw_df = parse_attendance_sheet("1PUerkTX4iCaFUP27FXV34azza6L5LpFYsb1nHVKrH-c", "253246412")
break_raw_df = load_all_combined_data_v15()

# Filters Configuration
st.subheader("🔍 Filters & Drilldown")
f0, f1, f2, f3 = st.columns(4)

with f0:
    sites = ["All Sites", "CDMX", "Tijuana"]
    selected_site = st.selectbox("Site:", sites, index=0)

with f1:
    accounts = ["All Accounts"]
    all_acc = set()
    if "Account" in attendance_raw_df.columns: all_acc.update(attendance_raw_df["Account"].dropna().unique())
    if "Account" in break_raw_df.columns: all_acc.update(break_raw_df["Account"].dropna().unique())
    accounts += sorted([a for a in all_acc if a and str(a).lower() != "nan"])
    selected_account = st.selectbox("Account / Source:", accounts, index=0)

with f2:
    months = ["All Months"]
    all_months = set()
    if "month" in attendance_raw_df.columns: all_months.update(attendance_raw_df["month"].dropna().unique())
    if "month" in break_raw_df.columns: all_months.update(break_raw_df["month"].dropna().unique())
    months += sorted([m for m in all_months if m and str(m).lower() != "nan"])
    selected_month = st.selectbox("Month:", months, index=0)

with f3:
    weeks = ["All Weeks"]
    all_weeks = set()
    if "week" in attendance_raw_df.columns: all_weeks.update(attendance_raw_df["week"].dropna().unique())
    if "week" in break_raw_df.columns: all_weeks.update(break_raw_df["week"].dropna().unique())
    weeks += sorted([w for w in all_weeks if w and str(w).lower() != "nan"])
    selected_week = st.selectbox("Work Week:", weeks, index=0)

# Filter Execution
def apply_filters(df):
    if df.empty:
        return df
    dff = df.copy()
    if selected_site != "All Sites" and "site" in dff.columns:
        dff = dff[dff["site"].astype(str).str.lower() == selected_site.lower()]
    if selected_account != "All Accounts" and "Account" in dff.columns:
        dff = dff[dff["Account"].astype(str).str.lower() == selected_account.lower()]
    if selected_month != "All Months" and "month" in dff.columns:
        dff = dff[dff["month"].astype(str).str.lower() == selected_month.lower()]
    if selected_week != "All Weeks" and "week" in dff.columns:
        dff = dff[dff["week"].astype(str).str.lower() == selected_week.lower()]
    return dff

filtered_attendance_df = apply_filters(attendance_raw_df)
filtered_break_df = apply_filters(break_raw_df)

# Dashboard Tabs
tab_attendance, tab_exceeded_break, tab_ops_kpi, tab_agent_scope, tab_service_hours = st.tabs([
    "📅 Attendance", 
    "⏰ Exceeded Break Time", 
    "📊 Operational KPI View", 
    "👤 Agent Scope", 
    "⏱️ Service Hours per Campaign"
])

# TAB 1: ATTENDANCE
with tab_attendance:
    a_col1, a_col2 = st.columns([3, 1])
    with a_col1:
        st.subheader("📅 Attendance Tracker Data")
    with a_col2:
        st.markdown("[🔗 Open Attendance Sheet](https://docs.google.com/spreadsheets/d/1PUerkTX4iCaFUP27FXV34azza6L5LpFYsb1nHVKrH-c/edit#gid=253246412)")
    
    if not filtered_attendance_df.empty:
        # Metrics
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("👥 Active Roster Headcount", f"{len(filtered_attendance_df)}")
        m2.metric("⚠️ Unjustified Absences", f"{int(pd.to_numeric(filtered_attendance_df.get('Unjustified Absences', 0), errors='coerce').fillna(0).sum())}")
        m3.metric("📋 Justified Absences", f"{int(pd.to_numeric(filtered_attendance_df.get('Justified Absences', 0), errors='coerce').fillna(0).sum())}")
        m4.metric("⏱️ Total Late Instances", f"{int(pd.to_numeric(filtered_attendance_df.get('Total Late', 0), errors='coerce').fillna(0).sum())}")

        st.divider()

        # Visual Chart
        st.write("### 📊 Agent Absence & Late Metrics Breakdown")
        chart_cols = [c for c in ["Unjustified Absences", "Justified Absences", "Total Late", "Suspensions", "Vacation Days"] if c in filtered_attendance_df.columns]
        if chart_cols and "Agent Name" in filtered_attendance_df.columns:
            plot_df = filtered_attendance_df.set_index("Agent Name")[chart_cols].apply(pd.to_numeric, errors="coerce").fillna(0)
            st.bar_chart(plot_df)

        st.divider()
        st.write("### 📋 Attendance Log")
        st.dataframe(filtered_attendance_df, use_container_width=True, hide_index=True)
    else:
        st.info("No attendance data found for the selected filter combination.")

# TAB 2: EXCEEDED BREAK TIME
with tab_exceeded_break:
    b_m1, b_m2 = st.columns(2)
    total_overage = filtered_break_df["Exceeded_Break_Raw_Mins"].sum() if "Exceeded_Break_Raw_Mins" in filtered_break_df.columns else 0
    with b_m1:
        st.metric("⏱️ Combined Break Overage", f"{int(total_overage)} Mins")
    with b_m2:
        st.write("**Direct Sheet Links:**")
        st.markdown("[🔗 TDS Sheet](https://docs.google.com/spreadsheets/d/18WdoYyycy71LWCEUesOq6-uLWqtAo52jD4p12ObGi3k/edit#gid=1537474403)")
        st.markdown("[🔗 TransDev Sheet](https://docs.google.com/spreadsheets/d/1bp9_e-ML_TVCxkvjsr893nhcJmyw1WILWAsgwdAcjUc/edit#gid=676189719)")

    st.divider()

    st.subheader("⏰ Raw Exceeded Break Time & Duration Logs")
    if not filtered_break_df.empty:
        break_cols = [c for c in ["Account", "site", "week", "Date", "Agent Name", "Total Break", "Total Meal", "Exceeded_Break_Raw", "Unaccounted"] if c in filtered_break_df.columns]
        st.dataframe(filtered_break_df[break_cols], use_container_width=True, hide_index=True)
    else:
        st.info("No break log data available for selected filters.")

# TAB 3: OPERATIONAL KPI VIEW
with tab_ops_kpi:
    st.subheader("📊 Hub & Site Level KPI Breakdown")
    kpi_cdmx, kpi_tj, kpi_bench = st.tabs(["🇲🇽 CDMX", "🇲🇽 Tijuana", "🎯 KPI Benchmarks"])
    with kpi_cdmx:
        cdmx_df = filtered_break_df[filtered_break_df["site"].astype(str).str.upper() == "CDMX"] if "site" in filtered_break_df.columns else pd.DataFrame()
        st.dataframe(cdmx_df, use_container_width=True, hide_index=True) if not cdmx_df.empty else st.info("No CDMX data found.")
    with kpi_tj:
        tj_df = filtered_break_df[filtered_break_df["site"].astype(str).str.upper() == "TIJUANA"] if "site" in filtered_break_df.columns else pd.DataFrame()
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
    if not filtered_break_df.empty and "Agent Name" in filtered_break_df.columns:
        agent_list = sorted(filtered_break_df["Agent Name"].dropna().unique().tolist())
        selected_agent = st.selectbox("Select Agent:", agent_list)
        st.dataframe(filtered_break_df[filtered_break_df["Agent Name"] == selected_agent], use_container_width=True, hide_index=True)

# TAB 5: SERVICE HOURS PER CAMPAIGN
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
    st.dataframe(break_raw_df, use_container_width=True, hide_index=True)
