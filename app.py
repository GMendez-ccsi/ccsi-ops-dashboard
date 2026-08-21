import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# -------------------------------------------------------------
# 0. CONFIGURATION & CONSTANTS
# -------------------------------------------------------------
st.set_page_config(
    page_title="Operations 360° Command Center",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

SHIFT_MINS_PER_DAY = 480.0  # 8-hour shift base


# -------------------------------------------------------------
# 1. HELPER & DATA PRE-PROCESSING ENGINES
# -------------------------------------------------------------
def deduplicate_dataframe_columns(df):
    """Safe, modern DataFrame column deduplication (Python 3.12+ / Pandas 2.0+ compatible)."""
    if df is None or df.empty:
        return df
    df = df.copy()
    cols = []
    counts = {}
    for col in df.columns:
        col_str = str(col)
        if col_str in counts:
            counts[col_str] += 1
            cols.append(f"{col_str}_{counts[col_str]}")
        else:
            counts[col_str] = 0
            cols.append(col_str)
    df.columns = cols
    return df


def parse_time_to_minutes(val):
    """Converts HH:MM:SS duration strings or numeric values to float minutes."""
    if pd.isna(val) or val == "" or str(val).strip() in ["-", "None", "nan"]:
        return 0.0
    val_str = str(val).strip()
    try:
        parts = val_str.split(":")
        if len(parts) == 3:  # HH:MM:SS
            return (
                float(parts[0]) * 60.0 + float(parts[1]) + float(parts[2]) / 60.0
            )
        elif len(parts) == 2:  # MM:SS or HH:MM
            return float(parts[0]) * 60.0 + float(parts[1])
        return float(val_str)
    except ValueError:
        return 0.0


def prepare_adherence_dataframe(df):
    """Standardizes sheet columns, maps MX -> CDMX, and parses time/adherence metrics."""
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()

    # Dynamic Column Mapping (handles exact sheet headers from raw data)
    col_map = {
        "SITE": "site",
        "ACCOUNT": "Account",
        "WEEK": "week",
        "DATE": "Date",
        "name": "Agent Name",
        "Exceeded break": "Exceeded_Break_Raw_Mins",
        "unaccou": "Unaccounted_Mins",
        "status adherence %": "Parsed_Adherence",
        "Source": "Source_Sheet",
    }
    df.rename(columns=col_map, inplace=True)

    # 1. Standardize SITE column (fixes the 'MX' site missing week data issue)
    if "site" in df.columns:
        df["site"] = (
            df["site"]
            .astype(str)
            .str.strip()
            .str.upper()
            .replace({"MX": "CDMX", "MEX": "CDMX", "UNKNOWN": "CDMX"})
        )
    else:
        df["site"] = "CDMX"

    # 2. Source Sheet Attribution
    if "Source_Sheet" not in df.columns:
        if "Account" in df.columns:
            df["Source_Sheet"] = np.where(
                df["Account"].astype(str).str.upper().isin(["OC", "SD", "TRANSDEV"]),
                "TransDev SD & OC",
                "TDS",
            )
        else:
            df["Source_Sheet"] = "TDS"

    # 3. Parse Status Adherence % (Column Q)
    if "Parsed_Adherence" in df.columns:
        df["Parsed_Adherence"] = (
            df["Parsed_Adherence"]
            .astype(str)
            .str.replace("%", "", regex=False)
            .str.strip()
        )
        df["Parsed_Adherence"] = pd.to_numeric(
            df["Parsed_Adherence"], errors="coerce"
        )

    # 4. Parse Exceeded Break Minutes (Column O)
    if "Exceeded_Break_Raw_Mins" in df.columns:
        df["Exceeded_Break_Raw_Mins"] = df["Exceeded_Break_Raw_Mins"].apply(
            parse_time_to_minutes
        )
    else:
        df["Exceeded_Break_Raw_Mins"] = 0.0

    # 5. Parse Unaccounted Minutes (Column P)
    if "Unaccounted_Mins" in df.columns:
        df["Unaccounted_Mins"] = df["Unaccounted_Mins"].apply(
            parse_time_to_minutes
        )
    else:
        df["Unaccounted_Mins"] = 0.0

    # Clean Week string formatting
    if "week" in df.columns:
        df["week"] = df["week"].astype(str).str.strip()

    return deduplicate_dataframe_columns(df)


# -------------------------------------------------------------
# 2. GOOGLE SHEETS & DASHBOARD LOADERS
# -------------------------------------------------------------
@st.cache_data(ttl=300)
def load_all_dashboard_data():
    """Loads operational sheets. Safely falls back to empty DataFrames if a sheet fails."""
    try:
        # Example using Streamlit GSheets Connection or Pandas reading public CSV endpoints
        # Replace the URLs below with your Google Sheets CSV publish links
        raw_df = pd.DataFrame() 
        attendance_df = pd.DataFrame()
        pivot_att_df = pd.DataFrame()
        qa_df = pd.DataFrame()
        cdmx_kpi = pd.DataFrame()
        tj_kpi = pd.DataFrame()
        cdmx_weekly = pd.DataFrame()
        forecast_df = pd.DataFrame()
    except Exception as e:
        st.error(f"Error loading data from Google Sheets: {e}")
        raw_df = pd.DataFrame()
        attendance_df = pd.DataFrame()
        pivot_att_df = pd.DataFrame()
        qa_df = pd.DataFrame()
        cdmx_kpi = pd.DataFrame()
        tj_kpi = pd.DataFrame()
        cdmx_weekly = pd.DataFrame()
        forecast_df = pd.DataFrame()

    return (
        prepare_adherence_dataframe(raw_df),
        attendance_df,
        pivot_att_df,
        qa_df,
        cdmx_kpi,
        tj_kpi,
        cdmx_weekly,
        forecast_df,
    )


(
    raw_adherence_df,
    raw_attendance_df,
    pivot_attendance_df,
    raw_qa_df,
    cdmx_kpis_df,
    tj_kpis_df,
    cdmx_weekly_trends_df,
    service_forecast_df,
) = load_all_dashboard_data()

# -------------------------------------------------------------
# 3. SIDEBAR FILTERS
# -------------------------------------------------------------
st.sidebar.title("🎛️ Operational Scope Filters")

if not raw_adherence_df.empty:
    sites_available = sorted(raw_adherence_df["site"].dropna().unique().tolist())
    selected_sites = st.sidebar.multiselect(
        "Select Sites:", sites_available, default=sites_available
    )

    accounts_available = sorted(raw_adherence_df["Account"].dropna().unique().tolist())
    selected_accounts = st.sidebar.multiselect(
        "Select Accounts:", accounts_available, default=accounts_available
    )

    weeks_available = sorted(raw_adherence_df["week"].dropna().unique().tolist())
    selected_weeks = st.sidebar.multiselect(
        "Select Weeks:", weeks_available, default=weeks_available
    )

    filtered_raw_df = raw_adherence_df[
        (raw_adherence_df["site"].isin(selected_sites))
        & (raw_adherence_df["Account"].isin(selected_accounts))
        & (raw_adherence_df["week"].isin(selected_weeks))
    ]
else:
    filtered_raw_df = pd.DataFrame()
    selected_sites = []

filtered_attendance_df = (
    raw_attendance_df[raw_attendance_df["site"].isin(selected_sites)]
    if not raw_attendance_df.empty and "site" in raw_attendance_df.columns
    else raw_attendance_df
)
filtered_qa_df = raw_qa_df.copy()


# -------------------------------------------------------------
# 4. ADHERENCE AGGREGATION CALCULATOR
# -------------------------------------------------------------
def calculate_adherence_summary(raw_df, group_cols=None):
    if raw_df is None or raw_df.empty:
        return pd.DataFrame()

    if group_cols is None:
        group_cols = [
            "Agent Name",
            "Account",
            "site",
            "role",
            "week",
            "Source_Sheet",
        ]

    valid_group_cols = [c for c in group_cols if c in raw_df.columns]

    if not valid_group_cols or raw_df.empty:
        return pd.DataFrame()

    summary = raw_df.groupby(valid_group_cols, as_index=False).agg(
        Days_Logged=(
            ("Date", "count")
            if "Date" in raw_df.columns
            else ("Exceeded_Break_Raw_Mins", "count")
        ),
        Exceeded_Break_Mins=("Exceeded_Break_Raw_Mins", "sum"),
        Unaccounted_Mins=("Unaccounted_Mins", "sum"),
        Direct_Adherence_Avg=("Parsed_Adherence", "mean"),
    )

    summary["Scheduled_Mins"] = summary["Days_Logged"] * SHIFT_MINS_PER_DAY
    summary["Total_Lost_Mins"] = (
        summary["Unaccounted_Mins"] + summary["Exceeded_Break_Mins"]
    )
    summary["Adherence_%"] = summary["Direct_Adherence_Avg"]

    missing_mask = summary["Adherence_%"].isna()
    if missing_mask.any():
        calc_vals = (
            1.0
            - (
                summary.loc[missing_mask, "Total_Lost_Mins"]
                / summary.loc[missing_mask, "Scheduled_Mins"]
            )
        ) * 100.0
        summary.loc[missing_mask, "Adherence_%"] = calc_vals.clip(
            lower=0, upper=100
        )

    summary["Goal_Met"] = summary["Adherence_%"] >= 88.0
    return deduplicate_dataframe_columns(summary)


filtered_df = calculate_adherence_summary(filtered_raw_df)


# -------------------------------------------------------------
# 5. RELATIONAL 360° AGENT SCORECARD ENGINE
# -------------------------------------------------------------
def build_360_agent_scorecard(att_df, adh_df, qa_df):
    if (att_df is None or att_df.empty) and (adh_df is None or adh_df.empty):
        return pd.DataFrame()

    records = {}

    if not att_df.empty and "Agent Name" in att_df.columns:
        att_grouped = att_df.groupby("Agent Name", as_index=False).agg(
            Unjustified_Absences=(
                "Unjustified Absences",
                lambda x: pd.to_numeric(x, errors="coerce").fillna(0).sum(),
            ),
            Justified_Absences=(
                "Justified Absences",
                lambda x: pd.to_numeric(x, errors="coerce").fillna(0).sum(),
            ),
            Total_Late_Mins=("Late_Mins_Numeric", "sum"),
        )
        for _, row in att_grouped.iterrows():
            name = str(row["Agent Name"]).strip()
            records[name] = {
                "Agent Name": name,
                "Unjustified Absences": int(row["Unjustified_Absences"]),
                "Justified Absences": int(row["Justified_Absences"]),
                "Late Minutes": float(row["Total_Late_Mins"]),
                "Adherence %": np.nan,
                "Exceeded Break Mins": 0.0,
                "Unaccounted Mins": 0.0,
                "QA Audit Count": 0,
                "QA Avg Score": np.nan,
            }

    if not adh_df.empty and "Agent Name" in adh_df.columns:
        adh_grouped = adh_df.groupby("Agent Name", as_index=False).agg(
            Avg_Adherence=("Adherence_%", "mean"),
            Exceeded_Break_Mins=("Exceeded_Break_Mins", "sum"),
            Unaccounted_Mins=("Unaccounted_Mins", "sum"),
        )
        for _, row in adh_grouped.iterrows():
            name = str(row["Agent Name"]).strip()
            if name not in records:
                records[name] = {
                    "Agent Name": name,
                    "Unjustified Absences": 0,
                    "Justified Absences": 0,
                    "Late Minutes": 0.0,
                    "Adherence %": row["Avg_Adherence"],
                    "Exceeded Break Mins": float(row["Exceeded_Break_Mins"]),
                    "Unaccounted Mins": float(row["Unaccounted_Mins"]),
                    "QA Audit Count": 0,
                    "QA Avg Score": np.nan,
                }
            else:
                records[name]["Adherence %"] = row["Avg_Adherence"]
                records[name]["Exceeded Break Mins"] = float(
                    row["Exceeded_Break_Mins"]
                )
                records[name]["Unaccounted Mins"] = float(
                    row["Unaccounted_Mins"]
                )

    if not qa_df.empty and "Agent Name" in qa_df.columns:
        qa_grouped = qa_df.groupby("Agent Name", as_index=False).agg(
            QA_Count=("QA_Score_Numeric", "count"),
            QA_Avg=("QA_Score_Numeric", "mean"),
        )
        for _, row in qa_grouped.iterrows():
            name = str(row["Agent Name"]).strip()
            if name in records:
                records[name]["QA Audit Count"] = int(row["QA_Count"])
                records[name]["QA Avg Score"] = row["QA_Avg"]

    scorecard_df = pd.DataFrame(list(records.values()))
    return deduplicate_dataframe_columns(scorecard_df)


master_scorecard_df = build_360_agent_scorecard(
    filtered_attendance_df, filtered_df, filtered_qa_df
)


# -------------------------------------------------------------
# 6. DASHBOARD LAYOUT & TAB ROUTING
# -------------------------------------------------------------
(
    tab_cmd_center,
    tab_attendance,
    tab_adherence,
    tab_ops_kpi,
    tab_agent_360,
    tab_service_hours,
    tab_qa,
) = st.tabs(
    [
        "⚡ Command Center",
        "📅 Attendance",
        "🎯 Status Adherence",
        "📊 Operational KPIs",
        "👤 360° Agent Scorecard",
        "⏱️ Service Hours & Forecast",
        "🛡️ Quality Assurance",
    ]
)

# -------------------------------------------------------------
# TAB 1: EXECUTIVE COMMAND CENTER
# -------------------------------------------------------------
with tab_cmd_center:
    st.subheader("⚡ Executive Operational Overview")

    total_roster = (
        filtered_attendance_df["Agent Name"].nunique()
        if not filtered_attendance_df.empty
        else (
            filtered_df["Agent Name"].nunique() if not filtered_df.empty else 0
        )
    )
    overall_adh = (
        filtered_df["Adherence_%"].mean() if not filtered_df.empty else 0.0
    )
    total_unjustified = (
        int(
            pd.to_numeric(
                filtered_attendance_df.get("Unjustified Absences", 0),
                errors="coerce",
            ).sum()
        )
        if not filtered_attendance_df.empty
        else 0
    )
    qa_avg_overall = (
        filtered_qa_df["QA_Score_Numeric"].mean()
        if not filtered_qa_df.empty
        and "QA_Score_Numeric" in filtered_qa_df.columns
        else np.nan
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("👥 Active Roster Headcount", f"{total_roster} Agents")
    c2.metric(
        "🎯 Status Adherence Score",
        f"{overall_adh:.1f}%" if not np.isnan(overall_adh) else "N/A",
        delta=(
            f"{overall_adh - 88.0:+.1f}% vs Goal"
            if not np.isnan(overall_adh)
            else None
        ),
    )
    c3.metric("⚠️ Total Unjustified Absences", f"{total_unjustified}")
    c4.metric(
        "🛡️ Average QA Score",
        f"{qa_avg_overall:.1f}%" if not pd.isna(qa_avg_overall) else "No Audits",
    )

    st.divider()

    col_left, col_right = st.columns([1.5, 1])

    with col_left:
        st.markdown("### 📈 Adherence Trend & Lost Time Over Time")
        if not filtered_df.empty and "week" in filtered_df.columns:
            weekly_cmd = (
                filtered_df.groupby("week", as_index=False)
                .agg(
                    Avg_Adherence=("Adherence_%", "mean"),
                    Total_Lost_Mins=("Total_Lost_Mins", "sum"),
                )
                .sort_values(
                    by="week",
                    key=lambda x: x.str.extract(r"(\d+)")[0].astype(float),
                )
            )

            fig_cmd = make_subplots(specs=[[{"secondary_y": True}]])
            fig_cmd.add_trace(
                go.Scatter(
                    x=weekly_cmd["week"],
                    y=weekly_cmd["Avg_Adherence"],
                    name="Adherence %",
                    mode="lines+markers+text",
                    text=[f"{v:.1f}%" for v in weekly_cmd["Avg_Adherence"]],
                    textposition="top center",
                    line=dict(color="#007AC1", width=3),
                ),
                secondary_y=False,
            )
            fig_cmd.add_hline(
                y=88.0,
                line_dash="dash",
                line_color="red",
                annotation_text="88% Target",
                secondary_y=False,
            )
            fig_cmd.add_trace(
                go.Bar(
                    x=weekly_cmd["week"],
                    y=weekly_cmd["Total_Lost_Mins"],
                    name="Lost Mins",
                    opacity=0.3,
                    marker_color="#FF4B4B",
                ),
                secondary_y=True,
            )
            fig_cmd.update_layout(
                hovermode="x unified",
                margin=dict(l=10, r=10, t=20, b=10),
                legend=dict(orientation="h", y=1.1),
            )
            fig_cmd.update_yaxes(range=[50, 105], secondary_y=False)
            st.plotly_chart(fig_cmd, use_container_width=True)
        else:
            st.info("No adherence trend data available for selected scope.")

    with col_right:
        st.markdown("### 🚨 High Risk Agents (Adherence < 88%)")
        if not filtered_df.empty:
            at_risk = filtered_df[filtered_df["Adherence_%"] < 88.0][
                ["Agent Name", "Account", "Adherence_%", "Total_Lost_Mins"]
            ].sort_values(by="Adherence_%", ascending=True)

            if not at_risk.empty:
                at_risk["Adherence_%"] = at_risk["Adherence_%"].apply(
                    lambda x: f"{x:.1f}%"
                )
                st.dataframe(
                    deduplicate_dataframe_columns(at_risk),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.success(
                    "🎉 All agents are currently meeting or exceeding the 88% goal!"
                )
        else:
            st.info("No agent risk records found.")

# -------------------------------------------------------------
# TAB 2: ATTENDANCE
# -------------------------------------------------------------
with tab_attendance:
    a_col1, a_col2 = st.columns([2.5, 1.5])
    with a_col1:
        st.subheader("📅 Attendance Tracker & Pivot Summary")
    with a_col2:
        st.markdown(
            "[🔗 Main Attendance Sheet](https://docs.google.com/spreadsheets/d/1PUerkTX4iCaFUP27FXV34azza6L5LpFYsb1nHVKrH-c/edit#gid=601856217)"
        )
        st.markdown(
            "[🔗 Pivot Attendance Summary](https://docs.google.com/spreadsheets/d/1kzXr88ueah-Gg0gVI4bhl1peFdWYgy0nIFRkZOl0RK0/edit#gid=243149129)"
        )

    if not filtered_attendance_df.empty:
        working_att = filtered_attendance_df.copy()
        working_att["Unjustified Absences"] = pd.to_numeric(
            working_att.get("Unjustified Absences", 0), errors="coerce"
        ).fillna(0)
        working_att["Justified Absences"] = pd.to_numeric(
            working_att.get("Justified Absences", 0), errors="coerce"
        ).fillna(0)
        working_att["Late_Mins_Numeric"] = pd.to_numeric(
            working_att.get("Late_Mins_Numeric", 0), errors="coerce"
        ).fillna(0)
        working_att["Total Late Instances"] = pd.to_numeric(
            working_att.get("Total Late Instances", 0), errors="coerce"
        ).fillna(0)

        agent_totals = working_att.groupby("Agent Name", as_index=False).agg(
            {
                "Unjustified Absences": "sum",
                "Justified Absences": "sum",
                "Total Late Instances": "sum",
                "Late_Mins_Numeric": "sum",
            }
        )

        active_headcount = agent_totals["Agent Name"].nunique()
        unjustified_absences = int(agent_totals["Unjustified Absences"].sum())
        justified_absences = int(agent_totals["Justified Absences"].sum())
        late_instances = int(agent_totals["Total Late Instances"].sum())
        total_late_mins = float(agent_totals["Late_Mins_Numeric"].sum())

        late_hours = int(total_late_mins // 60)
        remaining_mins = int(total_late_mins % 60)
        late_time_str = (
            f"{late_hours}h {remaining_mins}m"
            if late_hours > 0
            else f"{int(total_late_mins)} Mins"
        )

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("👥 Active Roster Headcount", f"{active_headcount}")
        m2.metric("⚠️ Unjustified Absences", f"{unjustified_absences}")
        m3.metric("📋 Justified Absences", f"{justified_absences}")
        m4.metric("⏱️ Total Late Instances", f"{late_instances}")
        m5.metric("⏳ Total Lateness Time", late_time_str)

        st.divider()

        st.write(
            "### 📌 Attendance Point Infractions (Rolling 60-Day Pivot Tracker)"
        )
        if not pivot_attendance_df.empty:
            st.dataframe(
                deduplicate_dataframe_columns(pivot_attendance_df),
                use_container_width=True,
                hide_index=True,
            )

        st.divider()
        st.write("### 📋 Primary Attendance Log")
        st.dataframe(
            deduplicate_dataframe_columns(filtered_attendance_df),
            use_container_width=True,
            hide_index=True,
        )

# -------------------------------------------------------------
# TAB 3: STATUS ADHERENCE
# -------------------------------------------------------------
with tab_adherence:
    sub_tab_combined, sub_tab_tds, sub_tab_transdev = st.tabs(
        [
            "🌐 Combined Overview",
            "🏢 TDS Operations",
            "🚌 TransDev (SD & OC)",
        ]
    )

    def render_adherence_dashboard(dataset_df, label_title):
        if dataset_df.empty:
            st.info(f"No adherence data available for {label_title}.")
            return

        m1, m2, m3, m4 = st.columns(4)
        overall_adherence = dataset_df["Adherence_%"].mean()
        non_compliant_count = len(
            dataset_df[dataset_df["Adherence_%"] < 88.0]
        )
        delta_val = (
            overall_adherence - 88.0 if not np.isnan(overall_adherence) else None
        )
        total_overage = dataset_df["Exceeded_Break_Mins"].sum()

        with m1:
            st.metric(
                "🎯 Adherence %",
                (
                    f"{overall_adherence:.1f}%"
                    if not np.isnan(overall_adherence)
                    else "N/A"
                ),
                delta=(
                    f"{delta_val:+.1f}% vs Goal (88%)"
                    if delta_val is not None
                    else None
                ),
            )
        with m2:
            st.metric(
                "🚨 Agents Below 88%",
                f"{non_compliant_count} Agents",
                delta=(
                    "Needs Attention"
                    if non_compliant_count > 0
                    else "All Compliant"
                ),
                delta_color=(
                    "inverse" if non_compliant_count > 0 else "normal"
                ),
            )
        with m3:
            st.metric("⏱️ Break Overage", f"{int(total_overage)} Mins")
        with m4:
            st.metric(
                "👥 Total Tracked Agents",
                f"{dataset_df['Agent Name'].nunique()}",
            )

        st.divider()

        col_acc, col_role = st.columns(2)
        with col_acc:
            st.markdown("### 📁 Adherence Breakdown by Account/Source")
            if "Account" in dataset_df.columns:
                acc_summary = dataset_df.groupby("Account", as_index=False).agg(
                    Avg_Adherence=("Adherence_%", "mean"),
                    Agents_Below_Goal=("Goal_Met", lambda x: (~x).sum()),
                )
                acc_summary["Avg_Adherence"] = acc_summary[
                    "Avg_Adherence"
                ].apply(lambda x: f"{x:.1f}%" if not pd.isna(x) else "N/A")
                st.dataframe(
                    deduplicate_dataframe_columns(acc_summary),
                    use_container_width=True,
                    hide_index=True,
                )

        with col_role:
            st.markdown("### 💼 Adherence Breakdown by Role")
            if "role" in dataset_df.columns:
                role_summary = dataset_df.groupby("role", as_index=False).agg(
                    Avg_Adherence=("Adherence_%", "mean"),
                    Agents_Below_Goal=("Goal_Met", lambda x: (~x).sum()),
                )
                role_summary["Avg_Adherence"] = role_summary[
                    "Avg_Adherence"
                ].apply(lambda x: f"{x:.1f}%" if not pd.isna(x) else "N/A")
                st.dataframe(
                    deduplicate_dataframe_columns(role_summary),
                    use_container_width=True,
                    hide_index=True,
                )

        st.divider()
        st.markdown(f"### 📋 Detailed Log ({label_title})")
        display_log = deduplicate_dataframe_columns(
            dataset_df.sort_values(by="Adherence_%", ascending=True)
        )
        st.dataframe(
            display_log,
            use_container_width=True,
            hide_index=True,
        )

    with sub_tab_combined:
        render_adherence_dashboard(filtered_df, "All Combined Operations")

    with sub_tab_tds:
        tds_data = (
            filtered_df[filtered_df["Source_Sheet"] == "TDS"]
            if not filtered_df.empty
            else pd.DataFrame()
        )
        render_adherence_dashboard(tds_data, "TDS Operations")

    with sub_tab_transdev:
        transdev_data = (
            filtered_df[filtered_df["Source_Sheet"] == "TransDev SD & OC"]
            if not filtered_df.empty
            else pd.DataFrame()
        )
        render_adherence_dashboard(transdev_data, "TransDev Operations")

# -------------------------------------------------------------
# TAB 4: OPERATIONAL KPIS
# -------------------------------------------------------------
with tab_ops_kpi:
    st.subheader("📊 Operational KPI View")
    col_cdmx, col_tj = st.columns(2)

    with col_cdmx:
        st.markdown("#### 🏢 CDMX Operational KPIs")
        if not cdmx_kpis_df.empty:
            st.dataframe(
                deduplicate_dataframe_columns(cdmx_kpis_df),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No CDMX KPI data loaded.")

    with col_tj:
        st.markdown("#### 🌊 Tijuana Operational KPIs")
        if not tj_kpis_df.empty:
            st.dataframe(
                deduplicate_dataframe_columns(tj_kpis_df),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No Tijuana KPI data loaded.")

    st.divider()
    st.markdown("#### 📈 CDMX Weekly Performance Trends")
    if not cdmx_weekly_trends_df.empty:
        st.dataframe(
            deduplicate_dataframe_columns(cdmx_weekly_trends_df),
            use_container_width=True,
            hide_index=True,
        )

# -------------------------------------------------------------
# TAB 5: 360° AGENT SCORECARD
# -------------------------------------------------------------
with tab_agent_360:
    st.subheader("👤 360° Agent Performance Scorecard")
    if not master_scorecard_df.empty:
        selected_agent = st.selectbox(
            "Select Agent to Audit:",
            options=sorted(master_scorecard_df["Agent Name"].unique()),
        )
        agent_profile = master_scorecard_df[
            master_scorecard_df["Agent Name"] == selected_agent
        ].iloc[0]

        p1, p2, p3, p4 = st.columns(4)
        p1.metric(
            "⚠️ Unjustified Absences",
            f"{int(agent_profile['Unjustified Absences'])} Absences",
        )
        p2.metric(
            "⏱️ Lateness Total",
            f"{int(agent_profile['Late Minutes'])} Mins",
        )
        adh_val = agent_profile["Adherence %"]
        p3.metric(
            "🎯 Status Adherence",
            f"{adh_val:.1f}%" if not pd.isna(adh_val) else "N/A",
            delta=(
                f"{adh_val - 88.0:+.1f}% vs Goal"
                if not pd.isna(adh_val)
                else None
            ),
        )
        qa_val = agent_profile["QA Avg Score"]
        p4.metric(
            "🛡️ QA Score Avg",
            f"{qa_val:.1f}%" if not pd.isna(qa_val) else "No Audits",
        )

        st.divider()
        st.markdown("### 📊 Master Agent Profile Matrix")
        st.dataframe(
            deduplicate_dataframe_columns(master_scorecard_df),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No consolidated agent records available.")

# -------------------------------------------------------------
# TAB 6: SERVICE HOURS & FORECAST
# -------------------------------------------------------------
with tab_service_hours:
    st.subheader("⏱️ Service Hours & Capacity Forecast")

    if not filtered_raw_df.empty:
        actual_hours_df = filtered_raw_df.groupby(
            ["Account", "site"], as_index=False
        ).agg(
            Days_Logged=(
                ("Date", "count")
                if "Date" in filtered_raw_df.columns
                else ("Exceeded_Break_Raw_Mins", "count")
            ),
            Exceeded_Break_Mins=("Exceeded_Break_Raw_Mins", "sum"),
            Unaccounted_Mins=("Unaccounted_Mins", "sum"),
        )
        actual_hours_df["Scheduled_Hours"] = (
            actual_hours_df["Days_Logged"] * 8.0
        )
        actual_hours_df["Lost_Hours"] = (
            actual_hours_df["Exceeded_Break_Mins"]
            + actual_hours_df["Unaccounted_Mins"]
        ) / 60.0
        actual_hours_df["Actual_Hours"] = (
            actual_hours_df["Scheduled_Hours"] - actual_hours_df["Lost_Hours"]
        )

        if (
            not service_forecast_df.empty
            and "Account" in service_forecast_df.columns
        ):
            forecast_summary = service_forecast_df.groupby(
                "Account", as_index=False
            ).agg(Forecasted_Hours=("Forecasted_Hours_Numeric", "sum"))
            merged_hours = pd.merge(
                actual_hours_df, forecast_summary, on="Account", how="left"
            )
            merged_hours["Forecasted_Hours"] = merged_hours[
                "Forecasted_Hours"
            ].fillna(merged_hours["Scheduled_Hours"])
        else:
            merged_hours = actual_hours_df.copy()
            merged_hours["Forecasted_Hours"] = merged_hours["Scheduled_Hours"]

        merged_hours["Fulfillment_%"] = (
            merged_hours["Actual_Hours"] / merged_hours["Forecasted_Hours"]
        ) * 100.0

        st.dataframe(
            deduplicate_dataframe_columns(merged_hours),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No capacity logs found for selected filters.")

# -------------------------------------------------------------
# TAB 7: QUALITY ASSURANCE
# -------------------------------------------------------------
with tab_qa:
    st.subheader("🛡️ Virtual Quality Assurance (QA) Engine")

    if not filtered_qa_df.empty and "QA_Score_Numeric" in filtered_qa_df.columns:
        valid_qa = filtered_qa_df.dropna(subset=["QA_Score_Numeric"])

        q1, q2, q3 = st.columns(3)
        q1.metric("📋 Total QA Audits", f"{len(valid_qa)}")
        q2.metric("🎯 Average Score", f"{valid_qa['QA_Score_Numeric'].mean():.1f}%")
        q3.metric(
            "⚠️ Critical Low Scores (<85%)",
            f"{len(valid_qa[valid_qa['QA_Score_Numeric'] < 85.0])}",
        )

        st.divider()

        col_qa1, col_qa2 = st.columns(2)
        with col_qa1:
            st.markdown("### 📊 QA Audit Score Distribution")
            fig_qa = px.histogram(
                valid_qa,
                x="QA_Score_Numeric",
                nbins=10,
                color_discrete_sequence=["#007AC1"],
                labels={"QA_Score_Numeric": "QA Score (%)"},
            )
            fig_qa.update_layout(margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig_qa, use_container_width=True)

        with col_qa2:
            st.markdown("### 📋 Evaluator Audit Summary")
            if "Evaluator" in valid_qa.columns:
                eval_summary = valid_qa.groupby(
                    "Evaluator", as_index=False
                ).agg(
                    Audits_Conducted=("QA_Score_Numeric", "count"),
                    Avg_Score=("QA_Score_Numeric", "mean"),
                )
                eval_summary["Avg_Score"] = eval_summary["Avg_Score"].apply(
                    lambda x: f"{x:.1f}%"
                )
                st.dataframe(
                    deduplicate_dataframe_columns(eval_summary),
                    use_container_width=True,
                    hide_index=True,
                )

        st.divider()
        st.markdown("### 📋 Primary Virtual QA Log")
        st.dataframe(
            deduplicate_dataframe_columns(filtered_qa_df),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No QA data available under selected scope.")
