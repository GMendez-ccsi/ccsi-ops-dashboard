import base64
import io
import re
import urllib.request
import numpy as np
import pandas as pd
import plotly.express as px
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
        "Combined Operations Hub: TDS, TransDev SD/OC | Attendance, Adherence, QA & Capacity Engine"
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
# 2. CORE DATA HELPERS & PARSERS
# -------------------------------------------------------------
def normalize_site(val):
    if pd.isna(val) or not str(val).strip():
        return "CDMX"
    s = str(val).strip().upper()
    if s in ["TJ", "TIJUANA", "TIJ"] or "TJ" in s or "TIJUANA" in s:
        return "Tijuana"
    if s in ["MX", "CDMX", "MEXICO", "SAN DIEGO", "OC"] or "MX" in s or "CDMX" in s or "SAN DIEGO" in s or "OC" in s:
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
    
    iso_match = re.search(r"\d{4}-[Ww](\d+)", val_str)
    if iso_match:
        return f"Week {int(iso_match.group(1))}"
    
    w_match = re.search(r"^[Ww](\d+)$", val_str)
    if w_match:
        return f"Week {int(w_match.group(1))}"
        
    week_match = re.search(r"[Ww]eek\s*(\d+)", val_str, re.IGNORECASE)
    if week_match:
        return f"Week {int(week_match.group(1))}"
        
    if val_str.isdigit():
        num = int(val_str)
        if 1 <= num <= 53:
            return f"Week {num}"
            
    digit_match = re.search(r"(\d+)", val_str)
    if digit_match:
        num = int(digit_match.group(1))
        if 1 <= num <= 53:
            return f"Week {num}"

    return val_str


