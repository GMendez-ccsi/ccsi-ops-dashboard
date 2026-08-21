import base64
import os
import re
import pandas as pd
import streamlit as st

# -------------------------------------------------------------
# PAGE CONFIGURATION
# -------------------------------------------------------------
st.set_page_config(
    page_title="Master Operations Command Dashboard",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -------------------------------------------------------------
# HELPER FUNCTIONS
# -------------------------------------------------------------
def get_image_base64(path: str) -> str:
    """Reads a local image file and converts it into a base64 string."""
    if os.path.exists(path):
        with open(path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode()
    return ""

# -------------------------------------------------------------
# BACKGROUND & THEMING (CUSTOM CSS)
# -------------------------------------------------------------
bg_wallpaper_path = "2. 2024 acsi wallpaper .jpg"
bg_b64 = get_image_base64(bg_wallpaper_path)

if bg_b64:
    st.markdown(
        f"""
        <style>
        /* Base page styling */
        .stApp {{
            background-color: #f8fafc;
        }}
        
        /* Subtle background overlay using ACSI wallpaper */
        .stApp::before {{
            content: "";
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            background-image: url("data:image/jpeg;base64,{bg_b64}");
            background-size: cover;
            background-position: center;
            background-repeat: no-repeat;
            opacity: 0.12; /* Low opacity watermark effect for readability */
            z-index: -1;
            pointer-events: none;
        }}

        /* Header styling */
        .header-title {{
            font-size: 26px;
            font-weight: 700;
            color: #1e293b;
            text-align: center;
        }}

        /* Card background polish for metrics and containers */
        div[data-testid="stMetric"] {{
            background-color: rgba(255, 255, 255, 0.85);
            border-radius: 8px;
            padding: 12px;
            box-shadow: 0px 2px 6px rgba(0,0,0,0.05);
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

# -------------------------------------------------------------
# HEADER WITH LOGOS
# -------------------------------------------------------------
acsi_b64 = get_image_base64("acsi_logo.png")
ccsi_b64 = get_image_base64("ccsi_logo.png")

col_acsi, col_title, col_ccsi = st.columns([1, 4, 1])

with col_acsi:
    if acsi_b64:
        st.markdown(f'<img src="data:image/png;base64,{acsi_b64}" width="110">', unsafe_allow_html=True)

with col_title:
    st.markdown('<div class="header-title">⚡ Master Operations Command Dashboard</div>', unsafe_allow_html=True)
    st.caption("<div style='text-align: center;'>Combined Operations: TDS & TransDev SD/OC | Target: ≥88% Status Adherence</div>", unsafe_allow_html=True)

with col_ccsi:
    if ccsi_b64:
        st.markdown(f'<img src="data:image/png;base64,{ccsi_b64}" width="110">', unsafe_allow_html=True)

st.divider()

# -------------------------------------------------------------
# SIDEBAR / GLOBAL FILTERS (MOCK / SETUP)
# -------------------------------------------------------------
with st.sidebar:
    st.header("🎛️ Dashboard Filters")
    selected_account = st.selectbox("Select Account", ["All Accounts", "TDS", "TransDev SD", "TransDev OC"])
    selected_weeks = st.multiselect("Select Work Week(s)", ["Week 31", "Week 32", "Week 33", "Week 34"], default=[])
    selected_roles = st.multiselect("Select Role(s)", ["CSA", "Reservationist", "Hybrid", "Team Leader"], default=[])

# Create top-level main tabs
tab1, tab2, tab3, tab4, tab5, tab_qa = st.tabs([
    "Tab 1", "Tab 2", "Tab 3", "Tab 4", "Tab 5", "🛡️ Quality Assurance"
])

# Standard Placeholder Tabs
with tab1:
    st.info("Tab 1 Content")
with tab2:
    st.info("Tab 2 Content")
with tab3:
    st.info("Tab 3 Content")
with tab4:
    st.info("Tab 4 Content")
with tab5:
    st.info("Tab 5 Content")

# -------------------------------------------------------------
# TAB 6: QUALITY ASSURANCE
# -------------------------------------------------------------
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
            st.error(f"Error loading MONITORING sheet tab: {e}")
            return pd.DataFrame()

    qa_df = load_qa_raw_monitoring()

    if qa_df is not None and not qa_df.empty:
        col_map = {c.lower(): c for c in qa_df.columns}
        
        week_col = col_map.get('week', 'week')
        date_col = col_map.get('date', 'DATE')
        lead_col = col_map.get('lead', 'LEAD')
        role_col = col_map.get('role', 'ROLE')
        project_col = col_map.get('project', 'PROJECT')
        queue_col = col_map.get('queue', 'QUEUE')
        feedback_col = col_map.get('feedback', 'FEEDBACK')
        comment_col = col_map.get('comment', 'COMMENT')

        filtered_qa = qa_df.copy()

        # -------------------------------------------------------------
        # GLOBAL FILTERS (UNRESTRICTED ALL-WEEK VIEW)
        # -------------------------------------------------------------

        # 1. Site Filter: Bypassed (All rows belong to MX/CDMX)

        # 2. Month Filter: Bypassed to prevent dropping historical weeks (e.g. July dates for Week 31-33)

        # 3. Work Week Filter: Matches raw integer weeks in Column A
        if 'selected_weeks' in locals() and len(selected_weeks) > 0:
            if week_col in filtered_qa.columns:
                target_week_nums = []
                for w in selected_weeks:
                    digits = ''.join(filter(str.isdigit, str(w)))
                    if digits:
                        target_week_nums.append(int(digits))
                
                if target_week_nums:
                    raw_numeric_weeks = pd.to_numeric(filtered_qa[week_col], errors='coerce')
                    filtered_qa = filtered_qa[raw_numeric_weeks.isin(target_week_nums)]

        # 4. Account / Queue Filter: Matches PROJECT (Col I) or QUEUE (Col L)
        if 'selected_account' in locals() and selected_account and selected_account != "All Accounts":
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

        # 5. Role Filter: Matches Column J (ROLE)
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
