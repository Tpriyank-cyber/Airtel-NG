import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="OSS KPI Processor", layout="wide")

st.title("📊 OSS KPI Processing Tool (Technology Agnostic)")

# ---------------------------------------------------
# CONSTANTS
# ---------------------------------------------------
IDENTIFIER_COLS = [
    "BSC name",
    "Segment Name",
    "Cell Name",
    "Site Name",
    "Period start time",
    "DATE",
    "Date"
]

rna_kpi_name = "TCH_Availability"   # default RNA KPI (can be changed later)

thresholds = {
    "TCH_Availability": (">=", 99.5),
    "AccessibilityCSSR": (">=", 98),
    "SDCCH Blocking": ("<=", 1.25),
    "TCH Blocking (User Perceived)": ("<=", 1.25),
    "SDCCH Drop": ("<=", 1.25),
    "CDR_2G": ("<=", 1.25),
    "HOSR_HW_2G": (">=", 90),
    "Cell avail accuracy 1s cellL": (">=", 99.5)
}

traffic_keywords = ["Traffic", "Erlang", "Data"]

# ---------------------------------------------------
# FILE UPLOAD
# ---------------------------------------------------
st.header("1️⃣ Upload OSS Files")

col1, col2 = st.columns(2)

with col1:
    oss1_file = st.file_uploader("Upload OSS-1 Excel", type=["xlsx"])

with col2:
    oss2_file = st.file_uploader("Upload OSS-2 Excel", type=["xlsx"])

# ---------------------------------------------------
# SHEET SELECTION
# ---------------------------------------------------
def get_sheets(file):
    if file is None:
        return []
    return pd.ExcelFile(file).sheet_names

st.header("2️⃣ Select BBH & DAY Sheets")

def sheet_selector(file, label):
    sheets = get_sheets(file)
    if not sheets:
        return None, None
    bbh = st.selectbox(f"{label} → Select BBH Sheet", sheets)
    day = st.selectbox(f"{label} → Select DAY Sheet", sheets)
    return bbh, day

oss1_bbh, oss1_day = sheet_selector(oss1_file, "OSS-1")
oss2_bbh, oss2_day = sheet_selector(oss2_file, "OSS-2")

# ---------------------------------------------------
# KPI DISCOVERY (DYNAMIC)
# ---------------------------------------------------
st.header("3️⃣ KPI Selection (Auto-Detected from Sheets)")

def extract_kpis(df):
    return [
        col for col in df.columns
        if col not in IDENTIFIER_COLS
    ]

kpi_candidates = set()

def load_df(file, sheet):
    if file is None or sheet is None:
        return None
    return pd.read_excel(file, sheet_name=sheet)

dfs = []

for f, b, d in [
    (oss1_file, oss1_bbh, oss1_day),
    (oss2_file, oss2_bbh, oss2_day)
]:
    df_bbh = load_df(f, b)
    df_day = load_df(f, d)
    if df_bbh is not None:
        dfs.append(df_bbh)
    if df_day is not None:
        dfs.append(df_day)

for df in dfs:
    kpi_candidates.update(extract_kpis(df))

kpi_candidates = sorted(list(kpi_candidates))

selected_kpis = st.multiselect(
    "Select KPIs to Process",
    kpi_candidates,
    default=kpi_candidates
)

# ---------------------------------------------------
# PROCESS BUTTON
# ---------------------------------------------------
st.header("4️⃣ Process Data")

if st.button("🚀 Generate KPI Report"):

    def prepare_long(df, selected_kpis):
        df = df.drop(index=1, errors="ignore")
        df["Period start time"] = pd.to_datetime(df["Period start time"])
        df["DATE"] = df["Period start time"].dt.strftime("%d-%b")

        melt_cols = [k for k in selected_kpis if k in df.columns]

        return df.melt(
            id_vars=["BSC name", "Segment Name", "DATE"],
            value_vars=melt_cols,
            var_name="KPI",
            value_name="VALUE"
        )

    all_long = []

    for f, b, d in [
        (oss1_file, oss1_bbh, oss1_day),
        (oss2_file, oss2_bbh, oss2_day)
    ]:
        df_bbh = load_df(f, b)
        df_day = load_df(f, d)

        if df_bbh is not None:
            all_long.append(prepare_long(df_bbh, selected_kpis))
        if df_day is not None:
            all_long.append(prepare_long(df_day, selected_kpis))

    df_all = pd.concat(all_long, ignore_index=True)

    final_df = df_all.pivot_table(
        index=["BSC name", "Segment Name", "KPI"],
        columns="DATE",
        values="VALUE",
        aggfunc="first"
    ).reset_index()

    # ---------------------------------------------------
    # REMARK LOGIC
    # ---------------------------------------------------
    date_cols = sorted(
        [c for c in final_df.columns if c not in ["BSC name", "Segment Name", "KPI"]],
        key=lambda x: pd.to_datetime(x, format="%d-%b")
    )

    last_date = date_cols[-1]

    def enhanced_remark(row):
        kpi = row["KPI"]
        v = row[last_date]

        if pd.isna(v):
            return "NO DATA"

        if kpi in ["TCH_Availability", "Cell avail accuracy 1s cellL"] and v == 0:
            return "SITE/CELL DOWN"

        remark = ""
        threshold_broken = False

        if kpi in thresholds:
            op, thr = thresholds[kpi]
            if (op == ">=" and v >= thr) or (op == "<=" and v <= thr):
                remark = "KPI Stable/Meeting Threshold"
            else:
                remark = "KPI not ok"
                threshold_broken = True

        is_traffic = any(word in kpi for word in traffic_keywords)

        if threshold_broken and not is_traffic:
            mask = (
                (final_df["BSC name"] == row["BSC name"]) &
                (final_df["Segment Name"] == row["Segment Name"]) &
                (final_df["KPI"] == rna_kpi_name)
            )
            if not final_df.loc[mask].empty:
                rna_val = round(float(final_df.loc[mask, last_date].values[0]), 2)
                op, thr = thresholds.get(rna_kpi_name, (None, None))
                if op and ((op == ">=" and rna_val < thr) or (op == "<=" and rna_val > thr)):
                    remark += f", RNA UNSTABLE {rna_val}%"

        return remark

    final_df["REMARKS"] = final_df.apply(enhanced_remark, axis=1)

    # ---------------------------------------------------
    # ROUND VALUES
    # ---------------------------------------------------
    value_cols = [c for c in final_df.columns if c not in ["BSC name", "Segment Name", "KPI", "REMARKS"]]
    final_df[value_cols] = final_df[value_cols].apply(pd.to_numeric, errors="coerce").round(2)

    # ---------------------------------------------------
    # EXPORT
    # ---------------------------------------------------
    buffer = BytesIO()
    final_df.to_excel(buffer, index=False)
    buffer.seek(0)

    st.success("✅ KPI Report Generated")

    st.download_button(
        label="📥 Download Excel",
        data=buffer,
        file_name="FINAL_KPI_OUTPUT.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
