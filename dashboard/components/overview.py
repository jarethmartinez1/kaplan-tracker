import streamlit as st
import pandas as pd


def render_overview(df: pd.DataFrame):
    """Render overview summary cards."""
    if df.empty:
        st.info("No candidate data available. Run the scraper first.")
        return

    st.subheader("Overview")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Candidates", len(df))

    with col2:
        avg_completion = df["completion_pct"].mean()
        st.metric("Avg Completion", f"{avg_completion:.0f}%")

    with col3:
        avg_score = df["avg_quiz_score"].dropna().mean()
        score_display = f"{avg_score:.0f}%" if pd.notna(avg_score) else "N/A"
        st.metric("Avg Quiz Score", score_display)

    with col4:
        at_risk = len(df[df["risk_status"].isin(["at_risk", "behind"])])
        on_pace = len(df[df["risk_status"] == "on_pace"])
        st.metric("On Pace / At Risk", f"{on_pace} / {at_risk}")
