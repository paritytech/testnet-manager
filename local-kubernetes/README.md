## Requirements

1. Helm
    a. Helmdiff
    b. Helmfile
2. Minikube or Rancher-desktop

## How-to: Deploy 

### Magic version (minikube or rancher-desktop)
> The minikube/rancher-desktop,helm and kubectl binaries should be in your path

Edit `Makefile` and set desired option. Example:
```
KUBERNETES_CONTEXT = minikube
CHAIN_NAMESPACE = rococo
```

Run:
```bash
make all
```
`make all` will perform the following operation: 
1. Start minikube or rancher-desktop depending on `KUBERNETES_CONTEXT` variable.
```bash
make kube
```
2. Build docker image inside `minikube` or `rancher-desktop` cluster.
```bash
make build
```
3. Install app
```bash
make install
```

### Normal version
see [testnet-manager](https://github.com/paritytech/helm-charts/tree/main/charts/testnet-manager) helm-chart.

## How-to: Access
### Alice RPC endpoint 
Run:
```
make rpc
```
This command will open browser and port-forward the 9944
> Note: you should have port `9944` free in your host before running `make rpc`

### Validator-manager web endpoint
Run:
```
make web
```
This command will open browser and port-forward the `8080` to k8s `80`

## How-to: Clean up

To clean that was created in these steps:

1. Remove charts but keep the namespace: `make uninstall`

2. Remove charts, their data and namespace `make cleanup`
