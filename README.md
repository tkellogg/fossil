# Fossil, a Mastodon client

A mastodon client (well, just a streamlit dashboard) that lets me consume my mastodon feed by categories according to their content.

## Running

This bad boy will get you going:

```bash
poetry run streamlit run dashboard.py
```


Before that, you'll need a `.env` file with these keys:

```
OAUTH_CLIENT_ID=
OAUTH_CLIENT_SECRET=
ACCESS_TOKEN=
OPENAI_KEY=
```

* Oauth (first 3) — In your mastodon UI, create a new "app" and copy the information into these
* OpenAI Key — create an account and paste the key here


# Status
It works on my box
