## How-to: Deploy 

### Magic version (minikube or rancher-desktop)
> The minikube/rancher-desktop,helm and kubectl binaries should be in your path

Run:
```bash
make all
```
`make all` will perform the following operation: 
1a. Start minikube 
```bash
make minikube
```
1b. Start the rancher-desktop application

2. Build docker image inside `minikube` or `rancher-desktop` folders.
```bash
make build
```
2. Install app
```bash
make install
```
3. Open dashboard
```bash
make dash
```

### Normal version
see `.gitlab-ci.yml` file

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

1. Remove charts but keep the data: `make uninstall`

2. Remove charts and their data `make cleanup`

3. *I'm done* (destroy minikube and everything in it) `make destroy`
