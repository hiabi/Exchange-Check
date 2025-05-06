# Versión auditoría: comparación de métodos de ciclo
import streamlit as st
import pandas as pd
import networkx as nx
from io import BytesIO
from pymongo import MongoClient

@st.cache_resource
def get_mongo_collection():
    client = MongoClient(st.secrets["mongo"]["uri"])
    db = client.car_exchange
    collection = db.user_uploads
    return collection

mongo_collection = get_mongo_collection() if "mongo" in st.secrets else None

st.title("🔍 Cycle Matching Audit Tool")
st.markdown("Compare greedy vs. exhaustive cycle extraction.")

def load_all_requests_from_mongo():
    requests = []
    participants = list(mongo_collection.find({}))
    for user in participants:
        for upload in user.get("uploads", []):
            offers = upload.get('offers', [])
            wants = upload.get('wants', [])
            for offer in offers:
                if 'full_name' not in offer and 'MODELO' in offer and 'VERSION' in offer:
                    offer['full_name'] = offer['MODELO'].strip().upper() + " - " + offer['VERSION'].strip().upper()
            for want in wants:
                if 'full_name' not in want and 'MODELO' in want and 'VERSION' in want:
                    want['full_name'] = want['MODELO'].strip().upper() + " - " + want['VERSION'].strip().upper()

            requests.append({
                'id': user['agency_id'],
                'name': user.get('name', user['agency_id']),
                'offers': offers,
                'wants': wants,
            })
    return requests

def build_graph(requests):
    G = nx.DiGraph()
    for req in requests:
        G.add_node(req['id'])
    for req_a in requests:
        for req_b in requests:
            if req_a['id'] != req_b['id']:
                if any(o['full_name'].lower() == w['full_name'].lower() for o in req_a['offers'] for w in req_b['wants']):
                    G.add_edge(req_a['id'], req_b['id'])
    return G

def violates_offer_conflict(cycle, request_map, used_offers):
    for i in range(len(cycle) - 1):
        giver_id, receiver_id = cycle[i], cycle[i + 1]
        giver = request_map[giver_id]
        receiver = request_map[receiver_id]
        for offer in giver['offers']:
            for want in receiver['wants']:
                if offer['full_name'].lower() == want['full_name'].lower():
                    key = (giver_id, offer['full_name'])
                    if key in used_offers:
                        return True
                    used_offers.add(key)
    return False

def sample_cycles_greedy(G, request_map, max_len=10):
    all_cycles, used_nodes, used_offers = [], set(), set()
    for component in nx.connected_components(G.to_undirected()):
        subgraph = G.subgraph(component).copy()
        cycles = list(nx.simple_cycles(subgraph))
        cycles = [c + [c[0]] for c in cycles if len(c) >= 3 and c[0] != c[-1]]
        cycles.sort(key=len, reverse=True)
        for cycle in cycles:
            if not any(node in used_nodes for node in cycle):
                if not violates_offer_conflict(cycle, request_map, used_offers):
                    all_cycles.append(cycle)
                    used_nodes.update(cycle)
    return all_cycles

def sample_cycles_exhaustive(G, request_map, max_len=10):
    all_cycles, used_offers = [], set()
    cycles = list(nx.simple_cycles(G))
    for cycle in cycles:
        if len(cycle) < 3 or cycle[0] != cycle[-1]:
            cycle.append(cycle[0])
            if not violates_offer_conflict(cycle, request_map, used_offers):
                all_cycles.append(cycle)
    return all_cycles

def describe_cycles(cycles, request_map):
    rows = []
    for i, cycle in enumerate(cycles):
        description = []
        for j in range(len(cycle) - 1):
            giver = request_map[cycle[j]]
            receiver = request_map[cycle[j + 1]]
            match = next((o for o in giver['offers'] for w in receiver['wants'] if o['full_name'].lower() == w['full_name'].lower()), None)
            if match:
                description.append(f"{giver['name']} offers '{match['full_name']}' → to {receiver['name']}")
        rows.append({'cycle_id': i, 'exchange_path': "\n".join(description)})
    return pd.DataFrame(rows)

if st.button("🔄 Run Cycle Comparison"):
    requests = load_all_requests_from_mongo()
    if not requests:
        st.warning("No data found.")
    else:
        request_map = {r['id']: r for r in requests}
        G = build_graph(requests)

        st.subheader("Greedy Cycle Extraction")
        greedy_cycles = sample_cycles_greedy(G, request_map)
        df_greedy = describe_cycles(greedy_cycles, request_map)
        st.dataframe(df_greedy)

        st.subheader("Exhaustive Cycle Extraction")
        exhaustive_cycles = sample_cycles_exhaustive(G, request_map)
        df_exhaustive = describe_cycles(exhaustive_cycles, request_map)
        st.dataframe(df_exhaustive)

        st.success(f"Found {len(greedy_cycles)} greedy and {len(exhaustive_cycles)} exhaustive cycles.")
