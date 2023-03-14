# Parity Testnet Manager

A simple UI and REST API to operate Polkadot multi-chains testnets in Kubernetes.

The **testnet-manager** let you view the following information about nodes running in your cluster:

- List Substrate nodes running in Kubernetes and query their status over RPC
- List Validators running in Kubernetes
- List Parachains and collator nodes

When provided with the relay-chain Sudo account, the **testnet-manager** can perform the following actions:

- Register/Deregister validator nodes
- Rotate validator session keys
- Onboard/Offboard a parachain
- Register/Deregister parachain collators
- Execute runtime upgrades on relay-chains and common good parachains

## Running tests

    python -m pytest

## Running locally

Note that running with those commands will fail to connect to your Kubernetes cluster and running nodes without adapting them to your setup.
As such, it is recommended to refer to the next section for instructions to run a complete local stack in Kubernetes.

Setup the local environment:

```shell
poetry install
poetry shell
```

Set environment variables, eg:

    NAMESPACE=rococo
    HEALTHY_MIN_PEER_COUNT="1"
    WS_ENDPOINT: "wss://rococo-rpc.polkadot.io"
    NODE_HTTP_PATTERN: "http://NODE_NAME.rococo:9933"
    NODE_WS_PATTERN: "ws://NODE_NAME.rococo:9944"
    HEALTHY_MIN_PEER_COUNT: "1"
    SUDO_SEED=***
    VALIDATORS_ROOT_SEED=***
    TESTNET_MANAGER_CONSENSUS=poa

Start the app:

    # Dev
    python -m uvicorn main:app --reload
    # Prod
    python -m gunicorn -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:5000 --timeout=3600 --capture-output --enable-stdio-inheritance --workers 4

## Running in a Local Kubernetes cluster

Install either [Minikube](https://minikube.sigs.k8s.io/docs/start/) or [Rancher-Desktop](https://rancherdesktop.io/).
Then, start your Kubernetes cluster in a VM and run:

```shell
cd local-kubernetes
make setup
make apply
```

Remark: Wait for the "setup" step (chainspec building) to complete before installing to prevent the nodes from failing to pull chainspecs files.
For more information see [helm/minikube/README.md](local-kubernetes/README.md)

Continuously deploy to Kubernetes with [Skaffold](https://skaffold.dev/):

```shell
skaffold dev
```
