# Deploy ML Models on AWS EKS with Kubeflow, KServe, Helm, and kubectl

This guide explains the EKS deployment path in simple beginner language.

Think of the tools like this:

- Kubeflow manages the ML workflow.
- KServe serves the model.
- Helm installs and upgrades the platform components.
- kubectl operates and debugs the running cluster.

Amazon EKS is the Kubernetes cluster where all of this runs.

This README focuses on the easiest useful path for a first deployment:

1. Create an EKS cluster.
2. Install cert-manager and KServe with Helm.
3. Put a trained model in Amazon S3.
4. Give KServe permission to read the model from S3.
5. Deploy a KServe InferenceService.
6. Test the prediction API.
7. Use Helm and kubectl for upgrades and debugging.

For the first deployment, this guide uses KServe's built-in scikit-learn runtime. That means you do not need to build a custom Docker image or push anything to Amazon ECR just to get started.

## What Each Tool Does

- Kubeflow is the workflow layer. Use it for notebooks, pipelines, experiments, and training workflows.
- KServe is the online serving layer. It runs the model behind an HTTP prediction endpoint.
- Helm installs cluster software such as cert-manager and KServe, and upgrades those platform components later.
- kubectl is the daily operations tool. Use it to apply YAML, check pods, view logs, and inspect errors.

If you only want to serve one model first, start with KServe. Add Kubeflow after the serving path works.

## Target Architecture

```text
Kubeflow pipeline or external training job -> model artifact in Amazon S3
                                                |
                                                v
                                         KServe InferenceService on EKS
                                                |
                                                v
                                           Prediction API
```

## Prerequisites

Install these tools first:

- AWS account with permission to create EKS, IAM, S3, and EC2 resources
- AWS CLI v2
- eksctl
- kubectl
- Helm 3
- A trained model file such as `model.joblib`

On Windows, you can install them with `winget`:

```powershell
winget install -e --id Amazon.AWSCLI --accept-source-agreements --accept-package-agreements
winget install -e --id eksctl.eksctl --accept-source-agreements --accept-package-agreements
winget install -e --id Kubernetes.kubectl --accept-source-agreements --accept-package-agreements
winget install -e --id Helm.Helm --version 3.20.0 --accept-source-agreements --accept-package-agreements
```

This guide assumes Helm 3. If you already installed Helm 4, replace it with a Helm 3 release before continuing.

Verify the tools:

```powershell
aws --version
eksctl version
kubectl version --client
helm version
```

Configure AWS credentials:

```powershell
aws configure
```

## IAM Access Flow for kubectl

ClusterIAMRole: EKS - Cluster

NodeIAMRole: EC2

ClusterIAMRole: AmazonEKSClusterPolicy

NodeIAMRole: AmazonEKSWorkerNodePolicy, AmazonEC2ContainerRegistryPullOnly, AmazonEKS_CNI_Policy

Example admin access flow:

```powershell
$CLUSTER_NAME = ""
$AWS_REGION = ""
$ADMIN_ROLE_ARN = ""

aws eks create-access-entry `
  --cluster-name $CLUSTER_NAME `
  --region $AWS_REGION `
  --principal-arn $ADMIN_ROLE_ARN `
  --type STANDARD

aws eks associate-access-policy `
  --cluster-name $CLUSTER_NAME `
  --region $AWS_REGION `
  --principal-arn $ADMIN_ROLE_ARN `
  --policy-arn arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy `
  --access-scope type=cluster

aws eks update-kubeconfig --name kousik_cluster_1 --region ap-south-2

when we enter aws configure we give the access_key and secret_access_key right its when we create the role.

now when we create cluster we give cluster_role and node_role 

cluster > access > add a new access for our local role being used.

Open your cluster.
Open the Access tab.
Open Access entries.
Click Create access entry.
Principal ARN:
choose arn:aws:iam::932566365205:role/kousik_role
or choose your IAM user if that is what you use locally
Type:
choose Standard
Save the access entry.
After creating it, attach an access policy.
Choose:
AmazonEKSClusterAdminPolicy

