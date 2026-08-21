# Filters UI
st.subheader("🔍 Filters & Drilldown")
f0, f1, f2, f3, f4 = st.columns(5)

with f0:
    sites = ["All Sites", "CDMX", "Tijuana"]
    selected_site = st.selectbox("Site:", sites, index=0)

# Pre-filter raw sources by Site
site_filtered_raw = df_raw.copy()
site_filtered_att = attendance_raw_df.copy()

if selected_site != "All Sites":
    if "site" in site_filtered_raw.columns:
        site_filtered_raw = site_filtered_raw[site_filtered_raw["site"].astype(str).str.strip().str.lower() == selected_site.lower()]
    if "site" in site_filtered_att.columns:
        site_filtered_att = site_filtered_att[site_filtered_att["site"].astype(str).str.strip().str.lower() == selected_site.lower()]

with f1:
    accounts = ["All Accounts"]
    all_acc = set()
    if "Account" in site_filtered_att.columns: all_acc.update(site_filtered_att["Account"].dropna().unique())
    if "Account" in site_filtered_raw.columns: all_acc.update(site_filtered_raw["Account"].dropna().unique())
    accounts += sorted([a for a in all_acc if a and str(a).lower() != "nan"])
    selected_account = st.selectbox("Account / Source:", accounts, index=0)

with f2:
    months = ["All Months"]
    all_months = set()
    if "month" in site_filtered_att.columns: all_months.update(site_filtered_att["month"].dropna().unique())
    if "month" in site_filtered_raw.columns: all_months.update(site_filtered_raw["month"].dropna().unique())
    clean_months = sorted([m for m in all_months if m and str(m).lower() != "nan"])
    months += clean_months
    aug_idx = months.index("August 2026") if "August 2026" in months else 0
    selected_month = st.selectbox("Month:", months, index=aug_idx)

with f3:
    all_weeks = set()
    if "week" in site_filtered_att.columns: all_weeks.update(site_filtered_att["week"].dropna().unique())
    if "week" in site_filtered_raw.columns: all_weeks.update(site_filtered_raw["week"].dropna().unique())
    available_weeks = sorted(
        [w for w in all_weeks if w and str(w).lower() != "nan"], 
        key=lambda x: int(re.search(r'\d+', str(x)).group()) if re.search(r'\d+', str(x)) else 0
    )
    selected_weeks = st.multiselect("Work Week (Multi-Select Allowed):", options=available_weeks, default=[])

with f4:
    # 1. Dynamically extract valid site-bound roles
    all_roles = set()
    if "role" in site_filtered_raw.columns:
        all_roles.update(site_filtered_raw["role"].dropna().astype(str).str.strip().unique())
    if "role" in site_filtered_att.columns:
        all_roles.update(site_filtered_att["role"].dropna().astype(str).str.strip().unique())
    
    roles_available = sorted([r for r in all_roles if r and r.lower() not in ["nan", "none", "role", "position", "unknown role"]])
    
    # Pre-select all available roles for the site by default so no un-selected leakage occurs
    selected_roles = st.multiselect("Role (Position):", options=roles_available, default=roles_available)


# 2. Hard filter enforcing site and role alignment
def apply_common_filters(df, strict_month=True):
    if df.empty:
        return df
    dff = df.copy()
    
    if selected_site != "All Sites" and "site" in dff.columns:
        dff = dff[dff["site"].astype(str).str.strip().str.lower() == selected_site.lower()]

    if selected_account != "All Accounts" and "Account" in dff.columns:
        dff = dff[dff["Account"].astype(str).str.strip().str.lower() == selected_account.strip().lower()]

    if strict_month and selected_month != "All Months" and "month" in dff.columns:
        target_month = selected_month.strip().lower()
        dff = dff[dff["month"].astype(str).str.strip().str.lower() == target_month]

        if "parsed_date" in dff.columns:
            sel_dt = pd.to_datetime(selected_month, errors="coerce")
            if pd.notna(sel_dt):
                dff = dff[
                    (dff["parsed_date"].dt.year == sel_dt.year) & 
                    (dff["parsed_date"].dt.month == sel_dt.month)
                ]

    if selected_weeks and "week" in dff.columns:
        selected_weeks_lower = [w.lower().strip() for w in selected_weeks]
        dff = dff[dff["week"].astype(str).str.strip().str.lower().isin(selected_weeks_lower)]

    # Filter by selected roles or restrict to site roles if dropdown is cleared
    if "role" in dff.columns:
        active_roles = selected_roles if selected_roles else roles_available
        active_roles_lower = [r.lower().strip() for r in active_roles]
        dff = dff[dff["role"].astype(str).str.strip().str.lower().isin(active_roles_lower)]
        
    return dff


def apply_pivot_filters(df):
    if df.empty:
        return df
    dff = df.copy()
    if selected_site != "All Sites" and "site" in dff.columns:
        dff = dff[dff["site"].astype(str).str.strip().str.lower() == selected_site.lower()]
    if "role" in dff.columns:
        active_roles = selected_roles if selected_roles else roles_available
        active_roles_lower = [r.lower().strip() for r in active_roles]
        dff = dff[dff["role"].astype(str).str.strip().str.lower().isin(active_roles_lower)]
    return dff
