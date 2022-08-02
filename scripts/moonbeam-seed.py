import sys
from lib.moonbeam import get_moon_root_uri, get_moon_keypair_from_uri

moon_keypair = get_moon_keypair_from_uri(get_moon_root_uri(sys.argv[1]))
print('address: ' + moon_keypair.ss58_address)
print('seed: ' + moon_keypair.seed_hex)