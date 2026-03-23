# Gvisor Code Execution Platform

A secure, Kubernetes-driven code generation, execution, and evaluation platform using Gvisor sandbox isolation.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Kubernetes](https://img.shields.io/badge/Kubernetes-Ready-blue)](https://kubernetes.io)

## Overview

This platform enables secure execution of arbitrary Python code in isolated Gvisor-sandboxed containers within Kubernetes. Every code execution creates a new, independent sandbox pod - ensuring complete isolation and no cross-contamination.

**Key Features:**
- 🔒 **Secure Execution** - Code runs in Gvisor-isolated containers
- 🔄 **Independent Sandboxes** - Each execution gets a fresh pod
- 🤖 **LLM Integration** - Generate code from AI models (OpenAI)
- 🧪 **Auto-Evaluation** - Automatic test generation and validation
- 🌐 **REST API + Web UI** - Submit code and view results via browser

## Table of Contents

- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Security](#security)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

```bash
# 1. Create Kind cluster with Gvisor
kind create cluster --config kindCluster/kind-config.yaml

# 2. Build and load image
docker build -t fibonacci-agent:latest .
kind load docker-image fibonacci-agent:latest --name gvisor-cluster

# 3. Deploy
kubectl apply -f kubernetes/agent-deployment.yaml
kubectl apply -f kubernetes/rbac.yaml
kubectl apply -f kubernetes/api-deployment.yaml

# 4. Access Web UI
kubectl get svc -n fibonacci-agent code-executor-api
# Open: http://<EXTERNAL-IP>:5000
```

That's it! The platform is ready to execute code.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Input                              │
│            (Task / Prompt / Direct Code)                       │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│  API Server (Deployment)                                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │   REST API  │  │   Web UI    │  │  In-Memory  │              │
│  │   Endpoint  │  │   (HTML)    │  │   Store     │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│  Step 1: Security Analysis                                     │
│  - Scans: subprocess, eval, exec, network, file ops            │
│  - Result: Safe ✅ or Unsafe ❌                                 │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│  Step 2: Gvisor Sandbox (NEW POD)                              │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Pod: sandbox-executor-xxxxx                             │    │
│  │ spec.runtimeClassName: gvisor                          │    │
│  │ securityContext:                                       │    │
│  │   - readOnlyRootFilesystem: true                      │    │
│  │   - allowPrivilegeEscalation: false                   │    │
│  │   - capabilities.drop: ALL                            │    │
│  │ resources: memory=128Mi, cpu=500m                     │    │
│  └─────────────────────────────────────────────────────────┘    │
│  Pod terminates after execution                                │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│  Step 3: Auto Evaluation                                        │
│  - Detects function type (fibonacci, sort, reverse, etc.)      │
│  - Generates appropriate test cases                            │
│  - Runs tests and reports pass/fail                            │
└─────────────────────────────────────────────────────────────────┘
                                ↓
                        Final Result
```

### Components

| Component | Type | Description |
|-----------|------|-------------|
| `run_dynamic.py` | CLI | Command-line execution |
| `api_server.py` | Web | REST API + Web UI |
| `gvisor_executor.py` | Library | Sandbox execution |
| `langchain_agent.py` | Library | LLM code generation |
| `evaluator.py` | Library | Auto-test generation |
| `security_analyzer.py` | Library | Security validation |

---

## Prerequisites

- Docker 20.10+
- Kubernetes cluster with Gvisor runtime
- kubectl configured
- (Optional) OpenAI API key for LLM code generation

### Verify Gvisor Setup

```bash
# Check RuntimeClass
kubectl get runtimeclass

# Should show:
# NAME   HANDLER    AGE
# gvisor runsc      XXm
```

---

## Installation

### 1. Create Kind Cluster with Gvisor

```bash
kind create cluster --config kindCluster/kind-config.yaml
```

### 2. Build Container Image

```bash
docker build -t fibonacci-agent:latest .
```

### 3. Load Image into Cluster

```bash
kind load docker-image fibonacci-agent:latest --name gvisor-cluster
```

### 4. Deploy Resources

```bash
# Core infrastructure
kubectl apply -f kubernetes/agent-deployment.yaml
kubectl apply -f kubernetes/rbac.yaml

# API Server + Web UI
kubectl apply -f kubernetes/api-deployment.yaml
```

### 5. Verify Deployment

```bash
# Check pods
kubectl get pods -n fibonacci-agent

# Check service
kubectl get svc -n fibonacci-agent code-executor-api
```

---

## Usage

### Option 1: Web UI (Recommended)

```bash
# Get service URL
kubectl get svc -n fibonacci-agent code-executor-api

# Open in browser
# http://<EXTERNAL-IP>:5000
```

Features:
- Submit code via Task (LLM), Prompt, or direct Code
- View execution history
- See test results in real-time

### Option 2: REST API

```bash
# Execute a task
curl -X POST http://<SERVICE-IP>:5000/api/execute \
  -H "Content-Type: application/json" \
  -d '{"mode": "task", "input": "reverse a string"}'

# Check status
curl http://<SERVICE-IP>:5000/api/status/<job_id>

# List all results
curl http://<SERVICE-IP>:5000/api/results
```

### Option 3: Kubernetes Job

```bash
# Deploy job
kubectl apply -f kubernetes/dynamic-job.yaml

# Customize task
kubectl set env job/dynamic-code-executor \
  TASK="calculate fibonacci" -n fibonacci-agent
```

---

## Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `KUBERNETES_MODE` | Force K8s execution | `true` | Yes |
| `CODE_OUTPUT_DIR` | Output directory | `/tmp/generated` | No |
| `RUNTIME_CLASS` | Runtime name | `gvisor` | Yes |
| `EXECUTION_TIMEOUT` | Max runtime (sec) | `30` | No |
| `MAX_MEMORY` | Memory limit | `128Mi` | No |
| `MAX_CPU` | CPU limit | `500m` | No |
| `OPENAI_API_KEY` | LLM API key | - | No |
| `AGENT_MODEL` | LLM model | `gpt-4` | No |

### Security Configuration

Each sandbox pod runs with:
- `runtimeClassName: gvisor` - Gvisor isolation
- `readOnlyRootFilesystem: true` - No filesystem writes
- `allowPrivilegeEscalation: false` - No privilege escalation
- `capabilities.drop: ALL` - No Linux capabilities
- `runAsNonRoot: true` - Non-root user (UID 1000)
- Resource limits: 128Mi memory, 500m CPU

---

## API Reference

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Web UI |
| POST | `/api/execute` | Submit code for execution |
| GET | `/api/status/<job_id>` | Get execution status |
| GET | `/api/results` | List all results |

### Execute Request

```json
{
  "mode": "task|prompt|code",
  "input": "string"
}
```

**Mode Options:**
- `task`: LLM generates code from task description
- `prompt`: LLM generates code from custom prompt  
- `code`: Execute provided Python code directly

### Response

```json
{
  "job_id": "uuid",
  "status": "pending|running|completed|failed",
  "security": { "safe": true, "report": "..." },
  "execution": { "success": true, "output": "..." },
  "evaluation": { "passed": true, "passed_tests": 3, "total_tests": 3 }
}
```

---

## Security

### Security Analysis

The platform scans for dangerous patterns:

| Category | Patterns |
|----------|----------|
| Execution | `subprocess`, `os.system`, `eval`, `exec` |
| Network | `socket`, `urllib`, `requests`, `http` |
| Filesystem | `os.chmod`, `os.remove`, `open(..., 'w')` |
| Imports | `__import__`, `pty`, `signal` |

### Defense Layers

1. **Gvisor Isolation** - Kernel-level sandbox
2. **Kubernetes RuntimeClass** - Pod-level isolation
3. **Security Context** - Container restrictions
4. **Resource Limits** - DoS prevention
5. **Security Analyzer** - Pre-execution validation

---

## Troubleshooting

### Pods Not Starting

```bash
# Check RuntimeClass
kubectl get runtimeclass

# Check containerd
docker exec <node> crictl info | grep runsc
```

### Image Pull Errors

```bash
# Reload image
kind load docker-image fibonacci-agent:latest --name gvisor-cluster

# Verify image
kubectl get pods -n fibonacci-agent -o wide
```

### Execution Timeouts

```bash
# Increase timeout
kubectl set env job/dynamic-code-executor EXECUTION_TIMEOUT=60 -n fibonacci-agent
```

### View Logs

```bash
# API server
kubectl logs -n fibonacci-agent -l app=code-executor-api

# Job logs
kubectl logs -n fibonacci-agent job/dynamic-code-executor
```

---

## Project Structure

```
gvisor/
├── agent/                  # Code generation
│   ├── langchain_agent.py
│   └── second_agent.py
├── sandbox/                # Execution
│   └── gvisor_executor.py
├── evaluation/            # Testing
│   └── evaluator.py
├── security/              # Analysis
│   └── security_analyzer.py
├── kubernetes/            # K8s manifests
│   ├── agent-deployment.yaml
│   ├── api-deployment.yaml
│   ├── dynamic-job.yaml
│   └── rbac.yaml
├── kindCluster/           # Cluster setup
│   ├── kind-config.yaml
│   └── runtimeclass.yaml
├── run_dynamic.py        # CLI entry point
├── api_server.py         # Web API
└── Dockerfile            # Container image
```

---

## License

MIT License - See [LICENSE](LICENSE) for details.