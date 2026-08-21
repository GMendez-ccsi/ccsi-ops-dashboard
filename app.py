import pandas as pd
import streamlit as st

st.set_page_config(page_title="Operations Dashboard", layout="wide")

# -------------------------------------------------------------
# GLOBAL FILTERS SECTION
# -------------------------------------------------------------
st.title("🔍 Filters & Drilldown")

col_site, col_account, col_month, col_week, col_role = st.columns(5)

with col_site:
    selected_site = st.selectbox("Site:", ["CDMX", "MX"])

with col_account:
    selected_account = st.selectbox(
        "Account / Source:", ["All Accounts", "TDS", "MTS", "OC"]
    )

with col_month:
    selected_month = st.selectbox(
        "Month:", ["August 2026", "July 2026", "All Months"]
    )

with col_week:
    selected_weeks = st.multiselect(
        "Work Week (Leave empty for ALL weeks):",
        ["Week 31", "Week 32", "Week 33", "Week 34"],
        default=[]
    )

with col_role:
    selected_roles = st.multiselect(
        "Role (Position) (Leave empty for ALL roles):",
        ["SD RESERVATIONIST", "OC RESERVATIONIST", "CSA", "TEAM LEADER"],
        default=[]
    )

st.divider()

# -------------------------------------------------------------
# MAIN DASHBOARD TABS
# -------------------------------------------------------------
tab_attend, tab_adh, tab_kpi, tab_scope, tab_hours, tab_qa = st.tabs([
    "📅 Attendance",
    "🎯 Status Adherence",
    "📊 Operational KPI View",
    "👤 Agent Scope",
    "⏱️ Service Hours per Campaign",
    "🛡️ Quality Assurance",
])

# TAB 1: ATTENDANCE
with tab_attend:
    st.subheader("📅 Attendance Overview")
    st.info("Attendance panel content.")

# TAB 2: STATUS ADHERENCE
with tab_adh:
    st.subheader("🎯 Status Adherence")
    st.info("Status adherence content.")

# TAB 3: OPERATIONAL KPI VIEW
with tab_kpi:
    st.subheader("📊 Operational KPI View")
    st.info("KPI content.")

# TAB 4: AGENT SCOPE
with tab_scope:
    st.subheader("👤 Agent Scope")
    st.info("Agent scope content.")

# TAB 5: SERVICE HOURS PER CAMPAIGN
with tab_hours:
    st.subheader("⏱️ Service Hours per Campaign")
    st.info("Service hours content.")

