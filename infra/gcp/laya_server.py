#!/usr/bin/env python3
"""Serve a Laya checkpoint (convaiinnovations/laya) behind TypeSafe's /v1/systemone request and response shape.

Laya is an in-process Python API with no HTTP server of its own. This wrapper is standard library only, so the
same file runs on the VM (as goldrails-run-laya) and on a laptop for a check. The checkpoint is pinned by
revision through huggingface_hub and loaded with the author's package; questions pass through unchanged because
Laya takes Jev's typed questions as they are and answers in Jev's shape (noul, choice with probabilities, score
with legend and probabilities).

    python laya_server.py --ref convaiinnovations/laya --revision <sha> --port 8012 --device cuda:0
"""
from __future__ import annotations

import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MAX_BODY = 4 * 1024 * 1024


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default="convaiinnovations/laya")
    ap.add_argument("--revision", required=True, help="40-hex commit of the Hugging Face repo")
    ap.add_argument("--subfolder", default=None, help="checkpoint inside the repo, e.g. multilingual")
    ap.add_argument("--model-name", default="laya", help="what /v1/models reports and requests may name")
    ap.add_argument("--device", default=None)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8012)
    a = ap.parse_args()

    from huggingface_hub import snapshot_download
    import laya

    path = snapshot_download(a.ref, revision=a.revision)
    t0 = time.perf_counter()
    agent = laya.load(path, device=a.device, subfolder=a.subfolder)
    print(json.dumps({"loaded": a.ref, "revision": a.revision, "device": str(agent.device),
                      "laya": getattr(laya, "__version__", None), "load_s": round(time.perf_counter() - t0, 1)}), flush=True)
    lock = threading.Lock()
    accepted = {None, a.model_name, a.ref, "laya"}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # one line per request, like the other servers
            print(f"{self.address_string()} - {fmt % args}", flush=True)

        def send(self, code, obj):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/v1/models":
                return self.send(200, {"models": [{"id": a.model_name, "name": a.model_name, "ref": a.ref, "revision": a.revision}]})
            if self.path == "/health":
                return self.send(200, {"ok": True})
            self.send(404, {"error": "not found"})

        def do_POST(self):
            if self.path != "/v1/systemone":
                return self.send(404, {"error": "not found"})
            try:
                n = int(self.headers.get("Content-Length", "0"))
                if n < 1 or n > MAX_BODY:
                    return self.send(413, {"error": "body size outside limits"})
                req = json.loads(self.rfile.read(n))
                if not isinstance(req, dict) or "state" not in req or not isinstance(req.get("questions"), dict):
                    return self.send(422, {"error": "request requires state and questions"})
                if req.get("model") not in accepted:
                    return self.send(422, {"error": "requested model is not loaded; see /v1/models"})
            except (ValueError, TypeError) as e:
                return self.send(422, {"error": str(e)})
            t = time.perf_counter()
            try:
                with lock:
                    out = agent.predict(req["state"], req["questions"])
            except (ValueError, KeyError, TypeError) as e:
                return self.send(422, {"error": str(e)})
            except Exception as e:  # never substitute an answer when inference fails
                import traceback; traceback.print_exc()
                return self.send(500, {"error": "model inference failed", "error_type": type(e).__name__})
            out["model"] = a.model_name
            out["metadata"] = {"ref": a.ref, "revision": a.revision, "device": str(agent.device),
                               "inference_seconds": round(time.perf_counter() - t, 4)}
            self.send(200, out)

    print(json.dumps({"url": f"http://{a.host}:{a.port}", "model": a.model_name}), flush=True)
    ThreadingHTTPServer((a.host, a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
