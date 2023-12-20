import streamlit as st
from datetime import timedelta, datetime
from . import core, config

def get_time_frame() -> timedelta:
    time_frame = st.radio("Show last:", ["6 hours", "day", "week"], horizontal=True)
    
    if time_frame == "6 hours":
        return timedelta(hours=6)
    elif time_frame == "day":
        return timedelta(days=1)
    elif time_frame == "week":
        return timedelta(weeks=1)
    raise ValueError("Invalid time frame")


def time_ago(dt: datetime) -> str:
    current_time = datetime.utcnow()
    time_ago = current_time - dt

    # Convert the time difference to a readable string
    if time_ago < timedelta(minutes=1):
        time_ago_str = "just now"
    elif time_ago < timedelta(hours=1):
        minutes = int(time_ago.total_seconds() / 60)
        time_ago_str = f"{minutes} minutes ago"
    elif time_ago < timedelta(days=1):
        hours = int(time_ago.total_seconds() / 3600)
        time_ago_str = f"{hours} hours ago"
    else:
        days = time_ago.days
        time_ago_str = f"{days} days ago"

    return time_ago_str

def display_toot(toot: core.Toot):
    with st.container(border=True):
        reply = "↩" if toot.is_reply else ""
        st.markdown(f"""
{reply}<a href="{toot.profile_url}"><img src="{toot.avatar_url}" style="width: 40px; height: 40px" />{toot.display_name} @{toot.author} ({time_ago(toot.created_at)})</a>
{toot.content}
""", unsafe_allow_html=True)
        cols = st.columns(10)
        with cols[7]:
            st.markdown(f"""<a href="{config.MASTO_BASE}/deck/@{toot.author}/{toot.toot_id}" target="_blank">🔗</a>""", unsafe_allow_html=True)
        with cols[8]:
            if st.button("⭐️", key=f"star-{toot.id}"):
                toot.do_star()
        with cols[9]:
            if st.button("️🔁", key=f"boost-{toot.id}"):
                toot.do_boost()