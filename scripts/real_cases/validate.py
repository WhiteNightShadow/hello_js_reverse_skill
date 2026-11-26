#!/usr/bin/env python3
# SPDX-License-Identifier: CC0-1.0
"""Validate prepared assets through a fresh real MCP stdio/browser session."""
from __future__ import annotations

import argparse
import asyncio
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import threading
import traceback

sys.dont_write_bytecode = True

from mcp_session import connect
from prepare import HERE, checked_path, member_parts, sha256, write_json
from server import make_server

NATIVE_BROWSER = "whitenightshadow/152.0.4-beta.30-reverse.5"


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def evaluation(value):
    # evaluate_js returns a tool envelope around the page result in current MCP.
    if isinstance(value, dict) and "value" in value and "type" in value:
        require(value["type"] != "error", "evaluate_js returned an execution error")
        value = value["value"]
    if isinstance(value, dict) and "result" in value and "ok" not in value and "outputs" not in value:
        value = value["result"]
    if isinstance(value, str):
        value = json.loads(value)
    require(isinstance(value, dict), "evaluate_js did not return a page result object")
    return value


def verify_assets(assets):
    require(assets.is_dir(), "--assets must be a prepared directory")
    report = json.loads((assets / "PREPARE.json").read_text(encoding="utf-8"))
    require(report.get("schema") == "real-case-prepare-v1" and report.get("status") == "complete",
            "Asset preparation is not complete")
    expected = json.loads((HERE / "sources.json").read_text(encoding="utf-8"))
    sources = report.get("sources", [])
    require(len(sources) == len(expected), "Prepared upstream inventory differs")
    for pin, source in zip(expected, sources):
        require(all(source.get(k) == v for k, v in pin.items()), "Prepared source pins differ")
    verified = set()
    for line in (assets / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        member_parts(name)
        require(re.fullmatch(r"[0-9a-f]{64}", digest) is not None, "Invalid manifest hash")
        require(name not in verified, "Duplicate asset manifest path")
        path = checked_path(assets / name)
        require(path.is_file() and sha256(path) == digest, f"Asset hash mismatch: {name}")
        verified.add(name)
    required = {"PREPARE.json", "crypto-fingerprint/samples/demo-keys.json"}
    required.update(f"vm-cff/dist/{f}" for f in ["baseline.bundle.js", "vm.bundle.js", "cff.bundle.js", "cff-disabled.bundle.js", "selftest.js"])
    required.update(f"crypto-fingerprint/assets/{f}" for f in ["crypto-js-4.2.0.js", "case-crypto.js", "fingerprintjs-5.2.0.js", "fingerprint-adapter.js"])
    require(required <= verified, "Manifest omits required browser assets")
    return {"files_verified": len(verified), "manifest_sha256": sha256(assets / "SHA256SUMS")}


@contextmanager
def own_server(assets, work):
    work.mkdir()
    server = make_server(assets, work)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}"
    write_json(work / "service.json", {"url": url, "owner_pid": os.getpid(), "private": True})
    try:
        yield url
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


async def evaluate(client, method):
    # A leading // comment after the native channel's `return` triggers ASI.
    # Keep the outer expression an explicit IIFE, with comments inside its body.
    expression = "(async () => {\nconst suite = " + (HERE / "validate-browser.js").read_text(encoding="utf-8") + f";\nreturn await suite.{method}();\n}})()"
    return evaluation(await client.call("evaluate_js", {"expression": expression, "world": "main"}))


async def launch(client, native=False):
    await client.list_tools()
    environment = await client.call("check_environment")
    config = {"headless": True}
    if native:
        config.update(browser_version=os.environ.get("REAL_CASE_NATIVE_BROWSER", NATIVE_BROWSER), enable_trace=True)
    result = await client.call("launch_browser", config)
    require(result.get("status") == "launched", "Expected a newly launched browser, not an existing session")
    return {"environment": environment, "launch": result}


async def install(client, files):
    for file in files:
        value = await client.call("instrumentation", {"action": "install", "url_pattern": "**/" + file,
                                  "on_oversized": "force", "include_source_site": True, "fallback_on_error": False})
        require(value.get("status") == "instrumenting", f"Instrumentation did not install for {file}")


def rewrite_records(value):
    records = []
    if isinstance(value, dict):
        if "files_rewritten" in value:
            records.append(value)
        for nested in value.values():
            records.extend(rewrite_records(nested))
    elif isinstance(value, list):
        for nested in value:
            records.extend(rewrite_records(nested))
    return records


