# Fossil, a Mastodon client

A mastodon client (well, just a streamlit dashboard) that lets me consume my mastodon feed by categories according to their content.

## Running

This bad boy will get you going:

```bash
poetry run streamlit run dashboard.py
```


Before that, you'll need a `.env` file with these keys:

```
ACCESS_TOKEN=
OPENAI_KEY=
```

They can also be environment variables. All available keys are here:

| Variable            | Required? | Value                                    |
| ---                 | ---       | ---                                      |
| OPENAI_API_BASE     |        no | eg. https://api.openai.com/v1            |
| OPENAI_KEY          |       yes | Create an account and paste the key here |
| MASTO_BASE          |       no? | eg. https://hackyderm.io                 |
| ACCESS_TOKEN        |       yes | In your mastodon UI, create a new "app" and copy the access token here |


# Status
It works on my box
