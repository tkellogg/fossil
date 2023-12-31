# Fossil, a Mastodon client

A read-only mastodon client that makes it easy to experiment with home feed algorithms. It consumes your timeline
(chronological ordering) and displays it in a way that suits you best. For example, topic-wise clustering of posts.

At the moment, there are 2 different UIs:

* streamlit: The first take. It was easy to hack on and prove the idea, but there's a lot of state bugs.
* FastAPI + htmx: A more traditional web app optimized for running the server on your laptop or under your bed.
 
Fossil is evolving quickly, but please contribute your own ideas. Create a ticket, or just create your own fork 
(and do whatever you want with it).

Sneak peek:

![image](https://gist.github.com/assets/437044/3152e5ae-bac7-4a67-a01b-82a712e90e26)


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
