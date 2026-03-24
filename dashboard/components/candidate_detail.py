import streamlit as st
import pandas as pd


STATUS_LABELS = {
    "on_pace": "On Pace",
    "at_risk": "At Risk",
    "behind": "Behind",
    "complete": "Complete",
    "not_started": "Not Started",
    "inactive": "Inactive",
    "unknown": "Unknown",
}


def _format_hrs_per_week(hrs, status):
    if status in ("not_started", "inactive"):
        return "--"
    if pd.isna(hrs):
        return "--"
    return f"{hrs:.1f}"


def render_candidate_table(df: pd.DataFrame):
    """Render per-candidate progress as a sortable, searchable dataframe."""
    if df.empty:
        return

    st.subheader("Candidate Progress")

    # Search box
    search = st.text_input("Search candidates", placeholder="Type a name...")
    if search:
        df = df[df["name"].str.contains(search, case=False, na=False)]

    # Build display dataframe
    display_df = pd.DataFrame({
        "Name": df["name"],
        "Completion": df["completion_pct"].apply(lambda x: f"{x:.0f}%" if pd.notna(x) else "--"),
        "Avg Hrs/Week": df.apply(
            lambda r: _format_hrs_per_week(r["avg_hrs_per_week"], r["risk_status"]),
            axis=1,
        ),
        "Avg Score": df["avg_quiz_score"].apply(lambda x: f"{x:.0f}%" if pd.notna(x) else "--"),
        "Status": df["risk_status"].map(STATUS_LABELS).fillna("Unknown"),
    })

    # Sort by completion ascending so in-progress candidates appear first
    display_df = display_df.sort_values("Name").reset_index(drop=True)

    st.dataframe(
        display_df,
        use_container_width=True,
        height=500,
        column_config={
            "Name": st.column_config.TextColumn("Name", width="medium"),
            "Completion": st.column_config.TextColumn("Completion", width="small"),
            "Avg Hrs/Week": st.column_config.TextColumn("Avg Hrs/Week", width="small"),
            "Avg Score": st.column_config.TextColumn("Avg Score", width="small"),
            "Status": st.column_config.TextColumn("Status", width="small"),
        },
        hide_index=True,
    )

    st.caption(f"Showing {len(display_df)} of {len(df)} candidates")
