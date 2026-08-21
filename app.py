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
    if any(k in s for k in ["TJ", "TIJUANA", "TIJ"]):
        return "Tijuana"
    if any(k in s for k in ["MX", "CDMX", "MEXICO", "SAN DIEGO", "OC"]):
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
            return parsed if "%" in val or parsed > 1.0 else parsed * 100.0
        except ValueError:
            return None
    return None


def format_percentage_display(val):
    parsed = parse_adherence_val(val) if not isinstance(val, (int, float)) else val
    if parsed is None or pd.isna(parsed):
        return "N/A"
    return f"{float(parsed):.2f}%"


def time_to_minutes(val):
    if pd.isna(val):
        return 0.0
    if isinstance(val, (int, float)):
        return float(val) * 1440.0
    val_str = str(val).strip()
    if not val_str or val_str.lower() in ["nan", "none", "0", "0:00", "00:00:00", ""]:
        return 0.0
    try:
        parts = val_str.split(":")
        if len(parts) == 3:
            return float(parts[0]) * 60.0 + float(parts[1]) + float(parts[2]) / 60.0
        elif len(parts) == 2:
            return float(parts[0]) * 60.0 + float(parts[1])
    except Exception:
        pass
    try:
        return float(val_str)
    except ValueError:
        return 0.0


def minutes_to_hhmmss(mins):
    if pd.isna(mins) or mins is None or mins <= 0:
        return "00:00:00"
    total_seconds = int(round(float(mins) * 60))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


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
def parse_transdev_sheet(sheet_id, gid):
    df_raw = fetch_raw_csv(sheet_id, gid)
    if df_raw.empty:
        return pd.DataFrame()

    header_idx = None
    for i in range(min(15, len(df_raw))):
        row_cells = [str(x).strip().lower() for x in df_raw.iloc[i].fillna("").tolist()]
        if "site" in row_cells and "account" in row_cells and "name" in row_cells:
            header_idx = i
            break

    if header_idx is None:
        return pd.DataFrame()

    headers = [str(c).strip().lower() for c in df_raw.iloc[header_idx].tolist()]
    df_data = df_raw.iloc[header_idx + 1 :].copy()
    df_data.columns = headers
    df_data = df_data.dropna(how="all")

    rename_dict = {
        "site": "site",
        "account": "Account",
        "week": "week",
        "date": "Date",
        "name": "Agent Name",
        "breaks": "Total Break",
        "meal": "Total Meal",
        "meeting": "Total Meeting",
        "training": "Total Training",
        "exceeded break": "Exceeded_Break_Raw",
        "unaccou": "Unaccounted",
        "status adhere": "Direct_Adherence",
    }

    mapped_cols = {col: rename_dict[col] for col in df_data.columns if col in rename_dict}
    df_clean = df_data.rename(columns=mapped_cols).copy()

    if "site" in df_clean.columns:
        df_clean["site"] = df_clean["site"].astype(str).str.strip().str.upper()
        df_clean["site"] = df_clean["site"].replace({"MX": "CDMX", "UNKNOWN": "CDMX"})

    if "week" in df_clean.columns:
        df_clean["week"] = df_clean["week"].apply(clean_week_str)

    if "Date" in df_clean.columns:
        parsed_dates = pd.to_datetime(df_clean["Date"], errors="coerce", format="mixed")
        df_clean["parsed_date"] = parsed_dates
        df_clean["month_clean"] = parsed_dates.dt.strftime("%B %Y").fillna("August 2026")
    else:
        df_clean["month_clean"] = "August 2026"

    if "Direct_Adherence" in df_clean.columns:
        df_clean["Parsed_Adherence"] = df_clean["Direct_Adherence"].apply(parse_adherence_val)
    else:
        df_clean["Parsed_Adherence"] = None

    for col in [
        "Total Break",
        "Total Meal",
        "Total Meeting",
        "Total Training",
        "Unaccounted",
        "Exceeded_Break_Raw",
    ]:
        if col in df_clean.columns:
            df_clean[f"{col}_Mins"] = df_clean[col].apply(time_to_minutes)
        else:
            df_clean[f"{col}_Mins"] = 0.0

    df_clean["Source_Sheet"] = "TransDev SD & OC"
    if "role" not in df_clean.columns or df_clean["role"].isna().all():
        df_clean["role"] = df_clean["Account"]

    df_clean = df_clean[
        ~df_clean["Agent Name"]
        .astype(str)
        .str.lower()
        .str.strip()
        .isin(["none", "nan", "", "mxc santiago delval"])
    ]

    return deduplicate_dataframe_columns(df_clean.reset_index(drop=True))


