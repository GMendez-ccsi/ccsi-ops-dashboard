import pandas as pd
import streamlit as st

# Set page config FIRST
st.set_page_config(page_title="Operations Dashboard", layout="wide")

# Inject Global Sticky Header CSS
st.markdown(
    """
    <style>
    /* Sticky Top-Level Navigation Tabs */
    div[data-baseweb="tab-list"] {
        position: sticky;
        top: 0px;
        background-color: var(--background-color, #ffffff);
        z-index: 9999;
        padding-top: 8px;
        padding-bottom: 8px;
        border-bottom: 2px solid rgba(49, 51, 63, 0.1);
    }
    
    /* Nesting adjust for sub-tabs inside tabs */
    div[data-baseweb="tab-panel"] div[data-baseweb="tab-list"] {
        top: 48px;
        z-index: 9998;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# -------------------------------------------------------------
# GLOBAL FILTERS SECTION
# -------------------------------------------------------------
st.title("🔍 Filters & Drilldown")

col_site, col_account, col_month, col_week, col_role = st.columns(5)

with col_site:
    selected_site = st.selectbox("Site:", ["CDMX", "MX"])

with col_account:
    selected_account = st.selectbox("Account / Source:", ["All Accounts", "TDS", "MTS", "OC"])

with col_month:
    selected_month = st.selectbox("Month:", ["August 2026", "July 2026", "All Months"])

with col_week:
    selected_weeks = st.multiselect("Work Week:", ["Week 31", "Week 32", "Week 33", "Week 34"], default=["Week 34"])

with col_role:
    selected_roles = st.multiselect("Role (Position):", ["SD RESERVATIONIST", "OC RESERVATIONIST", "CSA", "TEAM LEADER"])

st.divider()

# -------------------------------------------------------------
# MAIN APP TOP-LEVEL TABS
# -------------------------------------------------------------
tab_attend, tab_adh, tab_kpi, tab_scope, tab_hours, tab_qa = st.tabs([
    "📅 Attendance",
    "🎯 Status Adherence",
    "📊 Operational KPI View",
    "👤 Agent Scope",
    "⏱️ Service Hours per Campaign",
    "🛡️ Quality Assurance"
])

# TAB 1: ATTENDANCE
with tab_attend:
    st.subheader("📅 Attendance Dashboard")
    st.info("Attendance metrics container.")

# TAB 2: STATUS ADHERENCE
with tab_adh:
    st.subheader("🎯 Status Adherence View")
    st.info("Adherence metrics container.")

# TAB 3: OPERATIONAL KPI VIEW
with tab_kpi:
    st.subheader("📊 Operational KPI View")
    st.info("KPI metrics container.")

# TAB 4: AGENT SCOPE
with tab_scope:
    st.subheader("👤 Agent Scope")
    st.info("Agent scope metrics container.")

# TAB 5: SERVICE HOURS
with tab_hours:
    st.subheader("⏱️ Service Hours per Campaign")
    st.info("Hours tracking container.")

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
                df = df[df['week'].notna()]
            return df
        except Exception as e:
            st.error(f"Error loading MONITORING sheet: {e}")
            return pd.DataFrame()

    qa_df = load_qa_raw_monitoring()

    if qa_df is not None and not qa_df.empty:
        col_map = {c.lower(): c for c in qa_df.columns}
        
        week_col = col_map.get('week', 'week')
        lead_col = col_map.get('lead', 'LEAD')
        role_col = col_map.get('role', 'ROLE')
        project_col = col_map.get('project', 'PROJECT')
        queue_col = col_map.get('queue', 'QUEUE')
        feedback_col = col_map.get('feedback', 'FEEDBACK')
        comment_col = col_map.get('comment', 'COMMENT')

        filtered_qa = qa_df.copy()

        # Filtering logic for QA
        if len(selected_weeks) > 0 and week_col in filtered_qa.columns:
            target_week_nums = [int(''.join(filter(str.isdigit, str(w)))) for w in selected_weeks if ''.join(filter(str.isdigit, str(w)))]
            if target_week_nums:
                raw_numeric_weeks = pd.to_numeric(filtered_qa[week_col], errors='coerce')
                filtered_qa = filtered_qa[raw_numeric_weeks.isin(target_week_nums)]

        if selected_account != "All Accounts":
            acc_str = str(selected_account).strip().upper()
            search_terms = [acc_str]
            if "TDS" in acc_str:
                search_terms.extend(["TDS", "SAN DIEGO", "ORANGE COUNTY", "HYBRID"])
            pattern = "|".join(search_terms)
            
            q_match = filtered_qa[queue_col].astype(str).str.upper().str.contains(pattern, na=False) if queue_col in filtered_qa.columns else pd.Series(False, index=filtered_qa.index)
            p_match = filtered_qa[project_col].astype(str).str.upper().str.contains(pattern, na=False) if project_col in filtered_qa.columns else pd.Series(False, index=filtered_qa.index)
            
            combined_match = q_match | p_match
            if combined_match.any():
                filtered_qa = filtered_qa[combined_match]

        if len(selected_roles) > 0 and role_col in filtered_qa.columns:
            role_keywords = []
            for r in selected_roles:
                r_str = str(r).lower()
                if "reservation" in r_str: role_keywords.append("reservationist")
                elif "csa" in r_str: role_keywords.append("csa")
                elif "hybrid" in r_str: role_keywords.append("hybrid")
                elif "leader" in r_str or "lead" in r_str: role_keywords.append("team leader")

            if role_keywords:
                pattern = "|".join(role_keywords)
                filtered_qa = filtered_qa[filtered_qa[role_col].astype(str).str.strip().str.lower().str.contains(pattern, na=False)]

        # QA Sub-tabs
        qa_tab1, qa_tab2, qa_tab3 = st.tabs([
            "📌 Weekly Areas of Opportunity", 
            "📊 TL Virtual Monitoring Pivot", 
            "📋 Master QA Dataset"
        ])

        with qa_tab1:
            st.markdown("### 💡 Major Areas of Opportunity Summary")
            target_opp_col = feedback_col if feedback_col in filtered_qa.columns else comment_col
            if target_opp_col in filtered_qa.columns and week_col in filtered_qa.columns:
                opp_df = filtered_qa[[week_col, target_opp_col]].dropna(subset=[target_opp_col]).copy()
                opp_df[target_opp_col] = opp_df[target_opp_col].astype(str).str.strip()
                opp_df = opp_df[opp_df[target_opp_col] != ""]
                positive_keywords = ["good interaction", "positive and effective", "great job", "no areas for improvement"]
                opp_only_df = opp_df[~opp_df[target_opp_col].str.lower().str.contains("|".join(positive_keywords))]

                if not opp_only_df.empty:
                    def categorize_opportunity(text):
                        t = text.lower()
                        if "script order" in t or "sequence" in t: return "Script Order & Sequence Adherence"
                        elif "greeting" in t or "opening" in t: return "Mandatory Greeting / Script Opening"
                        elif "closing" in t or "call exit" in t: return "Mandatory Closing Script"
                        elif "identity" in t or "verification" in t: return "Customer Identity Verification"
                        else: return "General Script & Policy Adherence"

                    opp_only_df['Category'] = opp_only_df[target_opp_col].apply(categorize_opportunity)
                    st.info(f"🎯 **Top Area of Opportunity:** {opp_only_df['Category'].value_counts().idxmax()}")

                    cat_summary = opp_only_df.groupby([week_col, 'Category']).size().reset_index(name="Frequency Count")
                    st.dataframe(cat_summary, use_container_width=True, hide_index=True, height=300)
                    st.divider()
                    st.dataframe(opp_only_df[[week_col, target_opp_col]], use_container_width=True, hide_index=True, height=400)
                else:
                    st.warning("No improvement areas found.")

        with qa_tab2:
            st.markdown("### 🔍 TL Virtual Monitored Sessions Pivot")
            if lead_col in filtered_qa.columns and week_col in filtered_qa.columns:
                m1, m2, m3 = st.columns(3)
                m1.metric("🎧 Total Monitored Sessions", f"{len(filtered_qa):,}")
                m2.metric("👥 Active Team Leads", filtered_qa[lead_col].nunique())
                m3.metric("📅 Weeks Covered", filtered_qa[week_col].nunique())
                st.divider()
                tl_week_matrix = pd.crosstab(index=filtered_qa[lead_col], columns=filtered_qa[week_col], margins=True, margins_name="Total Monitored")
                st.dataframe(tl_week_matrix, use_container_width=True, height=350)

        with qa_tab3:
            st.markdown("### 📋 Full Raw QA Record Log")
            st.dataframe(filtered_qa, use_container_width=True, hide_index=True, height=550)
