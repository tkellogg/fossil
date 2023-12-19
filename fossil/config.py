
def get_config() -> dict:
    with open(".env") as handle:
        text = handle.read()
        return dict(line.split("=", 1) for line in text.splitlines() if line)

def headers():
    access_token = get_config()["ACCESS_TOKEN"]
    return {"Authorization": f"Bearer {access_token}"}