kubectl get nodes
```

If you see `the server has asked for the client to provide credentials`, your kubeconfig may be present, but the IAM principal you are using still does not have cluster access.
In that case, fix the access entry or the role assumption path first.

## Create the EKS Cluster and Worker Nodes

Important:

- `kubectl` does not create the EKS control plane or EC2 worker nodes.
- `eksctl` creates the EKS cluster and managed node groups.
- `kubectl` connects to the cluster after it exists.
- Helm installs software into the cluster. Helm does not create the cluster itself.

Set a cluster name, AWS Region, and node size:

```powershell
$CLUSTER_NAME = ""
$AWS_REGION = ""
$NODE_TYPE = "t3.medium"
```

For this guide, `t3.medium` is the practical minimum for running EKS add-ons plus KServe or Kubeflow components.
If your AWS account or console workflow is restricted to Free Tier-eligible EC2 types, do not keep `t3.medium` selected. That exact combination causes the managed node group to fail with `InvalidParameterCombination`.

Use one of these paths instead:

- Keep `$NODE_TYPE = "t3.medium"` and remove the Free Tier-only restriction.
- Or temporarily switch `$NODE_TYPE` to an x86_64 Free Tier-eligible type such as `t3.micro` after verifying what is available in your Region:

```powershell
aws ec2 describe-instance-types `
  --region $AWS_REGION `
  --filters Name=free-tier-eligible,Values=true `
  --query "InstanceTypes[?contains(ProcessorInfo.SupportedArchitectures, 'x86_64')].InstanceType" `
  --output text
```

Free Tier-sized nodes are only useful for validating that cluster creation works. They are usually too small for Kubeflow, KServe, or other multi-service ML workloads.

Create a new EKS cluster with one managed node group:

```powershell
eksctl create cluster `
       --name $CLUSTER_NAME `
       --region $AWS_REGION `
       --version 1.30 `
       --nodegroup-name linux-nodes `
       --node-type $NODE_TYPE `
       --nodes 2 `
       --nodes-min 2 `
       --nodes-max 4 `
       --managed
```

This command creates:

- The EKS control plane
- The required AWS networking resources
- A managed node group named `linux-nodes`
- Two worker nodes to start with
- A local `kubeconfig` entry in most cases so `kubectl` can connect

Confirm that the cluster is ready:

```powershell
aws eks list-clusters --region $AWS_REGION
aws eks update-kubeconfig --region $AWS_REGION --name $CLUSTER_NAME
# Use a human or CI access role that has an EKS access entry. Do not use the EC2 node role here.
aws eks update-kubeconfig --region $AWS_REGION --name $CLUSTER_NAME --role-arn arn:aws:iam::123456789012:role/EKSClusterAdminRole
kubectl get nodes
kubectl config current-context
kubectl cluster-info
kubectl get nodes -o wide
```

`kubectl` does not detect Amazon EKS automatically. It only reads your local `kubeconfig`.
If no EKS context is configured, `kubectl` falls back to `http://localhost:8080`.
If the EKS context exists but you see `the server has asked for the client to provide credentials`, your current AWS identity does not have access to that cluster yet.

If you need another node group later, create one with `eksctl`:

```powershell
eksctl create nodegroup `
       --cluster $CLUSTER_NAME `
       --region $AWS_REGION `
       --name batch-nodes `
       --node-type t3.large `
       --nodes 2 `
       --nodes-min 1 `
       --nodes-max 4 `
       --managed
```

If you only want to change the node count for an existing node group, scale it:

```powershell
eksctl scale nodegroup `
       --cluster $CLUSTER_NAME `
       --region $AWS_REGION `
       --name linux-nodes `
       --nodes 3
```

## View Nodes, Namespaces, and Pods with kubectl

After the cluster is up, these are the most useful inspection commands:

```powershell
kubectl get nodes
kubectl get nodes -o wide
kubectl get namespaces
kubectl get pods -A
kubectl get pods -n kube-system
kubectl get pods -o wide -A
```

Useful follow-up commands:

```powershell
kubectl describe node <node-name>
kubectl describe pod <pod-name> -n <namespace>
kubectl logs <pod-name> -n <namespace>
```

Example: view the system pods that EKS created:

```powershell
kubectl get pods -n kube-system
```