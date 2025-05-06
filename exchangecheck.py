# 🔍 Standalone Diagnostic App for Exchange Cycles
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

# --- Load Data ---
def load_all_requests():
    requests = []
    for user in mongo_collection.find({}):
        for upload in user.get("uploads", []):
            offers = upload.get("offers", [])
            wants = upload.get("wants", [])
            for offer in offers:
                if 'full_name' not in offer and 'MODELO' in offer and 'VERSION' in offer:
                    offer['full_name'] = offer['MODELO'].strip().upper() + " - " + offer['VERSION'].strip().upper()
            for want in wants:
                if 'full_name' not in want and 'MODELO' in want and 'VERSION' in want:
                    want['full_name'] = want['MODELO'].strip().upper() + " - " + want['VERSION'].strip().upper()
            requests.append({
                "id": user["agency_id"],
                "offers": offers,
                "wants": wants
            })
    return requests

# --- Build Graph ---
def build_graph(requests):
    G = nx.DiGraph()
    for req in requests:
        G.add_node(req['id'])

    for a in requests:
        for b in requests:
            if a['id'] == b['id']:
                continue
            if any(o['full_name'].lower() == w['full_name'].lower() for o in a['offers'] for w in b['wants']):
                G.add_edge(a['id'], b['id'])
    return G

# --- Exhaustive Cycle Listing ---
def list_all_cycles(G, max_len=6):
    all_cycles = []
    for cycle in nx.simple_cycles(G):
        if 3 <= len(cycle) <= max_len and cycle[0] == cycle[-1]:
            all_cycles.append(cycle)
    return all_cycles

# --- Streamlit UI ---
st.title("🔍 Exchange Cycle Diagnostics")

if mongo_collection is None:
    st.error("❌ MongoDB not connected.")
    st.stop()

requests = load_all_requests()
G = build_graph(requests)

st.success(f"Loaded {len(requests)} participants. Graph has {G.number_of_nodes()} nodes and {G.number_of_edges()} edges.")

max_cycle_len = st.slider("Max cycle length to search (simple cycles)", 3, 10, 6)

if st.button("🔍 Run Full Diagnostic"):
    cycles = list_all_cycles(G, max_len=max_cycle_len)
    st.info(f"Found {len(cycles)} full cycles.")

    for idx, cycle in enumerate(cycles[:20]):
        st.markdown(f"**Cycle {idx + 1}:** {' → '.join(cycle)} → {cycle[0]}")

    if len(cycles) > 20:
        st.caption("Only showing first 20 cycles.")
