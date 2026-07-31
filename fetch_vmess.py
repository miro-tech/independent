import requests
import base64
import json
import os

TOKEN = os.environ["DEVICE_TOKEN"]
GIST = os.environ["GIST_ID"]
GH = os.environ["GH_TOKEN"]

COUNTRY = "2b54e231-bb62-4d5e-98e5-5a62b73b193f"

HEADERS = {
    "X-Device-Token": TOKEN
}

servers = requests.get(
    "https://api.dvpnsdk.com/server",
    params={
        "country_id": COUNTRY,
        "filter": "V2RAY"
    },
    headers=HEADERS,
    timeout=30
).json()["data"]

links = []

for s in servers:
    try:
        r = requests.post(
            f"https://api.dvpnsdk.com/server/{s['id']}/credentials",
            headers=HEADERS,
            timeout=30
        ).json()["data"]

        hs = r["connection_handshake"]["response"]

        ip = hs["addrs"][0]

        meta = json.loads(
            base64.b64decode(hs["data"])
        )

        port = meta["metadata"][0]["port"]

        uid = r["uid"]

        link = (
            f"vmess://{uid}"
            f"@{ip}:{port}"
            f"?encryption=auto"
            f"&security=none"
            f"&type=grpc"
            f"#{s['name']}"
        )

        links.append(link)

        print(link)

    except Exception as e:
        print("ERROR:", s["name"], e)

text = "\n".join(links)

requests.patch(
    f"https://api.github.com/gists/{GIST}",
    headers={
        "Authorization": f"Bearer {GH}",
        "Accept": "application/vnd.github+json"
    },
    json={
        "files": {
            "configs.txt": {
                "content": text
            }
        }
    },
    timeout=30
)

print("Uploaded:", len(links))
