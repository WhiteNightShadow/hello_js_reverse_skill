# SPDX-License-Identifier: CC0-1.0
"""Offline adversarial tests for the public real-case preparation boundary.

Real npm builds and real MCP validation are separate explicit CLI runs.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1] / "scripts/real_cases"
sys.path.insert(0, str(TOOLS))
import prepare
import validate
from mcp_session import tool_error, unpack


class PreparationSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="real-case-security-")
        self.root = Path(self.temporary.name).resolve()

    def tearDown(self):
        self.temporary.cleanup()

    def archive(self, entries):
        path = self.root / "source.tar.gz"
        with tarfile.open(path, "w:gz") as tar:
            for name, kind, payload in entries:
                info = tarfile.TarInfo(name)
                info.type = kind
                info.mode = 0o7777
                if kind == tarfile.REGTYPE:
                    info.size = len(payload)
                    tar.addfile(info, io.BytesIO(payload))
                else:
                    if kind in (tarfile.SYMTYPE, tarfile.LNKTYPE):
                        info.linkname = payload.decode()
                    tar.addfile(info)
        return path

    def test_exact_bytes_and_license_preserved_without_permission_bits(self):
        archive = self.archive([("repo-commit/", tarfile.DIRTYPE, b""),
                                ("repo-commit/LICENSE", tarfile.REGTYPE, b"Original license\n"),
                                ("repo-commit/src/code.js", tarfile.REGTYPE, b"export const value = 3;\n")])
        dest = self.root / "out"
        rows = prepare.extract_archive(archive, dest, "repo-commit")
        self.assertEqual((dest / "LICENSE").read_bytes(), b"Original license\n")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["sha256"], hashlib.sha256(b"Original license\n").hexdigest())
        mode = (dest / "LICENSE").stat().st_mode & 0o7777
        if os.name == "nt":
            # Windows chmod only controls the read-only flag; POSIX owner/group
            # masks are not preserved. Still verify a writable regular file and
            # that the archive's executable/special bits were not carried over.
            self.assertTrue(mode & 0o200)
            self.assertEqual(mode & 0o7111, 0)
        else:
            self.assertEqual(mode, 0o644)

    def test_malicious_archive_is_rejected_before_any_extraction(self):
        cases = [
            [("/repo-commit/escape", tarfile.REGTYPE, b"x")],
            [("repo-commit/../escape", tarfile.REGTYPE, b"x")],
            [("repo-commit/./escape", tarfile.REGTYPE, b"x")],
            [("repo-commit//escape", tarfile.REGTYPE, b"x")],
            [("C:/repo-commit/escape", tarfile.REGTYPE, b"x")],
            [("repo-commit/C:/escape", tarfile.REGTYPE, b"x")],
            [("repo-commit/a\\..\\escape", tarfile.REGTYPE, b"x")],
            [("other-root/escape", tarfile.REGTYPE, b"x")],
            [("repo-commit/link", tarfile.SYMTYPE, b"../../escape")],
            [("repo-commit/link", tarfile.LNKTYPE, b"repo-commit/ok")],
            [("repo-commit/pipe", tarfile.FIFOTYPE, b"")],
            [("repo-commit/device", tarfile.CHRTYPE, b"")],
            [("repo-commit/dup", tarfile.REGTYPE, b"a"), ("repo-commit/dup", tarfile.REGTYPE, b"b")],
            [("repo-commit/A", tarfile.REGTYPE, b"a"), ("repo-commit/a", tarfile.REGTYPE, b"b")],
            [("repo-commit/file", tarfile.REGTYPE, b"a"), ("repo-commit/file/child", tarfile.REGTYPE, b"b")],
        ]
        for entries in cases:
            with self.subTest(entries=entries):
                archive = self.archive([("repo-commit/ok", tarfile.REGTYPE, b"first valid entry")] + entries)
                with self.assertRaises(ValueError):
                    prepare.extract_archive(archive, self.root / "out", "repo-commit")
                self.assertFalse((self.root / "out").exists())
                self.assertFalse((self.root / "escape").exists())

    def test_limits_empty_archive_and_refusal_to_overwrite(self):
        archive = self.archive([("repo-commit/data", tarfile.REGTYPE, b"12345")])
        with patch.object(prepare, "MAX_EXPANDED", 4), self.assertRaises(ValueError):
            prepare.extract_archive(archive, self.root / "out", "repo-commit")
        self.assertFalse((self.root / "out").exists())
        (self.root / "out").mkdir()
        with self.assertRaises(FileExistsError):
            prepare.extract_archive(archive, self.root / "out", "repo-commit")
        archive = self.archive([])
        with self.assertRaises(ValueError):
            prepare.extract_archive(archive, self.root / "empty", "repo-commit")

    def test_output_paths_and_read_only_cache_boundary(self):
        existing = self.root / "existing"
        existing.mkdir()
        marker = existing / "user-data"
        marker.write_text("keep", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            prepare.prepare(existing)
        self.assertEqual(marker.read_text(encoding="utf-8"), "keep")
        for path in (self.root / "missing/out", self.root / "../escape", TOOLS / "forbidden-output"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                prepare.validate_output(path)
        link = self.root / "alias"
        link.symlink_to(existing, target_is_directory=True)
        for path in (link, link / "child"):
            with self.assertRaises(ValueError):
                prepare.validate_output(path)
        broken = self.root / "broken"
        broken.symlink_to(self.root / "absent")
        with self.assertRaises(ValueError):
            prepare.validate_output(broken)
        with self.assertRaises(ValueError):
            prepare.prepare(existing / "new-output", existing)
        self.assertFalse((existing / "new-output").exists())

    def test_cache_hash_is_verified_and_bad_cache_never_falls_back_to_network(self):
        cache, downloads = self.root / "cache", self.root / "downloads"
        cache.mkdir(); downloads.mkdir()
        pin = {"archive": "repo-commit.tar.gz", "name": "repo", "commit": "commit",
               "url": "https://codeload.github.com/example/repo/tar.gz/commit",
               "sha256": hashlib.sha256(b"expected").hexdigest()}
        file = cache / pin["archive"]
        file.write_bytes(b"wrong")
        with patch.object(prepare.urllib.request, "urlopen", side_effect=AssertionError("unexpected network")):
            with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
                prepare.fetch_archive(pin, downloads, cache)
            self.assertFalse((downloads / pin["archive"]).exists())
            self.assertEqual(file.read_bytes(), b"wrong")
            file.write_bytes(b"expected")
            result, record = prepare.fetch_archive(pin, downloads, cache)
            self.assertEqual(result.read_bytes(), b"expected")
            self.assertEqual(record["obtained_from"], "cache")
            self.assertEqual(file.read_bytes(), b"expected")
            with self.assertRaises(FileExistsError):
                prepare.fetch_archive(pin, downloads, cache)
            self.assertEqual(result.read_bytes(), b"expected")

    def test_cache_symlink_and_download_size_limit(self):
        cache, downloads = self.root / "cache", self.root / "downloads"
        cache.mkdir(); downloads.mkdir()
        file = self.root / "file"
        file.write_bytes(b"payload")
        pin = {"archive": "source.tar.gz", "name": "source", "commit": "commit", "sha256": prepare.sha256(file)}
        (cache / pin["archive"]).symlink_to(file)
        with self.assertRaises(ValueError):
            prepare.fetch_archive(pin, downloads, cache)
        (cache / pin["archive"]).unlink()
        (cache / pin["archive"]).write_bytes(b"payload")
        with patch.object(prepare, "MAX_ARCHIVE", 2), self.assertRaises(ValueError):
            prepare.fetch_archive(pin, downloads, cache)
        self.assertFalse((downloads / pin["archive"]).exists())

    def test_recipes_are_fixed_and_do_not_bundle_upstream_or_acorn(self):
        for area in ("vm-cff", "crypto-fingerprint"):
            prepare.validate_lock(TOOLS / "templates" / area)
        vm_package = json.loads((TOOLS / "templates/vm-cff/package.json").read_text(encoding="utf-8"))
        self.assertNotIn("acorn", vm_package["dependencies"])
        forbidden = {"node_modules", "upstream", "vendor", "downloads", "samples", ".cache", "dist", "build"}
        for path in (TOOLS / "templates").rglob("*"):
            self.assertFalse(forbidden.intersection(path.relative_to(TOOLS / "templates").parts), str(path))
        self.assertEqual(len(json.loads((TOOLS / "sources.json").read_text(encoding="utf-8"))), 4)

    def test_poisoned_build_environment_is_not_used(self):
        with patch.dict(os.environ, {"NODE_OPTIONS": "--require untrusted.js", "NODE_PATH": "outside",
                                    "ESBUILD_BINARY_PATH": "outside", "NPM_CONFIG_PREFIX": "outside",
                                    "NODE_ENV": "production", "npm_config_ignore_scripts": "false"}):
            env = prepare.build_env(self.root)
        self.assertEqual(env["npm_config_ignore_scripts"], "true")
        for key in ("NODE_OPTIONS", "NODE_PATH", "ESBUILD_BINARY_PATH", "NPM_CONFIG_PREFIX", "NODE_ENV"):
            self.assertNotIn(key, env)

    def test_cli_help_and_invalid_output_do_not_require_mcp_or_browser(self):
        for script in ("prepare.py", "validate.py"):
            result = subprocess.run([sys.executable, "-B", str(TOOLS / script), "--help"], capture_output=True, text=True, encoding="utf-8", timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run([sys.executable, "-B", str(TOOLS / "prepare.py"), "--output", str(self.root)], capture_output=True, text=True, encoding="utf-8", timeout=10)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Refusing to overwrite", result.stderr)


class ValidationEvidenceTests(unittest.TestCase):
    def test_transport_errors_are_not_confused_with_success(self):
        raw = {"isError": True, "structuredContent": {"ok": True}}
        self.assertTrue(tool_error(raw, unpack(raw)))
        self.assertTrue(tool_error({}, {"mode": "error", "reason": "No events"}))
        self.assertEqual(unpack({"content": [{"type": "text", "text": '{"result":{"ok":true}}'}]}), {"result": {"ok": True}})
        self.assertEqual(validate.evaluation({"result": {"ok": True}}), {"ok": True})
        self.assertEqual(validate.evaluation({"type": "json", "value": {"ok": True}}), {"ok": True})

    def test_stock_browser_missing_ack_empty_and_truncated_native_never_pass(self):
        with self.assertRaises(RuntimeError):
            validate.check_native_capability({"engine_trace": {"enabled": True}, "browser_runtime": {"repo": "official"}}, {"acknowledged": True})
        launch = {"engine_trace": {"enabled": True}, "browser_runtime": {
            "repo": "custom", "property_trace": True, "property_trace_compatible": True}}
        with self.assertRaises(RuntimeError):
            validate.check_native_capability(launch, {"live_processes": 2})
        stopped = {"acknowledged": True, "trace_enabled": False}
        for trace in ({}, {"total_events": 10, "events": []},
                      {"coverage": {"scope": "fingerprint-native"}, "total_events": 1, "events": [{}], "truncated": True}):
            with self.subTest(trace=trace), self.assertRaises(RuntimeError):
                validate.check_native_events(trace, stopped)

    def test_empty_fingerprint_does_not_count_as_real_collection(self):
        with self.assertRaises(RuntimeError):
            validate.check_fingerprint({"stable": True, "version": "5.2.0", "monitoring": False})


if __name__ == "__main__":
    unittest.main()
