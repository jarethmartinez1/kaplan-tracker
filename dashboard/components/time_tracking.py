import streamlit as st
import pandas as pd
import plotly.express as px


def render_time_charts(sessions_df: pd.DataFrame, selected_candidates: list[str]):
    """Render study time bar charts."""
    st.subheader("Study Time")

    if sessions_df.empty:
        st.info("No study session data available yet.")
        return

    filtered = sessions_df[sessions_df["candidate_name"].isin(selected_candidates)].copy()
    if filtered.empty:
        st.info("No study session data for selected candidates.")
        return

    # Convert to hours and aggregate by week
    filtered["hours"] = filtered["duration_minutes"] / 60
    filtered["session_date"] = pd.to_datetime(filtered["session_date"])
    filtered["week"] = filtered["session_date"].dt.to_period("W").dt.start_time

    weekly = (
        filtered.groupby(["week", "candidate_name"])["hours"]
        .sum()
        .reset_index()
    )

    fig = px.bar(
        weekly,
        x="week",
        y="hours",
        color="candidate_name",
        barmode="group",
        labels={"week": "Week", "hours": "Hours", "candidate_name": "Candidate"},
    )

    fig.update_layout(
        height=400,
        margin=dict(l=20, r=20, t=30, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    st.plotly_chart(fig, use_container_width=True)
