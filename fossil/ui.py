from datetime import timedelta, datetime
import urllib.parse

import streamlit as st

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


class LinkStyle:
    def __init__(self):
        # ivory://acct/openURL?url=
        # {config.MASTO_BASE}/deck/@{toot.author}/{toot.toot_id}
        self.scheme = st.radio("Link scheme:", ["Desktop", "Ivory", "Original"], index=1, horizontal=True)

    def format_url(self, toot: core.Toot) -> str:
        if self.scheme == "Desktop":
            return f"{config.MASTO_BASE}/@{toot.author}/{toot.toot_id}"
        elif self.scheme == "Ivory":
            encoded_url = urllib.parse.quote(toot.url)
            return f"ivory://acct/openURL?url={encoded_url}"
        elif self.scheme == "Original":
            return toot.url
        raise ValueError("Invalid scheme")


def display_toot(toot: core.Toot, link_style: LinkStyle):
    with st.container(border=True):
        reply = "↩" if toot.is_reply else ""
        st.markdown(f"""
{reply}<a href="{toot.profile_url}"><img src="{toot.avatar_url}" style="width: 40px; height: 40px" />{toot.display_name} @{toot.author} ({time_ago(toot.created_at)})</a>
{toot.content}
""", unsafe_allow_html=True)

        attachments = [f'<a href="{a.url}"><img src="{a.preview_url}" style="max-width: 100%" /></a>' for a in toot.media_attachments]
        st.markdown(" ".join(attachments), unsafe_allow_html=True)

        cols = st.columns(4)
        with cols[0]:
            st.markdown(f"""<a href="{link_style.format_url(toot)}" target="_blank">🔗</a>""", unsafe_allow_html=True)
        with cols[1]:
            if st.button("⭐️", key=f"star-{toot.id}"):
                toot.do_star()
        with cols[2]:
            if st.button("️🔁", key=f"boost-{toot.id}"):
                toot.do_boost()
        with cols[3]:
            if st.button("🪲", key=f"delete-{toot.id}"):
                import json
                print(json.dumps(toot.orig_dict, indent=2))


def all_toot_summary(toots: list[core.Toot]):
    latest_date = max(t.created_at for t in toots)
    earliest_date = min(t.created_at for t in toots)
    now = datetime.utcnow()
    msg = f"{len(toots)} toots from {time_ago(earliest_date)} to {time_ago(latest_date)}"
    if latest_date > now:
        st.warning(msg)
    else:
        st.info(msg)