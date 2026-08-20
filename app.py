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
        # Direct Positional Mapping for TransDev
        df_clean["site"] = df[0] if 0 in df.columns else None
        df_clean["role"] = df[1] if 1 in df.columns else None
        df_clean["week"] = df[3] if 3 in df.columns else None
        df_clean["Date"] = df[4] if 4 in df.columns else None
        df_clean["Agent Name"] = df[5] if 5 in df.columns else None
        df_clean["Total Break"] = df[9] if 9 in df.columns else "0:00"
        df_clean["Total Meal"] = df[10] if 10 in df.columns else "0:00"
        df_clean["Unaccounted"] = df[15] if 15 in df.columns else "0:00"
        df_clean["Direct_Adherence"] = df[17] if 17 in df.columns else None
    else:
        # Direct Positional Mapping for TDS
        df_clean["site"] = df[0] if 0 in df.columns else None
        df_clean["role"] = df[1] if 1 in df.columns else None
        df_clean["week"] = df[3] if 3 in df.columns else None
        df_clean["Date"] = df[4] if 4 in df.columns else None
        df_clean["Agent Name"] = df[5] if 5 in df.columns else None
        df_clean["Total Break"] = df[9] if 9 in df.columns else "0:00"
        df_clean["Total Meal"] = df[10] if 10 in df.columns else "0:00"
        df_clean["Unaccounted"] = df[15] if 15 in df.columns else "0:00"
        df_clean["Direct_Adherence"] = df[17] if 17 in df.columns else None

    # Filter header row noise safely without type errors
    if "site" in df_clean.columns and "Agent Name" in df_clean.columns:
        site_mask = df_clean["site"].fillna("").astype(str).str.strip().str.upper().isin(["SITE", "SIT", "A", ""])
        agent_mask = df_clean["Agent Name"].fillna("").astype(str).str.strip().str.lower().isin(["name", "agent name", ""])
        df_clean = df_clean[~site_mask & ~agent_mask]

    # Fill defaults for required fields
    df_clean["site"] = df_clean["site"].fillna("MX").astype(str).str.strip()
    df_clean["role"] = df_clean["role"].fillna("Agent").astype(str).str.strip()
    df_clean["Account"] = account_name
    
    return df_clean.reset_index(drop=True)
