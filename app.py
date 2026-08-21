# Updated Attendance Sheet Parser
@st.cache_data(ttl=1800)
def parse_attendance_sheet(sheet_id, gid):
    df_raw = fetch_raw_csv(sheet_id, gid)
    if df_raw.empty:
        return pd.DataFrame()
    
    header_idx = None
    for i in range(min(20, len(df_raw))):
        row_cells = [str(x).strip().lower() for x in df_raw.iloc[i].fillna("").tolist()]
        if any(k in row_cells for k in ["agent", "name", "employee", "site", "account", "status", "role"]):
            header_idx = i
            break

    if header_idx is not None:
        headers = [str(c).strip() for c in df_raw.iloc[header_idx].tolist()]
        df_data = df_raw.iloc[header_idx + 1:].copy()
        df_data.columns = headers
    else:
        df_data = df_raw.copy()

    df_data = df_data.loc[:, ~df_data.columns.duplicated()].copy().dropna(how="all")

    col_map = {}
    for c in df_data.columns:
        clow = str(c).lower()
        if "site" in clow or "loc" in clow: col_map[c] = "site"
        elif "week" in clow: col_map[c] = "week"
        elif "account" in clow: col_map[c] = "Account"
        elif "month" in clow: col_map[c] = "month"
        elif any(k in clow for k in ["role", "position", "job title"]): col_map[c] = "role"
        elif any(k in clow for k in ["agent", "employee", "name"]) and "role" not in clow: col_map[c] = "Agent Name"
        elif "total late" in clow or "lateness" in clow or "late min" in clow: col_map[c] = "Total Late Time"
    
    df_data = df_data.rename(columns=col_map)

    if "site" in df_data.columns:
        df_data["site"] = df_data["site"].apply(normalize_site)
    else:
        df_data["site"] = "Tijuana"

    df_data["week"] = df_data["week"].apply(clean_week_str) if "week" in df_data.columns else "Week 1"
    if "month" not in df_data.columns: df_data["month"] = "August 2026"
    if "Account" not in df_data.columns: df_data["Account"] = "TDS"
    if "role" not in df_data.columns: df_data["role"] = "CSA"

    # Convert HH:MM:SS or string minutes to numeric minutes
    if "Total Late Time" in df_data.columns:
        df_data["Late_Mins_Numeric"] = df_data["Total Late Time"].astype(str).apply(time_to_minutes)
    else:
        df_data["Late_Mins_Numeric"] = 0.0

    # Derive Late Instances from numeric minutes (> 0 mins = 1 instance)
    df_data["Total Late Instances"] = (df_data["Late_Mins_Numeric"] > 0).astype(int)

    return df_data.reset_index(drop=True)

# TAB 1: ATTENDANCE
with tab_attendance:
    a_col1, a_col2 = st.columns([3, 1])
    with a_col1:
        st.subheader("📅 Attendance Tracker Data")
    with a_col2:
        st.markdown("[🔗 Open Attendance Sheet](https://docs.google.com/spreadsheets/d/1PUerkTX4iCaFUP27FXV34azza6L5LpFYsb1nHVKrH-c/edit#gid=253246412)")
    
    if not filtered_attendance_df.empty:
        m1, m2, m3, m4, m5 = st.columns(5)
        
        # Calculate total instances and total time accurately
        late_instances = int(filtered_attendance_df.get('Total Late Instances', pd.Series([0])).sum())
        total_late_mins = float(filtered_attendance_df.get('Late_Mins_Numeric', pd.Series([0])).sum())
        
        late_hours = int(total_late_mins // 60)
        remaining_mins = int(total_late_mins % 60)
        late_time_str = f"{late_hours}h {remaining_mins}m" if late_hours > 0 else f"{int(total_late_mins)} Mins"

        m1.metric("👥 Active Roster Headcount", f"{len(filtered_attendance_df)}")
        m2.metric("⚠️ Unjustified Absences", f"{int(pd.to_numeric(filtered_attendance_df.get('Unjustified Absences', 0), errors='coerce').fillna(0).sum())}")
        m3.metric("📋 Justified Absences", f"{int(pd.to_numeric(filtered_attendance_df.get('Justified Absences', 0), errors='coerce').fillna(0).sum())}")
        m4.metric("⏱️ Total Late Instances", f"{late_instances}")
        m5.metric("⏳ Total Lateness Time", late_time_str)

        st.divider()

        st.write("### 📊 Agent Absence & Lateness Duration Breakdown")
        chart_cols = [c for c in ["Unjustified Absences", "Justified Absences", "Total Late Instances", "Late_Mins_Numeric"] if c in filtered_attendance_df.columns]
        if chart_cols and "Agent Name" in filtered_attendance_df.columns:
            plot_df = filtered_attendance_df.set_index("Agent Name")[chart_cols].apply(pd.to_numeric, errors="coerce").fillna(0)
            plot_df = plot_df.rename(columns={"Late_Mins_Numeric": "Late Duration (Mins)"})
            st.bar_chart(plot_df)

        st.divider()
        st.write("### 📋 Attendance Log")
        st.dataframe(filtered_attendance_df, use_container_width=True, hide_index=True)
    else:
        st.info("No attendance data found for the selected filter combination.")