def deduplicate_dataframe_columns(df):
    if df.empty:
        return df
    counts = {}
    new_cols = []
    for col in df.columns:
        col_str = str(col).strip() if str(col).strip() != "" else "Col"
        if col_str in counts:
            counts[col_str] += 1
            new_cols.append(f"{col_str}_{counts[col_str]}")
        else:
            counts[col_str] = 0
            new_cols.append(col_str)
    df_out = df.copy()
    df_out.columns = new_cols
    return df_out


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
        "kpi", "metric", "project", "week", "date", "target", "score", "agent", "qa"
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
    return deduplicate_dataframe_columns(df_clean.dropna(how="all").reset_index(drop=True))


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

    for c in list(df_clean.columns):
        clow = str(c).lower().strip()
        if "site" in clow or "location" in clow:
            df_clean = df_clean.rename(columns={c: "site"})
        elif any(k in clow for k in ["agent", "employee"]) and "name" in clow:
            df_clean = df_clean.rename(columns={c: "Agent Name"})
        elif any(k in clow for k in ["role", "position"]):
            df_clean = df_clean.rename(columns={c: "role"})

    if "Agent Name" in df_clean.columns:
        agent_col = df_clean["Agent Name"]
        if isinstance(agent_col, pd.DataFrame):
            agent_col = agent_col.iloc[:, 0]
        df_clean = df_clean[
            ~agent_col.astype(str)
            .str.lower()
            .str.contains("total|grand total|blank|nan", na=False)
        ]

    if "site" in df_clean.columns:
        site_col = df_clean["site"]
        if isinstance(site_col, pd.DataFrame):
            site_col = site_col.iloc[:, 0]
        df_clean["site"] = site_col.apply(normalize_site)

    if "role" in df_clean.columns:
        role_col = df_clean["role"]
        if isinstance(role_col, pd.DataFrame):
            role_col = role_col.iloc[:, 0]
        df_clean["role"] = role_col.astype(str).str.strip().str.upper()

    return deduplicate_dataframe_columns(df_clean.reset_index(drop=True))


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
        raw_headers = [
            str(c).strip() if str(c).strip() != "nan" else f"Unused_{j}"
            for j, c in enumerate(df_raw.iloc[header_idx].tolist())
        ]
        df_clean = df_raw.iloc[header_idx + 1 :].copy()
        df_clean.columns = raw_headers
    else:
        df_clean = df_raw.copy()

    df_clean = df_clean.dropna(how="all")

    col_map = {}
    for c in df_clean.columns:
        clow = str(c).lower().strip()
        if ("site" in clow or "location" in clow) and "site" not in col_map.values():
            col_map[c] = "site"
        elif "week" in clow and "week" not in col_map.values():
            col_map[c] = "week"
        elif "account" in clow and "Account" not in col_map.values():
            col_map[c] = "Account"
        elif ("month" in clow or "date" in clow) and "month" not in col_map.values():
            col_map[c] = "month"
        elif any(k in clow for k in ["role", "position", "title"]) and "role" not in col_map.values():
            col_map[c] = "role"
        elif any(k in clow for k in ["agent", "employee", "name"]) and "Agent Name" not in col_map.values():
            col_map[c] = "Agent Name"
        elif "unjustified" in clow and "Unjustified Absences" not in col_map.values():
            col_map[c] = "Unjustified Absences"
        elif "justified" in clow and "Justified Absences" not in col_map.values():
            col_map[c] = "Justified Absences"
        elif ("late" in clow or "lateness" in clow) and "Total Late Time" not in col_map.values():
            col_map[c] = "Total Late Time"

    df_clean = df_clean.rename(columns=col_map)

    if "Agent Name" in df_clean.columns:
        agent_col = df_clean["Agent Name"]
        if isinstance(agent_col, pd.DataFrame):
            agent_col = agent_col.iloc[:, 0]
        df_clean = df_clean[
            ~agent_col.astype(str)
            .str.lower()
            .str.contains("total|grand total|blank|nan", na=False)
        ]

    if "site" in df_clean.columns:
        site_col = df_clean["site"]
        if isinstance(site_col, pd.DataFrame):
            site_col = site_col.iloc[:, 0]
        df_clean["site"] = site_col.apply(normalize_site)
    else:
        df_clean["site"] = "CDMX"

    if "week" in df_clean.columns:
        week_col = df_clean["week"]
        if isinstance(week_col, pd.DataFrame):
            week_col = week_col.iloc[:, 0]
        df_clean["week"] = week_col.apply(clean_week_str)
    else:
        df_clean["week"] = "Week 1"

    if "month" in df_clean.columns:
        month_col = df_clean["month"]
        if isinstance(month_col, pd.DataFrame):
            month_col = month_col.iloc[:, 0]
        df_clean["month_clean"] = month_col.astype(str).str.strip()
    else:
        df_clean["month_clean"] = "August 2026"

    if "Account" not in df_clean.columns:
        df_clean["Account"] = "TDS"

    if "role" not in df_clean.columns:
        df_clean["role"] = "CSA"
    else:
        role_col = df_clean["role"]
        if isinstance(role_col, pd.DataFrame):
            role_col = role_col.iloc[:, 0]
        df_clean["role"] = role_col.astype(str).str.strip().str.upper()

    if "Total Late Time" in df_clean.columns:
        late_col = df_clean["Total Late Time"]
        if isinstance(late_col, pd.DataFrame):
            late_col = late_col.iloc[:, 0]
        df_clean["Late_Mins_Numeric"] = late_col.apply(time_to_minutes)
    else:
        df_clean["Late_Mins_Numeric"] = 0.0

    df_clean["Total Late Instances"] = (
        df_clean["Late_Mins_Numeric"] > 0
    ).astype(int)

    return deduplicate_dataframe_columns(df_clean.reset_index(drop=True))


