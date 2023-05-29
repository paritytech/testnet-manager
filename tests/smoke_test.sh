#!/bin/bash -e

# Usage:
# kubectl --context minikube  port-forward service/testnet-manager 8080:80 -n rococo
# ./smoke_test.sh

ROUTE='index.html
nodes
nodes/localrococo-bootnode-0
nodes/localrococo-moonbase-alice-node-0
nodes/localrococo-shell-collator-node-0
nodes/localrococo-statemint-alice-node-0
validators
parachains
parachains/1000/runtime
parachains/1001/runtime
collators/1000
collators/1001
runtime
runtime/metadata
'

for path in $ROUTE;
do
  echo "/$path"
  curl --fail --silent --show-error http://localhost:8080/$path --create-dirs --remote-name --output-dir ./output
done

find ./output -type f -not -name "*.html" -exec mv {} {}.html \;
