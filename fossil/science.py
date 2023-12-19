import numpy as np
import openai
from . import core, config
from sklearn.cluster import KMeans
import openai


def assign_clusters(toots: list[core.Toot], n_clusters: int = 5):
    # Perform k-means clustering on the embeddings
    embeddings = np.array([toot.embedding for toot in toots])
    kmeans = KMeans(n_clusters=n_clusters)
    cluster_labels = kmeans.fit_predict(embeddings)

    client = openai.OpenAI(api_key=config.get_config()["OPENAI_KEY"])
    for i_clusters in range(n_clusters):
        clustered_toots = [toot for toot, cluster_label in zip(toots, cluster_labels) if cluster_label == i_clusters]
        combined_text = "\n\n".join([toot.content for toot in clustered_toots])

        # Use GPT-3.5-turbo to summarize the combined text
        prompt = f"Create a single label that describes all of these related tweets, make it succinct but descriptive. The label should describe all {len(clustered_toots)} of these\n\n{combined_text}"
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100,
        )
        summary = response.choices[0].message.content.strip()

        # Do something with the summary
        for toot, cluster_label in zip(toots, cluster_labels):
            if cluster_label == i_clusters:
                toot.cluster = summary