@st.cache_data(ttl=300)
def parse_generic_kpi_sheet(sheet_id, gid):
    df_raw = fetch_raw_csv(sheet_id, gid)
    if df_raw.empty:
        return pd.DataFrame()

    header_idx = 0
    keywords = ["kpi", "metric", "project", "week", "date", "target", "score", "agent", "qa"]
    for i in range(min(15, len(df_raw))):
        row_cells = [str(x).strip().lower() for x in df_raw.iloc[i].fillna("").tolist()]
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
        row_cells = [str(x).strip().lower() for x in df_raw.iloc[i].fillna("").tolist()]
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
        row_cells = [str(x).strip().lower() for x in df_raw.iloc[i].fillna("").tolist()]
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

    df_clean["Total Late Instances"] = (df_clean["Late_Mins_Numeric"] > 0).astype(int)

    return deduplicate_dataframe_columns(df_clean.reset_index(drop=True))


@st.cache_data(ttl=300)
def parse_sheet_by_structure(sheet_id, gid, default_account_label):
    df_raw = fetch_raw_csv(sheet_id, gid)
    if df_raw.empty:
        return pd.DataFrame()

    header_idx = None
    for i in range(min(15, len(df_raw))):
        row_cells = [str(x).strip().lower() for x in df_raw.iloc[i].fillna("").tolist()]
        if any(
            k in row_cells
            for k in [
                "site",
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

        if clow in ["site"]:
            col_map[c] = "site"
        elif clow in ["account"]:
            col_map[c] = "Account"
        elif clow in ["week"]:
            col_map[c] = "week"
        elif clow in ["date"]:
            col_map[c] = "Date"
        elif clow in ["name", "agent name", "agent"]:
            col_map[c] = "Agent Name"
        elif clow in ["breaks"]:
            col_map[c] = "Total Break"
        elif clow in ["meal"]:
            col_map[c] = "Total Meal"
        elif clow in ["meeting"]:
            col_map[c] = "Total Meeting"
        elif clow in ["training"]:
            col_map[c] = "Total Training"
        elif "exceeded break" in clow or clow == "exceeded break":
            col_map[c] = "Exceeded_Break_Raw"
        elif "unaccou" in clow or "unaccounted" in clow:
            col_map[c] = "Unaccounted"
        elif "status adhere" in clow or "adherence" in clow:
            col_map[c] = "Direct_Adherence"

    df_clean = df_data.rename(columns=col_map).copy()

    df_clean["Source_Sheet"] = default_account_label

    if "Account" not in df_clean.columns:
        df_clean["Account"] = default_account_label
    else:
        df_clean["Account"] = df_clean["Account"].replace(["Unknown", "", "nan", "None"], default_account_label)

    if "role" not in df_clean.columns:
        df_clean["role"] = df_clean["Account"]

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
        "mxc santiago delval",
    ])

    df_clean = df_clean[~invalid_mask.values].copy()

    if "Date" in df_clean.columns:
        parsed_dates = pd.to_datetime(df_clean["Date"], errors="coerce", format="mixed")
        df_clean["parsed_date"] = parsed_dates
        df_clean["month_clean"] = parsed_dates.dt.strftime("%B %Y").fillna("August 2026")
    else:
        df_clean["month_clean"] = "August 2026"

    for col in [
        "Total Break",
        "Total Meal",
        "Total Meeting",
        "Total Training",
        "Unaccounted",
        "Exceeded_Break_Raw",
    ]:
        if col in df_clean.columns:
            df_clean[f"{col}_Mins"] = df_clean[col].apply(time_to_minutes)
        else:
            df_clean[f"{col}_Mins"] = 0.0

    if "Direct_Adherence" in df_clean.columns:
        df_clean["Parsed_Adherence"] = df_clean["Direct_Adherence"].apply(parse_adherence_val)
    else:
        df_clean["Parsed_Adherence"] = None

    return deduplicate_dataframe_columns(df_clean.reset_index(drop=True))


