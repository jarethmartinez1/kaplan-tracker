import streamlit as st
import pandas as pd


STATUS_LABELS = {
    "on_track": "On Track",
    "at_risk": "At Risk",
    "behind": "Behind",
    "complete": "Complete",
    "unknown": "Unknown",
}


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
        "Projected Date": df["projected_date"].apply(
            lambda x: x.strftime("%b %d, %Y") if pd.notna(x) else "--"
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
            "Projected Date": st.column_config.TextColumn("Projected Date", width="medium"),
            "Avg Score": st.column_config.TextColumn("Avg Score", width="small"),
            "Status": st.column_config.TextColumn("Status", width="small"),
        },
        hide_index=True,
    )

    st.caption(f"Showing {len(display_df)} of {len(df)} candidates")
