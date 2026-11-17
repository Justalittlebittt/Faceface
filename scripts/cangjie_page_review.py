#!/usr/bin/env python3
"""M16.5: private side-by-side scanned-page proofreading app.

Run from repository root:
  python -m scripts.cangjie_page_review \
    --scan-dir C:/faceface-corpus/scans \
    --ocr-dir C:/faceface-corpus/ocr \
    --reviewed-dir C:/faceface-corpus/reviewed

Open http://127.0.0.1:8765 . This server binds to loopback ONLY; no
cloud service, external JS libraries, analytics, OCR upload, or automatic
endorsement of OCR output. Needs Poppler pdfinfo/pdftoppm in PATH.
"""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
from urllib.parse import parse_qs, urlparse

from scripts.cangjie_review_core import ReviewWorkspace

PAGE = Path(__file__).with_name("cangjie_review_ui.html")
MAX_POST_BYTES = 120_000


class ReviewServer(ThreadingHTTPServer):
    def __init__(self, port: int, workspace: ReviewWorkspace):
        super().__init__(("127.0.0.1", port), ReviewHandler)
        self.workspace = workspace
        self.edit_token = secrets.token_urlsafe(32)


class ReviewHandler(BaseHTTPRequestHandler):
    server: ReviewServer

    def log_message(self, fmt: str, *args: object) -> None:
        # Don't echo any user-submitted transcription or reviewer in logs.
        if args and " /api/" in str(args[0]):
            return
        super().log_message(fmt, *args)

    def _response(self, status: int, data: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; connect-src 'self'; img-src 'self'; "
            "style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; "
            "object-src 'none'; frame-ancestors 'none'; base-uri 'none'",
        )
        self.end_headers()
        self.wfile.write(data)

    def _json(self, obj: object, status: int = 200) -> None:
        self._response(
            status, (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8"),
            "application/json; charset=utf-8",
        )

    def _allowed_host(self) -> bool:
        return self.headers.get("Host", "") in {
            f"127.0.0.1:{self.server.server_port}",
            f"localhost:{self.server.server_port}",
        }

    def _page_args(self, query: str) -> tuple[str, int]:
        params = parse_qs(query, keep_blank_values=False)
        source = params.get("source", [""])[0]
        index = int(params.get("index", ["-1"])[0])
        self.server.workspace.page_paths(source, index)
        return source, index

    def do_GET(self) -> None:
        if not self._allowed_host():
            self._json({"error": "Local host only"}, 403)
            return
        path = urlparse(self.path)
        try:
            if path.path == "/":
                html = PAGE.read_text(encoding="utf-8").replace(
                    "__LOCAL_REVIEW_TOKEN_JSON__",
                    json.dumps(self.server.edit_token),
                )
                self._response(200, html.encode("utf-8"), "text/html; charset=utf-8")
            elif path.path == "/api/status":
                self._json(self.server.workspace.summary())
            elif path.path == "/api/page":
                source, index = self._page_args(path.query)
                self._json(self.server.workspace.page_info(source, index))
            elif path.path == "/api/image":
                source, index = self._page_args(path.query)
                params = parse_qs(path.query)
                dpi = int(params.get("dpi", ["150"])[0])
                image = self.server.workspace.image_path(source, index, dpi)
                self._response(200, image.read_bytes(), "image/png")
            else:
                self._json({"error": "Not found"}, 404)
        except (ValueError, KeyError, TypeError) as exc:
            self._json({"error": str(exc)}, 400)
        except Exception as exc:
            # A programming/runtime error must be observable; not a false success.
            self._json({"error": type(exc).__name__ + ": " + str(exc)}, 500)

    def do_POST(self) -> None:
        if not self._allowed_host():
            self._json({"error": "Local host only"}, 403)
            return
        if self.path != "/api/review":
            self._json({"error": "Not found"}, 404)
            return
        origin = self.headers.get("Origin")
        if origin not in (None, f"http://127.0.0.1:{self.server.server_port}",
                          f"http://localhost:{self.server.server_port}"):
            self._json({"error": "Cross-origin write refused"}, 403)
            return
        if self.headers.get("X-Faceface-Review-Token") != self.server.edit_token:
            self._json({"error": "Review session token required"}, 403)
            return
        if not self.headers.get("Content-Type", "").startswith("application/json"):
            self._json({"error": "JSON required"}, 415)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 1 <= length <= MAX_POST_BYTES:
                self._json({"error": "Invalid review size"}, 413)
                return
            fields = json.loads(self.rfile.read(length))
            if not isinstance(fields, dict):
                raise ValueError("Expected review fields")
            result = self.server.workspace.save_review(
                source=fields["source"],
                index=fields["index"],
                text=fields["text"],
                reviewer=fields["reviewer"],
                confirmed_against_image=fields["confirmed_against_image"],
                content_type=fields.get("content_type", "text"),
                printed_volume=fields.get("printed_volume", ""),
                section=fields.get("section", ""),
                notes=fields.get("notes", ""),
            )
            self._json({"saved": True, "page_id": result["page_id"],
                        "text_sha256": result["text_sha256"]})
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            self._json({"error": str(exc)}, 400)
        except Exception as exc:
            self._json({"error": type(exc).__name__ + ": " + str(exc)}, 500)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan-dir", required=True, type=Path)
    parser.add_argument("--ocr-dir", required=True, type=Path)
    parser.add_argument("--reviewed-dir", required=True, type=Path)
    parser.add_argument("--draft-dir", type=Path, help="Private M16.6 vision-agent draft location")
    parser.add_argument("--port", default=8765, type=int)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Port must be 1024..65535")
    workspace = ReviewWorkspace(args.scan_dir, args.ocr_dir, args.reviewed_dir,
                                draft_dir=args.draft_dir)
    server = ReviewServer(args.port, workspace)
    print(f"Faceface PRIVATE local scan review: http://127.0.0.1:{args.port}")
    print("No internet service or OCR API; all review text and agent drafts remain on THIS computer.")
    print(json.dumps(workspace.summary(), ensure_ascii=False))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