@st.cache_data(ttl=300)
def parse_sheet_by_structure(sheet_id, gid, default_account_label):
    df_raw = fetch_raw_csv(sheet_id, gid)
    if df_raw.empty:
        return pd.DataFrame()

    header_idx = None
    for i in range(min(15, len(df_raw))):
        row_cells = [
            str(x).strip().lower() for x in df_raw.iloc[i].fillna("").tolist()
        ]
        if any(
            k in row_cells
            for k in [
                "site",
                "position",
                "role",
                "account",
                "week",
                "date",
                "name",
                "status adhere",
                "unaccou",
                "breaks",
            ]
        ):
            header_idx = i
            break

    if header_idx is None:
        return pd.DataFrame()

    raw_headers = [str(c).strip() for c in df_raw.iloc[header_idx].tolist()]
    dedup_headers = []
    counts = {}
    for h in raw_headers:
        if h in counts:
            counts[h] += 1
            dedup_headers.append(f"{h}_{counts[h]}")
        else:
            counts[h] = 0
            dedup_headers.append(h)

    df_data = df_raw.iloc[header_idx + 1 :].copy()
    df_data.columns = dedup_headers
    df_data = df_data.dropna(how="all")

    col_map = {}
    for idx, c in enumerate(df_data.columns):
        clow = str(c).lower().strip()

        if any(k in clow for k in ["period", "work week", "ww"]) or (clow == "week" and "week" not in col_map.values()):
            col_map[c] = "week"

        elif (clow in ["account", "campaign"] or "account" in clow) and "Account" not in col_map.values():
            col_map[c] = "Account"

        elif (clow in ["position", "role"] or ("role" in clow and "exceeded" not in clow) or ("position" in clow and "exceeded" not in clow)) and "role" not in col_map.values():
            col_map[c] = "role"

        elif "site" in clow and "site" not in col_map.values():
            col_map[c] = "site"

        elif "date" in clow and "Date" not in col_map.values():
            col_map[c] = "Date"

        elif (
            clow in ["name", "agent name", "agent", "employee"]
            or "agent" in clow
        ) and "Agent Name" not in col_map.values():
            col_map[c] = "Agent Name"

        elif (
            clow in ["breaks", "total break"] or "break" in clow
        ) and "Total Break" not in col_map.values():
            col_map[c] = "Total Break"

        elif (
            clow in ["meal", "total meal"] or "meal" in clow
        ) and "Total Meal" not in col_map.values():
            col_map[c] = "Total Meal"

        elif (
            clow in ["meeting", "total meeting"] or "meeting" in clow
        ) and "Total Meeting" not in col_map.values():
            col_map[c] = "Total Meeting"

        elif (
            clow in ["training", "total training"] or "training" in clow
        ) and "Total Training" not in col_map.values():
            col_map[c] = "Total Training"

        elif "exceeded" in clow and "Exceeded_Break_Raw" not in col_map.values():
            col_map[c] = "Exceeded_Break_Raw"

        elif (
            ("unaccou" in clow or "unaccounted" in clow)
            and "Unaccounted" not in col_map.values()
        ):
            col_map[c] = "Unaccounted"

        elif (
            ("status adhere" in clow or "adherence" in clow or clow == "%")
            and "Direct_Adherence" not in col_map.values()
        ):
            col_map[c] = "Direct_Adherence"

    df_clean = df_data.rename(columns=col_map).copy()
    df_clean["Source_Sheet"] = default_account_label

    time_pattern = re.compile(r"^\d+:\d{2}(:\d{2})?$")

    # Strict isolation between Account and Role
    if "Account" not in df_clean.columns:
        df_clean["Account"] = default_account_label

    if "role" not in df_clean.columns:
        df_clean["role"] = "CSA"

    known_accounts = ["SAN DIEGO", "ORANGE COUNTY", "OC", "SD", "TRANSDEV", "TDS"]

    def clean_role_val(val):
        s = str(val).strip()
        if not s or s.lower() in ["nan", "none", "null", "position", "account", "role"]:
            return "CSA"
        if time_pattern.match(s):
            return "CSA"
        if s.upper() in known_accounts:
            return "CSA"
        return s.upper()

    def clean_account_val(val):
        s = str(val).strip()
        if not s or s.lower() in ["nan", "none", "null", "position", "account"]:
            return default_account_label
        if time_pattern.match(s):
            return default_account_label
        return s

    df_clean["Account"] = df_clean["Account"].apply(clean_account_val)
    df_clean["role"] = df_clean["role"].apply(clean_role_val)

    if "site" not in df_clean.columns:
        df_clean["site"] = "CDMX"
    else:
        site_col = df_clean["site"]
        if isinstance(site_col, pd.DataFrame):
            site_col = site_col.iloc[:, 0]
        df_clean["site"] = site_col.apply(normalize_site)

    if "week" in df_clean.columns:
        week_col = df_clean["week"]
        if isinstance(week_col, pd.DataFrame):
            week_col = week_col.iloc[:, 0]
        df_clean["week"] = week_col.apply(clean_week_str)
    else:
        df_clean["week"] = "Week 1"

    if "Agent Name" not in df_clean.columns:
        df_clean["Agent Name"] = "Unknown"

    for field in [
        "Total Break",
        "Total Meal",
        "Total Meeting",
        "Total Training",
        "Exceeded_Break_Raw",
        "Unaccounted",
    ]:
        if field not in df_clean.columns:
            df_clean[field] = "0:00"

    if "Direct_Adherence" not in df_clean.columns:
        df_clean["Direct_Adherence"] = None

    agent_series = df_clean["Agent Name"]
    if isinstance(agent_series, pd.DataFrame):
        agent_series = agent_series.iloc[:, 0]

    agent_str = agent_series.astype(str).str.lower().str.strip()
    invalid_mask = agent_str.isna() | agent_str.isin([
        "none",
        "nan",
        "",
        "agent name",
        "name",
        "agent",
        "employee",
        "site",
        "position",
        "total",
        "grand total",
    ])

    df_clean = df_clean[~invalid_mask.values].copy()
    return deduplicate_dataframe_columns(df_clean.reset_index(drop=True))