async def check_instrumentation(client, min_files):
    status = await client.call("instrumentation", {"action": "status"})
    logs = await client.call("instrumentation", {"action": "log", "limit": 8})
    records = rewrite_records(status)
    require(len(records) >= min_files and all(r["files_rewritten"] >= 1 and r.get("last_mode_used") == "ast"
                                            for r in records), "Real browser scripts were not all rewritten with AST")
    require(all(not r.get("last_error") and not r.get("files_passed_through") for r in records),
            "Instrumentation reports errors or passed-through scripts")
    require(logs.get("total_entries", 0) > 0, "No runtime AST instrumentation events were captured")
    return {"status": status, "logs": logs}


async def vm_scenario(work, mcp_root, url, kind, instrument):
    async with connect(work, mcp_root) as client:
        result = await launch(client)
        if instrument:
            await install(client, [kind + ".bundle.js"])
        await client.call("navigate", {"url": url + "/" + kind})
        page = await evaluate(client, "vm")
        require(page.get("ok") is True and page.get("failed") == 0 and page.get("passed") == 76
                and page.get("total") == 76, "VM/CFF differential or known-answer check failed")
        require(page.get("tapInstalled") is instrument, "Unexpected AST tap state")
        result.update(status="passed", checks=page["total"], instrumented=instrument)
        if instrument:
            result["instrumentation"] = await check_instrumentation(client, 1)
        return result


def check_fingerprint(value):
    require(value.get("version") == "5.2.0" and value.get("monitoring") is False,
            "Expected real FingerprintJS 5.2.0 with monitoring disabled")
    require(re.fullmatch(r"[0-9a-f]{32}", value.get("visitorId", "")) is not None,
            "FingerprintJS visitorId is absent")
    require(len(value.get("components", [])) >= 30 and value.get("stable") is True,
            "Fingerprint collection or short-window subset consistency failed")
    require(re.fullmatch(r"[0-9a-f]{64}", value["first"].get("fingerprint", "")) is not None,
            "Missing local fingerprint subset digest")


async def crypto_scenario(work, mcp_root, url, instrument):
    async with connect(work, mcp_root) as client:
        result = await launch(client)
        if instrument:
            await install(client, ["crypto-js-4.2.0.js", "case-crypto.js", "fingerprintjs-5.2.0.js", "fingerprint-adapter.js"])
        await client.call("navigate", {"url": url + "/crypto"})
        fingerprint = await evaluate(client, "fingerprint")
        check_fingerprint(fingerprint)
        exchanges = await evaluate(client, "exchange")
        require(len(exchanges.get("outputs", [])) == 2 and all(
            row.get("ok") is True and row.get("replayStatus") == 403
            and row.get("replay", {}).get("error") == "CHALLENGE_USED" for row in exchanges["outputs"]),
            "Browser/Python encrypted roundtrip, tamper rejection or replay check failed")
        require(exchanges.get("tapInstalled") is instrument, "Unexpected AST tap state")
        result.update(status="passed", instrumented=instrument, fingerprint=fingerprint, exchanges=exchanges)
        if instrument:
            result["instrumentation"] = await check_instrumentation(client, 4)
        return result


def check_native_capability(launch_result, state):
    runtime = launch_result.get("browser_runtime", {})
    require(launch_result.get("engine_trace", {}).get("enabled") is True
            and runtime.get("property_trace") is True
            and runtime.get("property_trace_compatible") is True
            and str(runtime.get("repo", "")).lower() != "official",
            "--native requires a real compatible custom browser; stock browser is not a substitute")
    require(state.get("ack_supported") is True and state.get("acknowledged") is True
            and state.get("live_processes", 0) > 0
            and not state.get("error_processes") and not state.get("data_loss_processes"),
            "Native control acknowledgement is missing or incomplete")


def check_native_events(trace, state):
    require(state.get("acknowledged") is True and not state.get("trace_enabled")
            and not state.get("error_processes") and not state.get("data_loss_processes"),
            "Native stop acknowledgement is incomplete")
    require(trace.get("coverage", {}).get("scope") == "fingerprint-native"
            and trace.get("total_events", 0) > 0 and bool(trace.get("events")),
            "No real native event sequence was returned")
    require(not trace.get("input_truncated") and not trace.get("possibly_capped") and not trace.get("truncated"),
            "Native trace was truncated or capped; cannot report complete evidence")
    require(all(isinstance(e, dict) and e.get("kind") in ("get", "set", "call")
                and isinstance(e.get("path"), str) and len(e["path"]) > 1
                and isinstance(e.get("pid"), int) and e["pid"] > 0 for e in trace["events"]),
            "Native event provenance is missing")


