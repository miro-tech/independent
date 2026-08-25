import requests
import base64
import json
import os
import time

TOKEN = os.environ["DEVICE_TOKEN"]
GIST = os.environ["GIST_ID"]
GH = os.environ["GH_TOKEN"]

COUNTRY = "c2708a97-28a8-46ae-b705-1132b6ae450e"


HEADERS = {
    "X-Device-Token": TOKEN,
    "User-Agent": "okhttp/4.12.0",
    "Accept": "application/json"
}


# ==========================
# Получение серверов с retry
# ==========================

servers = None

for attempt in range(5):

    try:
        resp = requests.get(
            "https://api.dvpnsdk.com/server",
            params={
                "country_id": COUNTRY,
                "filter": "V2RAY"
            },
            headers=HEADERS,
            timeout=60
        )

        print(
            "GET /server",
            "Attempt:",
            attempt + 1,
            "Status:",
            resp.status_code
        )

        if resp.status_code == 200:
            servers = resp.json()["data"]
            break

        else:
            print(resp.text[:300])

    except Exception as e:
        print("REQUEST ERROR:", e)

    time.sleep(10)


if servers is None:
    raise Exception("API unavailable")


print("Servers:", len(servers))


# ==========================
# Создание VMess
# ==========================

links = []


for s in servers:

    try:

        print("GET:", s["name"])


        r = requests.post(
            f"https://api.dvpnsdk.com/server/{s['id']}/credentials",
            headers=HEADERS,
            timeout=60
        )


        if r.status_code != 200:
            print(
                "Credential error:",
                r.status_code,
                r.text[:200]
            )
            continue


        data = r.json()["data"]


        hs = data["connection_handshake"]["response"]

        ip = hs["addrs"][0]


        meta = json.loads(
            base64.b64decode(
                hs["data"]
            )
        )


        # берем первый grpc порт
        port = None

        for m in meta["metadata"]:

            # transport_protocol 3 = grpc
            if m.get("transport_protocol") == 3:
                port = m["port"]
                break


        if port is None:
            print("No grpc:", s["name"])
            continue


        uid = data["uid"]


        vmess = (
            f"vmess://{uid}"
            f"@{ip}:{port}"
            f"?encryption=auto"
            f"&security=none"
            f"&type=grpc"
            f"#{s['name']}"
        )


        links.append(vmess)

        print(vmess)


    except Exception as e:

        print(
            "ERROR:",
            s.get("name"),
            e
        )


# ==========================
# Загрузка в Gist
# ==========================

text = "\n".join(links)


resp = requests.patch(
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
    timeout=60
)


if resp.status_code != 200:
    print(resp.text)
    raise Exception("Gist update failed")


print()
print("Uploaded:", len(links))
