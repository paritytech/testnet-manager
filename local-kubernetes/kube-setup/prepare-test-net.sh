#!/usr/bin/env bash
set -e
###
# Script to generate part of chainspec with keys and accounts.
###


if [ "$#" -ne 1 ]; then
	echo "Please provide the number of initial validators!"
	echo "Usage: "
	echo "export SUDO_SEED= sudo account seed" //Alice
  echo "export VALIDATORS_ROOT_SEED= base seed to derive from "
	echo "export PREFIX= derivation prefix "
	echo "$0 <number of nodes>"
	echo "Example: "
	echo "export SUDO_SEED=0xe5be9a5092b81bca64be81d212e7f2f9eba183bb7a90954f7b76361f6edb5c0a" //Alice
  echo "export VALIDATORS_ROOT_SEED='test test test test test test test test test test test junk'"
	echo "export PREFIX=localwococo-bootnode-"
	echo "$0 4"
	exit 1
fi

generate_address() {
	subkey inspect ${3:-} ${4:-} "$VALIDATORS_ROOT_SEED//$PREFIX$1//$2" | grep "SS58 Address" | awk '{ print $3 }'
}

V_NUM=$(($1 - 1))

BALANCES='\"balances\": {"balances": [\n'
INVULNERABLES='"invulnerables": [\n'
STAKERS='"stakers": [\n'
SESSION='"session": {\n   "keys": [\n'

SUDO_ADDRESS=$(subkey inspect $SUDO_SEED | grep "SS58 Address" | awk '{ print $3 }')
BALANCES+="  [\"${SUDO_ADDRESS}\", 1000000000000000000],\n"
SUDO="\"sudo\": {\"key\": \"${SUDO_ADDRESS}\" }"

for i in $(seq 0 $V_NUM); do
  if [ $i -eq $V_NUM ]
  then
    LAST=""
  else
    LAST=','
  fi
  STASH=$(generate_address $i stash)

  BALANCES+="  [\"${STASH}\", 100000000000000]${LAST}\n"
  INVULNERABLES+="  \"${STASH}\"${LAST}\n"
  STAKERS+="  [\"${STASH}\", \"$(generate_address $i controller)\", 100000000000000, \"Validator\"]${LAST}\n"

	SESSION+="[\n"
	SESSION+="  \"${STASH}\",\n"
	SESSION+="  \"${STASH}\",\n"
	SESSION+="  {\n"
	SESSION+="    \"grandpa\": \"$(generate_address $i grandpa '--scheme ed25519')\",\n"
	SESSION+="    \"babe\": \"$(generate_address $i babe '--scheme sr25519')\",\n"
	SESSION+="    \"im_online\": \"$(generate_address $i im_online '--scheme sr25519')\",\n"
	SESSION+="    \"para_validator\": \"$(generate_address $i para_validator '--scheme sr25519')\",\n"
	SESSION+="    \"para_assignment\": \"$(generate_address $i para_assignment '--scheme sr25519')\",\n"
	SESSION+="    \"authority_discovery\": \"$(generate_address $i authority_discovery '--scheme sr25519')\"\n"
	#SESSION+="    \"beefy\": \"$(generate_address $i beefy '--scheme ecdsa')\"\n"
	SESSION+="  }\n]${LAST}\n"
done
BALANCES+="]}"
INVULNERABLES+="]"
STAKERS+="]"
SESSION+='  ]\n}\n'

CHAINSPEC='
  {
    "name": "Wococo",
    "id": "wococo",
    "chainType": "Live",
    "genesis": {
      "runtime": {
       '"$BALANCES, \"staking\": {\"validatorCount\": 10, ${INVULNERABLES}, ${STAKERS}}, ${SESSION}, ${SUDO}"'
       }
    }
  }
'

printf "$CHAINSPEC" | jq

