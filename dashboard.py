import datetime
from fossil import config, core, science
import requests
import streamlit as st
import datetime

@st.cache_data
def default_date():
    return datetime.datetime.utcnow() - datetime.timedelta(days=1)

@st.cache_data
def get_toots_since(since: datetime.datetime):
    assert isinstance(since, datetime.datetime), type(since)
    core.create_database()
    core.download_timeline(since)
    return core.Toot.get_toots_since(since)

# Create a datepicker with the default date
selected_date = st.date_input("Select a date", default_date().date())
selected_time = st.time_input("Select a time", default_date().time())

# Combine the date and time
selected_date = datetime.datetime.combine(selected_date, selected_time)

n_clusters = st.slider("Number of clusters", 2, 20, 5)

if st.button("Execute"):
    toots = get_toots_since(selected_date)
    if len(toots) == 0:
        st.write("No toots found")
    else:
        st.write("Generating clusters")
        science.assign_clusters(toots, n_clusters=n_clusters)
        clusters = sorted(list({t.cluster for t in toots if t.cluster}))
        for cluster in clusters:
            cluster_count = len([t for t in toots if t.cluster == cluster])
            with st.expander(f"{cluster} ({cluster_count} toots)"):
                for toot in toots:
                    if toot.cluster == cluster:
                        st.markdown(f"**{toot.author}** ({core.time_ago(toot.created_at)})\n{toot.content}\n\n", unsafe_allow_html=True)
