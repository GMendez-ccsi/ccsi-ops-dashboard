import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# -------------------------------------------------------------
# CONFIGURATION & CONSTANTS
# -------------------------------------------------------------
st.set_page_config(
    page_title="Operations Command Center",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

SHIFT_MINS_PER_DAY = 480.0  # Standard 8-hour shift in minutes


# -------------------------------------------------------------
# HELPER & CLEANING UTILITIES
# -------------------------------------------------------------
def deduplicate_dataframe_columns(df):
    """Ensures DataFrame column names are unique to prevent Streamlit rendering crashes."""
    if df.empty:
        return df
    cols = pd.Series(df.columns)
    for dup in cols[cols.duplicated()].unique():
        cols[cols == dup] = [
            f"{dup}_{i}" if i != 0 else dup for i in range(sum(cols == dup))
        ]
    df.columns = cols
    return df


def clean_sheet_adherence_data(df):
    """
    Cleans raw Google Sheet string values into float/numeric formats
    for Pandas mathematical aggregations.
    Strips '%', 'mins', non-numeric artifacts, and converts HH:MM:SS to total minutes.
    """
    if df.empty:
        return df

    cleaned_df = df.copy()
    cleaned_df.columns = cleaned_df.columns.str.strip()

    # Clean Percentage Columns (e.g., "88.5%" -> 88.5)
    pct_cols = [
        c
        for c in cleaned_df.columns
        if "%" in c or "Adherence" in c or "Parsed_Adherence" in c
    ]
    for col in pct_cols:
        cleaned_df[col] = (
            cleaned_df[col]
            .astype(str)
            .str.replace("%", "", regex=False)
            .str.strip()
        )
        cleaned_df[col] = pd.to_numeric(cleaned_df[col], errors="coerce")

    # Clean Time/Minute Columns (e.g., "15 mins", "15:00", or raw string numbers)
    min_cols = [
        c
        for c in cleaned_df.columns
        if any(
            k in c
            for k in [
                "Mins",
                "Time",
                "Exceeded",
                "Unaccounted",
                "Break",
                "Meal",
                "Meeting",
                "Training",
                "Late",
            ]
        )
    ]
    for col in min_cols:
        col_str = cleaned_df[col].astype(str)
        if col_str.str.contains(":").any():
            # Convert HH:MM:SS duration string to numeric float minutes
            cleaned_df[col] = (
                pd.to_timedelta(col_str, errors="coerce").dt.total_seconds()
                / 60.0
            )
        else:
            # Strip non-numeric characters like "mins" or commas
            cleaned_df[col] = col_str.str.replace(r"[^\d.-]", "", regex=True)
            cleaned_df[col] = pd.to_numeric(cleaned_df[col], errors="coerce")

        cleaned_df[col] = cleaned_df[col].fillna(0.0)

    return cleaned_df


# -------------------------------------------------------------
# 3. ADHERENCE SUMMARY ENGINE
# -------------------------------------------------------------
def calculate_adherence_summary(
    raw_df, group_cols=["Agent Name", "Account", "role", "week", "Source_Sheet"]
):
    if raw_df.empty:
        return pd.DataFrame()

    df = clean_sheet_adherence_data(raw_df)
    valid_group_cols = [c for c in df.columns if c in group_cols]

    if not valid_group_cols:
        valid_group_cols = [
            c for c in ["Agent Name", "Account"] if c in df.columns
        ]
        if not valid_group_cols:
            return pd.DataFrame()

    # Dynamic Column Mapping Alias layer (Sheet -> Calculation Engine)
    col_mapping = {
        "Total Break Mins": "Total Break_Mins",
        "Total Break_Mins": "Total Break_Mins",
        "Total Meal Mins": "Total Meal_Mins",
        "Total Meal_Mins": "Total Meal_Mins",
        "Total Meeting Mins": "Total Meeting_Mins",
        "Total Meeting_Mins": "Total Meeting_Mins",
        "Total Training Mins": "Total Training_Mins",
        "Total Training_Mins": "Total Training_Mins",
        "Exceeded Break Mins": "Exceeded_Break_Raw_Mins",
        "Exceeded Break Raw Mins": "Exceeded_Break_Raw_Mins",
        "Exceeded_Break_Raw_Mins": "Exceeded_Break_Raw_Mins",
        "Total Time Exceeded": "Exceeded_Break_Raw_Mins",
        "Unaccounted Mins": "Unaccounted_Mins",
        "Unaccounted_Mins": "Unaccounted_Mins",
        "Status Adherence": "Parsed_Adherence",
        "Adherence %": "Parsed_Adherence",
        "Parsed_Adherence": "Parsed_Adherence",
    }
    df = df.rename(columns=col_mapping)

    # Ensure required aggregation target columns exist
    for c in [
        "Total Break_Mins",
        "Total Meal_Mins",
        "Total Meeting_Mins",
        "Total Training_Mins",
        "Exceeded_Break_Raw_Mins",
        "Unaccounted_Mins",
        "Parsed_Adherence",
    ]:
        if c not in df.columns:
            df[c] = 0.0

    summary = df.groupby(valid_group_cols, as_index=False).agg(
        Days_Logged=(
            ("Date", "count")
            if "Date" in df.columns
            else ("Total Break_Mins", "count")
        ),
        Total_Break_Mins=("Total Break_Mins", "sum"),
        Total_Meal_Mins=("Total Meal_Mins", "sum"),
        Total_Meeting_Mins=("Total Meeting_Mins", "sum"),
        Total_Training_Mins=("Total Training_Mins", "sum"),
        Exceeded_Break_Mins=("Exceeded_Break_Raw_Mins", "sum"),
        Unaccounted_Mins=("Unaccounted_Mins", "sum"),
        Direct_Adherence_Avg=("Parsed_Adherence", "mean"),
    )

    summary["Scheduled_Mins"] = summary["Days_Logged"] * SHIFT_MINS_PER_DAY
    summary["Total_Lost_Mins"] = (
        summary["Unaccounted_Mins"] + summary["Exceeded_Break_Mins"]
    )
    summary["Adherence_%"] = summary["Direct_Adherence_Avg"]

    # Dynamic Fallback Calculation if Direct Parse is missing or zero
    missing_mask = (
        summary["Adherence_%"].isna()
        | (summary["Adherence_%"] == 0.0)
        & (summary["Scheduled_Mins"] > 0)
    )
    if missing_mask.any():
        calc_vals = (
            1.0
            - (
                summary.loc[missing_mask, "Total_Lost_Mins"]
                / summary.loc[missing_mask, "Scheduled_Mins"].replace(
                    0, np.nan
                )
            )
        ) * 100.0
        summary.loc[missing_mask, "Adherence_%"] = calc_vals.clip(
            lower=0.0, upper=100.0
        ).fillna(0.0)

    summary["Goal_Met"] = summary["Adherence_%"] >= 88.0
    return deduplicate_dataframe_columns(summary)


# -------------------------------------------------------------
# 4. RELATIONAL 360° AGENT SCORECARD ENGINE
# -------------------------------------------------------------
def build_360_agent_scorecard(att_df, adh_df, qa_df):
    if att_df.empty and adh_df.empty and qa_df.empty:
        return pd.DataFrame()

    records = {}

    # 1. Process Attendance Data
    if not att_df.empty and "Agent Name" in att_df.columns:
        att_working = clean_sheet_adherence_data(att_df)
        att_grouped = att_working.groupby("Agent Name", as_index=False).agg(
            Unjustified_Absences=("Unjustified Absences", "sum"),
            Justified_Absences=("Justified Absences", "sum"),
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

    # 2. Process Adherence Data
    if not adh_df.empty and "Agent Name" in adh_df.columns:
        adh_working = clean_sheet_adherence_data(adh_df)

        adh_col = (
            "Adherence_%"
            if "Adherence_%" in adh_working.columns
            else "Parsed_Adherence"
        )
        exc_col = (
            "Exceeded_Break_Mins"
            if "Exceeded_Break_Mins" in adh_working.columns
            else "Exceeded_Break_Raw_Mins"
        )

        adh_grouped = adh_working.groupby("Agent Name", as_index=False).agg(
            Avg_Adherence=(
                adh_col,
                lambda x: (
                    x[pd.notna(x)].mean() if not x.dropna().empty else np.nan
                ),
            ),
            Exceeded_Break_Mins=(exc_col, "sum"),
            Unaccounted_Mins=("Unaccounted_Mins", "sum"),
        )
        for _, row in adh_grouped.iterrows():
            name = str(row["Agent Name"]).strip()
            avg_adh = (
                float(row["Avg_Adherence"])
                if pd.notna(row["Avg_Adherence"])
                else np.nan
            )
            exc_mins = float(row["Exceeded_Break_Mins"])
            unacc_mins = float(row["Unaccounted_Mins"])

            if name not in records:
                records[name] = {
                    "Agent Name": name,
                    "Unjustified Absences": 0,
                    "Justified Absences": 0,
                    "Late Minutes": 0.0,
                    "Adherence %": avg_adh,
                    "Exceeded Break Mins": exc_mins,
                    "Unaccounted Mins": unacc_mins,
                    "QA Audit Count": 0,
                    "QA Avg Score": np.nan,
                }
            else:
                records[name]["Adherence %"] = avg_adh
                records[name]["Exceeded Break Mins"] = exc_mins
                records[name]["Unaccounted Mins"] = unacc_mins

    # 3. Process QA Data
    if not qa_df.empty and "Agent Name" in qa_df.columns:
        qa_working = clean_sheet_adherence_data(qa_df)
        qa_grouped = qa_working.groupby("Agent Name", as_index=False).agg(
            QA_Count=("QA_Score_Numeric", "count"),
            QA_Avg=("QA_Score_Numeric", "mean"),
        )
        for _, row in qa_grouped.iterrows():
            name = str(row["Agent Name"]).strip()
            qa_cnt = int(row["QA_Count"])
            qa_score = (
                float(row["QA_Avg"]) if pd.notna(row["QA_Avg"]) else np.nan
            )

            if name not in records:
                records[name] = {
                    "Agent Name": name,
                    "Unjustified Absences": 0,
                    "Justified Absences": 0,
                    "Late Minutes": 0.0,
                    "Adherence %": np.nan,
                    "Exceeded Break Mins": 0.0,
                    "Unaccounted Mins": 0.0,
                    "QA Audit Count": qa_cnt,
                    "QA Avg Score": qa_score,
                }
            else:
                records[name]["QA Audit Count"] = qa_cnt
                records[name]["QA Avg Score"] = qa_score

    scorecard_df = pd.DataFrame(list(records.values()))
    return deduplicate_dataframe_columns(scorecard_df)


# -------------------------------------------------------------
# MOCK / PLACEHOLDER DATA INITIALIZATION (Replace with GSheets Loader)
# -------------------------------------------------------------
@st.cache_data
def load_mock_datasets():
    filtered_raw_df = pd.DataFrame({
        "Agent Name": [
            "John Doe",
            "Jane Smith",
            "Alice Johnson",
            "Bob Brown",
        ],
        "Account": ["TDS", "TransDev", "TDS", "TransDev"],
        "role": ["Agent", "Agent", "Lead", "Agent"],
        "week": ["Week 1", "Week 1", "Week 1", "Week 1"],
        "Source_Sheet": [
            "TDS",
            "TransDev SD & OC",
            "TDS",
            "TransDev SD & OC",
        ],
        "site": ["CDMX", "Tijuana", "CDMX", "Tijuana"],
        "Date": ["2026-03-01", "2026-03-01", "2026-03-01", "2026-03-01"],
        "Status Adherence": ["85.5%", "92.0%", "89.1%", "78.4%"],
        "Exceeded Break Mins": ["15 mins", "0 mins", "5 mins", "42 mins"],
        "Unaccounted Mins": ["10", "0", "0", "18"],
        "Total Break_Mins": [45, 45, 45, 45],
        "Total Meal_Mins": [60, 60, 60, 60],
        "Total Meeting_Mins": [0, 15, 0, 0],
        "Total Training_Mins": [0, 0, 0, 0],
    })

    filtered_attendance_df = pd.DataFrame({
        "Agent Name": [
            "John Doe",
            "Jane Smith",
            "Alice Johnson",
            "Bob Brown",
        ],
        "Unjustified Absences": [1, 0, 0, 2],
        "Justified Absences": [0, 1, 0, 0],
        "Total Late Instances": [2, 0, 1, 3],
        "Late_Mins_Numeric": [25, 0, 10, 45],
    })

    pivot_attendance_df = filtered_attendance_df.copy()

    filtered_qa_df = pd.DataFrame({
        "Agent Name": [
            "John Doe",
            "Jane Smith",
            "Alice Johnson",
            "Bob Brown",
        ],
        "QA_Score_Numeric": [88.0, 95.0, 91.0, 72.0],
        "Evaluator": ["QA Lead A", "QA Lead B", "QA Lead A", "QA Lead B"],
    })

    cdmx_kpis_df = pd.DataFrame(
        {"KPI": ["SLA %", "Occupancy"], "Target": ["90%", "85%"]}
    )
    tj_kpis_df = pd.DataFrame(
        {"KPI": ["SLA %", "Occupancy"], "Target": ["90%", "85%"]}
    )
    cdmx_weekly_trends_df = pd.DataFrame(
        {"Week": ["W1", "W2"], "Adherence": ["88%", "90%"]}
    )
    service_forecast_df = pd.DataFrame(
        {"Account": ["TDS", "TransDev"], "Forecasted_Hours_Numeric": [160, 160]}
    )

    return (
        filtered_raw_df,
        filtered_attendance_df,
        pivot_attendance_df,
        filtered_qa_df,
        cdmx_kpis_df,
        tj_kpis_df,
        cdmx_weekly_trends_df,
        service_forecast_df,
    )


(
    filtered_raw_df,
    filtered_attendance_df,
    pivot_attendance_df,
    filtered_qa_df,
    cdmx_kpis_df,
    tj_kpis_df,
    cdmx_weekly_trends_df,
    service_forecast_df,
) = load_mock_datasets()

# Calculate Summary and Scorecard Engine DataFrames
filtered_df = calculate_adherence_summary(filtered_raw_df)
master_scorecard_df = build_360_agent_scorecard(
    filtered_attendance_df, filtered_df, filtered_qa_df
)


# -------------------------------------------------------------
# 5. DASHBOARD LAYOUT & TAB ROUTING
# -------------------------------------------------------------
(
    tab_cmd_center,
    tab_attendance,
    tab_adherence,
    tab_ops_kpi,
    tab_agent_360,
    tab_service_hours,
    tab_qa,
) = st.tabs([
    "⚡ Command Center",
    "📅 Attendance",
    "🎯 Status Adherence",
    "📊 Operational KPIs",
    "👤 360° Agent Scorecard",
    "⏱️ Service Hours & Forecast",
    "🛡️ Quality Assurance",
])

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
                    key=lambda x: pd.to_numeric(
                        x.str.extract(r"(\d+)", expand=False), errors="coerce"
                    ).fillna(0),
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
                at_risk_display = at_risk.copy()
                at_risk_display["Adherence_%"] = at_risk_display[
                    "Adherence_%"
                ].apply(lambda x: f"{x:.1f}%")
                st.dataframe(
                    deduplicate_dataframe_columns(at_risk_display),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.success(
                    "🎉 All agents are currently meeting or exceeding the 88%"
                    " goal!"
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
            "[🔗 Main Attendance"
            " Sheet](https://docs.google.com/spreadsheets/d/1PUerkTX4iCaFUP27FXV34azza6L5LpFYsb1nHVKrH-c/edit#gid=601856217)"
        )
        st.markdown(
            "[🔗 Pivot Attendance"
            " Summary](https://docs.google.com/spreadsheets/d/1kzXr88ueah-Gg0gVI4bhl1peFdWYgy0nIFRkZOl0RK0/edit#gid=243149129)"
        )

    if not filtered_attendance_df.empty:
        working_att = clean_sheet_adherence_data(filtered_attendance_df)

        agent_totals = working_att.groupby("Agent Name", as_index=False).agg({
            "Unjustified Absences": "sum",
            "Justified Absences": "sum",
            "Total Late Instances": "sum",
            "Late_Mins_Numeric": "sum",
        })

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
    sub_tab_combined, sub_tab_tds, sub_tab_transdev = st.tabs([
        "🌐 Combined Overview",
        "🏢 TDS Operations",
        "🚌 TransDev (SD & OC)",
    ])

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
            overall_adherence - 88.0
            if not np.isnan(overall_adherence)
            else None
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
        display_log = dataset_df.sort_values(
            by="Adherence_%", ascending=True
        ).copy()
        display_log["Adherence_%"] = display_log["Adherence_%"].apply(
            lambda x: f"{x:.1f}%" if pd.notna(x) else "N/A"
        )
        st.dataframe(
            deduplicate_dataframe_columns(display_log),
            use_container_width=True,
            hide_index=True,
        )

    with sub_tab_combined:
        render_adherence_dashboard(filtered_df, "All Combined Operations")

    with sub_tab_tds:
        tds_data = (
            filtered_df[filtered_df["Source_Sheet"] == "TDS"]
            if not filtered_df.empty and "Source_Sheet" in filtered_df.columns
            else pd.DataFrame()
        )
        render_adherence_dashboard(tds_data, "TDS Operations")

    with sub_tab_transdev:
        transdev_data = (
            filtered_df[filtered_df["Source_Sheet"] == "TransDev SD & OC"]
            if not filtered_df.empty and "Source_Sheet" in filtered_df.columns
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

        scorecard_display = master_scorecard_df.copy()
        scorecard_display["Adherence %"] = scorecard_display[
            "Adherence %"
        ].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else "N/A")
        scorecard_display["QA Avg Score"] = scorecard_display[
            "QA Avg Score"
        ].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else "No Audits")

        st.dataframe(
            deduplicate_dataframe_columns(scorecard_display),
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
        clean_raw = clean_sheet_adherence_data(filtered_raw_df)
        group_keys = [
            c for c in ["Account", "site"] if c in clean_raw.columns
        ] or ["Account"]

        actual_hours_df = clean_raw.groupby(
            group_keys, as_index=False
        ).agg(
            Days_Logged=(
                ("Date", "count")
                if "Date" in clean_raw.columns
                else ("Total Break_Mins", "count")
            ),
            Exceeded_Break_Mins=(
                (
                    "Exceeded Break Mins"
                    if "Exceeded Break Mins" in clean_raw.columns
                    else "Exceeded_Break_Raw_Mins"
                ),
                "sum",
            ),
            Unaccounted_Mins=("Unaccounted Mins", "sum"),
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
            merged_hours["Actual_Hours"]
            / merged_hours["Forecasted_Hours"].replace(0, np.nan)
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
        clean_qa_df = clean_sheet_adherence_data(filtered_qa_df)
        valid_qa = clean_qa_df.dropna(subset=["QA_Score_Numeric"])

        q1, q2, q3 = st.columns(3)
        q1.metric("📋 Total QA Audits", f"{len(valid_qa)}")
        q2.metric(
            "🎯 Average Score", f"{valid_qa['QA_Score_Numeric'].mean():.1f}%"
        )
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
