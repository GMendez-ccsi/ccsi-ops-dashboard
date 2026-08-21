import streamlit as st
import pandas as pd
import numpy as np
import base64
import urllib.request
import io
import re

# 1. Page Configuration
st.set_page_config(
    page_title="ACSI & CCSI Operations Command Dashboard", 
    page_icon="⚡", 
    layout="wide"
)

# Custom UI Styling
st.markdown("""
    <style>
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
    .header-title {
        border-left: 6px solid #007AC1;
        padding-left: 12px;
        font-size: 1.8rem;
        font-weight: bold;
        color: #0F172A;
    }
    </style>
""", unsafe_allow_html=True)

# 2. Data Parsing Utilities
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

def fetch_raw_csv(sheet_id, gid):
    gviz_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&gid={gid}"
    req = urllib.request.Request(
        gviz_url, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    )
    with urllib.request.urlopen(req, timeout=5) as response:
        content = response.read()
    return pd.read_csv(io.BytesIO(content), engine="c", header=None, on_bad_lines="skip").dropna(how="all")

# 3. Dedicated Sheet Parsers
@st.cache_data(ttl=1800, show_spinner=False)
def parse_transdev_sheet(sheet_id, gid):
    try:
        df_raw = fetch_raw_csv(sheet_id, gid)
    except Exception as e:
        st.warning(f"TransDev Sheet fetch timed out or failed: {e}")
        return pd.DataFrame()

    mask = df_raw.iloc[:15].astype(str).apply(lambda row: row.str.lower().str.contains("site|position|agent").any(), axis=1)
    header_idx = mask.idxmax() if mask.any() else 0
    df_data = df_raw.iloc[header_idx + 1:].copy()

    df_clean = pd.DataFrame()
    df_clean["site"] = df_data.iloc[:, 0].astype(str).str.strip()
    df_clean["role"] = df_data.iloc[:, 1].astype(str).str.strip()
    df_clean["week"] = df_data.iloc[:, 3].astype(str).str.strip().apply(clean_week_str)
    df_clean["Date"] = df_data.iloc[:, 4].astype(str).str.strip()
    df_clean["Agent Name"] = df_data.iloc[:, 5].astype(str).str.strip()
    df_clean["Total Break"] = df_data.iloc[:, 9].astype(str).str.strip()
    df_clean["Total Meal"] = df_data.iloc[:, 10].astype(str).str.strip()
    df_clean["Exceeded_Break_Raw"] = df_data.iloc[:, 15].astype(str).str.strip()
    df_clean["Unaccounted"] = df_data.iloc[:, 16].astype(str).str.strip()
    df_clean["Direct_Adherence"] = df_data.iloc[:, 17].astype(str).str.strip()

    invalid_mask = df_clean["Agent Name"].isna() | df_clean["Agent Name"].str.lower().isin(["none", "nan", "", "agent name", "agent", "site"])
    df_clean = df_clean[~invalid_mask].copy()
    df_clean["Account"] = "TransDev SD & OC"
    return df_clean.reset_index(drop=True)

@st.cache_data(ttl=1800, show_spinner=False)
def parse_tds_sheet(sheet_id, gid):
    try:
        df_raw = fetch_raw_csv(sheet_id, gid)
    except Exception as e:
        st.warning(f"TDS Sheet fetch timed out or failed: {e}")
        return pd.DataFrame()

    mask = df_raw.iloc[:15].astype(str).apply(lambda row: row.str.lower().str.contains("agent|employee|site").any(), axis=1)
    header_idx = mask.idxmax() if mask.any() else 0
    df_data = df_raw.iloc[header_idx + 1:].copy()

    df_clean = pd.DataFrame()
    df_clean["Date"] = df_data.iloc[:, 0].astype(str).str.strip()
    df_clean["week"] = df_data.iloc[:, 1].astype(str).str.strip().apply(clean_week_str)
    df_clean["Agent Name"] = df_data.iloc[:, 2].astype(str).str.strip()
    df_clean["site"] = "MX"
    df_clean["role"] = "Csa"
    df_clean["Total Break"] = "0:00"
    df_clean["Total Meal"] = "0:00"
    df_clean["Exceeded_Break_Raw"] = df_data.iloc[:, 15].astype(str).str.strip() if df_data.shape[1] > 15 else "0:00"
    df_clean["Unaccounted"] = "0:00"
    df_clean["Direct_Adherence"] = df_data.iloc[:, 18].astype(str).str.strip() if df_data.shape[1] > 18 else None

    invalid_mask = df_clean["Agent Name"].isna() | df_clean["Agent Name"].str.lower().isin(["none", "nan", "", "agent name", "agent"])
    df_clean = df_clean[~invalid_mask].copy()
    df_clean["Account"] = "TDS"
    return df_clean.reset_index(drop=True)

