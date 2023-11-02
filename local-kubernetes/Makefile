# ============================================================================================
# Validator-manager Quick Deploy Makefile for Development and Testing
# ============================================================================================

KUBERNETES_CONTEXT = minikube #  minikube or rancher-desktop
# rococo or wococo (don't put space at the end of the variable it will be used as is)
CHAIN_NAMESPACE = rococo

# ============================================================================================

all: kube check build install

# ============================================================================================

kube: kube_${KUBERNETES_CONTEXT}

kube_minikube:
	@minikube start \
		--addons ingress --addons metrics-server --addons registry --driver docker \
		--kubernetes-version=1.27.4 --memory=6g --cpus=2

kube_minikube-podman:
	@minikube start \
		--addons ingress --addons metrics-server --addons registry --driver podman \
		--container-runtime=containerd --memory=8g --cpus=4

kube_rancher-desktop:
	@rancher-desktop

# ============================================================================================

check:
	@kubectl config use-context ${KUBERNETES_CONTEXT}
	@kubectl --context ${KUBERNETES_CONTEXT} get nodes

setup: setup_${KUBERNETES_CONTEXT}

setup_minikube:
	@kubectl --context ${KUBERNETES_CONTEXT} apply -f ./kube-setup

setup_rancher-desktop:
	@kubectl --context ${KUBERNETES_CONTEXT} apply -f ./kube-setup -f ./rancher-desktop/kube-setup

build: check build_${KUBERNETES_CONTEXT}

build_minikube:
	cd ../. && minikube image build . -t local/testnet-manager

build_rancher-desktop:
	cd ../. && docker image build -t local/testnet-manager:latest .

# ============================================================================================

rpc:
	@xdg-open 'https://polkadot.js.org/apps/?rpc=ws%3A%2F%2F127.0.0.1%3A9944#/explorer'
	@kubectl --context ${KUBERNETES_CONTEXT} port-forward service/local-${CHAIN_NAMESPACE}-bootnode 9944:9944 -n ${CHAIN_NAMESPACE}

para-shell:
	@xdg-open 'https://polkadot.js.org/apps/?rpc=ws%3A%2F%2F127.0.0.1%3A9948#/explorer'
	@kubectl --context ${KUBERNETES_CONTEXT} port-forward service/local-${CHAIN_NAMESPACE}-shell-collator-node 9948:9944 -n ${CHAIN_NAMESPACE}

para-moon:
	@xdg-open 'https://polkadot.js.org/apps/?rpc=ws%3A%2F%2F127.0.0.1%3A9949#/explorer'
	@kubectl --context ${KUBERNETES_CONTEXT} port-forward service/local-${CHAIN_NAMESPACE}-moonbase-alice-node 9949:9944 -n ${CHAIN_NAMESPACE}

para-mint:
	@xdg-open 'https://polkadot.js.org/apps/?rpc=ws%3A%2F%2F127.0.0.1%3A9950#/explorer'
	@kubectl --context ${KUBERNETES_CONTEXT} port-forward service/local-${CHAIN_NAMESPACE}-statemint-alice-node 9950:9944 -n ${CHAIN_NAMESPACE}

para-tick:
	@xdg-open 'https://polkadot.js.org/apps/?rpc=ws%3A%2F%2F127.0.0.1%3A9951#/explorer'
	@kubectl --context ${KUBERNETES_CONTEXT} port-forward service/local-${CHAIN_NAMESPACE}-tick-collator-node 9951:9944 -n ${CHAIN_NAMESPACE}

web:
	@xdg-open 'http://localhost:8080/'
	@kubectl --context ${KUBERNETES_CONTEXT} port-forward service/testnet-manager 8080:80 -n ${CHAIN_NAMESPACE}

web-tasks:
	@xdg-open 'http://localhost:8081/tasks'
	@kubectl --context ${KUBERNETES_CONTEXT} port-forward service/testnet-manager-task-scheduler 8081:80 -n ${CHAIN_NAMESPACE}

web-ci:
	kubectl --context ${KUBERNETES_CONTEXT} port-forward service/testnet-manager 8080:80 -n ${CHAIN_NAMESPACE} &
	timeout 30 sh -c 'until nc -z 127.0.0.1  8080; do sleep 1; echo -n .; done'

# ============================================================================================

apply: check
	@helmfile --file ./charts/helmfile-${CHAIN_NAMESPACE}.yaml apply

install: setup build apply

# ============================================================================================

reload: build
	@kubectl --context ${KUBERNETES_CONTEXT} delete pod  -l app.kubernetes.io/name=testnet-manager -n ${CHAIN_NAMESPACE}
	@kubectl --context ${KUBERNETES_CONTEXT} delete pod  -l app.kubernetes.io/name=testnet-manager-task-scheduler -n ${CHAIN_NAMESPACE} # force recreate testnet-manager pod
	@make log &
	@make web

log:
	@kubectl --context ${KUBERNETES_CONTEXT}  logs --tail 50 -f -l app.kubernetes.io/name=testnet-manager -n ${CHAIN_NAMESPACE}

# ============================================================================================

uninstall: check
	@helmfile --file ./charts/helmfile-${CHAIN_NAMESPACE}.yaml destroy
	@kubectl --context ${KUBERNETES_CONTEXT} delete pvc -n ${CHAIN_NAMESPACE} --all

cleanup: check
	@kubectl --context ${KUBERNETES_CONTEXT} delete namespace ${CHAIN_NAMESPACE}
