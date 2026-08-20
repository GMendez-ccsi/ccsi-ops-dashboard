def find_column_by_keywords(df, keywords):
    """Scans the first few rows to find the column index matching header keywords."""
    for col in df.columns:
        # Check first 5 rows for matching keywords
        col_series = df[col].dropna().astype(str).str.lower().str.strip()
        for kw in keywords:
            if col_series.head(5).str.contains(kw).any():
                return col
    return None

@st.cache_data(ttl=1800)
def parse_sheet_smart(sheet_id, gid, account_name):
    df = fetch_raw_csv(sheet_id, gid)
    
    # 1. Locate header row dynamically
    header_idx = None
    for i in range(min(10, len(df))):
        row_str = df.iloc[i].astype(str).str.lower().tolist()
        if any("agent" in cell or "site" in cell for cell in row_str):
            header_idx = i
            break

    if header_idx is not None:
        # Re-parse dataframe setting the detected header row
        headers = df.iloc[header_idx].astype(str).str.strip().str.lower()
        df_data = df.iloc[header_idx + 1:].copy()
        df_data.columns = headers
    else:
        df_data = df.copy()

    df_clean = pd.DataFrame()

    # 2. Dynamic column assignment by exact / fuzzy match
    def get_col_data(possible_names, default_val=None):
        for name in possible_names:
            matches = [c for c in df_data.columns if name in str(c).lower()]
            if matches:
                return df_data[matches[0]].astype(str).str.strip()
        return default_val

    df_clean["site"] = get_col_data(["site", "location", "sit"], "MX")
    df_clean["role"] = get_col_data(["role", "position", "title"], "Agent")
    df_clean["week"] = get_col_data(["week", "wk"], "Week 1")
    df_clean["Date"] = get_col_data(["date", "day"], None)
    df_clean["Agent Name"] = get_col_data(["agent name", "agent", "employee", "name"], None)
    
    # Time Columns
    df_clean["Total Break"] = get_col_data(["total break", "break time", "break"], "0:00")
    df_clean["Total Meal"] = get_col_data(["total meal", "meal time", "meal", "lunch"], "0:00")
    df_clean["Unaccounted"] = get_col_data(["unaccounted", "lost time"], "0:00")
    df_clean["Direct_Adherence"] = get_col_data(["adherence", "direct adherence", "status adherence"], None)

    # 3. Filter out bad noise/headers
    bad_sites = ["site", "sit", "location", "nan", "none", ""]
    bad_agents = ["agent name", "agent", "name", "employee", "nan", "none", ""]

    df_clean = df_clean[~df_clean["site"].str.lower().isin(bad_sites)]
    df_clean = df_clean[~df_clean["Agent Name"].str.lower().isin(bad_agents)]
    
    df_clean["Account"] = account_name
    return df_clean.dropna(subset=["Agent Name"]).reset_index(drop=True)

@st.cache_data(ttl=1800)
def load_all_combined_data_v3():
    frames = []
    
    try:
        tds_df = parse_sheet_smart("18WdoYyycy71LWCEUesOq6-uLWqtAo52jD4p12ObGi3k", "1537474403", "TDS")
        frames.append(tds_df)
    except Exception as e:
        st.error(f"Error fetching data for TDS: {e}")

    try:
        td_df = parse_sheet_smart("1bp9_e-ML_TVCxkvjsr893nhcJmyw1WILWAsgwdAcjUc", "676189719", "TransDev SD & OC")
        frames.append(td_df)
    except Exception as e:
        st.error(f"Error fetching data for TransDev SD & OC: {e}")

    if not frames:
        return pd.DataFrame()
        
    combined_df = pd.concat(frames, axis=0, ignore_index=True)
    
    if "Date" in combined_df.columns:
        combined_df["Parsed_Date"] = pd.to_datetime(combined_df["Date"], errors="coerce")
        combined_df["month"] = combined_df["Parsed_Date"].dt.strftime("%B %Y")
        combined_df["month"] = combined_df["month"].fillna("August 2026")
    else:
        combined_df["month"] = "August 2026"

    time_cols = ["Total Break", "Total Meal", "Unaccounted"]
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