@st.cache_data(ttl=300)
def parse_virtual_qa_sheet(sheet_id, gid):
    df_raw = fetch_raw_csv(sheet_id, gid)
    if df_raw.empty:
        return pd.DataFrame()

    header_idx = None
    for i in range(min(15, len(df_raw))):
        row_cells = [
            str(x).strip().lower() for x in df_raw.iloc[i].fillna("").tolist()
        ]
        if any("agent" in x or "score" in x or "evaluator" in x or "qa" in x for x in row_cells):
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

    col_map = {}
    for c in df_clean.columns:
        clow = str(c).lower().strip()
        if any(k in clow for k in ["agent", "employee", "name"]) and "Agent Name" not in col_map.values():
            col_map[c] = "Agent Name"
        elif any(k in clow for k in ["score", "percentage", "final score", "qa score"]) and "QA_Score_Raw" not in col_map.values():
            col_map[c] = "QA_Score_Raw"
        elif "evaluator" in clow or "qa name" in clow or "auditor" in clow:
            col_map[c] = "Evaluator"
        elif "campaign" in clow or "account" in clow:
            col_map[c] = "Account"
        elif "site" in clow or "location" in clow:
            col_map[c] = "site"

    df_clean = df_clean.rename(columns=col_map)

    if "Agent Name" in df_clean.columns:
        agent_col = df_clean["Agent Name"]
        if isinstance(agent_col, pd.DataFrame):
            agent_col = agent_col.iloc[:, 0]
        df_clean = df_clean[~agent_col.astype(str).str.lower().str.contains("total|grand total|nan|none", na=False)]

    if "site" in df_clean.columns:
        site_col = df_clean["site"]
        if isinstance(site_col, pd.DataFrame):
            site_col = site_col.iloc[:, 0]
        df_clean["site"] = site_col.apply(normalize_site)
    else:
        df_clean["site"] = "CDMX"

    if "QA_Score_Raw" in df_clean.columns:
        score_col = df_clean["QA_Score_Raw"]
        if isinstance(score_col, pd.DataFrame):
            score_col = score_col.iloc[:, 0]
        df_clean["QA_Score_Numeric"] = score_col.apply(parse_adherence_val)
    else:
        df_clean["QA_Score_Numeric"] = np.nan

    return deduplicate_dataframe_columns(df_clean.dropna(how="all").reset_index(drop=True))


