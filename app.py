# 3. Dedicated Parser: TDS (Hardcoded Index 19 for Column T Adherence)
@st.cache_data(ttl=1800)
def parse_tds_sheet(sheet_id, gid):
    df_raw = fetch_raw_csv(sheet_id, gid)
    
    header_idx = None
    for i in range(min(20, len(df_raw))):
        row_cells = [str(x).strip().lower() for x in df_raw.iloc[i].fillna("").tolist()]
        if any(term in cell for cell in row_cells for term in ["agent", "employee", "name", "site", "position"]):
            header_idx = i
            break

    if header_idx is not None:
        headers = [str(c).strip().lower() for c in df_raw.iloc[header_idx].values]
        df_data = df_raw.iloc[header_idx + 1:].copy()
        df_data.columns = headers
    else:
        df_data = df_raw.copy()

    df_clean = pd.DataFrame()

    def extract_by_names(names, default="Unknown"):
        cols = [str(c).strip().lower() for c in df_data.columns]
        for name in names:
            for idx, c in enumerate(cols):
                if name in c:
                    return df_data.iloc[:, idx].astype(str).str.strip()
        return pd.Series([default] * len(df_data), index=df_data.index)

    df_clean["site"] = extract_by_names(["site", "loc"], "MX")
    df_clean["role"] = extract_by_names(["position", "role", "title"], "Csa")
    raw_week = extract_by_names(["period", "week", "work week", "wk"], "Week 1")
    df_clean["week"] = raw_week.apply(clean_week_str)
    df_clean["Date"] = extract_by_names(["date", "day"], "2026-08-01")
    df_clean["Agent Name"] = extract_by_names(["name", "agent name", "agent", "employee"], "Unknown")
    df_clean["Total Break"] = extract_by_names(["total break", "breaks"], "0:00")
    df_clean["Total Meal"] = extract_by_names(["total meal", "meal"], "0:00")
    
    df_clean["Exceeded_Break_Raw"] = extract_by_names(["exceeded break", "total un", "break overage", "overage"], "0:00")
    df_clean["Unaccounted"] = extract_by_names(["unaccounted", "unaccou", "lost time"], "0:00")
    
    # STRICT DIRECT INDEX: Force Column T (Index 19) for TDS Adherence %
    if df_data.shape[1] > 19:
        df_clean["Direct_Adherence"] = df_data.iloc[:, 19].astype(str).str.strip()
    else:
        df_clean["Direct_Adherence"] = None

    invalid_mask = (
        df_clean["Agent Name"].isna() |
        df_clean["Agent Name"].str.lower().isin(["none", "nan", "", "agent name", "agent", "employee", "name"])
    )
    df_clean = df_clean[~invalid_mask].copy()
    df_clean["Account"] = "TDS"
    return df_clean.reset_index(drop=True)
