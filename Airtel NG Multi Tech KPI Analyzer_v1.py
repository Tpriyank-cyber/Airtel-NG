import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Multi-Tech KPI Analyzer", layout="wide")
st.title("📊 OSS KPI Analyzer (BBH / DAY Selection)")

# ---------------------------------------------------
# FILE UPLOAD
# ---------------------------------------------------
uploaded_files = st.file_uploader(
    "Upload OSS Excel Files",
    type=["xlsx"],
    accept_multiple_files=True
)

if not uploaded_files:
    st.stop()

# ---------------------------------------------------
# SHEET SELECTION PER FILE
# ---------------------------------------------------
st.subheader("📄 Sheet Selection")

bbh_dfs = []
day_dfs = []

for file in uploaded_files:
    st.markdown(f"### 📘 {file.name}")
    xls = pd.ExcelFile(file)
    sheets = xls.sheet_names

    col1, col2 = st.columns(2)

    with col1:
        bbh_sheet = st.selectbox(
            "Select BBH Sheet",
            options=["None"] + sheets,
            key=f"bbh_{file.name}"
        )

    with col2:
        day_sheet = st.selectbox(
            "Select DAY Sheet",
            options=["None"] + sheets,
            key=f"day_{file.name}"
        )

    if bbh_sheet != "None":
        df_bbh = pd.read_excel(file, sheet_name=bbh_sheet)
        df_bbh["__SOURCE__"] = file.name
        df_bbh["__TYPE__"] = "BBH"
        bbh_dfs.append(df_bbh)

    if day_sheet != "None":
        df_day = pd.read_excel(file, sheet_name=day_sheet)
        df_day["__SOURCE__"] = file.name
        df_day["__TYPE__"] = "DAY"
        day_dfs.append(df_day)

# ---------------------------------------------------
# COMBINE DATA
# ---------------------------------------------------
df_bbh = pd.concat(bbh_dfs, ignore_index=True) if bbh_dfs else None
df_day = pd.concat(day_dfs, ignore_index=True) if day_dfs else None

if df_bbh is None and df_day is None:
    st.error("❌ Please select at least one BBH or DAY sheet")
    st.stop()

# ---------------------------------------------------
# COLUMN DISCOVERY
# ---------------------------------------------------
sample_df = df_bbh if df_bbh is not None else df_day
available_columns = sample_df.columns.tolist()

st.subheader("🧱 Available Columns")
st.write(available_columns)

# ---------------------------------------------------
# USER CONFIGURATION
# ---------------------------------------------------
st.subheader("⚙️ Configuration")

segment_col = st.selectbox(
    "Segment Column",
    [c for c in available_columns if "segment" in c.lower()]
)

bsc_col = st.selectbox(
    "BSC Column",
    [c for c in available_columns if "bsc" in c.lower()]
)

time_col = st.selectbox(
    "Time Column",
    [c for c in available_columns if "time" in c.lower()]
)

kpi_cols = st.multiselect(
    "Select KPIs",
    [c for c in available_columns if c not in [segment_col, bsc_col, time_col]]
)

# ---------------------------------------------------
# THRESHOLDS
# ---------------------------------------------------
st.subheader("🎯 Thresholds")

thresholds = {}
for kpi in kpi_cols:
    c1, c2 = st.columns(2)
    with c1:
        op = st.selectbox(f"{kpi} Operator", [">=", "<="], key=f"op_{kpi}")
    with c2:
        val = st.number_input(f"{kpi} Threshold", value=0.0, key=f"val_{kpi}")
    thresholds[kpi] = (op, val)

rna_kpi = st.selectbox("RNA Availability KPI", kpi_cols)

traffic_kpis = st.multiselect(
    "Traffic / Data KPIs (No RNA remark)",
    kpi_cols
)

# ---------------------------------------------------
# PROCESS
# ---------------------------------------------------
if st.button("🚀 Process Data"):

    final_long = []

    def prepare_df(df):
        df = df.drop(index=1, errors="ignore").reset_index(drop=True)
        df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
        df["DATE"] = df[time_col].dt.strftime("%d-%b")
        keep = [bsc_col, segment_col, "DATE"] + kpi_cols
        return df[keep]

    if df_bbh is not None:
        final_long.append(prepare_df(df_bbh))
    if df_day is not None:
        final_long.append(prepare_df(df_day))

    df_all = pd.concat(final_long, ignore_index=True)

    df_long = df_all.melt(
        id_vars=[bsc_col, segment_col, "DATE"],
        value_vars=kpi_cols,
        var_name="KPI",
        value_name="VALUE"
    )

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
    def remark(row):
        kpi = row["KPI"]
        v = row[last_date]

        if pd.isna(v):
            return "NO DATA"

        if kpi == rna_kpi and v == 0:
            return "SITE/CELL DOWN"

        op, thr = thresholds.get(kpi, (None, None))
        remark = "KPI Stable/Meeting Threshold"
        broken = False

        if op:
            if not ((op == ">=" and v >= thr) or (op == "<=" and v <= thr)):
                remark = "KPI not ok"
                broken = True

        if broken and kpi not in traffic_kpis:
            mask = (
                (final_df[bsc_col] == row[bsc_col]) &
                (final_df[segment_col] == row[segment_col]) &
                (final_df["KPI"] == rna_kpi)
            )
            if not final_df.loc[mask].empty:
                rna_val = round(float(final_df.loc[mask, last_date].values[0]), 2)
                r_op, r_thr = thresholds[rna_kpi]
                if not ((r_op == ">=" and rna_val >= r_thr) or
                        (r_op == "<=" and rna_val <= r_thr)):
                    remark += f", RNA UNSTABLE {rna_val}%"

        return remark

    final_df["REMARKS"] = final_df.apply(remark, axis=1)
    final_df[date_cols] = final_df[date_cols].round(2)

    # ---------------------------------------------------
    # DOWNLOAD
    # ---------------------------------------------------
    buffer = BytesIO()
    final_df.to_excel(buffer, index=False)
    buffer.seek(0)

    st.success("✅ Processing Completed")
    st.download_button(
        "⬇️ Download Final Excel",
        buffer,
        "KPI_FINAL_OUTPUT.xlsx"
    )

    st.dataframe(final_df)
