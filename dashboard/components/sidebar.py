from datetime import date, timedelta

import streamlit as st


def render_sidebar(candidate_names: list[str]) -> dict:
    """Render sidebar filters and return filter state."""
    st.sidebar.title("Filters")

    # Candidate filter
    selected_candidates = st.sidebar.multiselect(
        "Candidates",
        options=candidate_names,
        default=candidate_names,
        help="Select candidates to display",
    )

    # Date range
    st.sidebar.subheader("Date Range")
    default_start = date.today() - timedelta(days=90)
    date_from = st.sidebar.date_input("From", value=default_start)
    date_to = st.sidebar.date_input("To", value=date.today())

    # Risk filter
    risk_filter = st.sidebar.multiselect(
        "Status",
        options=["on_track", "at_risk", "behind", "overdue", "complete", "not_started", "inactive", "unknown"],
        default=["on_track", "at_risk", "behind", "overdue", "complete"],
    )

    st.sidebar.divider()

    # Refresh button
    if st.sidebar.button("Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    return {
        "candidates": selected_candidates,
        "date_from": date_from,
        "date_to": date_to,
        "risk_filter": risk_filter,
    }