@st.cache_data(ttl=300)
def parse_virtual_qa_sheet(sheet_id, gid):
    df_raw = fetch_raw_csv(sheet_id, gid)
    if df_raw.empty:
        return pd.DataFrame()

    header_idx = None
    for i in range(min(15, len(df_raw))):
        row_cells = [str(x).strip().lower() for x in df_raw.iloc[i].fillna("").tolist()]
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
        row_cells = [str(x).strip().lower() for x in df_raw.iloc[i].fillna("").tolist()]
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
        td_df = parse_transdev_sheet(
            "1bp9_e-ML_TVCxkvjsr893nhcJmyw1WILWAsgwdAcjUc",
            "676189719"
        )
        if not td_df.empty:
            frames.append(td_df)
    except Exception as e:
        st.error(f"Error fetching data for TransDev SD & OC: {e}")

    if not frames:
        return pd.DataFrame()

    combined_df = pd.concat(frames, axis=0, ignore_index=True)
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

    clean_months = sorted([m for m in all_months if m and str(m).lower() not in ["nan", "none", ""]])
    months += clean_months

    selected_month = st.selectbox("Month:", months, index=0)

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
            if r and r not in ["NAN", "NONE", "ROLE", "POSITION", "UNKNOWN ROLE"]
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


def calculate_adherence_summary(raw_df):
    SHIFT_MINS_PER_DAY = 480.0
    group_cols = [
        "Account", "Source_Sheet", "month_clean", "week", "site", "role", "Agent Name"
    ]
    valid_group_cols = [c for c in group_cols if c in raw_df.columns]

    if not valid_group_cols or raw_df.empty:
        return pd.DataFrame()

    summary = raw_df.groupby(valid_group_cols, as_index=False).agg(
        Days_Logged=(
            ("Date", "count")
            if "Date" in raw_df.columns
            else ("Total Break_Mins", "count")
        ),
        Total_Break_Mins=("Total Break_Mins", "sum"),
        Total_Meal_Mins=("Total Meal_Mins", "sum"),
        Total_Meeting_Mins=("Total Meeting_Mins", "sum"),
        Total_Training_Mins=("Total Training_Mins", "sum"),
        Exceeded_Break_Mins=("Exceeded_Break_Raw_Mins", "sum"),
        Unaccounted_Mins=("Unaccounted_Mins", "sum"),
        Direct_Adherence_Avg=("Parsed_Adherence", "mean"),
    )

    summary["Scheduled_Mins"] = summary["Days_Logged"] * SHIFT_MINS_PER_DAY
    summary["Total_Lost_Mins"] = (
        summary["Unaccounted_Mins"] + summary["Exceeded_Break_Mins"]
    )
    summary["Adherence_%"] = summary["Direct_Adherence_Avg"]

    missing_mask = summary["Adherence_%"].isna()
    if missing_mask.any():
        calc_vals = (
            1
            - (
                summary.loc[missing_mask, "Total_Lost_Mins"]
                / summary.loc[missing_mask, "Scheduled_Mins"]
            )
        ) * 100.0
        summary.loc[missing_mask, "Adherence_%"] = calc_vals.clip(
            lower=0, upper=100
        )

    summary["Goal_Met"] = summary["Adherence_%"] >= 88.0

    summary["Total Break Time"] = summary["Total_Break_Mins"].apply(minutes_to_hhmmss)
    summary["Total Meal Time"] = summary["Total_Meal_Mins"].apply(minutes_to_hhmmss)
    summary["Total Unaccounted Time"] = summary["Unaccounted_Mins"].apply(minutes_to_hhmmss)
    summary["Exceeded Break Time"] = summary["Exceeded_Break_Mins"].apply(minutes_to_hhmmss)

    return deduplicate_dataframe_columns(summary)


