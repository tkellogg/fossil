import llm
import numpy as np
import openai
import tiktoken
from sklearn.cluster import KMeans

from . import config, core


def assign_clusters(session_id: str, toots: list[core.Toot], n_clusters: int = 5):
    # meh, ignore toots without content. I think this might be just an image, not sure
    toots = [toot for toot in toots if toot.embedding is not None]

    # Perform k-means clustering on the embeddings
    embeddings = np.array([toot.embedding for toot in toots])
    kmeans = KMeans(n_clusters=n_clusters)
    cluster_labels = kmeans.fit_predict(embeddings)

    client = openai.OpenAI(api_key=config.ConfigHandler.OPENAI_KEY)
    for i_clusters in range(n_clusters):
        clustered_toots = [toot for toot, cluster_label in zip(toots, cluster_labels) if cluster_label == i_clusters]
        combined_text = "\n\n".join([toot.content for toot in clustered_toots])

        # Use GPT-3.5-turbo to summarize the combined text
        prompt = f"Create a single label that describes all of these related tweets, make it succinct but descriptive. The label should describe all {len(clustered_toots)} of these\n\n{combined_text}"
        model = llm.get_model(config.ConfigHandler.SUMMARIZE_MODEL(session_id).name)
        summary = model.prompt(prompt).text()

        # Do something with the summary
        for toot, cluster_label in zip(toots, cluster_labels):
            if cluster_label == i_clusters:
                toot.cluster = summary

def get_encoding(session_id: str):
    try:
        return tiktoken.encoding_for_model(config.ConfigHandler.SUMMARIZE_MODEL(session_id).name)
    except KeyError:
        encoding_name = tiktoken.list_encoding_names()[-1]
        return tiktoken.get_encoding(encoding_name)

def reduce_size(session_id: str, text: str, model_limit: int = -1, est_output_size: int = 500) -> str:
    if model_limit < 0:
        config.ConfigHandler.SUMMARIZE_MODEL(session_id).context_length
    tokens = get_encoding(session_id).encode(text)
    return get_encoding(session_id).decode(tokens[:model_limit - est_output_size])
