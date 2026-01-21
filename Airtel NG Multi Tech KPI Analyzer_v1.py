import streamlit as st
import pandas as pd

st.set_page_config(page_title="OSS KPI Analyzer", layout="wide")

st.title("📊 OSS KPI Analyzer (BBH + DAY)")

# ---------------------------------------------------
# UPLOAD OSS FILES
# ---------------------------------------------------
st.header("1️⃣ Upload OSS Files")

oss1_file = st.file_uploader("Upload OSS 1 Excel", type=["xlsx"], key="oss1")
oss2_file = st.file_uploader("Upload OSS 2 Excel", type=["xlsx"], key="oss2")

# ---------------------------------------------------
# FUNCTION TO READ SHEET NAMES
# ---------------------------------------------------
def get_sheet_names(uploaded_file):
    if uploaded_file is None:
        return []
    xls = pd.ExcelFile(uploaded_file)
    return xls.sheet_names

# ---------------------------------------------------
# OSS 1 SHEET SELECTION
# ---------------------------------------------------
if oss1_file:
    st.subheader("📂 OSS 1 – Sheet Selection")

    oss1_sheets = get_sheet_names(oss1_file)

    col1, col2 = st.columns(2)
    with col1:
        oss1_bbh_sheet = st.selectbox(
            "Select BBH Sheet (OSS 1)",
            options=oss1_sheets,
            key="oss1_bbh"
        )
    with col2:
        oss1_day_sheet = st.selectbox(
            "Select DAY Sheet (OSS 1)",
            options=oss1_sheets,
            key="oss1_day"
        )

# ---------------------------------------------------
# OSS 2 SHEET SELECTION
# ---------------------------------------------------
if oss2_file:
    st.subheader("📂 OSS 2 – Sheet Selection")

    oss2_sheets = get_sheet_names(oss2_file)

    col1, col2 = st.columns(2)
    with col1:
        oss2_bbh_sheet = st.selectbox(
            "Select BBH Sheet (OSS 2)",
            options=oss2_sheets,
            key="oss2_bbh"
        )
    with col2:
        oss2_day_sheet = st.selectbox(
            "Select DAY Sheet (OSS 2)",
            options=oss2_sheets,
            key="oss2_day"
        )

# ---------------------------------------------------
# KPI SELECTION
# ---------------------------------------------------
st.header("2️⃣ Select KPIs")

default_kpis = [
    "TCH_Availability",
    "AccessibilityCSSR",
    "SDCCH Blocking",
    "TCH Blocking (User Perceived)",
    "SDCCH Drop",
    "CDR_2G",
    "HOSR_HW_2G",
    "TotalTrafficErlangs",
    "Total_Data_Traffic_HW",
    "Cell avail accuracy 1s cellL"
]

selected_kpis = st.multiselect(
    "Choose KPIs to Process",
    options=default_kpis,
    default=default_kpis
)

# ---------------------------------------------------
# PROCESS BUTTON
# ---------------------------------------------------
st.header("3️⃣ Process & Generate Output")

if st.button("🚀 Generate KPI Report"):

    if not oss1_file and not oss2_file:
        st.error("Please upload at least one OSS file.")
        st.stop()

    dfs_bbh = []
    dfs_day = []

    # ---- OSS 1 ----
    if oss1_file:
        df_bbh_oss1 = pd.read_excel(oss1_file, sheet_name=oss1_bbh_sheet)
        df_day_oss1 = pd.read_excel(oss1_file, sheet_name=oss1_day_sheet)

        dfs_bbh.append(df_bbh_oss1)
        dfs_day.append(df_day_oss1)

    # ---- OSS 2 ----
    if oss2_file:
        df_bbh_oss2 = pd.read_excel(oss2_file, sheet_name=oss2_bbh_sheet)
        df_day_oss2 = pd.read_excel(oss2_file, sheet_name=oss2_day_sheet)

        dfs_bbh.append(df_bbh_oss2)
        dfs_day.append(df_day_oss2)

    # ---------------------------------------------------
    # COMBINE DATA
    # ---------------------------------------------------
    df_bbh = pd.concat(dfs_bbh, ignore_index=True)
    df_day = pd.concat(dfs_day, ignore_index=True)

    st.success("OSS files loaded successfully!")

    st.write("🔍 BBH Data Preview")
    st.dataframe(df_bbh.head())

    st.write("🔍 DAY Data Preview")
    st.dataframe(df_day.head())

    # ---------------------------------------------------
    # 👉 HERE you plug your FINAL KPI LOGIC
    # (the exact script you finalized earlier)
    # ---------------------------------------------------

    st.info("⚙️ KPI processing logic will run here (final script integration)")

    # Example output
    output_file = "2G_FINAL_OUTPUT.xlsx"
    # final_df.to_excel(output_file, index=False)

    st.success("✅ KPI Report Generated Successfully!")
    st.download_button(
        "📥 Download Output Excel",
        data=open(output_file, "rb"),
        file_name=output_file
    )
