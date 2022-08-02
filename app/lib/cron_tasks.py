# Define tasks to be run on a CRON schedule
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.lib.kubernetes_client import list_stateful_sets, list_validator_stateful_sets
from app.config.network_configuration import get_network, network_tasks_cron_schedule
from app.lib.network_utils import rotate_nodes_session_keys, register_statefulset_validators
from app.lib.substrate import get_relay_chain_client

log = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()
network = get_network()


async def load_cron_tasks():
    log.info('loading CRON tasks')
    scheduler.start()
    # Register CRON jobs
    tasks_cron_schedule = network_tasks_cron_schedule()
    if tasks_cron_schedule:
        tasks_cron_trigger = CronTrigger.from_crontab(tasks_cron_schedule)
        find_rotate_session_keys = find_network_rotate_session_keys()
        scheduler.add_job(find_rotate_session_keys,
                          name='find_session_keys_to_rotate',
                          trigger=tasks_cron_trigger),
        register_inactive_validators = register_network_inactive_validators()
        scheduler.add_job(register_inactive_validators,
                          name='register_inactive_validators',
                          trigger=tasks_cron_trigger)


async def exec_cron_task(job_id):
    log.info(f'Executing task now: {scheduler.get_job(job_id).name}')
    await scheduler.get_job(job_id).func()


def list_cron_tasks():
    scheduler_jobs = scheduler.get_jobs()

    return list(map(lambda job: {
            'id': job.id,
            'name': job.name,
            'cron': str(job.trigger),
            'nextRun': str(job.next_run_time),
            'timeZone': str(job.next_run_time.tzinfo) if job.next_run_time else ''
        }, scheduler_jobs))


# Perform session keys auto-rotation based on the following logic:
#  * Check the statefulset `rotateSessionKeysBlocksInterval` label to populate an internal map of statefulset -> "next rotate keys block height"
#  * At each scheduled cron (defined globally for each network), check if the current block is greater than the "next rotate keys block height"
#  * If we passed the block, rotate the sessions keys for these statefulset nodes and set the "next rotate keys block height" to current_block + rotateSessionKeysBlocksInterval
def find_network_rotate_session_keys():
    # initialize session keys rotation map for the current network
    next_session_keys_rotations = {}

    async def find_rotate_session_keys():
        validator_stateful_sets = list_stateful_sets()
        substrate_client = get_relay_chain_client()
        current_block_height = substrate_client.get_block()['header']['number']
        log.debug(f'Finding {network} stateful sets for which to rotate session keys, current_block_height={current_block_height}')
        for stateful_set in validator_stateful_sets:
            stateful_set_name = stateful_set['metadata']['name']
            stateful_set_labels = stateful_set['metadata']['labels']
            # If the next scheduled session key rotation block has passed for the stateful set
            if stateful_set_name in next_session_keys_rotations and \
                    current_block_height > next_session_keys_rotations[stateful_set_name]:
                log.info(f'Rotating session keys for stateful_set={stateful_set_name} as current_block_height={current_block_height} > next_session_key_rotation_block_height={next_session_keys_rotations[stateful_set_name]}')
                await rotate_nodes_session_keys(stateful_set_name)
                next_session_keys_rotations.pop(stateful_set_name)
            # If the stateful set doesn't have a scheduled key rotation and has the rotate_keys label
            if stateful_set_name not in next_session_keys_rotations and 'rotateSessionKeysBlocksInterval' in stateful_set_labels:
                rotate_session_keys_blocks_interval = int(stateful_set_labels['rotateSessionKeysBlocksInterval'])
                next_rotate_key_block_height = current_block_height + rotate_session_keys_blocks_interval
                log.info(f'On statefulset={stateful_set_name}, session_keys_rotation_blocks_interval={rotate_session_keys_blocks_interval} => next_session_key_rotation_block_height={next_rotate_key_block_height}')
                next_session_keys_rotations[stateful_set_name] = next_rotate_key_block_height

    return find_rotate_session_keys


def register_network_inactive_validators():
    async def register_inactive_validators():
        log.info(f'Registering inactive validators for network={network}')
        validator_stateful_sets = list_validator_stateful_sets(network)
        for stateful_set in validator_stateful_sets:
            await register_statefulset_validators(stateful_set)
            print(stateful_set)
        log.info('Finished registering inactive validators')
    return register_inactive_validators
