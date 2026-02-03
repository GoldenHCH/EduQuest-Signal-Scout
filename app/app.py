#!/usr/bin/env python3
"""Streamlit viewer for Utah Board Signal Scout.

Usage:
    streamlit run app/app.py
"""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings

# Page config
st.set_page_config(
    page_title="Utah Board Signal Scout",
    page_icon="🎯",
    layout="wide",
)

# Title
st.title("🎯 Utah Board Signal Scout")
st.markdown("*Buying signals from Utah school board meetings*")

# Load data
@st.cache_data
def load_signals():
    """Load signals from CSV."""
    if not settings.signals_csv.exists():
        return None
    return pd.read_csv(settings.signals_csv)


signals_df = load_signals()

if signals_df is None or signals_df.empty:
    st.warning("No signals found. Run the pipeline first:")
    st.code("python scripts/run_weekly.py --limit-districts 5 --limit-docs 3")
    st.stop()

# Sidebar filters
st.sidebar.header("Filters")

# Score filter
min_score, max_score = st.sidebar.slider(
    "Opportunity Score",
    min_value=0,
    max_value=100,
    value=(50, 100),
)

# Category filter
categories = ["All"] + sorted(signals_df["category"].unique().tolist())
selected_category = st.sidebar.selectbox("Category", categories)

# District filter
districts = ["All"] + sorted(signals_df["district"].unique().tolist())
selected_district = st.sidebar.selectbox("District", districts)

# Next step filter
next_steps = ["All"] + sorted(signals_df["recommended_next_step"].unique().tolist())
selected_step = st.sidebar.selectbox("Recommended Action", next_steps)

# Apply filters
filtered_df = signals_df.copy()
filtered_df = filtered_df[
    (filtered_df["opportunity_score"] >= min_score)
    & (filtered_df["opportunity_score"] <= max_score)
]

if selected_category != "All":
    filtered_df = filtered_df[filtered_df["category"] == selected_category]

if selected_district != "All":
    filtered_df = filtered_df[filtered_df["district"] == selected_district]

if selected_step != "All":
    filtered_df = filtered_df[filtered_df["recommended_next_step"] == selected_step]

# Sort by score
filtered_df = filtered_df.sort_values("opportunity_score", ascending=False)

# Stats
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Signals", len(filtered_df))
with col2:
    st.metric("Avg Score", f"{filtered_df['opportunity_score'].mean():.1f}" if len(filtered_df) > 0 else "N/A")
with col3:
    reach_out_count = len(filtered_df[filtered_df["recommended_next_step"] == "reach_out_now"])
    st.metric("Reach Out Now", reach_out_count)
with col4:
    unique_districts = filtered_df["district"].nunique()
    st.metric("Districts", unique_districts)

st.markdown("---")

# Display signals
for idx, row in filtered_df.iterrows():
    # Color code by score
    if row["opportunity_score"] >= 70:
        color = "🔥"
    elif row["opportunity_score"] >= 50:
        color = "⚡"
    else:
        color = "💡"

    with st.expander(
        f"{color} **{row['district']}** - Score: {row['opportunity_score']} | {row['category'].replace('_', ' ').title()}"
    ):
        col1, col2 = st.columns([2, 1])

        with col1:
            st.markdown(f"**Summary:** {row['summary']}")
            st.markdown(f"**Evidence:**")
            st.info(row["evidence_snippet"])

        with col2:
            st.markdown(f"**Meeting Date:** {row.get('meeting_date', 'Unknown')}")
            st.markdown(f"**Confidence:** {row['confidence']:.0%}")
            st.markdown(f"**Category:** {row['category'].replace('_', ' ').title()}")

            next_step = row["recommended_next_step"]
            if next_step == "reach_out_now":
                st.success(f"🔥 {next_step.replace('_', ' ').title()}")
            elif next_step == "research_more":
                st.warning(f"🔍 {next_step.replace('_', ' ').title()}")
            else:
                st.info(f"👀 {next_step.replace('_', ' ').title()}")

        if row.get("source_url"):
            st.markdown(f"[📄 View Source Document]({row['source_url']})")

# Download buttons
st.markdown("---")
st.subheader("Export")

col1, col2 = st.columns(2)

with col1:
    csv_data = filtered_df.to_csv(index=False)
    st.download_button(
        label="📥 Download CSV",
        data=csv_data,
        file_name="signals_export.csv",
        mime="text/csv",
    )

with col2:
    json_data = filtered_df.to_json(orient="records", indent=2)
    st.download_button(
        label="📥 Download JSON",
        data=json_data,
        file_name="signals_export.json",
        mime="application/json",
    )

# Footer
st.markdown("---")
st.caption("Utah Board Signal Scout - 2026 GTM Hackathon by Mobly")
