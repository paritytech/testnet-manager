import logging

from substrateinterface import Keypair

from app.lib.collator_account import get_moon_keypair_from_uri
from app.lib.collator_moonbeam import get_moon_node_collator_uri, register_moon_collator
from app.config.network_configuration import network_root_seed
from app.lib.collator_tick import register_tick_collator
from app.lib.collator_mint import register_mint_collator, deregister_mint_collator
from app.lib.kubernetes_client import list_collator_pods
from app.lib.substrate import substrate_sudo_relay_xcm_call, get_node_client, get_query_weight

log = logging.getLogger('collator_manager')


def get_derived_collator_account(node_name, ss58_format):
    key_seed = network_root_seed()
    keypair = Keypair.create_from_uri(key_seed + "//collator//" + node_name, ss58_format=int(ss58_format))
    return keypair.ss58_address


def get_derived_moon_collator_account(node_name):
    key_seed = network_root_seed()
    keypair = get_moon_keypair_from_uri(get_moon_node_collator_uri(key_seed, node_name))
    return keypair.ss58_address


def get_moon_collator_status(node_account, selected_candidates, candidate_pool):
    log.debug(f'Getting Moon collator status for: node_account={node_account}, selected_candidates={selected_candidates}, candidates={candidate_pool}')

    if node_account in [x.lower() for x in selected_candidates]:
        return True
    else:
        if any(d['owner'].lower() == node_account.lower() for d in candidate_pool):
            return 'inCandidatePool'
        else:
            return False


def get_collator_status(node_account, invulnerables, candidates):
    log.debug(f'Getting collator status for: node_account={node_account}, invulnerables={invulnerables}, candidates={candidates}')
    try:
        if node_account in invulnerables:
            return "Invulnerable"
        if any(d['who'].lower() == node_account.lower() for d in candidates):
            return "Candidate"
    except Exception as err:
        log.info(err)
    return False


# map register function with network type
async def collator_register(chain, node_name, ss58_format):
    if chain.startswith("moon"):
        log.info('Detected that collators are moon-based {}'.format(chain))
        return register_moon_collator(node_name)
    elif chain.startswith("tick") or chain.startswith("trick") or chain.startswith("track"):
        log.info('Detected that collators are tick-based {}'.format(chain))
        return register_tick_collator(node_name)
    elif chain.endswith("mint") or chain.endswith("mine"):
        log.info('Detected that collators are mint-based {}'.format(chain))
        return register_mint_collator(node_name, ss58_format)
    else:
        log.error('Only registration of moon-based, tick, statemint, statemine chains are supported! Chain:{}'.format(chain))
        return None


async def collator_deregister(chain, node_name, ss58_format):
    if chain.startswith("moon"):
        log.info('Detected that collators are moon-based {}'.format(chain))
        # todo implement https://docs.moonbeam.network/node-operators/networks/collators/activities/#stop-collating
        log.error('NOT IMPLEMENTED')
        return None
    elif chain.startswith("tick") or chain.startswith("trick") or chain.startswith("track"):
        log.info('Detected that collators are tick-based {}'.format(chain))
        log.error('NOT IMPLEMENTED')
        return None
    elif chain.endswith("mint") or chain.endswith("mine"):
        log.info('Detected that collators are mint-based {}'.format(chain))
        return deregister_mint_collator(node_name, ss58_format)
    else:
        log.error('Only deregistration of moon-based, tick, statemint, statemine chains are supported! Chain:{}'.format(chain))
        return None


def get_parachain_rpc_client(para_id):
    collator_pods = list_collator_pods(para_id)
    for collator in collator_pods:
        parachain_client = get_node_client(collator.metadata.name)
        if parachain_client:
            return parachain_client


def get_collator_selection_invulnerables(para_id):
    node_client = get_parachain_rpc_client(para_id)
    return node_client.query('CollatorSelection', 'Invulnerables').value


async def set_collator_selection_invulnerables(para_id, invulnerables):
    log.info(f'Set the collatorSelection Invulnerables list to {invulnerables} for para #{para_id}')
    node_client = get_parachain_rpc_client(para_id)
    call = node_client.compose_call(
        call_module='CollatorSelection',
        call_function='set_invulnerables',
        call_params={
            'new': invulnerables
        }
    )
    encoded_call = call.encode()
    weight = get_query_weight(node_client, call)
    log.info("call: {}, weight: {}".format(call, weight))
    receipt = substrate_sudo_relay_xcm_call(para_id, encoded_call, weight)
    if receipt and receipt.is_success:
        log.info(f'✅ Success: new invulnerable list send via XCM to para #{para_id}')
    else:
        log.error(f'Failed to run xcm call para_id {para_id}, message: {encoded_call}, err: {invulnerables}')
        return None
