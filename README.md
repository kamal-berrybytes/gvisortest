# Fibonacci Code Agent with Gvisor Sandbox

This project implements a secure code generation, execution, and evaluation workflow using Gvisor sandboxing in a Kubernetes Kind cluster. The system uses LangChain to prompt a model to generate Fibonacci code in Python, executes it in a sandbox environment, and evaluates the output before passing verified code to a second agent.

**Everything runs in Kubernetes** - from code generation to sandbox execution to evaluation.

## Architecture Overview

The complete workflow runs as Kubernetes Jobs:

1. **Code Generation Job** - Agent prompts LLM to generate Fibonacci code
2. **Security Analysis Job** - Analyzes code for malicious patterns
3. **Sandbox Execution Job** - Executes code in Gvisor-isolated pod
4. **Evaluation Job** - Validates output against unit tests
5. **Second Agent Job** - Executes verified code in production-like environment

### Kubernetes Components

- **RuntimeClass**: Defines the Gvisor runtime using the `runsc` handler
- **Jobs**: Each agent component runs as a Kubernetes Job
- **PersistentVolumeClaim**: Shared storage for code/artifacts between jobs
- **ConfigMap**: Configuration for the agent

## Project Structure

```
gvisor/
├── kindCluster/
│   ├── Dockerfile              # Custom Kind node with Gvisor
│   ├── kind-config.yaml        # Kind cluster configuration
│   └── runtimeclass.yaml       # Gvisor RuntimeClass
├── agent/
│   ├── main.py                 # Main agent orchestration
│   ├── langchain_agent.py      # LangChain-based code generator
│   └── second_agent.py         # Second agent for verified code
├── sandbox/
│   └── gvisor_executor.py      # Gvisor sandbox executor
├── evaluation/
│   └── evaluator.py            # Code evaluation module
├── security/
│   └── security_analyzer.py    # Security analysis
├── kubernetes/
│   ├── agent-deployment.yaml   # Namespace, ConfigMap, PVC
│   ├── agent-jobs.yaml         # Kubernetes Jobs for each step
│   ├── agent-workflow.yaml     # Argo Workflow for orchestration
│   └── rbac.yaml               # ServiceAccount and RBAC
├── testpod/
│   └── busyboxpod.yaml         # Test pod for Gvisor
├── Dockerfile                  # Agent container image
└── requirements.txt            # Python dependencies
```

## Prerequisites

- Docker
- Kind cluster with Gvisor integration
- kubectl configured

## Setup Instructions

### 1. Kind Cluster with Gvisor

The cluster should already be created with Gvisor integration:

```bash
# Verify cluster exists
kind get clusters

# Verify nodes
kubectl get nodes -o wide

# Verify RuntimeClass
kubectl get runtimeclass
```

### 2. Build Agent Container Image

```bash
# Build the agent image
docker build -t fibonacci-agent:latest .

# Load into Kind cluster (required for pods to use the image)
kind load docker-image fibonacci-agent:latest --name gvisor-cluster
```

### 3. Deploy to Kubernetes

```bash
# Apply namespace, config, PVC, and RBAC
kubectl apply -f kubernetes/agent-deployment.yaml
kubectl apply -f kubernetes/rbac.yaml

# Apply the jobs
kubectl apply -f kubernetes/agent-jobs.yaml
```

### 4. Monitor Execution

```bash
# Watch job status
kubectl get jobs -n fibonacci-agent

# Watch pods
kubectl get pods -n fibonacci-agent

# Check logs
kubectl logs -n fibonacci-agent job/fibonacci-code-generator
kubectl logs -n fibonacci-agent job/fibonacci-security-analyzer
kubectl logs -n fibonacci-agent job/fibonacci-sandbox-executor
kubectl logs -n fibonacci-agent job/fibonacci-code-evaluator
kubectl logs -n fibonacci-agent job/fibonacci-second-agent
```

## Workflow Steps

### Step 1: fibonacci-code-generator (Job)
- Uses LangChain to prompt LLM for Fibonacci code
- Generates unit tests using pytest
- Saves to `/tmp/generated/fibonacci.py`
- Note: Falls back to template generation if no LLM API key is configured

### Step 2: fibonacci-security-analyzer (Job)
- Analyzes code for dangerous patterns
- Checks for subprocess, eval, exec, network access, file operations
- Produces security report at `/tmp/generated/security_report.json`

### Step 3: fibonacci-sandbox-executor (Job)
- Executes generated code with Gvisor runtime
- Uses resource limits (128Mi memory, 500m CPU)
- Saves execution result to `/tmp/generated/execution_result.json`

### Step 4: fibonacci-code-evaluator (Job)
- Runs unit tests against generated code
- Validates Fibonacci correctness
- Produces evaluation report at `/tmp/generated/evaluation_result.json`

### Step 5: fibonacci-second-agent (Job)
- Receives verified code
- Executes in production-like environment
- Generates final report

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `KUBERNETES_MODE` | Run in Kubernetes | `false` |
| `CODE_OUTPUT_DIR` | Output directory | `/tmp/generated` |
| `RUNTIME_CLASS` | Gvisor runtime | `gvisor` |
| `EXECUTION_TIMEOUT` | Timeout in seconds | `30` |
| `MAX_MEMORY` | Memory limit | `128Mi` |
| `MAX_CPU` | CPU limit | `500m` |