async def native_scenario(work, mcp_root, url):
    async with connect(work, mcp_root) as client:
        result = await launch(client, native=True)
        state = await client.call("trace_property_access", {"action": "status"})
        check_native_capability(result["launch"], state)
        await client.call("navigate", {"url": url + "/blank"})
        await client.call("trace_property_access", {"action": "start"})
        await client.call("click", {"selector": "#noop"})
        control = await client.call("trace_property_access", {"action": "stop", "mode": "sequence", "limit": 10000}, allow_error=True)
        # Empty control is evidence about that window, not a successful native trace.
        if control.get("mode") == "error":
            require(control.get("reason") == "No trace events captured during the window.", "Native control window failed")
        else:
            require(not control.get("error"), "Native control window failed")
        await client.call("trace_property_access", {"action": "start"})
        await client.call("navigate", {"url": url + "/fingerprint"})
        fingerprint = await evaluate(client, "fingerprint")
        check_fingerprint(fingerprint)
        trace = await client.call("trace_property_access", {"action": "stop", "mode": "sequence", "limit": 100000})
        stopped = await client.call("trace_property_access", {"action": "status"})
        check_native_events(trace, stopped)
        result.update(status="passed", control=control, trace=trace, stopped=stopped, fingerprint=fingerprint,
                      scope="Native events during SDK page load/get, including page setup; no 77-site coverage claim")
        return result


async def run(assets, mcp_root, work, native):
    report = {"schema": "real-case-validation-v1", "status": "running", "assets": str(assets),
              "mcp_root": str(mcp_root), "transport": "mcp-sdk-stdio", "scenarios": {},
              "native": {"status": "pending" if native else "not_requested"}}
    try:
        report["integrity"] = verify_assets(assets)
        with own_server(assets, work / "server") as url:
            scenarios = [(f"{kind}-{'instrumented' if instrument else 'plain'}", vm_scenario,
                          (kind, instrument)) for kind in ("vm", "cff") for instrument in (False, True)]
            scenarios += [(f"crypto-{'instrumented' if instrument else 'plain'}", crypto_scenario,
                           (instrument,)) for instrument in (False, True)]
            for label, fn, args in scenarios:
                print(f"Validating {label} through real MCP stdio", flush=True)
                try:
                    value = await fn(work / label, mcp_root, url, *args)
                except Exception as exc:
                    value = {"status": "failed", "error": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))}
                report["scenarios"][label] = value
                write_json(work / "VALIDATE.json", report)
                print(f"{label}: {value['status']}", flush=True)
            if native:
                print("Validating real custom-browser native trace", flush=True)
                try:
                    report["native"] = await native_scenario(work / "native", mcp_root, url)
                except Exception as exc:
                    report["native"] = {"status": "failed_or_unavailable", "error": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))}
        passed = all(s["status"] == "passed" for s in report["scenarios"].values())
        native_passed = not native or report["native"]["status"] == "passed"
        report["status"] = "passed" if passed and native_passed else "failed" if not passed else "incomplete"
        return 0 if report["status"] == "passed" else 2 if report["status"] == "incomplete" else 1
    except Exception as exc:
        report.update(status="failed", error=str(exc))
        return 1
    finally:
        write_json(work / "VALIDATE.json", report)
        print(json.dumps({"status": report["status"], "report": str(work / "VALIDATE.json"),
                          "native": report["native"]["status"]}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", required=True, help="Read-only output of prepare.py")
    parser.add_argument("--mcp-root", required=True, help="Existing camoufox-reverse-mcp checkout with src/")
    parser.add_argument("--native", action="store_true", help="Also require real custom-browser native trace")
    args = parser.parse_args()
    try:
        assets, mcp_root = checked_path(args.assets), checked_path(args.mcp_root)
        require((mcp_root / "src/camoufox_reverse_mcp/__main__.py").is_file(), "Invalid --mcp-root checkout")
        # Deliberately retained for review. No reports or samples are written into assets or MCP source.
        work = Path(tempfile.mkdtemp(prefix="real-case-validate-")).resolve()
        print(f"Validation evidence: {work}", flush=True)
        return asyncio.run(run(assets, mcp_root, work, args.native))
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"validate: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
