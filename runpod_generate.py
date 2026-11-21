#!/usr/bin/env python3
"""
Automated RunPod Community Cloud image generator for marketing scenes.
- Spins up an NVIDIA RTX A5000 (Community Cloud, ~$0.16/hr)
- Runs FLUX.1-schnell (Apache 2.0, ungated, fast 4-step generation)
- Downloads all scene PNGs from campaign.json into assets/scenes/
- ALWAYS terminates the Pod in finally: so no money is wasted.
"""

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
CAMPAIGN_PATH = BASE_DIR / "campaign.json"
SCENES_DIR = BASE_DIR / "assets" / "scenes"

GRAPHQL_URL = "https://api.runpod.io/graphql"
GPU_FALLBACK_LIST = [
    ("NVIDIA GeForce RTX 3090", 0.22),
    ("NVIDIA GeForce RTX 4090", 0.34),
    ("NVIDIA RTX 4000 Ada Generation", 0.20),
    ("NVIDIA RTX A5000", 0.16),
]
DOCKER_IMAGE = "runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404"

SERVER_PY = r'''
import base64
import io
import json
import os
import subprocess
import sys
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

os.environ["HF_HOME"] = "/workspace/hf_cache"
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"

pipe = None
load_error = None
load_stage = "starting"
gen_lock = threading.Lock()


def _load_model_bg():
    global pipe, load_error, load_stage
    try:
        load_stage = "pip installing diffusers/hf_transfer"
        proc = subprocess.run(
            [
                sys.executable, "-m", "pip", "install", "-q", "--no-cache-dir",
                "hf_transfer", "diffusers", "transformers", "accelerate", "sentencepiece", "protobuf",
            ],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"pip failed:\n{proc.stdout}\n{proc.stderr}")

        load_stage = "importing torch & diffusers"
        import torch
        from diffusers import DPMSolverMultistepScheduler, StableDiffusionXLPipeline

        load_stage = "downloading/loading RealVisXL_V5.0"
        p = StableDiffusionXLPipeline.from_pretrained(
            "SG161222/RealVisXL_V5.0",
            torch_dtype=torch.float16,
            use_safetensors=True,
        )
        p.scheduler = DPMSolverMultistepScheduler.from_config(
            p.scheduler.config, use_karras_sigmas=True
        )
        p.to("cuda")
        pipe = p
        load_stage = "ready"
    except Exception:
        load_error = traceback.format_exc()
        load_stage = "error"


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, code: int, obj: dict):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path == "/health":
            if load_error:
                self._send_json(200, {"status": "error", "stage": load_stage, "error": load_error})
            elif pipe is None:
                self._send_json(200, {"status": "loading", "stage": load_stage})
            else:
                self._send_json(200, {"status": "ready", "stage": "ready"})
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/generate":
            self._send_json(404, {"error": "not found"})
            return
        if pipe is None:
            self._send_json(503, {"error": f"Model not ready ({load_stage})"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            req = json.loads(self.rfile.read(length).decode("utf-8"))
            import torch
            with gen_lock:
                gen = torch.Generator(device="cuda").manual_seed(int(req.get("seed", 42)))
                img = pipe(
                    prompt=req["prompt"],
                    negative_prompt="text, letters, words, watermark, logo, signature, blurry, low quality, deformed",
                    width=int(req.get("width", 1024)),
                    height=int(req.get("height", 1024)),
                    num_inference_steps=int(req.get("steps", 25)),
                    guidance_scale=5.0,
                    generator=gen,
                ).images[0]
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            self._send_json(200, {"image_base64": base64.b64encode(buf.getvalue()).decode("utf-8")})
        except Exception:
            self._send_json(500, {"error": traceback.format_exc()})


if __name__ == "__main__":
    threading.Thread(target=_load_model_bg, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
'''


def load_api_key() -> str:
    if not ENV_PATH.exists():
        raise RuntimeError(f"Missing {ENV_PATH}")
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if line.startswith("RUNPOD_API_KEY="):
            key = line.split("=", 1)[1].strip().strip('"').strip("'")
            if key:
                return key
    raise RuntimeError("RUNPOD_API_KEY is empty in .env")