### Job Configuration

Each job uses:
- `runtimeClassName: gvisor` - Run with Gvisor isolation
- `imagePullPolicy: Never` - Use locally loaded image
- Resource limits for CPU and memory

## Verifying Gvisor Configuration

### 1. Check RuntimeClass exists

```bash
kubectl get runtimeclass
```

Expected output:
```
NAME     HANDLER   AGE
gvisor   runsc     XXm
```

### 2. Verify runsc is registered in containerd

```bash
docker exec gvisor-cluster-worker crictl info | grep -A2 runsc
```

Expected output:
```
"runsc": {
  "runtimeType": "io.containerd.runsc.v1",
```

### 3. Check pods use Gvisor runtime

```bash
kubectl get pods -n fibonacci-agent -o wide
```

Verify the `RUNTIME CLASS` column shows `gvisor`:
```
kubectl get pods -n fibonacci-agent -o jsonpath='{.items[*].spec.runtimeClassName}'
```

### 4. Verify runtimeClassName in pod spec

```bash
kubectl get pod <pod-name> -n fibonacci-agent -o jsonpath='{.spec.runtimeClassName}'
```

Should output: `gvisor`

### 5. Check pod events for Gvisor

```bash
kubectl describe pod <pod-name> -n fibonacci-agent | grep -i runtime
```

Should show: `RuntimeClass: gvisor`

## Troubleshooting

### ErrImagePull / ImagePullBackOff

If pods fail with `ErrImagePull` or `ImagePullBackOff`, the image isn't available in the cluster's container runtime.

**Symptom:**
```
Failed to pull image "fibonacci-agent:latest": pull access denied, repository does not exist or may require authorization
```

**Cause:** Kubernetes is trying to pull from Docker Hub instead of using the locally built image.

**Solution:**

1. **Load image into Kind cluster nodes:**
   ```bash
   kind load docker-image fibonacci-agent:latest --name gvisor-cluster
   ```

2. **Add `imagePullPolicy: Never` to job specs:**
   
   Edit `kubernetes/agent-jobs.yaml` and add `imagePullPolicy: Never` to each container spec:
   ```yaml
   containers:
     - name: generator
       image: fibonacci-agent:latest
       imagePullPolicy: Never  # Add this line
   ```

3. **Reapply jobs:**
   ```bash
   kubectl delete jobs -n fibonacci-agent --all
   kubectl apply -f kubernetes/agent-jobs.yaml
   ```

**Alternative - Use a local registry:**
```bash
# Create a local registry
docker run -d --name registry -p 5000:5000 registry:2

# Tag and push to local registry
docker tag fibonacci-agent:latest localhost:5000/fibonacci-agent:latest
docker push localhost:5000/fibonacci-agent:latest

# Update job images to use localhost:5000/fibonacci-agent:latest
```

## Known Issues

1. **LLM API Key Required** - The LangChain agent requires an LLM provider (OpenAI, Anthropic, etc.) with API key configured. Without it, falls back to template generation.

2. **Security Analyzer False Positives** - The security analyzer may flag some safe patterns (e.g., pytest imports). Review the security report before using code in production.

3. **RBAC for Nested Pods** - The sandbox executor needs proper RBAC to create pods within Kubernetes. Current setup may require additional ClusterRole bindings for full nested pod execution.

## Security Features

- **Gvisor Isolation**: Sandboxed container execution using runsc
- **RuntimeClass**: Kubernetes-level runtime isolation
- **Resource Limits**: CPU and memory restrictions per job
- **Persistent Volume**: Shared storage for artifacts between jobs
- **No Auto-Delete**: Jobs remain after completion for inspection

## Example Output

```bash
$ kubectl get pods -n fibonacci-agent

NAME                                READY   STATUS      RESTARTS   AGE
fibonacci-code-generator-w965j      0/1     Completed   0          9s
fibonacci-security-analyzer-wjkxr  0/1     Completed   0          9s
fibonacci-sandbox-executor-26kvx   0/1     Completed   0          9s
fibonacci-code-evaluator-fgdx8     0/1     Completed   0          9s
fibonacci-second-agent-kvw4z        0/1     Completed   0          9s

$ kubectl logs -n fibonacci-agent job/fibonacci-code-evaluator
2026-03-23 13:21:15,571 - INFO - Evaluation complete. Passed: 5/5
```

## Verification

Check generated artifacts in any completed job pod:

```bash
# List generated files
kubectl exec fibonacci-code-evaluator-fgdx8 -n fibonacci-agent -- ls /tmp/generated/

# View security report
kubectl exec fibonacci-code-evaluator-fgdx8 -n fibonacci-agent -- cat /tmp/generated/security_report.json

# View evaluation results
kubectl exec fibonacci-code-evaluator-fgdx8 -n fibonacci-agent -- cat /tmp/generated/evaluation_result.json
```

## Cleanup

```bash
# Delete all jobs
kubectl delete jobs -n fibonacci-agent --all

# Delete namespace and all resources
kubectl delete namespace fibonacci-agent
```

## Dependencies

- Python 3.11+
- Kubernetes (Kind cluster)
- Gvisor (runsc)
- Docker
- kubectl
- langchain (for LLM code generation)
