# Parity Testnet Manager

A simple UI and REST API to operate Polkadot multi-chains testnets in Kubernetes.

The **testnet-manager** let you view the following information about nodes running in your cluster:

- List Substrate nodes running in Kubernetes and query their status over RPC
- List Validators running in Kubernetes
- List Parachains

When provided with the relay-chain Sudo account, the **testnet-manager** can perform the following actions:

- Register/Deregister validator nodes
- Rotate validator session keys
- Onboard/Offboard a parachain
- Register/Deregister parachain collators

## Running locally

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
    VALIDATORS_ROOT_SEED=***
    SUDO_SEED=***

Start the app:

    # Local Dev
    python -m uvicorn main:app --reload
    # Prod
    python -m gunicorn -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:5000 --timeout=3600 --capture-output --enable-stdio-inheritance --workers 4

## Running tests

    python -m pytest

## Running in a Local Kubernetes cluster

Install either [Minikube](https://minikube.sigs.k8s.io/docs/start/) or [Rancher-Desktop](https://rancherdesktop.io/).
Then, start your Kubernetes cluster in a VM and run:

```shell
cd local-kubernetes/minikube # cd local-kubernetes/rancher-desktop
make setup
make install
```

Remark: Wait for the "setup" step (chainspec building) to complete before installing to prevent the node from failing to pull chainspecs files.
For more information see [helm/minikube/README.md](local-kubernetes/README.md)

Continuous deploy to Kubernetes with [Skaffold](https://skaffold.dev/):
```shell
skaffold dev
```
