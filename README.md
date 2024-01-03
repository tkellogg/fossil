# Fossil, a Mastodon client

A mastodon client optimized for reading, with a configurable and 
hackable timeline algorithm powered by Simon Wilison's [llm](https://llm.datasette.io/en/stable/index.html) tool. Try making your own algorithm!


Sneak peek:

![image](https://gist.github.com/assets/437044/3152e5ae-bac7-4a67-a01b-82a712e90e26)


## Running

Clone the repo and then run:

```bash
poetry run uvicorn --host 0.0.0.0 --port 8888 --reload fossil.server:app
```


Before that, you'll need a `.env` file with these keys:

```
ACCESS_TOKEN=
```

They can also be environment variables. All available keys are here:

| Variable            | Required? | Value                                    |
| ---                 | ---       | ---                                      |
| OPENAI_API_BASE     |        no | eg. https://api.openai.com/v1            |
| MASTO_BASE          |       no? | eg. https://hackyderm.io                 |
| ACCESS_TOKEN        |       yes | In your mastodon UI, create a new "app" and copy the access token here |


# Status
It works on my box
