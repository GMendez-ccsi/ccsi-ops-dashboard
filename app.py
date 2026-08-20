@st.cache_data(ttl=1800)
def load_all_combined_data_v6():
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
    
    # Robust multi-format Date Parser for TDS & TransDev
    if "Date" in combined_df.columns:
        parsed_dates = pd.to_datetime(combined_df["Date"], errors="coerce", format="mixed")
        combined_df["month"] = parsed_dates.dt.strftime("%B %Y").fillna("August 2026")
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
