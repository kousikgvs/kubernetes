Streamlit Deployment Commands (EKS + ECR)

1) Set variables

$AWS_REGION = "ap-south-2"
$AWS_ACCOUNT_ID = "932566365205"
$CLUSTER_NAME = "kousik_cluster"
$ECR_REPO_NAME = "streamlit_repo"
$IMAGE_TAG = "v1"
$IMAGE_URI = "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}:${IMAGE_TAG}"

2) Verify AWS identity and cluster access

aws sts get-caller-identity
aws eks update-kubeconfig --name $CLUSTER_NAME --region $AWS_REGION
kubectl get nodes

3) Create ECR repo if missing

aws ecr create-repository --repository-name $ECR_REPO_NAME --region $AWS_REGION

If AlreadyExistsException appears, continue.

4) Login Docker to ECR

aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

5) Build, tag, push image

docker build -t "${ECR_REPO_NAME}:${IMAGE_TAG}" .\frontend
docker tag "${ECR_REPO_NAME}:${IMAGE_TAG}" "${IMAGE_URI}"
docker push "${IMAGE_URI}"

6) Confirm image tag exists in ECR

aws ecr describe-images --region $AWS_REGION --repository-name $ECR_REPO_NAME --query "imageDetails[].imageTags" --output json

7) Ensure deployment image matches pushed repo/tag

kubectl set image deployment/streamlit-frontend streamlit-frontend="$IMAGE_URI" -n streamlit-app

8) Apply manifests

kubectl apply -f .\k8s\streamlit.yaml -f .\k8s\service.yaml

9) Verify rollout and endpoints

kubectl rollout status deployment/streamlit-frontend -n streamlit-app

kubectl get pods -n streamlit-app -o wide

kubectl get endpoints streamlit-frontend -n 
streamlit-app

kubectl get svc streamlit-frontend -n streamlit-app

kubectl get svc streamlit-frontend -n streamlit-app -w

10) If EXTERNAL-IP stays pending

Check subnet tags in the EKS VPC:

- kubernetes.io/role/elb = 1 (public LB)
- kubernetes.io/role/internal-elb = 1 (internal LB)

Then run:

kubectl describe svc streamlit-frontend -n streamlit-app

11) If URL is not reachable

kubectl get pods -n streamlit-app
kubectl describe pod -n streamlit-app <pod-name>
kubectl logs -n streamlit-app <pod-name>

If pods show ImagePullBackOff, rebuild and push image again (steps 5 and 6), then restart rollout:

kubectl rollout restart deployment/streamlit-frontend -n streamlit-app
kubectl rollout status deployment/streamlit-frontend -n streamlit-app