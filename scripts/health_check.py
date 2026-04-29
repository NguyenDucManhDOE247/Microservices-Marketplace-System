#!/usr/bin/env python3
"""
health_check.py — Online Service Marketplace Health Monitor

Checks:
  1. Kubernetes pod/deployment status (via kubectl)
  2. HTTP endpoints via Ingress (if --base-url provided)

Usage:
  python health_check.py
  python health_check.py --namespace osm --base-url http://<INGRESS_IP>
  python health_check.py --skip-k8s --base-url http://<INGRESS_IP>

Environment variables:
  OSM_NAMESPACE   K8s namespace (default: osm)
  OSM_BASE_URL    Ingress/LoadBalancer URL for HTTP checks
  OSM_TIMEOUT     HTTP timeout seconds (default: 10)

Exit codes:
  0  All checks passed
  1  One or more checks failed
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# ── ANSI colours ──────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Service definitions ───────────────────────────────────────────────────────
DEPLOYMENTS = [
    "user-service",
    "product-service",
    "order-service",
    "payment-service",
    "frontend",
    "gateway",
]

HTTP_ENDPOINTS = [
    {"name": "frontend",        "path": "/",             "expected": 200},
    {"name": "user-service",    "path": "/api/users",    "expected": 200},
    {"name": "product-service", "path": "/api/products", "expected": 200},
    {"name": "order-service",   "path": "/api/orders",   "expected": 200},
    {"name": "payment-service", "path": "/api/payments", "expected": 200},
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def ok_icon(ok: bool) -> str:
    return f"{GREEN}✓ PASS{RESET}" if ok else f"{RED}✗ FAIL{RESET}"


def run_kubectl(args: list) -> tuple:
    cmd = ["kubectl"] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


# ── K8s checks ────────────────────────────────────────────────────────────────

def check_pods(namespace: str) -> dict:
    rc, out, err = run_kubectl(["get", "pods", "-n", namespace, "-o", "json"])
    if rc != 0:
        return {
            "ok": False,
            "error": err or "kubectl unavailable / namespace not found",
            "pods": [],
        }

    pods = json.loads(out).get("items", [])
    results = []
    all_ok = True
    for pod in pods:
        name   = pod["metadata"]["name"]
        phase  = pod["status"].get("phase", "Unknown")
        cstats = pod["status"].get("containerStatuses", [])
        ready  = sum(1 for c in cstats if c.get("ready"))
        total  = len(cstats)
        pod_ok = phase == "Running" and ready == total
        if not pod_ok:
            all_ok = False
        results.append({
            "name":  name,
            "phase": phase,
            "ready": f"{ready}/{total}",
            "ok":    pod_ok,
        })

    return {"ok": all_ok, "pods": results}


def check_deployments(namespace: str) -> dict:
    results = []
    all_ok  = True
    for deploy in DEPLOYMENTS:
        rc, out, _ = run_kubectl([
            "rollout", "status",
            f"deployment/{deploy}",
            "-n", namespace,
            "--timeout=15s",
        ])
        ok = rc == 0
        if not ok:
            all_ok = False
        msg = (out.split("\n")[-1]) if out else "no output"
        results.append({"name": deploy, "ok": ok, "message": msg})
    return {"ok": all_ok, "deployments": results}


# ── HTTP checks ───────────────────────────────────────────────────────────────

def check_http_endpoints(base_url: str, timeout: int) -> dict:
    if not REQUESTS_AVAILABLE:
        return {
            "ok": False,
            "error": "requests not installed — run: pip install -r requirements.txt",
            "endpoints": [],
        }

    results = []
    all_ok  = True
    for ep in HTTP_ENDPOINTS:
        url = f"{base_url.rstrip('/')}{ep['path']}"
        try:
            t0   = time.time()
            resp = requests.get(url, timeout=timeout, allow_redirects=True)
            ms   = int((time.time() - t0) * 1000)
            ok   = resp.status_code == ep["expected"]
        except requests.exceptions.Timeout:
            results.append({
                "name": ep["name"], "url": url,
                "status": "TIMEOUT", "ms": timeout * 1000, "ok": False,
            })
            all_ok = False
            continue
        except requests.exceptions.ConnectionError as exc:
            results.append({
                "name": ep["name"], "url": url,
                "status": "CONN_ERR", "ms": 0, "ok": False, "error": str(exc),
            })
            all_ok = False
            continue

        if not ok:
            all_ok = False
        results.append({
            "name": ep["name"], "url": url,
            "status": resp.status_code, "ms": ms, "ok": ok,
        })

    return {"ok": all_ok, "endpoints": results}


# ── Report printers ───────────────────────────────────────────────────────────

def section(title: str):
    print(f"\n{BOLD}{'─' * 62}{RESET}")
    print(f"{BOLD}  {title}{RESET}")
    print(f"{BOLD}{'─' * 62}{RESET}")


def print_pods(result: dict):
    section("POD STATUS")
    if "error" in result:
        print(f"  {RED}{result['error']}{RESET}")
        return
    print(f"  {BOLD}{'NAME':<48} {'PHASE':<12} READY{RESET}")
    for p in result["pods"]:
        print(f"  {p['name']:<48} {p['phase']:<12} {p['ready']:<6}  {ok_icon(p['ok'])}")
    print(f"\n  Overall: {ok_icon(result['ok'])}")


def print_deployments(result: dict):
    section("DEPLOYMENT ROLLOUT")
    for d in result["deployments"]:
        print(f"  {d['name']:<30}  {ok_icon(d['ok'])}  {d['message']}")
    print(f"\n  Overall: {ok_icon(result['ok'])}")


def print_http(result: dict):
    section("HTTP ENDPOINTS")
    if "error" in result:
        print(f"  {RED}{result['error']}{RESET}")
        return
    print(f"  {BOLD}{'SERVICE':<20} {'STATUS':<10} {'TIME':>8}{RESET}")
    for ep in result["endpoints"]:
        ms_str = f"{ep['ms']}ms"
        print(f"  {ep['name']:<20} {str(ep['status']):<10} {ms_str:>8}  {ok_icon(ep['ok'])}")
    print(f"\n  Overall: {ok_icon(result['ok'])}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="OSM Health Check")
    p.add_argument(
        "--namespace", "-n",
        default=os.environ.get("OSM_NAMESPACE", "osm"),
        help="K8s namespace (default: osm)",
    )
    p.add_argument(
        "--base-url", "-u",
        default=os.environ.get("OSM_BASE_URL", ""),
        help="Ingress URL for HTTP checks, e.g. http://<IP>",
    )
    p.add_argument(
        "--timeout", "-t",
        type=int,
        default=int(os.environ.get("OSM_TIMEOUT", "10")),
        help="HTTP timeout seconds (default: 10)",
    )
    p.add_argument(
        "--skip-k8s",
        action="store_true",
        help="Skip kubectl checks (no kubeconfig required)",
    )
    return p.parse_args()


def main():
    args = parse_args()
    ts   = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Auto-prepend http:// when no scheme is provided
    if args.base_url and not args.base_url.startswith(("http://", "https://")):
        args.base_url = "http://" + args.base_url

    print(f"\n{BOLD}{'=' * 62}{RESET}")
    print(f"{BOLD}  OSM Health Check  —  {ts}{RESET}")
    print(f"{BOLD}  Namespace : {args.namespace}{RESET}")
    if args.base_url:
        print(f"{BOLD}  Base URL  : {args.base_url}{RESET}")
    print(f"{BOLD}{'=' * 62}{RESET}")

    all_ok = True

    if not args.skip_k8s:
        pod_res    = check_pods(args.namespace)
        deploy_res = check_deployments(args.namespace)
        print_pods(pod_res)
        print_deployments(deploy_res)
        if not pod_res["ok"] or not deploy_res["ok"]:
            all_ok = False
    else:
        print(f"\n  {YELLOW}K8s checks skipped (--skip-k8s){RESET}")

    if args.base_url:
        http_res = check_http_endpoints(args.base_url, args.timeout)
        print_http(http_res)
        if not http_res["ok"]:
            all_ok = False
    else:
        print(f"\n  {YELLOW}HTTP checks skipped — provide --base-url to enable{RESET}")

    print(f"\n{BOLD}{'=' * 62}{RESET}")
    if all_ok:
        print(f"{BOLD}  RESULT: {GREEN}ALL CHECKS PASSED ✓{RESET}")
    else:
        print(f"{BOLD}  RESULT: {RED}ONE OR MORE CHECKS FAILED ✗{RESET}")
    print(f"{BOLD}{'=' * 62}{RESET}\n")

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
