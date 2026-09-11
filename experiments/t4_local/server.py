from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .engine import LocalSimulator, SimulatorConfig, SimulatorError


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _depth(value, level=1):
    if isinstance(value, dict):
        return max([level] + [_depth(v, level + 1) for v in value.values()])
    if isinstance(value, list):
        return max([level] + [_depth(v, level + 1) for v in value])
    return level


def make_handler(simulator: LocalSimulator):
    class Handler(BaseHTTPRequestHandler):
        def _json(self, status: int, payload: dict):
            body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if self.path not in {"/enter", "/measure", "/clear", "/exit"}:
                self._json(404, simulator._base(False, rejected=True))
                return
            content_type = self.headers.get("Content-Type", "")
            parts = [part.strip().lower() for part in content_type.split(";")]
            if not parts or parts[0] != "application/json" or any(part != "charset=utf-8" for part in parts[1:]):
                self._json(415, simulator._base(False, rejected=True))
                return
            if self.headers.get("Content-Encoding", "identity").lower() != "identity":
                self._json(415, simulator._base(False, rejected=True))
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length > 65536:
                    self._json(413, simulator._base(False, rejected=True))
                    return
                payload = json.loads(self.rfile.read(length).decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
                if not isinstance(payload, dict):
                    raise ValueError("request body must be an object")
                if _depth(payload) > 16:
                    raise ValueError("JSON nesting exceeds 16 levels")
                response = simulator.handle(self.path, payload)
                self._json(200, response)
            except SimulatorError as exc:
                status = 409 if "conflict" in str(exc) else 400
                self._json(status, simulator._base(False, rejected=True) | {"error": str(exc)})
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                self._json(400, simulator._base(False, rejected=True) | {"error": str(exc)})

        def do_GET(self):
            self._json(405 if self.path in {"/enter", "/measure", "/clear", "/exit"} else 404, simulator._base(False, rejected=True))

        do_PUT = do_GET
        do_DELETE = do_GET
        do_PATCH = do_GET
        do_OPTIONS = do_GET

        def log_message(self, fmt, *args):
            return

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description="T4 local evaluator HTTP server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2027)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--robot-id", default="local-robot")
    parser.add_argument("--directional-probability", type=float, default=0.5)
    args = parser.parse_args()
    simulator = LocalSimulator(SimulatorConfig(seed=args.seed, robot_id=args.robot_id, directional_probability=args.directional_probability))
    server = ThreadingHTTPServer((args.host, args.port), make_handler(simulator))
    print(f"local evaluator ready: http://{args.host}:{args.port} seed={args.seed}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        print(json.dumps(simulator.truth_summary(), ensure_ascii=False, indent=2), flush=True)
        server.server_close()


if __name__ == "__main__":
    main()