@st.cache_data(ttl=300)
def parse_service_hours_forecast(sheet_id, gid):
    df_raw = fetch_raw_csv(sheet_id, gid)
    if df_raw.empty:
        return pd.DataFrame()

    header_idx = 0
    for i in range(min(15, len(df_raw))):
        row_cells = [
            str(x).strip().lower() for x in df_raw.iloc[i].fillna("").tolist()
        ]
        if any("campaign" in x or "hours" in x or "forecast" in x or "scheduled" in x for x in row_cells):
            header_idx = i
            break

    headers = [
        str(c).strip() if str(c).strip() != "nan" else f"Col_{j}"
        for j, c in enumerate(df_raw.iloc[header_idx].tolist())
    ]
    df_clean = df_raw.iloc[header_idx + 1 :].copy()
    df_clean.columns = headers

    col_map = {}
    for c in df_clean.columns:
        clow = str(c).lower().strip()
        if "campaign" in clow or "account" in clow:
            col_map[c] = "Account"
        elif "site" in clow:
            col_map[c] = "site"
        elif "week" in clow:
            col_map[c] = "week"
        elif "scheduled" in clow or "forecast" in clow or "target" in clow:
            col_map[c] = "Forecasted_Hours"

    df_clean = df_clean.rename(columns=col_map)
    if "Forecasted_Hours" in df_clean.columns:
        fc_col = df_clean["Forecasted_Hours"]
        if isinstance(fc_col, pd.DataFrame):
            fc_col = fc_col.iloc[:, 0]
        df_clean["Forecasted_Hours_Numeric"] = pd.to_numeric(
            fc_col.astype(str).str.replace(",", "").str.strip(), errors="coerce"
        ).fillna(0.0)
    else:
        df_clean["Forecasted_Hours_Numeric"] = 0.0

    return deduplicate_dataframe_columns(df_clean.reset_index(drop=True))


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

    if "Date" in combined_df.columns:
        date_col = combined_df["Date"]
        if isinstance(date_col, pd.DataFrame):
            date_col = date_col.iloc[:, 0]
        parsed_dates = pd.to_datetime(
            date_col, errors="coerce", format="mixed"
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
        "Total Meeting",
        "Total Training",
        "Unaccounted",
        "Exceeded_Break_Raw",
    ]
    for col in time_cols:
        if col in combined_df.columns:
            target_series = combined_df[col]
            if isinstance(target_series, pd.DataFrame):
                target_series = target_series.iloc[:, 0]
            combined_df[f"{col}_Mins"] = target_series.apply(time_to_minutes)
        else:
            combined_df[f"{col}_Mins"] = 0.0

    if "Direct_Adherence" in combined_df.columns:
        adh_series = combined_df["Direct_Adherence"]
        if isinstance(adh_series, pd.DataFrame):
            adh_series = adh_series.iloc[:, 0]
        combined_df["Parsed_Adherence"] = adh_series.apply(parse_adherence_val)
    else:
        combined_df["Parsed_Adherence"] = None

    return deduplicate_dataframe_columns(combined_df)


# Ingest Data from Google Sheets
attendance_raw_df = parse_primary_attendance_sheet("1PUerkTX4iCaFUP27FXV34azza6L5LpFYsb1nHVKrH-c", "601856217")
pivot_attendance_df = parse_pivot_attendance_sheet_raw("1kzXr88ueah-Gg0gVI4bhl1peFdWYgy0nIFRkZOl0RK0", "243149129")
df_raw = load_all_combined_data_v15()
cdmx_kpis_df = parse_generic_kpi_sheet("1RW3LApb5TgMtdtBKqKHfZ3_t3sBQYCuUZqp8owA3ndM", "1978250855")
tj_kpis_df = parse_generic_kpi_sheet("12uF_syUu7enzOjob7di6c2UlPa6-EUgcTUHG7UcIMgk", "517756888")
cdmx_weekly_trends_df = parse_generic_kpi_sheet("1RW3LApb5TgMtdtBKqKHfZ3_t3sBQYCuUZqp8owA3ndM", "1684808847")
service_forecast_df = parse_service_hours_forecast("1PEybVFo8uL4jfasxJfrvWtEFHyk1EYGmsjLnMgk1Qt4", "1459025310")
virtual_qa_df = parse_virtual_qa_sheet("17blbXU8PWciUJrU0PMTj1iMydQOqPQyGRUYVf3LhbNk", "490191452")


# -------------------------------------------------------------
# 3. GLOBAL FILTERS UI
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

    clean_acc = [
        str(a).strip() for a in all_acc
        if a and str(a).lower() not in ["nan", "none", ""]
        and not re.match(r"^\d+:\d{2}", str(a).strip())
    ]
    accounts += sorted(clean_acc)
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
            r for r in all_roles
            if r and r not in ["NAN", "NONE", "ROLE", "POSITION", "UNKNOWN ROLE", "SAN DIEGO", "ORANGE COUNTY"]
            and not re.match(r"^\d+:\d{2}", r)
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


