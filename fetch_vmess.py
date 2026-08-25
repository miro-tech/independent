import requests
import base64
import json
import os
import time

TOKEN = os.environ["DEVICE_TOKEN"]
GIST = os.environ["GIST_ID"]
GH = os.environ["GH_TOKEN"]

COUNTRY = "cb7b2d44-91a5-4dc0-8f5b-9d2e3f2ffb3b"

API = "https://api.dvpnsdk.com"

HEADERS = {
    "X-Device-Token": TOKEN,
    "User-Agent": "okhttp/4.12.0",
    "Accept": "application/json"
}


# ============================================================
# GET SERVERS
# Логика перенесена из PHP:
#
# offset=0,100,200...900
# limit=100
# filter=V2RAY
# затем country_id == COUNTRY
# ============================================================

servers = []
seen = set()

for offset in range(0, 1000, 100):

    try:

        print(
            f"GET /server offset={offset}"
        )

        r = requests.get(
            f"{API}/server",
            params={
                "filter": "V2RAY",
                "offset": offset,
                "limit": 100
            },
            headers=HEADERS,
            timeout=60
        )

        print(
            "HTTP:",
            r.status_code
        )

        if r.status_code != 200:
            print(r.text[:500])
            continue

        data = r.json().get("data", [])

        print(
            "Received:",
            len(data)
        )

        if not data:
            break

        for s in data:

            # PHP:
            #
            # if (
            #     isset($s['country_id']) &&
            #     $s['country_id'] === $country
            # )

            if s.get("country_id") != COUNTRY:
                continue

            sid = s.get("id")

            if not sid:
                continue

            # Убираем дубли как PHP
            if sid in seen:
                continue

            seen.add(sid)
            servers.append(s)

    except Exception as e:

        print(
            "SERVER REQUEST ERROR:",
            e
        )

        continue


print()
print("Servers:", len(servers))
print()


if not servers:
    raise Exception("Servers not found")


# ============================================================
# GET CREDENTIALS + BUILD VMESS
# ============================================================

links = []


for s in servers:

    name = s.get("name", "Unknown")
    sid = s.get("id")

    print("GET:", name)

    try:

        # ====================================================
        # POST /server/{id}/credentials
        # ====================================================

        r = requests.post(
            f"{API}/server/{sid}/credentials",
            headers=HEADERS,
            timeout=60
        )

        if r.status_code != 200:

            print(
                "Credential error:",
                r.status_code,
                r.text[:300]
            )

            continue


        credentials = r.json()


        # ====================================================
        # data
        # ====================================================

        data = credentials.get("data")

        if not data:
            print("Invalid credentials response")
            continue


        # ====================================================
        # connection_handshake.response
        # ====================================================

        hs = (
            data
            .get("connection_handshake", {})
            .get("response", {})
        )

        if not hs:
            print("No handshake response")
            continue


        # ====================================================
        # IP
        #
        # PHP:
        #
        # $ip = $hs['addrs'][0];
        # ====================================================

        addrs = hs.get("addrs", [])

        if not addrs:

            print("No addresses")
            continue

        ip = addrs[0]


        # ====================================================
        # handshake.data
        #
        # Base64 -> JSON
        # ====================================================

        handshake_data = hs.get("data")

        if not handshake_data:

            print("No handshake data")
            continue


        try:

            decoded = base64.b64decode(
                handshake_data,
                validate=True
            )

        except Exception:

            print("Base64 decode failed")
            continue


        try:

            meta = json.loads(
                decoded.decode("utf-8")
            )

        except Exception:

            print("Invalid metadata JSON")
            continue


        metadata = meta.get("metadata")

        if not isinstance(metadata, list):

            print("Invalid metadata")
            continue


        # ====================================================
        # Ищем gRPC
        #
        # PHP:
        #
        # transport_protocol == 3
        # ====================================================

        port = None

        for m in metadata:

            if (
                m.get("transport_protocol") == 3
                and m.get("port") is not None
            ):

                port = m["port"]
                break


        # ====================================================
        # FALLBACK
        #
        # PHP:
        #
        # если grpc не найден,
        # берётся metadata[0].port
        # ====================================================

        if port is None:

            if (
                metadata
                and metadata[0].get("port") is not None
            ):

                port = metadata[0]["port"]


        if port is None:

            print("No port")
            continue


        # ====================================================
        # UUID
        # ====================================================

        uid = data.get("uid")

        if not uid:

            print("No UID")
            continue


        # ====================================================
        # Старый VMess JSON
        # ====================================================

        vmess = {
            "v": "2",
            "ps": name,
            "add": ip,
            "port": str(port),
            "id": uid,
            "aid": "0",
            "scy": "auto",

            # ВАЖНО:
            # это именно формат из PHP
            "net": "grpc",
            "type": "gun",

            "host": "",
            "path": "",

            "tls": "",
            "sni": "",
            "alpn": "",
            "fp": ""
        }


        # ====================================================
        # JSON -> BASE64
        # ====================================================

        vmess_json = json.dumps(
            vmess,
            ensure_ascii=False,
            separators=(",", ":")
        )

        encoded = base64.b64encode(
            vmess_json.encode("utf-8")
        ).decode("ascii")


        link = "vmess://" + encoded

        links.append(link)


        print("IP:   ", ip)
        print("Port: ", port)
        print("UUID: ", uid)
        print("VMess:")
        print(link)
        print()


    except Exception as e:

        print(
            "ERROR:",
            name,
            e
        )


# ============================================================
# RESULT
# ============================================================

print("========================================")
print("Generated links:", len(links))
print("========================================")


if not links:
    raise Exception("No VMess links generated")


text = "\n".join(links)


# ============================================================
# GITHUB GIST
# ============================================================

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