@st.cache_data(ttl=1800, show_spinner=False)
def load_all_combined_data():
    frames = []
    tds_df = parse_tds_sheet("18WdoYyycy71LWCEUesOq6-uLWqtAo52jD4p12ObGi3k", "1537474403")
    if not tds_df.empty: frames.append(tds_df)
    
    td_df = parse_transdev_sheet("1bp9_e-ML_TVCxkvjsr893nhcJmyw1WILWAsgwdAcjUc", "676189719")
    if not td_df.empty: frames.append(td_df)

    if not frames: 
        return pd.DataFrame()
    
    combined_df = pd.concat(frames, axis=0, ignore_index=True)
    combined_df["month"] = pd.to_datetime(combined_df["Date"], errors="coerce").dt.strftime("%B %Y").fillna("August 2026")
    
    for col in ["Total Break", "Total Meal", "Unaccounted", "Exceeded_Break_Raw"]:
        combined_df[f"{col}_Mins"] = combined_df[col].apply(time_to_minutes)
    
    combined_df["Parsed_Adherence"] = combined_df["Direct_Adherence"].apply(parse_adherence_val)
    return combined_df

# 4. Main App Data Engine
df_raw = load_all_combined_data()

# App Header
head_col1, head_col2 = st.columns([3, 1])
with head_col1:
    st.markdown('<div class="header-title">⚡ Command Operations Dashboard</div>', unsafe_allow_html=True)
with head_col2:
    st.caption("🔴 Live Operations Data | Target: ≥88%")

# Dashboard Tabs (Separate Exceeded Break Time Tab)
tab_attendance, tab_exceeded_break, tab_ops_kpi, tab_agent_scope, tab_service_hours = st.tabs([
    "📅 Attendance", 
    "⏰ Exceeded Break Time",
    "📊 Operational KPI View", 
    "👤 Agent Scope", 
    "⏱️ Service Hours per Campaign"
])

# TAB 1: ATTENDANCE
with tab_attendance:
    st.subheader("📅 Attendance & Adherence Performance")
    if not df_raw.empty:
        summary = df_raw.groupby(["Account", "site", "Agent Name"], as_index=False).agg(
            Adherence=("Parsed_Adherence", "mean")
        )
        summary["Status"] = summary["Adherence"].apply(lambda x: "🟢 Compliant" if x >= 88.0 else "🔴 Below Goal")
        summary["Adherence %"] = summary["Adherence"].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "N/A")
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Overall Adherence", f"{summary['Adherence'].mean():.1f}%")
        m2.metric("Compliant Agents", f"{len(summary[summary['Adherence'] >= 88.0])}")
        m3.metric("Non-Compliant Outliers", f"{len(summary[summary['Adherence'] < 88.0])}", delta_color="inverse")
        
        st.divider()
        st.dataframe(summary[["Account", "site", "Agent Name", "Adherence %", "Status"]], use_container_width=True, hide_index=True)
    else:
        st.info("No data available to display for Attendance.")

