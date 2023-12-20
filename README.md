# Fossil, a Mastodon client

A mastodon client (well, just a streamlit dashboard) that lets me consume my mastodon feed by categories according to their content.

## Running

This bad boy will get you going:

```bash
poetry run streamlit run dashboard.py
```


Before that, you'll need a `.env` file with these keys:

```
OPENAI_API_BASE=https://api.openai.com/v1
OPENAI_KEY=
OAUTH_CLIENT_URI=
OAUTH_CLIENT_ID=
OAUTH_CLIENT_SECRET=
ACCESS_TOKEN=
```

| Variable            | Value                                    |
| ---                 | ---                                      |
| OPENAI_API_BASE     | eg. https://api.openai.com/v1            |
| OPENAI_KEY          | Create an account and paste the key here |
| OAUTH_CLIENT_URI    | eg. https://hackyderm.io                 |
| OAUTH_CLIENT_ID     | In your mastodon UI, create a new "app" and copy the information into these: |
| OAUTH_CLIENT_SECRET |                                          |
| ACCESS_TOKEN        |                                          |

# Status
It works on my box
