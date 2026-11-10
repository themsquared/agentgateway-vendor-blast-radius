#!/usr/bin/env python3
"""Stand-in for a third-party inference vendor's Chat Completions API.

Plays the role of "the vendor" in this demo (the role Fireworks AI played for
Notion). It only accepts requests that carry the vendor API key, and it never
sees who the end user is -- it just sees "a request from the gateway."
"""
import json
import os
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VENDOR_API_KEY = os.environ["MOCK_VENDOR_API_KEY"]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[mock-vendor] {self.address_string()} {fmt % args}")

    def do_POST(self):
        if self.path != "/v1/chat/completions":
            self.send_response(404)
            self.end_headers()
            return

        auth = self.headers.get("Authorization", "")
        if auth != f"Bearer {VENDOR_API_KEY}":
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "invalid vendor api key"}).encode())
            return

        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        model = body.get("model", "vendor-default")
        user_msg = ""
        for m in body.get("messages", []):
            if m.get("role") == "user":
                user_msg = m.get("content", "")

        reply = {
            "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": f"[mock-vendor saw: {user_msg!r}] response from {model}",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20},
        }
        payload = json.dumps(reply).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"[mock-vendor] listening on :{port}")
    server.serve_forever()
