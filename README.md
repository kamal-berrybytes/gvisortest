# Fibonacci Code Agent with Gvisor Sandbox

This project implements a secure code generation, execution, and evaluation workflow using Gvisor sandboxing in a Kubernetes Kind cluster. The system uses LangChain or DSPy to prompt a model to generate Fibonacci code in Python, executes it in a sandbox environment, and evaluates the output before passing verified code to a second agent.

**Everything runs in Kubernetes** - from code generation to sandbox execution to evaluation.

## Architecture Overview

The complete workflow runs as Kubernetes Jobs and Workflows:

1. **Code Generation Job** - Agent prompts LLM to generate Fibonacci code
2. **Security Analysis Job** - Analyzes code for malicious patterns
3. **Sandbox Execution Job** - Executes code in Gvisor-isolated pod
4. **Evaluation Job** - Validates output against unit tests
5. **Second Agent Job** - Executes verified code in production-like environment

### Kubernetes Components

- **RuntimeClass**: Defines the Gvisor runtime using the `runsc` handler
- **Jobs**: Each agent component runs as a Kubernetes Job
- **Workflow**: Argo Workflows orchestrates the complete pipeline
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
│   ├── langchain_agent.py      # LangChain/DSPy-based code generator
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
- (Optional) Argo Workflows for orchestration

## Setup Instructions

### 1. Create Kind Cluster with Gvisor

```bash
# Build custom Gvisor node image
cd kindCluster
docker build -t kindest/node-gvisor:latest .

# Create Kind cluster
kind create cluster --config kind-config.yaml

# Apply RuntimeClass
kubectl apply -f runtimeclass.yaml

# Verify
kubectl get runtimeclass
```

### 2. Build Agent Container Image

```bash
# Build the agent image
docker build -t fibonacci-agent:latest .

# Load into Kind cluster
kind load docker-image fibonacci-agent:latest
```

### 3. Deploy to Kubernetes

```bash
# Apply namespace, config, and RBAC
kubectl apply -f kubernetes/agent-deployment.yaml
kubectl apply -f kubernetes/rbac.yaml

# Apply the jobs
kubectl apply -f kubernetes/agent-jobs.yaml
```

### 4. Run the Workflow (Argo Workflows)

```bash
# Install Argo Workflows
kubectl apply -f https://raw.githubusercontent.com/argoproj/argo-workflows/stable/manifests/quick-start-postgres.yaml

# Wait for Argo to be ready
kubectl get pods -n argo

# Submit the workflow
kubectl apply -f kubernetes/agent-workflow.yaml
argo submit kubernetes/agent-workflow.yaml -n fibonacci-agent
```

### 5. Run Individual Jobs

```bash
# Jobs run in sequence via dependencies
kubectl apply -f kubernetes/agent-jobs.yaml

# Check status
kubectl get jobs -n fibonacci-agent
kubectl get pods -n fibonacci-agent
```

## Workflow Steps

### Step 1: generate-code (Job)
- Uses LangChain/DSPy to prompt LLM for Fibonacci code
- Generates unit tests using pytest
- Saves to PersistentVolume or ConfigMap

### Step 2: security-analysis (Job)
- Analyzes code for dangerous patterns
- Checks for subprocess, eval, exec, network access, file operations
- Produces security report

### Step 3: sandbox-execution (Job)
- Creates Gvisor-isolated pod
- Executes generated code with resource limits
- Captures output and errors

### Step 4: evaluate-code (Job)
- Runs unit tests
- Validates Fibonacci correctness
- Produces evaluation report

### Step 5: second-agent (Job)
- Receives verified code
- Executes in production-like environment
- Generates final report

## Security Features

- **Gvisor Isolation**: Sandboxed container execution using runsc
- **RuntimeClass**: Kubernetes-level runtime isolation
- **Resource Limits**: CPU and memory restrictions per job
- **Security Context**: Non-root user, read-only filesystem, dropped capabilities
- **Job Dependencies**: Each step must pass before next runs
- **TTL Cleanup**: Jobs auto-cleanup after completion (300s)

## Example Output

```bash
$ kubectl get pods -n fibonacci-agent

NAME                              READY   STATUS      RESTARTS   AGE
fibonacci-code-generator-xxxxx    0/1     Completed   0          2m
fibonacci-security-analyzer-xxxxx 0/1     Completed   0          3m
fibonacci-sandbox-executor-xxxxx  0/1     Completed   0          5m
fibonacci-code-evaluator-xxxxx    0/1     Completed   0          6m
fibonacci-second-agent-xxxxx      0/1     Completed   0          7m

$ kubectl logs fibonacci-code-evaluator-xxxxx -n fibonacci-agent
2024-01-15 10:30:00 - INFO - Evaluating code
2024-01-15 10:30:00 - INFO - Evaluation complete. Passed: 5/5
```

## Configuration

Edit ConfigMap for agent settings:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: fibonacci-agent-config
  namespace: fibonacci-agent
data:
  AGENT_MODEL: "gpt-4"
  AGENT_PROVIDER: "langchain"
  SANDBOX_RUNTIME: "gvisor"
  EXECUTION_TIMEOUT: "30"
  MAX_MEMORY: "128Mi"
  MAX_CPU: "500m"
```

## Local Testing

Run locally without Kubernetes:

```bash
# Set environment variables (optional)
export OPENAI_API_KEY=your-api-key

# Run the agent
python agent/main.py
```

## Verification

Check generated artifacts:

```bash
# In a job pod
kubectl exec -it fibonacci-code-evaluator-xxxxx -n fibonacci-agent -- ls /tmp/generated/

# View security report
kubectl exec fibonacci-code-evaluator-xxxxx -n fibonacci-agent -- cat /tmp/generated/security_report.json

# View evaluation results
kubectl exec fibonacci-code-evaluator-xxxxx -n fibonacci-agent -- cat /tmp/generated/evaluation_result.json
```

## Dependencies

- Python 3.11+
- Kubernetes (Kind cluster)
- Gvisor (runsc)
- Argo Workflows (optional, for orchestration)
- Docker
- kubectl
- langchain, dspy (optional, for LLM code generation)

## License

MIT
