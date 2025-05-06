# 🔍 Cycle Completeness Checker
import streamlit as st
import pandas as pd
import networkx as nx
from pymongo import MongoClient
import datetime

@st.cache_resource

def get_mongo_collection():
    client = MongoClient(st.secrets["mongo"]["uri"])
    db = client.car_exchange
    return db.user_uploads

mongo_collection = get_mongo_collection()

# === Load all requests ===
def load_all_requests():
    requests = []
    participants = list(mongo_collection.find({}))
    for user in participants:
        for upload in user.get("uploads", []):
            offers = upload.get("offers", [])
            wants = upload.get("wants", [])
            for o in offers:
                if "full_name" not in o:
                    o["full_name"] = o.get("MODELO", "").strip().upper() + " - " + o.get("VERSION", "").strip().upper()
            for w in wants:
                if "full_name" not in w:
                    w["full_name"] = w.get("MODELO", "").strip().upper() + " - " + w.get("VERSION", "").strip().upper()
            requests.append({
                "id": user["agency_id"],
                "name": user.get("name", user["agency_id"]),
                "offers": offers,
                "wants": wants,
            })
    return requests

# === Graph construction ===
def build_graph(requests):
    G = nx.DiGraph()
    for r in requests:
        G.add_node(r["id"])
    for a in requests:
        for b in requests:
            if a["id"] == b["id"]:
                continue
            if any(o["full_name"].lower() == w["full_name"].lower() for o in a["offers"] for w in b["wants"]):
                G.add_edge(a["id"], b["id"])
    return G

# === Greedy Matching ===
def violates_offer_conflict(cycle, request_map, used_offers):
    for i in range(len(cycle) - 1):
        giver = request_map[cycle[i]]
        receiver = request_map[cycle[i + 1]]
        for o in giver["offers"]:
            for w in receiver["wants"]:
                if o["full_name"].lower() == w["full_name"].lower():
                    key = (cycle[i], o["full_name"])
                    if key in used_offers:
                        return True
                    used_offers.add(key)
    return False

def greedy_cycles(G, request_map):
    used_nodes, used_offers = set(), set()
    cycles = []
    for component in nx.connected_components(G.to_undirected()):
        sub = G.subgraph(component)
        all = list(nx.simple_cycles(sub))
        all.sort(key=len, reverse=True)
        for c in all:
            if len(c) >= 3 and c[0] == c[-1] and not any(x in used_nodes for x in c):
                if not violates_offer_conflict(c, request_map, used_offers):
                    used_nodes.update(c)
                    cycles.append(c)
    return cycles

# === App ===
st.title("🔍 Cycle Completeness Audit")

all_requests = load_all_requests()
G = build_graph(all_requests)
request_map = {r["id"]: r for r in all_requests}

full_cycles = [c for c in nx.simple_cycles(G) if len(c) >= 3 and c[0] == c[-1]]
greedy = greedy_cycles(G, request_map)

st.write(f"🔢 Total possible valid cycles found: {len(full_cycles)}")
st.write(f"✅ Cycles selected by Greedy Algorithm: {len(greedy)}")
st.write(f"❌ Skipped cycles: {len(full_cycles) - len(greedy)}")

if st.checkbox("🔎 Show skipped cycles"):
    used_ids = {tuple(c) for c in greedy}
    skipped = [c for c in full_cycles if tuple(c) not in used_ids]
    for i, c in enumerate(skipped):
        st.write(f"Cycle {i+1}: {c}")

st.info("This tool helps verify if the greedy strategy is leaving potential valid cycles behind.")
