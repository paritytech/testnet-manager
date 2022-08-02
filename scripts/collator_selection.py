from app.lib.substrate import get_substrate_client

node_client = get_substrate_client("ws://localhost:9944")

try:
    candidates = node_client.query('CollatorSelection', 'Candidates', params=[]).value
    print(candidates)
    desired_candidates = node_client.query('CollatorSelection', 'DesiredCandidates', params=[]).value
    print(desired_candidates)
    invulnerable_candidates = node_client.query('CollatorSelection', 'Invulnerables', params=[]).value
    print(invulnerable_candidates)
except Exception as err:
    print(err)