filtered_df = calculate_adherence_summary(filtered_raw_df)


# -------------------------------------------------------------
# 4. RELATIONAL 360° AGENT SCORECARD ENGINE
# -------------------------------------------------------------
def build_360_agent_scorecard(att_df, adh_df, qa_df):
    if att_df.empty and adh_df.empty:
        return pd.DataFrame()

    records = {}

    if not att_df.empty and "Agent Name" in att_df.columns:
        att_grouped = att_df.groupby("Agent Name", as_index=False).agg(
            Unjustified_Absences=("Unjustified Absences", lambda x: pd.to_numeric(x, errors="coerce").fillna(0).sum()),
            Justified_Absences=("Justified Absences", lambda x: pd.to_numeric(x, errors="coerce").fillna(0).sum()),
            Total_Late_Mins=("Late_Mins_Numeric", "sum"),
        )
        for _, row in att_grouped.iterrows():
            name = str(row["Agent Name"]).strip()
            records[name] = {
                "Agent Name": name,
                "Unjustified Absences": int(row["Unjustified_Absences"]),
                "Justified Absences": int(row["Justified_Absences"]),
                "Late Minutes": float(row["Total_Late_Mins"]),
                "Adherence %": np.nan,
                "Exceeded Break Mins": 0.0,
                "Unaccounted Mins": 0.0,
                "QA Audit Count": 0,
                "QA Avg Score": np.nan,
            }

    if not adh_df.empty and "Agent Name" in adh_df.columns:
        adh_grouped = adh_df.groupby("Agent Name", as_index=False).agg(
            Avg_Adherence=("Adherence_%", "mean"),
            Exceeded_Break_Mins=("Exceeded_Break_Mins", "sum"),
            Unaccounted_Mins=("Unaccounted_Mins", "sum"),
        )
        for _, row in adh_grouped.iterrows():
            name = str(row["Agent Name"]).strip()
            if name not in records:
                records[name] = {
                    "Agent Name": name,
                    "Unjustified Absences": 0,
                    "Justified Absences": 0,
                    "Late Minutes": 0.0,
                    "Adherence %": row["Avg_Adherence"],
                    "Exceeded Break Mins": float(row["Exceeded_Break_Mins"]),
                    "Unaccounted Mins": float(row["Unaccounted_Mins"]),
                    "QA Audit Count": 0,
                    "QA Avg Score": np.nan,
                }
            else:
                records[name]["Adherence %"] = row["Avg_Adherence"]
                records[name]["Exceeded Break Mins"] = float(row["Exceeded_Break_Mins"])
                records[name]["Unaccounted Mins"] = float(row["Unaccounted_Mins"])

    if not qa_df.empty and "Agent Name" in qa_df.columns:
        qa_grouped = qa_df.groupby("Agent Name", as_index=False).agg(
            QA_Count=("QA_Score_Numeric", "count"),
            QA_Avg=("QA_Score_Numeric", "mean"),
        )
        for _, row in qa_grouped.iterrows():
            name = str(row["Agent Name"]).strip()
            if name in records:
                records[name]["QA Audit Count"] = int(row["QA_Count"])
                records[name]["QA Avg Score"] = row["QA_Avg"]

    scorecard_df = pd.DataFrame(list(records.values()))
    return deduplicate_dataframe_columns(scorecard_df)


master_scorecard_df = build_360_agent_scorecard(
    filtered_attendance_df, filtered_df, filtered_qa_df
)


# -------------------------------------------------------------
# 5. DASHBOARD LAYOUT & TAB ROUTING
# -------------------------------------------------------------
(
    tab_cmd_center,
    tab_attendance,
    tab_adherence,
    tab_ops_kpi,
    tab_agent_360,
    tab_service_hours,
    tab_qa,
) = st.tabs([
    "⚡ Command Center",
    "📅 Attendance",
    "🎯 Status Adherence",
    "📊 Operational KPIs",
    "👤 360° Agent Scorecard",
    "⏱️ Service Hours & Forecast",
    "🛡️ Quality Assurance",
])