def gql(api_key: str, query: str, variables: dict | None = None) -> dict:
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    req = urllib.request.Request(
        GRAPHQL_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "hackathon-runpod-runner/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if "errors" in data and data["errors"]:
        raise RuntimeError(f"RunPod GraphQL error: {data['errors']}")
    return data["data"]


def deploy_pod(api_key: str, gpu_type_id: str) -> str:
    server_b64 = base64.b64encode(SERVER_PY.encode("utf-8")).decode("ascii")
    startup_cmd = (
        f"bash -c '"
        f"mkdir -p /workspace/hf_cache && "
        f"echo {server_b64} | base64 -d > /workspace/server.py && "
        f"python3 /workspace/server.py"
        f"'"
    )

    mutation = """
    mutation deployPod($input: PodFindAndDeployOnDemandInput!) {
      podFindAndDeployOnDemand(input: $input) {
        id
        name
        desiredStatus
        costPerHr
        machine { gpuDisplayName }
      }
    }
    """
    variables = {
        "input": {
            "cloudType": "COMMUNITY",
            "gpuCount": 1,
            "volumeInGb": 45,
            "containerDiskInGb": 15,
            "gpuTypeId": gpu_type_id,
            "name": "hackathon-flux-gen",
            "imageName": DOCKER_IMAGE,
            "dockerArgs": startup_cmd,
            "ports": "8000/http",
            "volumeMountPath": "/workspace",
            "env": [{"key": "HF_HOME", "value": "/workspace/hf_cache"}],
        }
    }
    res = gql(api_key, mutation, variables)
    pod = res["podFindAndDeployOnDemand"]
    print(
        f"[RunPod] Deployed Pod {pod['id']} | GPU: {gpu_type_id} | Cost: ${pod.get('costPerHr')}/hr",
        flush=True,
    )
    return pod["id"]


def terminate_pod(api_key: str, pod_id: str) -> None:
    mutation = """
    mutation terminatePod($input: PodTerminateInput!) {
      podTerminate(input: $input)
    }
    """
    try:
        gql(api_key, mutation, {"input": {"podId": pod_id}})
        print(f"[RunPod] Terminated Pod {pod_id} cleanly.", flush=True)
    except Exception as e:
        print(f"[RunPod] WARNING: Failed to terminate pod {pod_id}: {e}", flush=True)


def wait_for_ready(api_key: str, pod_id: str, timeout_sec: int = 420) -> str:
    base_url = f"https://{pod_id}-8000.proxy.runpod.net"
    health_url = f"{base_url}/health"
    start = time.time()
    last_log = 0.0
    print(f"[RunPod] Waiting for FLUX.1-schnell server at {health_url} ...", flush=True)
    while time.time() - start < timeout_sec:
        elapsed = int(time.time() - start)
        data = None
        try:
            req = urllib.request.Request(
                health_url, headers={"User-Agent": "hackathon-runpod-runner/1.0"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if time.time() - last_log > 20:
                print(f"[RunPod] {elapsed}s — booting/installing (HTTP {e.code}) ...", flush=True)
                last_log = time.time()
        except Exception as e:
            if time.time() - last_log > 20:
                uptime = None
                try:
                    pinfo = gql(api_key, f'{{ pod(input: {{podId: "{pod_id}"}}) {{ desiredStatus runtime {{ uptimeInSeconds }} }} }}')
                    pod_obj = pinfo.get("pod") or {}
                    uptime = (pod_obj.get("runtime") or {}).get("uptimeInSeconds")
                except Exception:
                    pass
                print(f"[RunPod] {elapsed}s — waiting ({type(e).__name__}: {e}, uptime={uptime}s) ...", flush=True)
                last_log = time.time()

        if data is not None:
            status = data.get("status")
            stage = data.get("stage", "")
            if status == "ready":
                print(f"[RunPod] Model is READY in {elapsed}s!", flush=True)
                return base_url
            if status == "error":
                raise RuntimeError(f"Pod model load error:\n{data.get('error')}")
            if time.time() - last_log > 15:
                print(f"[RunPod] {elapsed}s — status: {status} ({stage}) ...", flush=True)
                last_log = time.time()
        time.sleep(5)
    raise TimeoutError(f"Pod {pod_id} did not become ready within {timeout_sec}s")


def generate_scene(base_url: str, scene: dict, out_path: Path) -> None:
    payload = {
        "prompt": scene["prompt"],
        "width": 1024,
        "height": 1024,
        "steps": 25,
        "seed": scene.get("seed", 42),
    }
    req = urllib.request.Request(
        f"{base_url}/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "hackathon-runpod-runner/1.0",
        },
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    img_bytes = base64.b64decode(data["image_base64"])
    out_path.write_bytes(img_bytes)
    print(f"[Gen] Saved {out_path.name} ({len(img_bytes)//1024} KB) in {time.time()-t0:.1f}s", flush=True)


def discover_community_gpus(api_key: str, max_price: float = 0.65) -> list[tuple[str, float]]:
    query = """
    {
      gpuTypes {
        id
        displayName
        memoryInGb
        lowestPrice(input: { gpuCount: 1, secureCloud: false }) {
          stockStatus
          uninterruptablePrice
        }
      }
    }
    """
    data = gql(api_key, query)
    candidates = []
    for g in data["gpuTypes"]:
        lp = g.get("lowestPrice") or {}
        price = lp.get("uninterruptablePrice")
        if (
            lp.get("stockStatus")
            and price
            and price <= max_price
            and g.get("memoryInGb", 0) >= 16
            and "V100" not in g["id"]
        ):
            candidates.append((g["id"], float(price), g["memoryInGb"]))
    # Prefer >= 16GB and cheapest first
    candidates.sort(key=lambda x: (0 if x[2] >= 16 else 1, x[1]))
    return [(c[0], c[1]) for c in candidates]


def main() -> None:
    api_key = load_api_key()
    campaign = json.loads(CAMPAIGN_PATH.read_text(encoding="utf-8"))
    SCENES_DIR.mkdir(parents=True, exist_ok=True)

    scenes_to_gen = [
        s for s in campaign["scenes"] if not (SCENES_DIR / f"{s['id']}.png").exists()
    ]
    if not scenes_to_gen:
        print("[RunPod] All scenes already exist locally. Skipping GPU spin-up.")
        return

    if len(sys.argv) > 1:
        gpu_candidates = [(sys.argv[1], 0.25)]
    else:
        live = discover_community_gpus(api_key, max_price=0.65)
        print(f"[RunPod] Live Community Cloud candidates: {live}", flush=True)
        gpu_candidates = live + [g for g in GPU_FALLBACK_LIST if g[0] not in {x[0] for x in live}]
    pod_id = None
    chosen_rate = 0.20
    t_start = time.time()
    try:
        for gpu_id, rate in gpu_candidates:
            try:
                pod_id = deploy_pod(api_key, gpu_id)
                chosen_rate = rate
                break
            except RuntimeError as e:
                if "SUPPLY_CONSTRAINT" in str(e):
                    print(f"[RunPod] {gpu_id} out of stock in Community Cloud, trying next...", flush=True)
                    continue
                raise
        if not pod_id:
            raise RuntimeError("No GPU available in Community Cloud from fallback list.")
        base_url = wait_for_ready(api_key, pod_id)
        for scene in scenes_to_gen:
            out_path = SCENES_DIR / f"{scene['id']}.png"
            generate_scene(base_url, scene, out_path)
    finally:
        if pod_id:
            terminate_pod(api_key, pod_id)
            total_min = (time.time() - t_start) / 60.0
            print(f"[RunPod] Total session time: {total_min:.2f} min (~${total_min/60*chosen_rate:.4f})", flush=True)


if __name__ == "__main__":
    main()