# TAB 6: QUALITY ASSURANCE
with tab_qa:
    st.subheader("🛡️ Quality Assurance Overview")
    st.markdown(
        "[🔗 Open QA Audit Google Sheet](https://docs.google.com/spreadsheets/d/17blbXU8PWciUJrU0PMTj1iMydQOqPQyGRUYVf3LhbNk/edit#gid=0)"
    )

    @st.cache_data(ttl=300)
    def load_qa_raw_monitoring():
        try:
            sheet_id = "17blbXU8PWciUJrU0PMTj1iMydQOqPQyGRUYVf3LhbNk"
            url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet=MONITORING"
            df = pd.read_csv(url, low_memory=False)
            df.columns = [str(c).strip() for c in df.columns]

            if "week" in df.columns:
                df = df[df["week"].notna()]
            return df
        except Exception as e:
            st.error(f"Error loading MONITORING sheet tab: {e}")
            return pd.DataFrame()

    qa_df = load_qa_raw_monitoring()

    if qa_df is not None and not qa_df.empty:
        col_map = {c.lower(): c for c in qa_df.columns}

        week_col = col_map.get("week", "week")
        date_col = col_map.get("date", "DATE")
        lead_col = col_map.get("lead", "LEAD")
        role_col = col_map.get("role", "ROLE")
        project_col = col_map.get("project", "PROJECT")
        queue_col = col_map.get("queue", "QUEUE")
        feedback_col = col_map.get("feedback", "FEEDBACK")
        comment_col = col_map.get("comment", "COMMENT")

        filtered_qa = qa_df.copy()

        # Work Week Filter
        if len(selected_weeks) > 0:
            if week_col in filtered_qa.columns:
                target_week_nums = []
                for w in selected_weeks:
                    digits = "".join(filter(str.isdigit, str(w)))
                    if digits:
                        target_week_nums.append(int(digits))

                if target_week_nums:
                    raw_numeric_weeks = pd.to_numeric(
                        filtered_qa[week_col], errors="coerce"
                    )
                    filtered_qa = filtered_qa[
                        raw_numeric_weeks.isin(target_week_nums)
                    ]

        # Account / Queue Filter
        if selected_account and selected_account != "All Accounts":
            acc_str = str(selected_account).strip().upper()
            search_terms = [acc_str]
            if "TDS" in acc_str:
                search_terms.extend(
                    ["TDS", "SAN DIEGO", "ORANGE COUNTY", "HYBRID"]
                )

            pattern = "|".join(search_terms)
            q_match = (
                filtered_qa[queue_col]
                .astype(str)
                .str.upper()
                .str.contains(pattern, na=False)
                if queue_col in filtered_qa.columns
                else pd.Series(False, index=filtered_qa.index)
            )
            p_match = (
                filtered_qa[project_col]
                .astype(str)
                .str.upper()
                .str.contains(pattern, na=False)
                if project_col in filtered_qa.columns
                else pd.Series(False, index=filtered_qa.index)
            )

            combined_match = q_match | p_match
            if combined_match.any():
                filtered_qa = filtered_qa[combined_match]

        # Role Filter
        if len(selected_roles) > 0:
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
                    role_series = (
                        filtered_qa[role_col]
                        .astype(str)
                        .str.strip()
                        .str.lower()
                    )
                    filtered_qa = filtered_qa[
                        role_series.str.contains(pattern, na=False)
                    ]

        qa_tab1, qa_tab2, qa_tab3 = st.tabs([
            "📌 Weekly Areas of Opportunity",
            "📊 TL Virtual Monitoring Pivot",
            "📋 Master QA Dataset",
        ])

        with qa_tab1:
            st.markdown("### 💡 Major Areas of Opportunity Summary")

            target_opp_col = (
                feedback_col
                if feedback_col in filtered_qa.columns
                else comment_col
            )

            if (
                target_opp_col in filtered_qa.columns
                and week_col in filtered_qa.columns
            ):
                opp_df = (
                    filtered_qa[[week_col, target_opp_col]]
                    .dropna(subset=[target_opp_col])
                    .copy()
                )
                opp_df[target_opp_col] = (
                    opp_df[target_opp_col].astype(str).str.strip()
                )
                opp_df = opp_df[opp_df[target_opp_col] != ""]

                positive_keywords = [
                    "good interaction",
                    "positive and effective",
                    "great job",
                    "no areas for improvement",
                    "perfect call",
                ]
                opp_only_df = opp_df[
                    ~opp_df[target_opp_col]
                    .str.lower()
                    .str.contains("|".join(positive_keywords))
                ]

                if not opp_only_df.empty:

                    def categorize_opportunity(text):
                        t = text.lower()
                        if "script order" in t or "sequence" in t:
                            return "Script Order & Sequence Adherence"
                        elif "greeting" in t or "opening" in t:
                            return "Mandatory Greeting / Script Opening"
                        elif "closing" in t or "call exit" in t:
                            return "Mandatory Closing Script"
                        elif (
                            "identity" in t
                            or "verification" in t
                            or "first and last name" in t
                        ):
                            return "Customer Identity Verification"
                        elif "reservation" in t or "trip details" in t:
                            return "Trip & Reservation Data Collection"
                        else:
                            return "General Script & Policy Adherence"

                    opp_only_df["Category"] = opp_only_df[
                        target_opp_col
                    ].apply(categorize_opportunity)

                    top_category = (
                        opp_only_df["Category"].value_counts().idxmax()
                    )
                    st.info(f"🎯 **Top Area of Opportunity:** {top_category}")

                    cat_summary = (
                        opp_only_df.groupby([week_col, "Category"])
                        .size()
                        .reset_index(name="Frequency Count")
                        .sort_values(
                            by=[week_col, "Frequency Count"],
                            ascending=[True, False],
                        )
                    )

                    st.markdown("**Opportunities Categorized by Week**")
                    st.dataframe(
                        cat_summary, use_container_width=True, hide_index=True
                    )

                    st.divider()
                    st.markdown("**Detailed Feedback Log**")
                    st.dataframe(
                        opp_only_df[[week_col, target_opp_col]],
                        use_container_width=True,
                        hide_index=True,
                    )
                else:
                    st.warning(
                        "No improvement areas logged for the selected filter combination."
                    )
            else:
                st.warning("Could not find feedback or week columns.")

        with qa_tab2:
            st.markdown("### 🔍 TL Virtual Monitored Sessions Pivot")

            if (
                lead_col in filtered_qa.columns
                and week_col in filtered_qa.columns
            ):
                m1, m2, m3 = st.columns(3)
                m1.metric(
                    "🎧 Total Monitored Sessions", f"{len(filtered_qa):,}"
                )
                m2.metric(
                    "👥 Active Team Leads", filtered_qa[lead_col].nunique()
                )
                m3.metric("📅 Weeks Covered", filtered_qa[week_col].nunique())

                st.divider()

                st.markdown(
                    "**Matrix View: Monitored Sessions (Team Lead vs Week)**"
                )
                tl_week_matrix = pd.crosstab(
                    index=filtered_qa[lead_col],
                    columns=filtered_qa[week_col],
                    margins=True,
                    margins_name="Total Monitored",
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
                    .sort_values(
                        by=[lead_col, week_col], ascending=[True, True]
                    )
                )
                st.dataframe(
                    tl_breakdown, use_container_width=True, hide_index=True
                )
            else:
                st.warning(
                    "Unable to identify 'LEAD' or 'week' columns required to build the pivot."
                )

        with qa_tab3:
            st.markdown("### 📋 Full Raw QA Record Log (`MONITORING` Sheet Tab)")
            st.dataframe(filtered_qa, use_container_width=True, hide_index=True)

    else:
        st.info(
            "No QA data returned from Google Sheets. Check access permissions or filter selections."
        )
