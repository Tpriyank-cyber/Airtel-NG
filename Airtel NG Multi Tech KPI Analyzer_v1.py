# -*- coding: utf-8 -*-
"""
Created on Wed Jan 21 11:26:52 2026

@author: tpriyank
"""

import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Multi-Tech KPI Analyzer", layout="wide")
st.title("📊 Multi-Technology KPI Analyzer (BBH + DAY)")

# ---------------------------------------------------
# FILE UPLOAD
# ---------------------------------------------------
uploaded_files = st.file_uploader(
    "Upload OSS Excel Files (multiple allowed)",
    type=["xlsx"],
    accept_multiple_files=True
)

if not uploaded_files:
    st.stop()

# ---------------------------------------------------
# READ ALL SHEETS FROM ALL FILES
# ---------------------------------------------------
all_dfs = []
sheet_info = {}

for file in uploaded_files:
    xls = pd.ExcelFile(file)
    sheet_info[file.name] = xls.sheet_names
    for sheet in xls.sheet_names:
        df = pd.read_excel(file, sheet_name=sheet)
        df["__SOURCE_FILE__"] = file.name
        df["__SHEET__"] = sheet
        all_dfs.append(df)

raw_df = pd.concat(all_dfs, ignore_index=True)

st.subheader("📄 Detected Sheets")
st.json(sheet_info)

# ---------------------------------------------------
# COLUMN DISCOVERY
# ---------------------------------------------------
st.subheader("🧱 Available Columns")
available_columns = raw_df.columns.tolist()
st.multiselect(
    "Columns found in uploaded data:",
    available_columns,
    default=[]
)

# ---------------------------------------------------
# USER SELECTIONS
# ---------------------------------------------------
st.subheader("⚙️ Configuration")

segment_col = st.selectbox(
    "Select Segment Column",
    [c for c in available_columns if "segment" in c.lower()]
)

bsc_col = st.selectbox(
    "Select BSC Column",
    [c for c in available_columns if "bsc" in c.lower()]
)

time_col = st.selectbox(
    "Select Time Column",
    [c for c in available_columns if "time" in c.lower()]
)

kpi_cols = st.multiselect(
    "Select KPIs to Process",
    [c for c in available_columns if c not in [segment_col, bsc_col, time_col]],
)

# ---------------------------------------------------
# THRESHOLD CONFIG
# ---------------------------------------------------
st.subheader("🎯 KPI Thresholds")
thresholds = {}
for kpi in kpi_cols:
    col1, col2 = st.columns(2)
    with col1:
        op = st.selectbox(f"{kpi} Operator", [">=", "<="], key=f"op_{kpi}")
    with col2:
        val = st.number_input(f"{kpi} Threshold", value=0.0, key=f"val_{kpi}")
    thresholds[kpi] = (op, val)

rna_kpi = st.selectbox(
    "Select Availability KPI for RNA logic",
    kpi_cols
)

traffic_kpis = st.multiselect(
    "Traffic / Data KPIs (RNA will NOT apply)",
    kpi_cols
)

# ---------------------------------------------------
# PROCESS BUTTON
# ---------------------------------------------------
if st.button("🚀 Process KPI Data"):

    df = raw_df.copy()

    # ---------------------------------------------------
    # CLEAN
    # ---------------------------------------------------
    df = df.drop(index=1, errors="ignore").reset_index(drop=True)
    df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
    df["DATE"] = df[time_col].dt.strftime("%d-%b")

    # ---------------------------------------------------
    # KEEP REQUIRED ONLY
    # ---------------------------------------------------
    required_cols = [bsc_col, segment_col, "DATE"] + kpi_cols
    df = df[required_cols]

    # ---------------------------------------------------
    # UNPIVOT
    # ---------------------------------------------------
    df_long = df.melt(
        id_vars=[bsc_col, segment_col, "DATE"],
        value_vars=kpi_cols,
        var_name="KPI",
        value_name="VALUE"
    )

    # ---------------------------------------------------
    # PIVOT
    # ---------------------------------------------------
    final_df = df_long.pivot_table(
        index=[bsc_col, segment_col, "KPI"],
        columns="DATE",
        values="VALUE",
        aggfunc="first"
    ).reset_index()

    date_cols = sorted(
        [c for c in final_df.columns if c not in [bsc_col, segment_col, "KPI"]],
        key=lambda x: pd.to_datetime(x, format="%d-%b")
    )
    last_date = date_cols[-1]

    # ---------------------------------------------------
    # REMARK LOGIC
    # ---------------------------------------------------
    def enhanced_remark(row):
        kpi = row["KPI"]
        v = row[last_date]

        if pd.isna(v):
            return "NO DATA"

        if kpi == rna_kpi and v == 0:
            return "SITE/CELL DOWN"

        remark = "KPI Stable/Meeting Threshold"
        threshold_broken = False

        if kpi in thresholds:
            op, val = thresholds[kpi]
            if not ((op == ">=" and v >= val) or (op == "<=" and v <= val)):
                remark = "KPI not ok"
                threshold_broken = True

        if threshold_broken and kpi not in traffic_kpis:
            mask = (
                (final_df[bsc_col] == row[bsc_col]) &
                (final_df[segment_col] == row[segment_col]) &
                (final_df["KPI"] == rna_kpi)
            )
            if not final_df.loc[mask].empty:
                rna_val = round(float(final_df.loc[mask, last_date].values[0]), 2)
                rna_op, rna_thr = thresholds[rna_kpi]
                if not ((rna_op == ">=" and rna_val >= rna_thr) or
                        (rna_op == "<=" and rna_val <= rna_thr)):
                    remark += f", RNA UNSTABLE {rna_val}%"

        return remark

    final_df["REMARKS"] = final_df.apply(enhanced_remark, axis=1)

    # ---------------------------------------------------
    # ROUND
    # ---------------------------------------------------
    final_df[date_cols] = final_df[date_cols].apply(
        pd.to_numeric, errors="coerce"
    ).round(2)

    # ---------------------------------------------------
    # EXPORT
    # ---------------------------------------------------
    buffer = BytesIO()
    final_df.to_excel(buffer, index=False)
    buffer.seek(0)

    st.success("✅ KPI Processing Completed")
    st.download_button(
        "⬇️ Download Excel Output",
        buffer,
        file_name="KPI_FINAL_OUTPUT.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    st.dataframe(final_df)
