import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def render_score_distribution(quizzes_df: pd.DataFrame, selected_candidates: list[str]):
    """Render a histogram showing score distribution across candidates."""
    st.subheader("Score Distribution")

    if quizzes_df.empty:
        st.info("No quiz data available yet.")
        return

    filtered = quizzes_df[quizzes_df["candidate_name"].isin(selected_candidates)]
    if filtered.empty:
        st.info("No quiz data for selected candidates.")
        return

    fig = px.histogram(
        filtered,
        x="score",
        nbins=15,
        color_discrete_sequence=["#4361ee"],
        labels={"score": "Exam Score (%)", "count": "Number of Candidates"},
    )

    # Add passing score line
    passing = filtered["passing_score"].dropna()
    if not passing.empty:
        avg_passing = passing.mean()
        fig.add_vline(
            x=avg_passing,
            line_dash="dash",
            line_color="red",
            annotation_text=f"Passing ({avg_passing:.0f}%)",
            annotation_position="top right",
        )

    # Add mean score line
    mean_score = filtered["score"].mean()
    fig.add_vline(
        x=mean_score,
        line_dash="dot",
        line_color="green",
        annotation_text=f"Avg ({mean_score:.0f}%)",
        annotation_position="top left",
    )

    fig.update_layout(
        height=400,
        margin=dict(l=20, r=20, t=30, b=20),
        bargap=0.05,
        xaxis_title="Exam Score (%)",
        yaxis_title="Number of Exams",
    )

    st.plotly_chart(fig, use_container_width=True)

    # Summary stats below the chart
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Lowest", f"{filtered['score'].min():.0f}%")
    with col2:
        st.metric("Average", f"{mean_score:.0f}%")
    with col3:
        st.metric("Highest", f"{filtered['score'].max():.0f}%")
    with col4:
        pass_rate = (filtered["passed"].sum() / len(filtered) * 100) if len(filtered) > 0 else 0
        st.metric("Pass Rate", f"{pass_rate:.0f}%")
