# Install Helm

```
curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3

chmod 700 get_helm.sh

./get_helm.sh
```

## Initialize a Helm Chart Repository

```
helm repo add bitnami https://charts.bitnami.com/bitnami
```