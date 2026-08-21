import base64
import io
import re
import urllib.request
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots
from streamlit_autorefresh import st_autorefresh

# -------------------------------------------------------------
# 1. PAGE CONFIGURATION & AUTO-REFRESH
# -------------------------------------------------------------
st.set_page_config(
    page_title="ACSI & CCSI Operations Command Dashboard",
    page_icon="⚡",
    layout="wide",
)
st_autorefresh(interval=1800000, key="combined_refresh")


def get_image_base64(file_path):
    try:
        with open(file_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode()
    except Exception:
        return None


ccsi_b64 = get_image_base64("ccsi_logo.png")
acsi_b64 = get_image_base64("acsi_logo.png")

st.markdown(
    """
    <style>
    div[data-testid="stLinkButton"]>a {
        background-color: #007AC1 !important;
        color: white !important;
        border-radius: 6px;
        border: none;
        font-weight: bold;
    }
    .header-title {
        border-left: 6px solid #007AC1;
        padding-left: 12px;
        font-size: 2rem;
        font-weight: bold;
        color: #111111;
        line-height: 1.2;
    }
    </style>
""",
    unsafe_allow_html=True,
)

col_acsi, col_title, col_ccsi = st.columns([1.2, 5, 1.2])

with col_acsi:
    if acsi_b64:
        st.markdown(
            f'<img src="data:image/png;base64,{acsi_b64}" width="140">',
            unsafe_allow_html=True,
        )
    else:
        st.markdown("### **ACSI**")

with col_title:
    st.markdown(
        '<div class="header-title">⚡ Master Operations Command Dashboard</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Combined Operations: TDS & TransDev SD/OC | Target: ≥88% Status"
        " Adherence"
    )

with col_ccsi:
    if ccsi_b64:
        st.markdown(
            f'<img src="data:image/png;base64,{ccsi_b64}" width="140">',
            unsafe_allow_html=True,
        )
    else:
        st.markdown("### **CCSi**")

st.divider()


# -------------------------------------------------------------
# 2. CORE DATA HELPERS & DATA PARSING
# -------------------------------------------------------------
def normalize_site(val):
    if pd.isna(val) or not str(val).strip():
        return "Unknown"
    s = str(val).strip().upper()
    if s in ["TJ", "TIJUANA", "TIJ"] or "TJ" in s or "TIJUANA" in s:
        return "Tijuana"
    if s in ["MX", "CDMX", "MEXICO"] or "MX" in s or "CDMX" in s:
        return "CDMX"
    return str(val).strip().title()


def parse_adherence_val(val):
    if pd.isna(val):
        return None
    if isinstance(val, (int, float)):
        return float(val) * 100.0 if float(val) <= 1.0 else float(val)
    if isinstance(val, str):
        val_str = val.replace("%", "").strip()
        try:
            parsed = float(val_str)
            return (
                parsed * 100.0 if parsed <= 1.0 and "%" not in val else parsed
            )
        except ValueError:
            return None
    return None


def time_to_minutes(val):
    if pd.isna(val):
        return 0.0
    if isinstance(val, (int, float)):
        return float(val) * 1440.0
    val_str = str(val).strip()
    if not val_str or val_str.lower() in ["nan", "none", "0", "0:00", "00:00:00"]:
        return 0.0
    try:
        parts = val_str.split(":")
        if len(parts) == 3:
            return (
                float(parts[0]) * 60.0
                + float(parts[1])
                + float(parts[2]) / 60.0
            )
        elif len(parts) == 2:
            return float(parts[0]) * 60.0 + float(parts[1])
    except Exception:
        pass
    try:
        return float(val_str)
    except ValueError:
        return 0.0


def clean_week_str(val):
    if pd.isna(val) or not str(val).strip():
        return "Week 1"
    val_str = str(val).strip()
    w_match = re.search(r"[Ww](\d+)", val_str)
    if w_match:
        return f"Week {int(w_match.group(1))}"
    match = re.search(r"(\d+)", val_str)
    if match:
        num = int(match.group(1))
        return f"Week {num}" if num < 100 else "Week 1"
    return val_str


def fetch_raw_csv(sheet_id, gid):
    gviz_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&gid={gid}"
    req = urllib.request.Request(
        gviz_url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
    )
    with urllib.request.urlopen(req) as response:
        content = response.read()
    return pd.read_csv(
        io.BytesIO(content), engine="python", header=None, on_bad_lines="skip"
    ).dropna(how="all")


@st.cache_data(ttl=300)
def parse_generic_kpi_sheet(sheet_id, gid):
    df_raw = fetch_raw_csv(sheet_id, gid)
    if df_raw.empty:
        return pd.DataFrame()

    header_idx = 0
    keywords = [
        "kpi",
        "metric",
        "project",
        "week",
        "date",
        "target",
        "score",
        "agent",
        "qa",
    ]
    for i in range(min(15, len(df_raw))):
        row_cells = [
            str(x).strip().lower() for x in df_raw.iloc[i].fillna("").tolist()
        ]
        if any(any(k in x for k in keywords) for x in row_cells):
            header_idx = i
            break

    headers = [
        str(c).strip() if str(c).strip() != "nan" else f"Col_{j}"
        for j, c in enumerate(df_raw.iloc[header_idx].tolist())
    ]
    df_clean = df_raw.iloc[header_idx + 1 :].copy()
    df_clean.columns = headers
    return df_clean.dropna(how="all").reset_index(drop=True)


@st.cache_data(ttl=300)
def parse_pivot_attendance_sheet_raw(sheet_id, gid):
    df_raw = fetch_raw_csv(sheet_id, gid)
    if df_raw.empty:
        return pd.DataFrame()

    header_idx = None
    for i in range(min(15, len(df_raw))):
        row_cells = [
            str(x).strip().lower() for x in df_raw.iloc[i].fillna("").tolist()
        ]
        if any("agent" in x or "site" in x or "name" in x for x in row_cells):
            header_idx = i
            break

    if header_idx is not None:
        headers = [
            str(c).strip() if str(c).strip() != "nan" else f"Col_{j}"
            for j, c in enumerate(df_raw.iloc[header_idx].tolist())
        ]
        df_clean = df_raw.iloc[header_idx + 1 :].copy()
        df_clean.columns = headers
    else:
        df_clean = df_raw.copy()

    df_clean = df_clean.dropna(how="all")

    for c in df_clean.columns:
        clow = str(c).lower().strip()
        if "site" in clow or "location" in clow:
            df_clean = df_clean.rename(columns={c: "site"})
        elif any(k in clow for k in ["agent", "employee"]) and "name" in clow:
            df_clean = df_clean.rename(columns={c: "Agent Name"})
        elif any(k in clow for k in ["role", "position"]):
            df_clean = df_clean.rename(columns={c: "role"})

    if "Agent Name" in df_clean.columns:
        df_clean = df_clean[
            ~df_clean["Agent Name"]
            .astype(str)
            .str.lower()
            .str.contains("total|grand total|blank|nan", na=False)
        ]

    if "site" in df_clean.columns:
        df_clean["site"] = df_clean["site"].apply(normalize_site)

    if "role" in df_clean.columns:
        df_clean["role"] = df_clean["role"].astype(str).str.strip().str.upper()

    return df_clean.reset_index(drop=True)


@st.cache_data(ttl=300)
def parse_primary_attendance_sheet(sheet_id, gid):
    df_raw = fetch_raw_csv(sheet_id, gid)
    if df_raw.empty:
        return pd.DataFrame()

    header_idx = None
    for i in range(min(15, len(df_raw))):
        row_cells = [
            str(x).strip().lower() for x in df_raw.iloc[i].fillna("").tolist()
        ]
        if any("agent" in x or "name" in x or "site" in x for x in row_cells):
            header_idx = i
            break

    if header_idx is not None:
        headers = [str(c).strip() for c in df_raw.iloc[header_idx].tolist()]
        df_clean = df_raw.iloc[header_idx + 1 :].copy()
        df_clean.columns = headers
    else:
        df_clean = df_raw.copy()

    df_clean = df_clean.loc[:, ~df_clean.columns.duplicated()].dropna(
        how="all"
    )

    col_map = {}
    for c in df_clean.columns:
        clow = str(c).lower().strip()
        if "site" in clow or "location" in clow:
            col_map[c] = "site"
        elif "week" in clow:
            col_map[c] = "week"
        elif "account" in clow:
            col_map[c] = "Account"
        elif "month" in clow or "date" in clow:
            col_map[c] = "month"
        elif any(k in clow for k in ["role", "position", "title"]):
            col_map[c] = "role"
        elif any(k in clow for k in ["agent", "employee", "name"]):
            col_map[c] = "Agent Name"
        elif "unjustified" in clow:
            col_map[c] = "Unjustified Absences"
        elif "justified" in clow:
            col_map[c] = "Justified Absences"
        elif "late" in clow or "lateness" in clow:
            col_map[c] = "Total Late Time"

    df_clean = df_clean.rename(columns=col_map)

    if "Agent Name" in df_clean.columns:
        df_clean = df_clean[
            ~df_clean["Agent Name"]
            .astype(str)
            .str.lower()
            .str.contains("total|grand total|blank|nan", na=False)
        ]

    if "site" in df_clean.columns:
        df_clean["site"] = df_clean["site"].apply(normalize_site)
    else:
        df_clean["site"] = "CDMX"

    df_clean["week"] = (
        df_clean["week"].apply(clean_week_str)
        if "week" in df_clean.columns
        else "Week 1"
    )

    if "month" in df_clean.columns:
        df_clean["month_clean"] = df_clean["month"].astype(str).str.strip()
    else:
        df_clean["month_clean"] = "August 2026"

    if "Account" not in df_clean.columns:
        df_clean["Account"] = "TDS"
    if "role" not in df_clean.columns:
        df_clean["role"] = "CSA"
    else:
        df_clean["role"] = (
            df_clean["role"].astype(str).str.strip().str.upper()
        )

    if "Total Late Time" in df_clean.columns:
        df_clean["Late_Mins_Numeric"] = df_clean["Total Late Time"].apply(
            time_to_minutes
        )
    else:
        df_clean["Late_Mins_Numeric"] = 0.0

    df_clean["Total Late Instances"] = (
        df_clean["Late_Mins_Numeric"] > 0
    ).astype(int)

    return df_clean.reset_index(drop=True)


@st.cache_data(ttl=300)
def parse_sheet_by_structure(sheet_id, gid, default_account_label):
    df_raw = fetch_raw_csv(sheet_id, gid)
    if df_raw.empty:
        return pd.DataFrame()

    header_idx = None
    for i in range(min(25, len(df_raw))):
        row_cells = [
            str(x).strip().lower() for x in df_raw.iloc[i].fillna("").tolist()
        ]
        if any(
            k in row_cells
            for k in [
                "site",
                "position",
                "date",
                "name",
                "period",
                "agent name",
                "status adhere",
            ]
        ):
            header_idx = i
            break

    if header_idx is None:
        return pd.DataFrame()

    headers = [str(c).strip() for c in df_raw.iloc[header_idx].tolist()]
    df_data = df_raw.iloc[header_idx + 1 :].copy()
    df_data.columns = headers

    df_data = df_data.loc[:, ~df_data.columns.duplicated()].dropna(how="all")

    col_map = {}
    for c in df_data.columns:
        clow = str(c).lower().strip()
        if clow == "site":
            col_map[c] = "site"
        elif any(k in clow for k in ["position", "account", "campaign"]):
            col_map[c] = "Account_Source"
        elif any(k in clow for k in ["period", "week", "work week"]):
            col_map[c] = "week"
        elif "date" in clow:
            col_map[c] = "Date"
        elif any(k in clow for k in ["name", "agent"]):
            col_map[c] = "Agent Name"
        elif "breaks" in clow or "total break" in clow:
            col_map[c] = "Total Break"
        elif "meal" in clow or "total meal" in clow:
            col_map[c] = "Total Meal"
        elif "exceeded" in clow:
            col_map[c] = "Exceeded_Break_Raw"
        elif "unaccou" in clow or "unaccounted" in clow:
            col_map[c] = "Unaccounted"
        elif "status adhere" in clow or "adherence" in clow:
            col_map[c] = "Direct_Adherence"

    df_clean = df_data.rename(columns=col_map).copy()

    if "Account_Source" in df_clean.columns:
        df_clean["Account"] = df_clean["Account_Source"].astype(str).str.strip()
        df_clean["role"] = (
            df_clean["Account_Source"].astype(str).str.strip().str.upper()
        )
    else:
        df_clean["Account"] = default_account_label
        df_clean["role"] = "CSA"

    if "site" not in df_clean.columns:
        df_clean["site"] = "CDMX"
    else:
        df_clean["site"] = df_clean["site"].apply(normalize_site)

    if "week" not in df_clean.columns:
        df_clean["week"] = "Week 1"
    else:
        df_clean["week"] = df_clean["week"].apply(clean_week_str)

    if "Agent Name" not in df_clean.columns:
        df_clean["Agent Name"] = "Unknown"

    for field in [
        "Total Break",
        "Total Meal",
        "Exceeded_Break_Raw",
        "Unaccounted",
    ]:
        if field not in df_clean.columns:
            df_clean[field] = "0:00"

    if "Direct_Adherence" not in df_clean.columns:
        df_clean["Direct_Adherence"] = None

    invalid_mask = df_clean["Agent Name"].isna() | df_clean[
        "Agent Name"
    ].astype(str).str.lower().isin([
        "none",
        "nan",
        "",
        "agent name",
        "agent",
        "employee",
        "name",
        "site",
        "position",
    ])
    df_clean = df_clean[~invalid_mask].copy()

    return df_clean.reset_index(drop=True)


@st.cache_data(ttl=300)
def load_all_combined_data_v15():
    frames = []

    try:
        tds_df = parse_sheet_by_structure(
            "18WdoYyycy71LWCEUesOq6-uLWqtAo52jD4p12ObGi3k", "1537474403", "TDS"
        )
        if not tds_df.empty:
            frames.append(tds_df)
    except Exception as e:
        st.error(f"Error fetching data for TDS: {e}")

    try:
        td_df = parse_sheet_by_structure(
            "1bp9_e-ML_TVCxkvjsr893nhcJmyw1WILWAsgwdAcjUc",
            "676189719",
            "TransDev SD & OC",
        )
        if not td_df.empty:
            frames.append(td_df)
    except Exception as e:
        st.error(f"Error fetching data for TransDev SD & OC: {e}")

    if not frames:
        return pd.DataFrame()

    combined_df = pd.concat(frames, axis=0, ignore_index=True)

    combined_df["Account"] = (
        combined_df["Account"].fillna("Unknown").astype(str).str.strip()
    )
    combined_df = combined_df[
        ~combined_df["Account"].str.lower().isin(["nan", "none", "", "position"])
    ]

    if "Date" in combined_df.columns:
        parsed_dates = pd.to_datetime(
            combined_df["Date"], errors="coerce", format="mixed"
        )
        combined_df["parsed_date"] = parsed_dates
        combined_df["month_clean"] = (
            parsed_dates.dt.strftime("%B %Y").fillna("August 2026")
        )
    else:
        combined_df["month_clean"] = "August 2026"

    time_cols = [
        "Total Break",
        "Total Meal",
        "Unaccounted",
        "Exceeded_Break_Raw",
    ]
    for col in time_cols:
        if col in combined_df.columns:
            combined_df[f"{col}_Mins"] = combined_df[col].apply(
                time_to_minutes
            )
        else:
            combined_df[f"{col}_Mins"] = 0.0

    if "Direct_Adherence" in combined_df.columns:
        combined_df["Parsed_Adherence"] = combined_df[
            "Direct_Adherence"
        ].apply(parse_adherence_val)
    else:
        combined_df["Parsed_Adherence"] = None

    return combined_df


# Load Primary Datasets
attendance_raw_df = parse_primary_attendance_sheet(
    "1PUerkTX4iCaFUP27FXV34azza6L5LpFYsb1nHVKrH-c", "601856217"
)
pivot_attendance_df = parse_pivot_attendance_sheet_raw(
    "1kzXr88ueah-Gg0gVI4bhl1peFdWYgy0nIFRkZOl0RK0", "243149129"
)
df_raw = load_all_combined_data_v15()

# Load Operational KPI Sheets
cdmx_kpis_df = parse_generic_kpi_sheet(
    "1RW3LApb5TgMtdtBKqKHfZ3_t3sBQYCuUZqp8owA3ndM", "1978250855"
)
tj_kpis_df = parse_generic_kpi_sheet(
    "12uF_syUu7enzOjob7di6c2UlPa6-EUgcTUHG7UcIMgk", "517756888"
)
cdmx_weekly_trends_df = parse_generic_kpi_sheet(
    "1RW3LApb5TgMtdtBKqKHfZ3_t3sBQYCuUZqp8owA3ndM", "1684808847"
)

# -------------------------------------------------------------
# 3. GLOBAL FILTERS UI & DYNAMIC LOGIC
# -------------------------------------------------------------
st.subheader("🔍 Filters & Drilldown")
f0, f1, f2, f3, f4 = st.columns(5)

with f0:
    sites = ["All Sites", "CDMX", "Tijuana"]
    selected_site = st.selectbox("Site:", sites, index=1)

site_filtered_raw = df_raw.copy()
site_filtered_att = attendance_raw_df.copy()

if selected_site != "All Sites":
    if "site" in site_filtered_raw.columns:
        site_filtered_raw = site_filtered_raw[
            site_filtered_raw["site"].astype(str).str.strip().str.lower()
            == selected_site.lower()
        ]
    if "site" in site_filtered_att.columns:
        site_filtered_att = site_filtered_att[
            site_filtered_att["site"].astype(str).str.strip().str.lower()
            == selected_site.lower()
        ]

with f1:
    accounts = ["All Accounts"]
    all_acc = set()
    if "Account" in site_filtered_att.columns:
        all_acc.update(site_filtered_att["Account"].dropna().unique())
    if "Account" in site_filtered_raw.columns:
        all_acc.update(site_filtered_raw["Account"].dropna().unique())
    accounts += sorted([a for a in all_acc if a and str(a).lower() != "nan"])
    selected_account = st.selectbox("Account / Source:", accounts, index=0)

with f2:
    months = ["All Months"]
    all_months = set()
    if "month_clean" in site_filtered_att.columns:
        all_months.update(site_filtered_att["month_clean"].dropna().unique())
    if "month_clean" in site_filtered_raw.columns:
        all_months.update(site_filtered_raw["month_clean"].dropna().unique())

    clean_months = sorted(
        [m for m in all_months if m and str(m).lower() != "nan"]
    )
    months += clean_months

    aug_idx = months.index("August 2026") if "August 2026" in months else 0
    selected_month = st.selectbox("Month:", months, index=aug_idx)

with f3:
    all_weeks = set()
    if "week" in site_filtered_att.columns:
        all_weeks.update(site_filtered_att["week"].dropna().unique())
    if "week" in site_filtered_raw.columns:
        all_weeks.update(site_filtered_raw["week"].dropna().unique())
    available_weeks = sorted(
        [w for w in all_weeks if w and str(w).lower() != "nan"],
        key=lambda x: (
            int(re.search(r"\d+", str(x)).group())
            if re.search(r"\d+", str(x))
            else 0
        ),
    )
    selected_weeks = st.multiselect(
        "Work Week (Leave empty for ALL weeks):",
        options=available_weeks,
        default=[],
    )

with f4:
    all_roles = set()
    if "role" in site_filtered_raw.columns:
        all_roles.update(
            site_filtered_raw["role"]
            .dropna()
            .astype(str)
            .str.strip()
            .str.upper()
            .unique()
        )
    if "role" in site_filtered_att.columns:
        all_roles.update(
            site_filtered_att["role"]
            .dropna()
            .astype(str)
            .str.strip()
            .str.upper()
            .unique()
        )

    roles_available = sorted(
        [
            r
            for r in all_roles
            if r and r not in ["NAN", "NONE", "ROLE", "POSITION", "UNKNOWN ROLE"]
        ]
    )
    selected_roles = st.multiselect(
        "Role (Position) (Leave empty for ALL roles):",
        options=roles_available,
        default=[],
    )


def apply_common_filters(df, strict_month=True):
    if df.empty:
        return df
    dff = df.copy()

    if selected_site != "All Sites" and "site" in dff.columns:
        dff = dff[
            dff["site"].astype(str).str.strip().str.lower()
            == selected_site.lower()
        ]

    if selected_account != "All Accounts" and "Account" in dff.columns:
        dff = dff[
            dff["Account"].astype(str).str.strip().str.lower()
            == selected_account.strip().lower()
        ]

    if strict_month and selected_month != "All Months":
        target_month = selected_month.strip().lower()
        if "month_clean" in dff.columns:
            dff = dff[
                dff["month_clean"].astype(str).str.strip().str.lower()
                == target_month
            ]

    if len(selected_weeks) > 0 and "week" in dff.columns:
        selected_weeks_lower = [w.lower().strip() for w in selected_weeks]
        dff = dff[
            dff["week"]
            .astype(str)
            .str.strip()
            .str.lower()
            .isin(selected_weeks_lower)
        ]

    if len(selected_roles) > 0 and "role" in dff.columns:
        active_roles_upper = [r.upper().strip() for r in selected_roles]
        pattern = "|".join([re.escape(r) for r in active_roles_upper])
        dff = dff[
            dff["role"]
            .astype(str)
            .str.upper()
            .str.contains(pattern, na=False)
        ]

    return dff


filtered_attendance_df = apply_common_filters(
    attendance_raw_df, strict_month=True
)
filtered_raw_df = apply_common_filters(df_raw, strict_month=True)


def apply_pivot_filters(df):
    if df.empty:
        return df
    dff = df.copy()
    if selected_site != "All Sites" and "site" in dff.columns:
        dff = dff[
            dff["site"].astype(str).str.strip().str.lower()
            == selected_site.lower()
        ]
    if len(selected_roles) > 0 and "role" in dff.columns:
        active_roles_upper = [r.upper().strip() for r in selected_roles]
        pattern = "|".join([re.escape(r) for r in active_roles_upper])
        dff = dff[
            dff["role"]
            .astype(str)
            .str.upper()
            .str.contains(pattern, na=False)
        ]
    return dff


independent_pivot_df = apply_pivot_filters(pivot_attendance_df)

# Metrics & Aggregations Calculation
SHIFT_MINS_PER_DAY = 480.0
group_cols = ["Account", "month_clean", "week", "site", "role", "Agent Name"]
valid_group_cols = [c for c in group_cols if c in filtered_raw_df.columns]

if valid_group_cols and not filtered_raw_df.empty:
    adherence_summary = filtered_raw_df.groupby(
        valid_group_cols, as_index=False
    ).agg(
        Days_Logged=(
            ("Date", "nunique")
            if "Date" in filtered_raw_df.columns
            else ("Total Break_Mins", "count")
        ),
        Total_Break_Mins=("Total Break_Mins", "sum"),
        Exceeded_Break_Mins=("Exceeded_Break_Raw_Mins", "sum"),
        Total_Meal_Mins=("Total Meal_Mins", "sum"),
        Unaccounted_Mins=("Unaccounted_Mins", "sum"),
        Direct_Adherence_Avg=("Parsed_Adherence", "mean"),
    )

    adherence_summary["Scheduled_Mins"] = (
        adherence_summary["Days_Logged"] * SHIFT_MINS_PER_DAY
    )
    adherence_summary["Total_Lost_Mins"] = (
        adherence_summary["Unaccounted_Mins"]
        + adherence_summary["Exceeded_Break_Mins"]
    )

    adherence_summary["Adherence_%"] = adherence_summary["Direct_Adherence_Avg"]

    missing_mask = adherence_summary["Adherence_%"].isna()
    if missing_mask.any():
        calc_vals = (
            1
            - (
                adherence_summary.loc[missing_mask, "Total_Lost_Mins"]
                / adherence_summary.loc[missing_mask, "Scheduled_Mins"]
            )
        ) * 100.0
        adherence_summary.loc[missing_mask, "Adherence_%"] = calc_vals.clip(
            lower=0, upper=100
        )

    adherence_summary["Goal_Met"] = adherence_summary["Adherence_%"] >= 88.0
    filtered_df = adherence_summary
else:
    filtered_df = pd.DataFrame()

# -------------------------------------------------------------
# 4. MAIN DASHBOARD TABS
# -------------------------------------------------------------
(
    tab_attendance,
    tab_adherence,
    tab_ops_kpi,
    tab_agent_scope,
    tab_service_hours,
    tab_qa,
) = st.tabs([
    "📅 Attendance",
    "🎯 Status Adherence",
    "📊 Operational KPI View",
    "👤 Agent Scope",
    "⏱️ Service Hours per Campaign",
    "🛡️ Quality Assurance",
])

# -------------------------------------------------------------
# TAB 1: ATTENDANCE
# -------------------------------------------------------------
with tab_attendance:
    a_col1, a_col2 = st.columns([2.5, 1.5])
    with a_col1:
        st.subheader("📅 Attendance Tracker & Pivot Summary")
    with a_col2:
        st.markdown(
            "[🔗 Open Main Attendance"
            " Sheet](https://docs.google.com/spreadsheets/d/1PUerkTX4iCaFUP27FXV34azza6L5LpFYsb1nHVKrH-c/edit#gid=601856217)"
        )
        st.markdown(
            "[🔗 Open Pivot Attendance Summary"
            " Sheet](https://docs.google.com/spreadsheets/d/1kzXr88ueah-Gg0gVI4bhl1peFdWYgy0nIFRkZOl0RK0/edit#gid=243149129)"
        )

    if not filtered_attendance_df.empty:
        working_att = filtered_attendance_df.copy()
        working_att["Unjustified Absences"] = pd.to_numeric(
            working_att.get("Unjustified Absences", 0), errors="coerce"
        ).fillna(0)
        working_att["Justified Absences"] = pd.to_numeric(
            working_att.get("Justified Absences", 0), errors="coerce"
        ).fillna(0)
        working_att["Late_Mins_Numeric"] = pd.to_numeric(
            working_att.get("Late_Mins_Numeric", 0), errors="coerce"
        ).fillna(0)
        working_att["Total Late Instances"] = pd.to_numeric(
            working_att.get("Total Late Instances", 0), errors="coerce"
        ).fillna(0)

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
        st.caption(
            "ℹ️ Unfiltered by Month/Week filters as infractions operate on a"
            " 60-day running window."
        )

        if not independent_pivot_df.empty:

            def style_escalation_status(val):
                s = str(val).strip().lower()
                if "terminate" in s:
                    return (
                        "background-color: #7F1D1D; color: #FFFFFF;"
                        " font-weight: bold;"
                    )
                elif "probation" in s:
                    return (
                        "background-color: #F97316; color: #FFFFFF;"
                        " font-weight: bold;"
                    )
                elif "written warning" in s or "final" in s:
                    return (
                        "background-color: #FEE2E2; color: #991B1B;"
                        " font-weight: bold;"
                    )
                elif (
                    "verbal warning" in s
                    or "coaching" in s
                    or "review" in s
                ):
                    return (
                        "background-color: #FEF3C7; color: #92400E;"
                        " font-weight: bold;"
                    )
                elif "safe" in s or "0" in s or "none" in s:
                    return (
                        "background-color: #D1FAE5; color: #065F46;"
                        " font-weight: bold;"
                    )
                return ""

            esc_cols = [
                c
                for c in independent_pivot_df.columns
                if "escalation" in str(c).lower()
            ]
            styler = independent_pivot_df.style
            if esc_cols:
                styled_pivot = (
                    styler.map(style_escalation_status, subset=esc_cols)
                    if hasattr(styler, "map")
                    else styler.applymap(
                        style_escalation_status, subset=esc_cols
                    )
                )
            else:
                styled_pivot = styler

            st.dataframe(
                styled_pivot, use_container_width=True, hide_index=True
            )
        else:
            st.info("No 60-day point infractions logged.")

        st.divider()

        st.write("### 📊 Agent Absence & Lateness Duration Breakdown")
        if not agent_totals.empty:
            plot_df = agent_totals.set_index("Agent Name").rename(
                columns={"Late_Mins_Numeric": "Late Duration (Mins)"}
            )
            st.bar_chart(
                plot_df[[
                    "Unjustified Absences",
                    "Justified Absences",
                    "Total Late Instances",
                    "Late Duration (Mins)",
                ]]
            )

        st.divider()
        st.write("### 📋 Primary Attendance Log")
        st.dataframe(
            filtered_attendance_df, use_container_width=True, hide_index=True
        )
    else:
        st.info("No attendance data found for the selected filter combination.")

# -------------------------------------------------------------
# TAB 2: STATUS ADHERENCE
# -------------------------------------------------------------
with tab_adherence:
    m1, m2, m3, m4 = st.columns(4)

    overall_adherence = (
        filtered_df["Adherence_%"].mean() if not filtered_df.empty else 0.0
    )
    non_compliant_count = (
        len(filtered_df[filtered_df["Adherence_%"] < 88.0])
        if not filtered_df.empty
        else 0
    )
    delta_val = overall_adherence - 88.0

    mom_delta_str = "N/A"
    if not df_raw.empty and "month_clean" in df_raw.columns:
        all_months_sorted = sorted(
            df_raw["month_clean"].dropna().unique().tolist()
        )
        if len(all_months_sorted) > 1:
            current_m = (
                selected_month
                if selected_month != "All Months"
                else all_months_sorted[-1]
            )
            if current_m in all_months_sorted:
                curr_idx = all_months_sorted.index(current_m)
                if curr_idx > 0:
                    prev_m = all_months_sorted[curr_idx - 1]
                    prev_df = apply_common_filters(
                        df_raw[df_raw["month_clean"] == prev_m],
                        strict_month=False,
                    )
                    if (
                        not prev_df.empty
                        and "Parsed_Adherence" in prev_df.columns
                    ):
                        prev_avg = prev_df["Parsed_Adherence"].mean()
                        if pd.notna(prev_avg):
                            mom_diff = overall_adherence - prev_avg
                            mom_delta_str = f"{mom_diff:+.1f}% vs {prev_m}"

    with m1:
        st.metric(
            "🎯 Combined Adherence %",
            f"{overall_adherence:.1f}%",
            delta=f"{delta_val:+.1f}% vs Goal (88%)",
            delta_color="normal",
        )
    with m2:
        st.metric(
            "📈 MoM Performance Trend",
            f"{overall_adherence:.1f}%",
            delta=mom_delta_str,
            delta_color="normal",
        )
    with m3:
        st.metric(
            "🚨 Total Agents Below 88%",
            f"{non_compliant_count} Agents",
            delta=(
                "Needs Attention" if non_compliant_count > 0 else "All Compliant"
            ),
            delta_color=(
                "inverse" if non_compliant_count > 0 else "normal"
            ),
        )
    with m4:
        total_overage = (
            filtered_df["Exceeded_Break_Mins"].sum()
            if not filtered_df.empty
            else 0
        )
        st.metric("⏱️ Combined Break Overage", f"{int(total_overage)} Mins")

    st.divider()

    if not filtered_df.empty and "week" in filtered_df.columns:
        st.subheader("📈 Weekly Status Adherence & Lost Minutes Trend")

        weekly_chart_data = (
            filtered_df.groupby("week", as_index=False)
            .agg(
                Avg_Adherence=("Adherence_%", "mean"),
                Total_Lost_Mins=("Total_Lost_Mins", "sum"),
            )
            .sort_values(
                by="week",
                key=lambda x: x.str.extract(r"(\d+)")[0].astype(float),
            )
        )

        fig = make_subplots(specs=[[{"secondary_y": True}]])

        fig.add_trace(
            go.Scatter(
                x=weekly_chart_data["week"],
                y=weekly_chart_data["Avg_Adherence"],
                name="Adherence %",
                mode="lines+markers+text",
                text=[
                    f"{v:.1f}%" for v in weekly_chart_data["Avg_Adherence"]
                ],
                textposition="top center",
                line=dict(color="#007AC1", width=3),
                marker=dict(size=8),
            ),
            secondary_y=False,
        )

        fig.add_hline(
            y=88.0,
            line_dash="dash",
            line_color="red",
            annotation_text="Target Goal (88%)",
            annotation_position="bottom right",
            secondary_y=False,
        )

        fig.add_trace(
            go.Bar(
                x=weekly_chart_data["week"],
                y=weekly_chart_data["Total_Lost_Mins"],
                name="Lost Time (Mins)",
                opacity=0.3,
                marker_color="#FF4B4B",
            ),
            secondary_y=True,
        )

        fig.update_layout(
            title="Weekly Adherence Trend vs. Total Unaccounted/Overage Minutes",
            xaxis_title="Work Week",
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=20, r=20, t=50, b=20),
        )

        fig.update_yaxes(
            title_text="Adherence Score (%)", range=[50, 105], secondary_y=False
        )
        fig.update_yaxes(
            title_text="Total Lost Time (Minutes)",
            showgrid=False,
            secondary_y=True,
        )

        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    if not filtered_df.empty:
        col_acc, col_site, col_role = st.columns(3)

        with col_acc:
            st.markdown("### 📁 Adherence by Account")
            if "Account" in filtered_df.columns:
                acc_summary = filtered_df.groupby(
                    "Account", as_index=False
                ).agg(
                    Avg_Adherence=("Adherence_%", "mean"),
                    Agents_Below_Goal=("Goal_Met", lambda x: (~x).sum()),
                )
                acc_summary["Avg_Adherence"] = acc_summary[
                    "Avg_Adherence"
                ].apply(lambda x: f"{x:.1f}%")
                st.dataframe(
                    acc_summary, use_container_width=True, hide_index=True
                )

        with col_site:
            st.markdown("### 🏢 Adherence by Site")
            if "site" in filtered_df.columns:
                site_summary = filtered_df.groupby("site", as_index=False).agg(
                    Avg_Adherence=("Adherence_%", "mean"),
                    Agents_Below_Goal=("Goal_Met", lambda x: (~x).sum()),
                )
                site_summary["Avg_Adherence"] = site_summary[
                    "Avg_Adherence"
                ].apply(lambda x: f"{x:.1f}%")
                st.dataframe(
                    site_summary, use_container_width=True, hide_index=True
                )

        with col_role:
            st.markdown("### 💼 Adherence by Role")
            if "role" in filtered_df.columns:
                role_summary = filtered_df.groupby("role", as_index=False).agg(
                    Avg_Adherence=("Adherence_%", "mean"),
                    Agents_Below_Goal=("Goal_Met", lambda x: (~x).sum()),
                )
                role_summary["Avg_Adherence"] = role_summary[
                    "Avg_Adherence"
                ].apply(lambda x: f"{x:.1f}%")
                st.dataframe(
                    role_summary, use_container_width=True, hide_index=True
                )

        st.divider()
        st.markdown("### 📋 Agent Adherence Detail Log")
        st.dataframe(
            filtered_df.sort_values(by="Adherence_%", ascending=True),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No adherence data available for selected filter options.")

# -------------------------------------------------------------
# TAB 3: OPERATIONAL KPI VIEW
# -------------------------------------------------------------
with tab_ops_kpi:
    st.subheader("📊 Operational KPI View")
    col_cdmx, col_tj = st.columns(2)

    with col_cdmx:
        st.markdown("#### 🏢 CDMX Operational KPIs")
        if not cdmx_kpis_df.empty:
            st.dataframe(cdmx_kpis_df, use_container_width=True, hide_index=True)
        else:
            st.info("No CDMX KPI data loaded.")

    with col_tj:
        st.markdown("#### 🌊 Tijuana Operational KPIs")
        if not tj_kpis_df.empty:
            st.dataframe(tj_kpis_df, use_container_width=True, hide_index=True)
        else:
            st.info("No Tijuana KPI data loaded.")

    st.divider()
    st.markdown("#### 📈 CDMX Weekly Performance Trends")
    if not cdmx_weekly_trends_df.empty:
        st.dataframe(cdmx_weekly_trends_df, use_container_width=True, hide_index=True)
    else:
        st.info("No weekly trend data available.")

# -------------------------------------------------------------
# TAB 4: AGENT SCOPE
# -------------------------------------------------------------
with tab_agent_scope:
    st.subheader("👤 Agent Scope & Performance Drilldown")
    if not filtered_df.empty and "Agent Name" in filtered_df.columns:
        selected_agent = st.selectbox(
            "Select Agent to Audit:",
            options=sorted(filtered_df["Agent Name"].unique()),
        )
        agent_data = filtered_df[filtered_df["Agent Name"] == selected_agent]

        st.write(f"### Profile Performance Summary: **{selected_agent}**")
        st.dataframe(agent_data, use_container_width=True, hide_index=True)
    else:
        st.info("No agent details found in the current selection scope.")

# -------------------------------------------------------------
# TAB 5: SERVICE HOURS PER CAMPAIGN
# -------------------------------------------------------------
with tab_service_hours:
    st.subheader("⏱️ Service Hours per Campaign & Account")

    if not filtered_raw_df.empty:
        service_df = filtered_raw_df.groupby(["Account", "site"], as_index=False).agg(
            Total_Days_Logged=(
                ("Date", "nunique")
                if "Date" in filtered_raw_df.columns
                else ("Total Break_Mins", "count")
            ),
            Total_Break_Mins=("Total Break_Mins", "sum"),
            Total_Meal_Mins=("Total Meal_Mins", "sum"),
            Exceeded_Break_Mins=("Exceeded_Break_Raw_Mins", "sum"),
            Unaccounted_Mins=("Unaccounted_Mins", "sum"),
        )

        service_df["Scheduled_Hours"] = service_df["Total_Days_Logged"] * 8.0
        service_df["Lost_Hours"] = (
            service_df["Exceeded_Break_Mins"] + service_df["Unaccounted_Mins"]
        ) / 60.0
        service_df["Actual_Service_Hours"] = (
            service_df["Scheduled_Hours"] - service_df["Lost_Hours"]
        )
        service_df["Fulfillment_%"] = (
            service_df["Actual_Service_Hours"] / service_df["Scheduled_Hours"]
        ) * 100.0

        h1, h2, h3, h4 = st.columns(4)
        total_sched = service_df["Scheduled_Hours"].sum()
        total_actual = service_df["Actual_Service_Hours"].sum()
        overall_fulfillment = (
            (total_actual / total_sched * 100.0) if total_sched > 0 else 0.0
        )

        h1.metric("📅 Scheduled Target Hours", f"{total_sched:,.1f} hrs")
        h2.metric("⏱️ Net Delivered Hours", f"{total_actual:,.1f} hrs")
        h3.metric("🔻 Total Lost Hours", f"{service_df['Lost_Hours'].sum():,.1f} hrs")
        h4.metric("🎯 Hours Fulfillment Rate", f"{overall_fulfillment:.1f}%")

        st.divider()

        st.write("### 📈 Scheduled vs. Delivered Hours by Campaign")

        fig_hours = make_subplots(specs=[[{"secondary_y": True}]])

        fig_hours.add_trace(
            go.Bar(
                x=service_df["Account"] + " (" + service_df["site"] + ")",
                y=service_df["Scheduled_Hours"],
                name="Scheduled Target (Hrs)",
                marker_color="#CBD5E1",
                opacity=0.7,
            ),
            secondary_y=False,
        )

        fig_hours.add_trace(
            go.Bar(
                x=service_df["Account"] + " (" + service_df["site"] + ")",
                y=service_df["Actual_Service_Hours"],
                name="Delivered Hours",
                marker_color="#007AC1",
                text=[f"{val:,.1f}h" for val in service_df["Actual_Service_Hours"]],
                textposition="auto",
            ),
            secondary_y=False,
        )

        fig_hours.add_trace(
            go.Scatter(
                x=service_df["Account"] + " (" + service_df["site"] + ")",
                y=service_df["Fulfillment_%"],
                name="Fulfillment Rate (%)",
                mode="lines+markers+text",
                text=[f"{val:.1f}%" for val in service_df["Fulfillment_%"]],
                textposition="top center",
                line=dict(color="#16A34A", width=3),
                marker=dict(size=8),
            ),
            secondary_y=True,
        )

        fig_hours.update_layout(
            title="Service Hours Delivered vs Target by Account & Site",
            barmode="group",
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=20, r=20, t=50, b=20),
        )

        fig_hours.update_yaxes(title_text="Hours", secondary_y=False)
        fig_hours.update_yaxes(
            title_text="Fulfillment Rate (%)", range=[50, 110], secondary_y=True
        )

        st.plotly_chart(fig_hours, use_container_width=True)

        st.divider()

        st.write("### 📋 Campaign Hours Audit Breakdown")
        display_service_df = service_df.copy()
        display_service_df["Scheduled_Hours"] = display_service_df[
            "Scheduled_Hours"
        ].apply(lambda x: f"{x:,.1f} hrs")
        display_service_df["Actual_Service_Hours"] = display_service_df[
            "Actual_Service_Hours"
        ].apply(lambda x: f"{x:,.1f} hrs")
        display_service_df["Lost_Hours"] = display_service_df[
            "Lost_Hours"
        ].apply(lambda x: f"{x:,.1f} hrs")
        display_service_df["Fulfillment_%"] = display_service_df[
            "Fulfillment_%"
        ].apply(lambda x: f"{x:.1f}%")

        st.dataframe(
            display_service_df, use_container_width=True, hide_index=True
        )
    else:
        st.info("No raw operational data available to compute service hours.")

# -------------------------------------------------------------
# TAB 6: QUALITY ASSURANCE
# -------------------------------------------------------------
with tab_qa:
    st.subheader("🛡️ Quality Assurance (QA) Metrics")
    st.info("Quality Assurance evaluation integrations are active.")
