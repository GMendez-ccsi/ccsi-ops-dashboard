import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import urllib.parse
import re

# Set Streamlit Page Configuration
st.set_page_config(
    page_title="Operations & QA Performance Dashboard",
    page_icon="📊",
    layout="wide"
)

# HELPER FUNCTIONS & DATA FETCHERS
@st.cache_data(ttl=300)
def fetch_raw_csv(sheet_id: str, gid: str) -> pd.DataFrame:
    """Fetch raw CSV data from Google Sheets by ID and GID."""
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    try:
        df = pd.read_csv(url, header=None)
        return df
    except Exception as e:
        st.error(f"Failed to fetch CSV feed: {e}")
        return pd.DataFrame()

def normalize_site(val) -> str:
    if pd.isna(val):
        return "UNKNOWN"
    s = str(val).strip().upper()
    if "CDMX" in s or "MEXICO" in s:
        return "CDMX"
    if "TJ" in s or "TIJUANA" in s:
        return "TJ"
    return s

def clean_week_str(val) -> str:
    if pd.isna(val):
        return "Unknown"
    s = str(val).strip()
    match = re.search(r"W\d+", s, re.IGNORECASE)
    if match:
        return match.group(0).upper()
    return s

def apply_common_filters(df: pd.DataFrame, strict_month: bool = False) -> pd.DataFrame:
    """Apply standard sidebar filters (Site, Role, Week) to target DataFrame."""
    filtered_df = df.copy()
    
    if "site" in filtered_df.columns and "selected_sites" in st.session_state:
        if st.session_state.selected_sites:
            filtered_df = filtered_df[filtered_df["site"].isin(st.session_state.selected_sites)]
            
    if "role" in filtered_df.columns and "selected_roles" in st.session_state:
        if st.session_state.selected_roles:
            filtered_df = filtered_df[filtered_df["role"].isin(st.session_state.selected_roles)]
            
    if "Week" in filtered_df.columns and "selected_weeks" in st.session_state:
        if st.session_state.selected_weeks:
            filtered_df = filtered_df[filtered_df["Week"].isin(st.session_state.selected_weeks)]
            
    return filtered_df


# SIDEBAR GLOBAL FILTERS
st.sidebar.header("🔍 Dashboard Filters")
st.session_state.selected_sites = st.sidebar.multiselect("Select Site(s):", ["CDMX", "TJ"], default=["CDMX", "TJ"])
st.session_state.selected_roles = st.sidebar.multiselect("Select Role(s):", ["AGENT", "TL", "QA", "OM"], default=[])
st.session_state.selected_weeks = st.sidebar.multiselect("Select Week(s):", [f"W{i}" for i in range(1, 53)], default=[])


# NAVIGATION TABS
tab_overview, tab_attendance, tab_shrinkage, tab_attrition, tab_service_hours, tab_qa = st.tabs([
    "🏠 Overview",
    "📅 Attendance",
    "📉 Shrinkage",
    "🚪 Attrition",
    "⏱️ Service Hours",
    "🛡️ Quality Assurance"
])


# TAB 1: OVERVIEW
with tab_overview:
    st.title("🚀 Operational Performance Overview")
    st.info("Welcome to the Operations Performance Dashboard. Use the top navigation tabs to inspect granular data feeds for Service Hours, QA, Attendance, and Attrition.")


# TAB 2: ATTENDANCE
with tab_attendance:
    st.subheader("📅 Attendance Analytics")
    st.caption("Tracking attendance compliance across active operational sites.")


# TAB 3: SHRINKAGE
with tab_shrinkage:
    st.subheader("📉 Shrinkage Tracking")
    st.caption("Planned and unplanned shrinkage metrics per campaign.")