filtered_attendance_df = apply_common_filters(attendance_raw_df, strict_month=True)
filtered_raw_df = apply_common_filters(df_raw, strict_month=True)
filtered_qa_df = apply_common_filters(virtual_qa_df, strict_month=False)


# -------------------------------------------------------------
# 4. ADHERENCE SUMMARY & CALCULATIONS
# -------------------------------------------------------------
def calculate_adherence_summary(raw_df):
    if raw_df.empty:
        return np.nan, 0, 0.0, 0, pd.DataFrame(), pd.DataFrame()

    df_calc = raw_df.copy()

    # Calculate Adherence percentage per row if not provided directly
    if "Parsed_Adherence" in df_calc.columns and df_calc["Parsed_Adherence"].notna().any():
        avg_adherence = df_calc["Parsed_Adherence"].mean()
    else:
        # Fallback metric calculation based on non-productive unaccounted minutes
        total_unaccounted = df_calc["Unaccounted_Mins"].sum() if "Unaccounted_Mins" in df_calc.columns else 0.0
        total_tracked_days = len(df_calc)
        total_scheduled_mins = total_tracked_days * 480.0
        
        if total_scheduled_mins > 0:
            avg_adherence = max(0.0, min(100.0, ((total_scheduled_mins - total_unaccounted) / total_scheduled_mins) * 100.0))
        else:
            avg_adherence = np.nan

    # Break overage
    total_break_overage = df_calc["Exceeded_Break_Raw_Mins"].sum() if "Exceeded_Break_Raw_Mins" in df_calc.columns else 0.0

    # Total unique agents tracked
    total_agents = df_calc["Agent Name"].nunique() if "Agent Name" in df_calc.columns else 0

    # Count agents below goal threshold (88%)
    if "Agent Name" in df_calc.columns:
        if "Parsed_Adherence" in df_calc.columns and df_calc["Parsed_Adherence"].notna().any():
            agent_adh = df_calc.groupby("Agent Name")["Parsed_Adherence"].mean()
            agents_below_88 = (agent_adh < 88.0).sum()
        else:
            agents_below_88 = 0
    else:
        agents_below_88 = 0

    # Breakdown by Account
    acc_summary = (
        df_calc.groupby("Account")
        .agg(
            Avg_Adherence=("Parsed_Adherence", lambda x: round(x.mean(), 1) if x.notna().any() else "N/A"),
            Agents_Below_Goal=("Agent Name", "nunique")
        )
        .reset_index()
    )

    # Breakdown by Role
    role_summary = (
        df_calc.groupby("role")
        .agg(
            Avg_Adherence=("Parsed_Adherence", lambda x: round(x.mean(), 1) if x.notna().any() else "N/A"),
            Agents_Below_Goal=("Agent Name", "nunique")
        )
        .reset_index()
    )

    return avg_adherence, agents_below_88, total_break_overage, total_agents, acc_summary, role_summary


# Render Status Adherence Metrics
avg_adh, below_88, break_overage, total_agents, acc_breakdown, role_breakdown = calculate_adherence_summary(filtered_raw_df)

c1, c2, c3, c4 = st.columns(4)
with c1:
    adh_str = f"{avg_adh:.1f}%" if pd.notna(avg_adh) else "N/A"
    st.metric("🎯 Adherence %", adh_str)
with c2:
    st.metric("🚨 Agents Below 88%", f"{below_88} Agents")
with c3:
    st.metric("⏱️ Break Overage", f"{int(break_overage)} Mins")
with c4:
    st.metric("👥 Total Tracked Agents", total_agents)

st.divider()

col_acc, col_role = st.columns(2)
with col_acc:
    st.markdown("### 📁 Adherence Breakdown by Account/Source")
    st.dataframe(acc_breakdown, use_container_width=True)

with col_role:
    st.markdown("### 💼 Adherence Breakdown by Role")
    st.dataframe(role_breakdown, use_container_width=True)

st.divider()
st.markdown("### 📋 Detailed Log (TransDev Operations)")
st.dataframe(filtered_raw_df, use_container_width=True)
