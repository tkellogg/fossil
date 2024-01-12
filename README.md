# Fossil, a Mastodon Client for Reading

A mastodon client optimized for reading, with a configurable and 
hackable timeline algorithm powered by Simon Wilison's [llm](https://llm.datasette.io/en/stable/index.html) tool. Try making your own algorithm!


Sneak peek:

![image](https://gist.github.com/assets/437044/3152e5ae-bac7-4a67-a01b-82a712e90e26)


# Installing & Running

## From PyPi

I highly suggest not installing any Python app directly into your global Python. Create a virtual environment:

```
python -m venv fossil
```

And then activate it (see [here](https://docs.python.org/3/library/venv.html))

```
source fossil/bin/activate
```

Alternatively, **use [`pipx`](https://pipx.pypa.io/stable/installation/)**:

```
pip install pipx
pipx install fossil-mastodon
```

## From Source

Clone this repo:

```
git clone https://github.com/tkellogg/fossil.git
```

And then `cd fossil` to get into the correct directory.


## Configure the `.env` file

Before that, you'll need a `.env` file with these keys:

```
ACCESS_TOKEN=
```

Alternatively, you can set them as environment variables. All available keys are here:

| Variable            | Required? | Value                                    |
| ---                 | ---       | ---                                      |
| OPENAI_API_BASE     |        no | eg. https://api.openai.com/v1            |
| MASTO_BASE          |       no? | eg. https://hackyderm.io                 |
| ACCESS_TOKEN        |       yes | In your mastodon UI, create a new "app" and copy the access token here |

### Connecting to Mastodon

To get `MASTO_BASE` and `ACCESS_TOKEN`:

1. Go to Mastodon web UI
2. Preferences -> Development
3. Click "New Application"
4. Set the name
5. Set "Redirect URI" to `urn:ietf:wg:oauth:2.0:oob`
6. Set scopes to all `read` and `write` (contribution idea: figure out what's strictly necessary and send a pull request to update this)
7. Click Submit
8. Copy your access token into `ACCESS_TOKEN` in the `.env` file.
9. Set `MAST_BASE`. You should be able to copy the URL from your browser and then remove the entire path (everything after `/`, inclusive).

## Usage
1. Ensure the settings are correct
2. "Load More" to populate the database with toots
3. "Re-Train Algorithm" to categorize and label those toots.

# Configure Models
Models can be configured and/or added via `llm`.

## OpenAI
Here's how to set your OpenAI API key, which gives you access to OpenAI models:

```
$ llm keys set openai
Enter key: ...
```
## Local (Experimental)
You will need to install an embedding model and a large language model. The instructions here use the `llm-sentence-transformers` and `llm-gpt4all` plugins to do so.

```sh
$ llm install llm-sentence-transformers # An Embedding Model Plugin
$ llm install llm-gpt4all # A Large Language Model Plugin
$ llm sentence-transformers register all-mpnet-base-v2 --alias mpnet # Download/Register one of the Embedding Models
```

### Notes
- A full list of possible embedding models is composed of [the default list](https://www.sbert.net/docs/pretrained_models.html) and [these models from huggingface](https://huggingface.co/models?library=sentence-transformers).
- The [llm-gpt4all](https://github.com/simonw/llm-gpt4all) README gives a list of models and their requirements
- The first time you use a model, `llm` will need to download it. This will add to the overall time it takes to process 
- The "Re-Train Algorithm" step will take a long time depending on your hardware; a progress bar is shown in the console window
- The quality of the categorization and labels are not guaranteed

## Run the server

If you installed from PyPi:

```
uvicorn --host 0.0.0.0 --port 8888 fossil_mastodon.server:app
```

If you installed from source:

```
poetry run uvicorn --host 0.0.0.0 --port 8888 --reload fossil_mastodon.server:app
```

If you're working on CSS or HTML files, you should include them:

```
poetry run uvicorn --host 0.0.0.0 --port 8888 --reload --reload-include '*.html' --reload-include '*.css' fossil_mastodon.server:app
```

(Note the `--reload` makes it much easier to develop, but is generally unneccessary if you're not developing)