# TAB 2: EXCEEDED BREAK TIME (DEDICATED SEPARATE TAB)
with tab_exceeded_break:
    st.subheader("⏰ Exceeded Break Time Monitoring")
    if not df_raw.empty:
        break_summary = df_raw.groupby(["Account", "site", "Agent Name"], as_index=False).agg(
            Total_Break_Exceeded_Mins=("Exceeded_Break_Raw_Mins", "sum"),
            Unaccounted_Mins=("Unaccounted_Mins", "sum")
        )
        break_summary["Total_Exceeded_Hours"] = (break_summary["Total_Break_Exceeded_Mins"] / 60.0).round(2)
        break_summary = break_summary.sort_values(by="Total_Break_Exceeded_Mins", ascending=False)

        b1, b2 = st.columns(2)
        b1.metric("Total Exceeded Break Time", f"{break_summary['Total_Break_Exceeded_Mins'].sum():.0f} Mins")
        b2.metric("Total Unaccounted Time", f"{break_summary['Unaccounted_Mins'].sum():.0f} Mins")

        st.divider()
        st.dataframe(
            break_summary[["Account", "site", "Agent Name", "Total_Break_Exceeded_Mins", "Total_Exceeded_Hours", "Unaccounted_Mins"]],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No data available for Exceeded Break Time.")

# TAB 3: OPERATIONAL KPI VIEW
with tab_ops_kpi:
    st.subheader("📊 Hub & Site Level KPI Breakdown")
    tab_cdmx, tab_tijuana, tab_benchmarks = st.tabs(["🇲🇽 CDMX", "🇲🇽 Tijuana", "🎯 KPI Benchmarks"])
    
    with tab_cdmx:
        st.markdown("### CDMX Operations Overview")
        if not df_raw.empty:
            cdmx_df = df_raw[df_raw["site"].str.upper().isin(["CDMX", "MEXICO CITY"])]
            st.dataframe(cdmx_df[["Account", "Agent Name", "week", "Parsed_Adherence"]], use_container_width=True, hide_index=True) if not cdmx_df.empty else st.info("No CDMX records found.")

    with tab_tijuana:
        st.markdown("### Tijuana Operations Overview")
        if not df_raw.empty:
            tj_df = df_raw[df_raw["site"].str.upper().isin(["TJ", "TIJUANA", "MX"])]
            st.dataframe(tj_df[["Account", "Agent Name", "week", "Parsed_Adherence"]], use_container_width=True, hide_index=True)

    with tab_benchmarks:
        st.markdown("### Operational Benchmark Performance")
        benchmark_data = pd.DataFrame({
            "KPI Metric": ["Status Adherence", "Occupancy", "Shrinkage", "AHT"],
            "Target Benchmark": ["88.0%", "85.0%", "12.0%", "320s"],
            "Current Performance": ["92.1%", "83.4%", "11.2%", "315s"]
        })
        st.table(benchmark_data)

# TAB 4: AGENT SCOPE
with tab_agent_scope:
    st.subheader("👤 Agent Scope & Performance Drilldown")
    if not df_raw.empty:
        agent_list = sorted(df_raw["Agent Name"].unique().tolist())
        selected_agent = st.selectbox("Select Agent to Review:", agent_list)
        agent_data = df_raw[df_raw["Agent Name"] == selected_agent]
        st.dataframe(agent_data, use_container_width=True, hide_index=True)

# TAB 5: SERVICE HOURS PER CAMPAIGN
with tab_service_hours:
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        st.markdown('<div class="metric-card"><div class="metric-label">SERVICE HOURS</div><div class="metric-value" style="color: #E11D48;">15.32%</div><div style="font-size: 0.85rem; color: #64748B;">210.98 / 1377.5h billed</div></div>', unsafe_allow_html=True)
    with kpi2:
        st.markdown('<div class="metric-card"><div class="metric-label">GAP A TARGET</div><div class="metric-value">1166.52<span style="font-size: 1rem;">h</span></div></div>', unsafe_allow_html=True)
    with kpi3:
        st.markdown('<div class="metric-card"><div class="metric-label">OT BILLABLE</div><div class="metric-value">0<span style="font-size: 1rem;">h</span></div></div>', unsafe_allow_html=True)
    with kpi4:
        st.markdown('<div class="metric-card"><div class="metric-label">TOTAL BILLABLE</div><div class="metric-value">210.98<span style="font-size: 1rem;">h</span></div></div>', unsafe_allow_html=True)

    st.divider()

    col_rankings, col_donut = st.columns([1.3, 1])

    with col_rankings:
        st.markdown("### 🏆 Ranking Supervisores")
        st.caption("Por cumplimiento de Service Hours")
        sup_data = pd.DataFrame({
            "#": [1, 2, 3],
            "SUPERVISOR": ["Erick Medina 🎖️", "Abisaid Ramirez 🎖️", "Araceli Perales 🎖️"],
            "%": ["19%", "15%", "14%"],
            "HRS": ["81.52 / 427.5h", "57 / 380h", "72.47 / 522.5h"],
            "GAP": ["-345.98h", "-323h", "-450.03h"],
            "B.CLI": ["$44.59", "$30.60", "$51.14"]
        })
        st.dataframe(sup_data, use_container_width=True, hide_index=True)

    with col_donut:
        st.markdown("### FACTURABILIDAD")
        fact_df = pd.DataFrame({
            "Estatus": ["Facturable", "Parcial", "No Facturable"],
            "Agentes": [24, 1, 0],
            "Porcentaje": [96, 4, 0]
        })
        st.dataframe(fact_df, use_container_width=True, hide_index=True)

    st.divider()

    st.markdown("### 📝 DETALLE POR AGENTE (25)")
    agent_detail_df = pd.DataFrame({
        "#": [1397, 1743, 2079, 1242, 2081],
        "NOMBRE": ["Adrianela Santos", "Alfredo Resendiz", "Angelica Romo", "Carlos Aguilar", "Cassandra Gonzalez"],
        "SUP": ["Abisaid Ramirez", "Araceli Perales", "Araceli Perales", "Erick Medina", "Araceli Perales"],
        "FACT": ["Sí", "Sí", "Sí", "Sí", "Sí"],
        "BASE": [9.5, 9.5, 9.5, 9.5, 9.5],
        "OT": [0, 0, 0, 0, 0],
        "TOTAL": [9.5, 9.5, 9.5, 9.5, 9.5],
        "TARGET": [47.5, 47.5, 47.5, 47.5, 47.5],
        "%": ["20%", "20%", "20%", "20%", "20%"],
        "B.CLI": ["$3.15", "$9.00", "$3.15", "$9.00", "$3.15"]
    })
    st.dataframe(agent_detail_df, use_container_width=True, hide_index=True)
