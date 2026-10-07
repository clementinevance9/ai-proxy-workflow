import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parents[1]))
from proxy.server import ALLOWED_PATHS, build_request, load_aliases, rewrite_payload


class ProxyTests(unittest.TestCase):
    def test_paths_and_body_cap_are_explicit(self):
        self.assertIn("/responses", ALLOWED_PATHS)
        self.assertIn("/images/edits", ALLOWED_PATHS)
        source = (pathlib.Path(__file__).parents[1] / "proxy/server.py").read_text(encoding="utf-8")
        self.assertIn("MAX_BODY_BYTES = 2_000_000", source)
        self.assertIn("MAX_RESPONSE_BYTES = 20_000_000", source)

    def test_alias_rewrite_is_json_only_and_precise(self):
        body = rewrite_payload(b'{"model":"fast","input":"hello"}', {"fast": "gpt-6-sol"})
        self.assertEqual(json.loads(body)["model"], "gpt-6-sol")
        with self.assertRaises(ValueError):
            rewrite_payload(b"[]", {})
        with self.assertRaises(ValueError):
            rewrite_payload(b'{"model": 3}', {})

    def test_alias_config_validation(self):
        self.assertEqual(load_aliases('{"fast":"gpt-6-sol"}')["fast"], "gpt-6-sol")
        with self.assertRaises(ValueError):
            load_aliases("[]")
        with self.assertRaises(ValueError):
            load_aliases('{"fast": 3}')

    def test_upstream_request_contains_neutral_user_agent_and_auth(self):
        request = build_request("/responses", b"{}", "https://argolink.io/v1", "test-key")
        self.assertEqual(request.full_url, "https://argolink.io/v1/responses")
        self.assertEqual(request.get_header("User-agent"), "ai-proxy-workflow/1.0")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-key")
        self.assertEqual(request.get_header("Content-length"), "2")

    def test_no_retired_base_or_key_in_source(self):
        source = (pathlib.Path(__file__).parents[1] / "proxy/server.py").read_text(encoding="utf-8")
        self.assertNotIn("api." + "argolink.io", source)
        self.assertNotIn("sk-", source.lower())


if __name__ == "__main__":
    unittest.main()
