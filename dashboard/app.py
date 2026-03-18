import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from data.database import get_session, init_db, check_db_size
from dashboard.utils import (
    load_candidates_df,
    load_quizzes_df,
)
from dashboard.components.sidebar import render_sidebar
from dashboard.components.overview import render_overview
from dashboard.components.candidate_detail import render_candidate_table
from dashboard.components.score_trends import render_score_distribution


st.set_page_config(
    page_title="Kaplan RE Prep Tracker",
    page_icon=":mortar_board:",
    layout="wide",
)

st.title("Kaplan Real Estate Exam Prep Tracker")


@st.cache_resource
def get_db_engine():
    return init_db()


def get_db_session():
    engine = get_db_engine()
    return get_session(engine)


# --- Database size warning (Supabase free tier: 500 MB) ---
@st.cache_data(ttl=3600)  # check once per hour
def _db_usage():
    engine = get_db_engine()
    return check_db_size(engine)

usage = _db_usage()
if usage and usage["warn"]:
    st.warning(
        f"Database usage: {usage['size_mb']} MB / {usage['limit_mb']} MB "
        f"(Supabase free tier). Consider cleaning old data to avoid charges."
    )


@st.cache_data(ttl=300)
def load_all_data():
    session = get_db_session()
    candidates = load_candidates_df(session)
    quizzes = load_quizzes_df(session)
    return candidates, quizzes


# Load data
candidates_df, quizzes_df = load_all_data()

# Sidebar filters
candidate_names = candidates_df["name"].tolist() if not candidates_df.empty else []
filters = render_sidebar(candidate_names)

# Apply filters
if not candidates_df.empty:
    filtered_df = candidates_df[
        candidates_df["name"].isin(filters["candidates"])
        & candidates_df["risk_status"].isin(filters["risk_filter"])
    ]
else:
    filtered_df = candidates_df

# Overview
render_overview(filtered_df)

st.divider()

# Candidate progress table
render_candidate_table(filtered_df)

st.divider()

# Score distribution
render_score_distribution(quizzes_df, filters["candidates"])