# TAB 4: ATTRITION
with tab_attrition:
    st.subheader("🚪 Attrition Rates")
    st.caption("Monthly employee turnover rates by site and tier.")


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
    qa_head1, qa_head2 = st.columns([3, 1])
    with qa_head1:
        st.subheader("🛡️ Quality Assurance (QA) Evaluations & Pivot Metrics")
    with qa_head2:
        st.markdown("[🔗 Open Live QA Evaluations Sheet](https://docs.google.com/spreadsheets/d/17blbXU8PWciUJrU0PMTj1iMydQOqPQyGRUYVf3LhbNk/edit#gid=490191452)")

    @st.cache_data(ttl=300)
    def load_qa_master_sheet():
        sheet_id = "17blbXU8PWciUJrU0PMTj1iMydQOqPQyGRUYVf3LhbNk"
        gid = "490191452"
        try:
            df = fetch_raw_csv(sheet_id, gid)
            if df.empty:
                return pd.DataFrame()
            
            # Locate Header Row
            header_idx = 0
            for i in range(min(15, len(df))):
                row_cells = [str(x).strip().lower() for x in df.iloc[i].fillna("").tolist()]
                if any("agent" in x or "qa" in x or "score" in x or "tl" in x or "week" in x for x in row_cells):
                    header_idx = i
                    break
            
            headers = [str(c).strip() if str(c).strip() != "nan" else f"Col_{j}" for j, c in enumerate(df.iloc[header_idx].tolist())]
            df_clean = df.iloc[header_idx + 1:].copy()
            df_clean.columns = headers
            df_clean = df_clean.dropna(how="all").reset_index(drop=True)
            
            # Standardize Column Names safely
            col_map = {}
            for c in df_clean.columns:
                clow = str(c).lower().strip()
                if "week" in clow: col_map[c] = "Week"
                elif "site" in clow or "hub" in clow: col_map[c] = "site"
                elif "role" in clow or "position" in clow: col_map[c] = "role"
                elif "agent" in clow or "employee" in clow: col_map[c] = "Agent Name"
                elif "tl" in clow or "team lead" in clow or "supervisor" in clow: col_map[c] = "TL Name"
                elif "score" in clow or "qa %" in clow or "overall" in clow: col_map[c] = "QA Score"
                elif "type" in clow or "session" in clow or "monitoring" in clow: col_map[c] = "Session Type"

            df_clean = df_clean.rename(columns=col_map)
            
            if "site" in df_clean.columns:
                df_clean["site"] = df_clean["site"].apply(normalize_site)
            if "Week" in df_clean.columns:
                df_clean["Week"] = df_clean["Week"].apply(clean_week_str)
            if "role" in df_clean.columns:
                df_clean["role"] = df_clean["role"].astype(str).apply(lambda x: x.strip().upper())

            return df_clean
        except Exception as e:
            st.error(f"Error reading QA Sheet: {e}")
            return pd.DataFrame()

    qa_raw_df = load_qa_master_sheet()

    if not qa_raw_df.empty:
        qa_df = apply_common_filters(qa_raw_df, strict_month=False)

        # Safely parse numeric QA scores
        if "QA Score" in qa_df.columns:
            qa_df["_numeric_score"] = (
                qa_df["QA Score"]
                .astype(str)
                .apply(lambda x: x.replace("%", "").strip())
            )
            qa_df["_numeric_score"] = pd.to_numeric(qa_df["_numeric_score"], errors="coerce")
        else:
            qa_df["_numeric_score"] = None

        # 1. Summary KPI Cards
        avg_qa = qa_df["_numeric_score"].mean() if "_numeric_score" in qa_df.columns else None
        total_evals = len(qa_df)
        
        if "Session Type" in qa_df.columns:
            virtual_mask = qa_df["Session Type"].astype(str).apply(lambda x: "virtual" in x.lower() or "monitored" in x.lower())
            virtual_count = len(qa_df[virtual_mask])
        else:
            virtual_count = total_evals

        qm1, qm2, qm3 = st.columns(3)
        qm1.metric("🛡️ Overall QA Score Avg", f"{avg_qa:.1f}%" if pd.notna(avg_qa) else "N/A")
        qm2.metric("📋 Total Evaluations Logged", f"{total_evals}")
        qm3.metric("🎧 Monitored Sessions Count", f"{virtual_count}")

        st.divider()

        # 2. Pivot Table: Virtual Monitored Sessions by TL, Role & Week
        st.markdown("### 📊 Monitored Sessions Pivot (By TL / Role / Week)")
        
        pivot_tl_col = "TL Name" if "TL Name" in qa_df.columns else ("Agent Name" if "Agent Name" in qa_df.columns else None)
        pivot_role_col = "role" if "role" in qa_df.columns else None
        pivot_week_col = "Week" if "Week" in qa_df.columns else None

        if pivot_tl_col and pivot_week_col:
            index_cols = [c for c in [pivot_tl_col, pivot_role_col] if c is not None]
            
            qa_pivot = pd.pivot_table(
                qa_df,
                values="_numeric_score" if "_numeric_score" in qa_df.columns else qa_df.columns[0],
                index=index_cols,
                columns=pivot_week_col,
                aggfunc="count",
                fill_value=0,
                margins=True,
                margins_name="Total Sessions"
            )
            st.dataframe(qa_pivot, use_container_width=True)
        else:
            st.info("Missing TL, Role, or Week columns to generate full pivot table.")

        st.divider()

        # 3. Weekly Areas of Opportunity (Major Error Categories)
        st.markdown("### ⚠️ Major Areas of Opportunity per Week")
        st.caption("Identifies individual evaluated criteria/questions with the lowest compliance rates.")

        meta_cols = ["Week", "site", "role", "Agent Name", "TL Name", "QA Score", "Session Type", "_numeric_score", "Date", "month_clean"]
        criteria_cols = [c for c in qa_df.columns if c not in meta_cols and not c.startswith("Col_")]

        if criteria_cols and "Week" in qa_df.columns:
            weekly_opps = []
            
            for week_name, week_group in qa_df.groupby("Week"):
                col_means = {}
                for col in criteria_cols:
                    series = (
                        week_group[col]
                        .astype(str)
                        .apply(lambda x: x.replace("%", "").strip())
                    )
                    numeric_series = pd.to_numeric(series, errors="coerce")
                    if numeric_series.notna().sum() > 0:
                        col_means[col] = numeric_series.mean()
                
                if col_means:
                    sorted_opps = sorted(col_means.items(), key=lambda x: x[1])[:3]
                    for opp_item, score_val in sorted_opps:
                        weekly_opps.append({
                            "Work Week": week_name,
                            "Area of Opportunity / Evaluation Item": opp_item,
                            "Avg Score / Compliance Rate": f"{score_val:.1f}%"
                        })

            if weekly_opps:
                st.dataframe(pd.DataFrame(weekly_opps), use_container_width=True, hide_index=True)
            else:
                st.info("No numerical breakdown columns found to compute specific areas of opportunity.")
        else:
            st.info("Itemized evaluation sub-scores are not available in the current sheet view.")

        st.divider()

        # 4. Master QA Audit Log
        st.markdown("### 📋 Complete QA Audit Log")
        display_qa = qa_df.drop(columns=["_numeric_score"], errors="ignore")
        st.dataframe(display_qa, use_container_width=True, hide_index=True)

    else:
        st.info("Unable to load live Quality Assurance data from the target spreadsheet.")
