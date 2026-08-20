@st.cache_data(ttl=1800)
def fetch_single_sheet(account_name, sheet_id, gid):
    gviz_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&gid={gid}"
    req = urllib.request.Request(
        gviz_url, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    )
    with urllib.request.urlopen(req) as response:
        content = response.read()
        
    df = pd.read_csv(io.BytesIO(content), engine="python", header=None, on_bad_lines="skip").dropna(how="all")

    df_clean = pd.DataFrame()

    if account_name == "TransDev SD & OC":
        # Positional index mapping for TransDev
        # Col 0: SITE (A), Col 1: POSITION (B), Col 3: PERIOD (D), Col 4: DATE (E), Col 5: name (F)
        # Col 9: Breaks (J), Col 10: meal (K), Col 15: total Un / unapproved (P), Col 17: status adherence (R)
        df_clean["site"] = df[0]
        df_clean["role"] = df[1]
        df_clean["week"] = df[3]
        df_clean["Date"] = df[4]
        df_clean["Agent Name"] = df[5]
        df_clean["Total Break"] = df[9] if 9 in df.columns else "0:00"
        df_clean["Total Meal"] = df[10] if 10 in df.columns else "0:00"
        df_clean["Unaccounted"] = df[15] if 15 in df.columns else "0:00"
        df_clean["Direct_Adherence"] = df[17] if 17 in df.columns else None

        df_clean = df_clean[~df_clean["site"].astype(str).str.upper().isin(["SITE", "SIT", "A"])]
        df_clean = df_clean[df_clean["Agent Name"].notna() & (df_clean["Agent Name"].astype(str).str.strip() != "name")]
    else:
        # Core/TDS positional mapping with safe string conversion
        header_row = [str(x).strip() for x in df.iloc[0].tolist()]
        df_body = df.iloc[1:].copy()
        
        # Standardize column header list
        col_map = {}
        for idx, col_name in enumerate(header_row):
            c_upper = col_name.upper()
            if "SITE" in c_upper or c_upper == "SIT":
                col_map["site"] = idx
            elif "POSITION" in c_upper or "ROLE" in c_upper:
                col_map["role"] = idx
            elif "PERIOD" in c_upper or "WEEK" in c_upper:
                col_map["week"] = idx
            elif "DATE" in c_upper:
                col_map["Date"] = idx
            elif "NAME" in c_upper or "AGENT" in c_upper:
                col_map["Agent Name"] = idx
            elif "BREAK" in c_upper:
                col_map["Total Break"] = idx
            elif "MEAL" in c_upper:
                col_map["Total Meal"] = idx
            elif "UNACCOU" in c_upper or "UNAPPROVED" in c_upper:
                col_map["Unaccounted"] = idx
            elif "ADHERENCE" in c_upper:
                col_map["Direct_Adherence"] = idx

        for target_col, src_idx in col_map.items():
            df_clean[target_col] = df_body[src_idx]

    # Ensure required columns exist
    for required_col in ["site", "role", "week", "Date", "Agent Name", "Total Break", "Total Meal", "Unaccounted", "Direct_Adherence"]:
        if required_col not in df_clean.columns:
            df_clean[required_col] = None

    df_clean["site"] = df_clean["site"].fillna("MX").astype(str).str.strip()
    df_clean["role"] = df_clean["role"].fillna("Agent").astype(str).str.strip()
    df_clean["Account"] = account_name
    
    return df_clean.reset_index(drop=True)