# -------------------------------------------------------------
# TAB 1: EXECUTIVE COMMAND CENTER
# -------------------------------------------------------------
with tab_cmd_center:
    st.subheader("⚡ Executive Operational Overview")

    total_roster = (
        filtered_attendance_df["Agent Name"].nunique()
        if not filtered_attendance_df.empty
        else (filtered_df["Agent Name"].nunique() if not filtered_df.empty else 0)
    )
    overall_adh = filtered_df["Adherence_%"].mean() if not filtered_df.empty else np.nan
    total_unjustified = (
        int(pd.to_numeric(filtered_attendance_df.get("Unjustified Absences", 0), errors="coerce").sum())
        if not filtered_attendance_df.empty
        else 0
    )
    qa_avg_overall = (
        filtered_qa_df["QA_Score_Numeric"].mean()
        if not filtered_qa_df.empty and "QA_Score_Numeric" in filtered_qa_df.columns
        else np.nan
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("👥 Active Roster Headcount", f"{total_roster} Agents")
    c2.metric(
        "🎯 Status Adherence Score",
        f"{overall_adh:.2f}%" if not np.isnan(overall_adh) else "N/A",
        delta=f"{overall_adh - 88.0:+.2f}% vs Goal" if not np.isnan(overall_adh) else None,
    )
    c3.metric("⚠️ Total Unjustified Absences", f"{total_unjustified}")
    c4.metric(
        "🛡️ Average QA Score",
        f"{qa_avg_overall:.2f}%" if not pd.isna(qa_avg_overall) else "No Audits",
    )

    st.divider()

    col_left, col_right = st.columns([1.5, 1])

    with col_left:
        st.markdown("### 📈 Adherence Trend & Lost Time Over Time")
        if not filtered_df.empty and "week" in filtered_df.columns:
            weekly_cmd = (
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

            fig_cmd = make_subplots(specs=[[{"secondary_y": True}]])
            fig_cmd.add_trace(
                go.Scatter(
                    x=weekly_cmd["week"],
                    y=weekly_cmd["Avg_Adherence"],
                    name="Adherence %",
                    mode="lines+markers+text",
                    text=[f"{v:.1f}%" for v in weekly_cmd["Avg_Adherence"]],
                    textposition="top center",
                    line=dict(color="#007AC1", width=3),
                ),
                secondary_y=False,
            )
            fig_cmd.add_hline(
                y=88.0,
                line_dash="dash",
                line_color="red",
                annotation_text="88% Target",
                secondary_y=False,
            )
            fig_cmd.add_trace(
                go.Bar(
                    x=weekly_cmd["week"],
                    y=weekly_cmd["Total_Lost_Mins"],
                    name="Lost Mins",
                    opacity=0.3,
                    marker_color="#FF4B4B",
                ),
                secondary_y=True,
            )
            fig_cmd.update_layout(
                hovermode="x unified",
                margin=dict(l=10, r=10, t=20, b=10),
                legend=dict(orientation="h", y=1.1),
            )
            fig_cmd.update_yaxes(range=[50, 105], secondary_y=False)
            st.plotly_chart(fig_cmd, use_container_width=True)
        else:
            st.info("No adherence trend data available for selected scope.")

    with col_right:
        st.markdown("### 🚨 High Risk Agents (Adherence < 88%)")
        if not filtered_df.empty:
            at_risk = filtered_df[filtered_df["Adherence_%"] < 88.0][
                ["Agent Name", "Account", "Adherence_%", "Total_Lost_Mins"]
            ].sort_values(by="Adherence_%", ascending=True)

            if not at_risk.empty:
                at_risk["Adherence_%"] = at_risk["Adherence_%"].apply(lambda x: f"{x:.2f}%")
                st.dataframe(
                    deduplicate_dataframe_columns(at_risk),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.success("🎉 All agents are currently meeting or exceeding the 88% goal!")
        else:
            st.info("No agent risk records found.")

# -------------------------------------------------------------
# TAB 2: ATTENDANCE
# -------------------------------------------------------------
with tab_attendance:
    a_col1, a_col2 = st.columns([2.5, 1.5])
    with a_col1:
        st.subheader("📅 Attendance Tracker & Pivot Summary")
    with a_col2:
        st.markdown(
            "[🔗 Main Attendance Sheet](https://docs.google.com/spreadsheets/d/1PUerkTX4iCaFUP27FXV34azza6L5LpFYsb1nHVKrH-c/edit#gid=601856217)"
        )
        st.markdown(
            "[🔗 Pivot Attendance Summary](https://docs.google.com/spreadsheets/d/1kzXr88ueah-Gg0gVI4bhl1peFdWYgy0nIFRkZOl0RK0/edit#gid=243149129)"
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

        st.write("### 📌 Attendance Point Infractions (Rolling 60-Day Pivot Tracker)")
        if not pivot_attendance_df.empty:
            st.dataframe(
                deduplicate_dataframe_columns(pivot_attendance_df),
                use_container_width=True,
                hide_index=True,
            )

        st.divider()
        st.write("### 📋 Primary Attendance Log")
        st.dataframe(
            deduplicate_dataframe_columns(filtered_attendance_df),
            use_container_width=True,
            hide_index=True,
        )

# -------------------------------------------------------------
# TAB 3: STATUS ADHERENCE
# -------------------------------------------------------------
with tab_adherence:
    sub_tab_combined, sub_tab_tds, sub_tab_transdev = st.tabs([
        "🌐 Combined Overview",
        "🏢 TDS Operations",
        "🚌 TransDev (SD & OC)",
    ])

    def render_adherence_dashboard(dataset_df, label_title):
        if dataset_df.empty:
            st.info(f"No adherence data available for {label_title}.")
            return

        m1, m2, m3, m4 = st.columns(4)
        overall_adherence = dataset_df["Adherence_%"].mean()
        non_compliant_count = len(dataset_df[dataset_df["Adherence_%"] < 88.0])
        delta_val = overall_adherence - 88.0 if not np.isnan(overall_adherence) else None
        total_overage = dataset_df["Exceeded_Break_Mins"].sum()

        with m1:
            st.metric(
                "🎯 Adherence %",
                f"{overall_adherence:.2f}%" if not np.isnan(overall_adherence) else "N/A",
                delta=f"{delta_val:+.2f}% vs Goal (88%)" if delta_val is not None else None,
            )
        with m2:
            st.metric(
                "🚨 Agents Below 88%",
                f"{non_compliant_count} Agents",
                delta=(
                    "Needs Attention"
                    if non_compliant_count > 0
                    else "All Compliant"
                ),
                delta_color=(
                    "inverse" if non_compliant_count > 0 else "normal"
                ),
            )
        with m3:
            st.metric("⏱️ Break Overage", f"{int(total_overage)} Mins")
        with m4:
            st.metric(
                "👥 Total Tracked Agents", f"{dataset_df['Agent Name'].nunique()}"
            )

        st.divider()

        col_acc, col_role = st.columns(2)
        with col_acc:
            st.markdown("### 📁 Adherence Breakdown by Account/Source")
            if "Account" in dataset_df.columns:
                acc_summary = dataset_df.groupby("Account", as_index=False).agg(
                    Avg_Adherence=("Adherence_%", "mean"),
                    Agents_Below_Goal=("Goal_Met", lambda x: (~x).sum()),
                )
                acc_summary["Avg_Adherence"] = acc_summary["Avg_Adherence"].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "N/A")
                st.dataframe(
                    deduplicate_dataframe_columns(acc_summary),
                    use_container_width=True,
                    hide_index=True,
                )

        with col_role:
            st.markdown("### 💼 Adherence Breakdown by Role")
            if "role" in dataset_df.columns:
                role_summary = dataset_df.groupby("role", as_index=False).agg(
                    Avg_Adherence=("Adherence_%", "mean"),
                    Agents_Below_Goal=("Goal_Met", lambda x: (~x).sum()),
                )
                role_summary["Avg_Adherence"] = role_summary["Avg_Adherence"].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "N/A")
                st.dataframe(
                    deduplicate_dataframe_columns(role_summary),
                    use_container_width=True,
                    hide_index=True,
                )

        st.divider()
        st.markdown(f"### 📋 Detailed Log ({label_title})")
        display_log = dataset_df.sort_values(by="Adherence_%", ascending=True).copy()

        if "Adherence_%" in display_log.columns:
            display_log["Adherence_%"] = display_log["Adherence_%"].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "N/A")

        st.dataframe(
            deduplicate_dataframe_columns(display_log),
            use_container_width=True,
            hide_index=True,
        )

    with sub_tab_combined:
        render_adherence_dashboard(filtered_df, "All Combined Operations")

    with sub_tab_tds:
        tds_data = (
            filtered_df[filtered_df["Source_Sheet"] == "TDS"]
            if not filtered_df.empty
            else pd.DataFrame()
        )
        render_adherence_dashboard(tds_data, "TDS Operations")

    with sub_tab_transdev:
        transdev_data = (
            filtered_df[filtered_df["Source_Sheet"] == "TransDev SD & OC"]
            if not filtered_df.empty
            else pd.DataFrame()
        )
        render_adherence_dashboard(transdev_data, "TransDev Operations")

# -------------------------------------------------------------
# TAB 4: OPERATIONAL KPIS
# -------------------------------------------------------------
with tab_ops_kpi:
    st.subheader("📊 Operational KPI View")
    col_cdmx, col_tj = st.columns(2)

    with col_cdmx:
        st.markdown("#### 🏢 CDMX Operational KPIs")
        if not cdmx_kpis_df.empty:
            st.dataframe(deduplicate_dataframe_columns(cdmx_kpis_df), use_container_width=True, hide_index=True)
        else:
            st.info("No CDMX KPI data loaded.")

    with col_tj:
        st.markdown("#### 🌊 Tijuana Operational KPIs")
        if not tj_kpis_df.empty:
            st.dataframe(deduplicate_dataframe_columns(tj_kpis_df), use_container_width=True, hide_index=True)
        else:
            st.info("No Tijuana KPI data loaded.")

    st.divider()
    st.markdown("#### 📈 CDMX Weekly Performance Trends")
    if not cdmx_weekly_trends_df.empty:
        st.dataframe(deduplicate_dataframe_columns(cdmx_weekly_trends_df), use_container_width=True, hide_index=True)

# -------------------------------------------------------------
# TAB 5: 360° AGENT SCORECARD
# -------------------------------------------------------------
with tab_agent_360:
    st.subheader("👤 360° Agent Performance Scorecard")
    if not master_scorecard_df.empty:
        selected_agent = st.selectbox(
            "Select Agent to Audit:",
            options=sorted(master_scorecard_df["Agent Name"].unique()),
        )
        agent_profile = master_scorecard_df[master_scorecard_df["Agent Name"] == selected_agent].iloc[0]

        p1, p2, p3, p4 = st.columns(4)
        p1.metric(
            "⚠️ Unjustified Absences",
            f"{int(agent_profile['Unjustified Absences'])} Absences",
        )
        p2.metric(
            "⏱️ Lateness Total",
            f"{int(agent_profile['Late Minutes'])} Mins",
        )
        adh_val = agent_profile["Adherence %"]
        p3.metric(
            "🎯 Status Adherence",
            f"{adh_val:.2f}%" if not pd.isna(adh_val) else "N/A",
            delta=f"{adh_val - 88.0:+.2f}% vs Goal" if not pd.isna(adh_val) else None,
        )
        qa_val = agent_profile["QA Avg Score"]
        p4.metric(
            "🛡️ QA Score Avg",
            f"{qa_val:.2f}%" if not pd.isna(qa_val) else "No Audits",
        )

        st.divider()
        st.markdown("### 📊 Master Agent Profile Matrix")

        scorecard_display = master_scorecard_df.copy()
        if "Adherence %" in scorecard_display.columns:
            scorecard_display["Adherence %"] = scorecard_display["Adherence %"].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "N/A")
        if "QA Avg Score" in scorecard_display.columns:
            scorecard_display["QA Avg Score"] = scorecard_display["QA Avg Score"].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "N/A")

        st.dataframe(
            deduplicate_dataframe_columns(scorecard_display),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No consolidated agent records available.")

# -------------------------------------------------------------
# TAB 6: SERVICE HOURS & FORECAST
# -------------------------------------------------------------
with tab_service_hours:
    st.subheader("⏱️ Service Hours & Capacity Forecast")

    if not filtered_raw_df.empty:
        actual_hours_df = filtered_raw_df.groupby(["Account", "site"], as_index=False).agg(
            Days_Logged=(
                ("Date", "count")
                if "Date" in filtered_raw_df.columns
                else ("Total Break_Mins", "count")
            ),
            Exceeded_Break_Mins=("Exceeded_Break_Raw_Mins", "sum"),
            Unaccounted_Mins=("Unaccounted_Mins", "sum"),
        )
        actual_hours_df["Scheduled_Hours"] = actual_hours_df["Days_Logged"] * 8.0
        actual_hours_df["Lost_Hours"] = (
            actual_hours_df["Exceeded_Break_Mins"] + actual_hours_df["Unaccounted_Mins"]
        ) / 60.0
        actual_hours_df["Actual_Hours"] = actual_hours_df["Scheduled_Hours"] - actual_hours_df["Lost_Hours"]

        if not service_forecast_df.empty and "Account" in service_forecast_df.columns:
            forecast_summary = service_forecast_df.groupby("Account", as_index=False).agg(
                Forecasted_Hours=("Forecasted_Hours_Numeric", "sum")
            )
            merged_hours = pd.merge(actual_hours_df, forecast_summary, on="Account", how="left")
            merged_hours["Forecasted_Hours"] = merged_hours["Forecasted_Hours"].fillna(merged_hours["Scheduled_Hours"])
        else:
            merged_hours = actual_hours_df.copy()
            merged_hours["Forecasted_Hours"] = merged_hours["Scheduled_Hours"]

        merged_hours["Fulfillment_%"] = (
            merged_hours["Actual_Hours"] / merged_hours["Forecasted_Hours"]
        ) * 100.0

        st.dataframe(
            deduplicate_dataframe_columns(merged_hours),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No capacity logs found for selected filters.")

# -------------------------------------------------------------
# TAB 7: QUALITY ASSURANCE
# -------------------------------------------------------------
with tab_qa:
    st.subheader("🛡️ Virtual Quality Assurance (QA) Engine")

    if not filtered_qa_df.empty and "QA_Score_Numeric" in filtered_qa_df.columns:
        valid_qa = filtered_qa_df.dropna(subset=["QA_Score_Numeric"])

        q1, q2, q3 = st.columns(3)
        q1.metric("📋 Total QA Audits", f"{len(valid_qa)}")
        q2.metric("🎯 Average Score", f"{valid_qa['QA_Score_Numeric'].mean():.2f}%")
        q3.metric(
            "⚠️ Critical Low Scores (<85%)",
            f"{len(valid_qa[valid_qa['QA_Score_Numeric'] < 85.0])}",
        )

        st.divider()

        col_qa1, col_qa2 = st.columns(2)
        with col_qa1:
            st.markdown("### 📊 QA Audit Score Distribution")
            fig_qa = px.histogram(
                valid_qa,
                x="QA_Score_Numeric",
                nbins=10,
                color_discrete_sequence=["#007AC1"],
                labels={"QA_Score_Numeric": "QA Score (%)"},
            )
            fig_qa.update_layout(margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig_qa, use_container_width=True)

        with col_qa2:
            st.markdown("### 📋 Evaluator Audit Summary")
            if "Evaluator" in valid_qa.columns:
                eval_summary = valid_qa.groupby("Evaluator", as_index=False).agg(
                    Audits_Conducted=("QA_Score_Numeric", "count"),
                    Avg_Score=("QA_Score_Numeric", "mean"),
                )
                eval_summary["Avg_Score"] = eval_summary["Avg_Score"].apply(lambda x: f"{x:.2f}%")
                st.dataframe(
                    deduplicate_dataframe_columns(eval_summary),
                    use_container_width=True,
                    hide_index=True,
                )

        st.divider()
        st.markdown("### 📋 Primary Virtual QA Log")
        st.dataframe(
            deduplicate_dataframe_columns(filtered_qa_df),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No QA data available under selected scope.")
