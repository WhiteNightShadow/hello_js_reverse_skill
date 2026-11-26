#!/usr/bin/env python3
# SPDX-License-Identifier: CC0-1.0
"""Explicitly fetch pinned upstream code OUTSIDE the Skill, build, and self-test."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
SKILL_ROOT = HERE.parents[1]
MAX_ARCHIVE = 64 * 1024 * 1024
MAX_EXPANDED = 256 * 1024 * 1024
MAX_MEMBERS = 50000


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def checked_path(value):
    """Do not resolve away a symlink or traversal before checking user input."""
    path = Path(value).expanduser()
    if ".." in path.parts:
        raise ValueError("Parent traversal is not accepted; pass a canonical path")
    if not path.is_absolute():
        path = Path.cwd() / path
    for part in [*reversed(path.parents), path]:
        if part.is_symlink():
            raise ValueError(f"Symlink path is not accepted: {part}")
    return path


def validate_output(value):
    path = checked_path(value)
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite existing output: {path}")
    if not path.parent.is_dir():
        raise ValueError("Output parent must already exist")
    if path == SKILL_ROOT or SKILL_ROOT in path.parents:
        raise ValueError("Upstream/GPL assets must be prepared outside the Skill repository")
    return path


def member_parts(name):
    if not name or "\\" in name or "\x00" in name or name.startswith("/"):
        raise ValueError(f"Unsafe archive path: {name!r}")
    parts = name.rstrip("/").split("/")
    if any(p in ("", ".", "..") or ":" in p for p in parts):
        raise ValueError(f"Unsafe archive path: {name!r}")
    return parts


def extract_archive(archive, dest, expected_root):
    """Validate the entire tar before writing; never use extract/extractall."""
    if dest.exists() or dest.is_symlink():
        raise FileExistsError(f"Extraction destination already exists: {dest}")
    with tarfile.open(archive, "r:gz") as tar:
        entries, seen, size = [], set(), 0
        for member in tar:
            parts = member_parts(member.name)
            if parts[0] != expected_root:
                raise ValueError("Archive root does not match the pinned commit")
            if not (member.isfile() or member.isdir()) or member.issparse():
                raise ValueError(f"Links, sparse files and special entries are forbidden: {member.name}")
            rel = PurePosixPath(*parts[1:])
            key = str(rel).casefold()
            if key in seen:
                raise ValueError(f"Duplicate/case-colliding archive path: {member.name}")
            seen.add(key)
            size += member.size
            if member.size < 0 or size > MAX_EXPANDED or len(seen) > MAX_MEMBERS:
                raise ValueError("Archive exceeds extraction limits")
            if len(parts) == 1:
                if not member.isdir():
                    raise ValueError("Archive root must be a directory")
                continue
            entries.append((member, rel))
        if not any(m.isfile() for m, _ in entries):
            raise ValueError("Archive contains no source files")
        kinds = {str(rel).casefold(): m.isdir() for m, rel in entries}
        for _, rel in entries:
            if any(kinds.get(str(p).casefold()) is False for p in rel.parents):
                raise ValueError("Archive uses a file as a parent directory")
        dest.mkdir(parents=True, exist_ok=False)
        inventory = []
        for member, rel in entries:
            target = dest / rel
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with tar.extractfile(member) as src, target.open("xb") as dst:
                shutil.copyfileobj(src, dst, length=1024 * 1024)
            target.chmod(0o644)
            inventory.append({"path": str(rel), "bytes": member.size, "sha256": sha256(target)})
        return inventory


def fetch_archive(pin, downloads, cache):
    dest = downloads / pin["archive"]
    if dest.exists() or dest.is_symlink():
        raise FileExistsError(f"Refusing to overwrite archive: {dest}")
    cached = cache / pin["archive"] if cache else None
    if cached is not None and cached.is_symlink():
        raise ValueError(f"Symlink archive is forbidden: {cached}")
    if cached is not None and cached.exists() and not cached.is_file():
        raise ValueError(f"Cache entry must be a regular archive: {cached}")
    source = "cache" if cached is not None and cached.exists() else "download"
    if source == "cache":
        stream = cached.open("rb")
    else:
        request = urllib.request.Request(pin["url"], headers={"User-Agent": "real-case-prepare/1"})
        stream = urllib.request.urlopen(request, timeout=60)
        if urlparse(stream.geturl()).scheme != "https":
            stream.close()
            raise ValueError("Archive download redirected away from HTTPS")
    h, size, created = hashlib.sha256(), 0, False
    try:
        with stream, dest.open("xb") as output:
            created = True
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                size += len(chunk)
                if size > MAX_ARCHIVE:
                    raise ValueError("Archive exceeds download limit")
                h.update(chunk)
                output.write(chunk)
        actual = h.hexdigest()
        if actual != pin["sha256"]:
            raise ValueError(f"SHA256 mismatch for {pin['name']}: expected {pin['sha256']}, got {actual}")
    except BaseException:
        if created:
            dest.unlink(missing_ok=True)
        raise
    print(f"Verified {pin['name']} @ {pin['commit']} SHA256={actual} ({source})", flush=True)
    return dest, {**pin, "obtained_from": source, "archive_bytes": size, "verified_sha256": actual}


def build_env(output):
    env = {k: v for k, v in os.environ.items() if not k.lower().startswith("npm_config_")}
    for key in ("NODE_OPTIONS", "NODE_PATH", "ESBUILD_BINARY_PATH", "NODE_ENV"):
        env.pop(key, None)
    env.update(PYTHONDONTWRITEBYTECODE="1", PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD="1",
               npm_config_ignore_scripts="true", npm_config_update_notifier="false",
               TMPDIR=str(output / ".tmp"), TMP=str(output / ".tmp"), TEMP=str(output / ".tmp"))
    return env


def run_step(output, cwd, label, command, env):
    log = output / "logs" / f"{label}.log"
    entry = {"step": label, "cwd": str(cwd.relative_to(output)), "command": command,
             "started_at": datetime.now(timezone.utc).isoformat(), "log": str(log.relative_to(output))}
    print(f"Running {label}; log: {entry['log']}", flush=True)
    try:
        with log.open("w", encoding="utf-8") as stream:
            stream.write(json.dumps(entry) + "\n")
            stream.flush()
            result = subprocess.run(command, cwd=cwd, env=env, stdout=stream, stderr=subprocess.STDOUT,
                                    timeout=900, check=False)
        entry["returncode"] = result.returncode
        if result.returncode:
            raise RuntimeError(f"{label} failed with exit {result.returncode}; see {log}")
    except BaseException as exc:
        entry["error"] = str(exc)
        raise
    finally:
        entry["ended_at"] = datetime.now(timezone.utc).isoformat()
        with (output / "logs/steps.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(entry) + "\n")


def dependency_inventory(root):
    lock = json.loads((root / "package-lock.json").read_text(encoding="utf-8"))
    records = []
    for location, metadata in sorted(lock["packages"].items()):
        if not location:
            continue
        folder = root / location
        package = folder / "package.json"
        record = {"path": location, "version": metadata["version"],
                  "integrity": metadata.get("integrity"), "resolved": metadata.get("resolved"),
                  "optional": metadata.get("optional", False), "installed": package.is_file()}
        if package.is_file():
            actual = json.loads(package.read_text(encoding="utf-8"))
            if actual["version"] != metadata["version"]:
                raise ValueError(f"Installed dependency version mismatch: {location}")
            record.update(name=actual["name"], license=actual.get("license", actual.get("licenses")),
                          package_sha256=sha256(package), license_files=[])
            for file in sorted(folder.iterdir()):
                if file.is_file() and file.name.lower().startswith(("license", "licence", "copying", "notice")):
                    dest = root / "licenses/dependencies" / location.removeprefix("node_modules/") / file.name
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(file, dest)
                    record["license_files"].append({"path": str(dest.relative_to(root)), "sha256": sha256(dest)})
        elif not metadata.get("optional"):
            raise ValueError(f"Required locked dependency missing: {location}")
        records.append(record)
    write_json(root / "evidence/dependencies.json", {"lock_sha256": sha256(root / "package-lock.json"),
                                                   "dependencies": records})


def validate_lock(root):
    package = json.loads((root / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((root / "package-lock.json").read_text(encoding="utf-8"))
    if lock.get("lockfileVersion") != 3:
        raise ValueError("Expected a v3 fixed lockfile")
    for field in ("dependencies", "devDependencies"):
        if package.get(field, {}) != lock["packages"][""].get(field, {}):
            raise ValueError("Package and lock dependencies differ")
        if any(not re.fullmatch(r"\d+\.\d+\.\d+", v) for v in package.get(field, {}).values()):
            raise ValueError("Direct dependencies must use exact versions")
    for location, item in lock["packages"].items():
        if location and (not location.startswith("node_modules/") or ".." in PurePosixPath(location).parts
                         or not item.get("resolved", "").startswith("https://registry.npmjs.org/")
                         or not item.get("integrity", "").startswith("sha512-")):
            raise ValueError(f"Unpinned/unsafe npm lock entry: {location}")


def prepare(output, cache=None):
    output = validate_output(output)
    if cache is not None:
        cache = checked_path(cache)
        if not cache.is_dir():
            raise ValueError("--archive-dir must be an existing read-only cache directory")
        if cache in output.parents:
            raise ValueError("Output must not be inside the read-only archive cache")
    node, npm = shutil.which("node"), shutil.which("npm")
    if not node or not npm:
        raise ValueError("Node.js >=18 and npm with lockfile v3 support are required")
    # Never import npm configuration or package contents from the source case workspaces.
    output.mkdir(mode=0o700, exist_ok=False)
    report = {"schema": "real-case-prepare-v1", "status": "preparing", "sources": []}
    try:
        for name in ("logs", "downloads", "licenses", ".tmp", ".cache/npm"):
            (output / name).mkdir(parents=True)
        for name in ("README.md", "LICENSE", "sources.json"):
            shutil.copyfile(HERE / name, output / name)
        for area in ("vm-cff", "crypto-fingerprint"):
            shutil.copytree(HERE / "templates" / area, output / area)
            for name in ("evidence", "licenses", "samples"):
                (output / area / name).mkdir(exist_ok=True)
            validate_lock(output / area)
        for pin in json.loads((HERE / "sources.json").read_text(encoding="utf-8")):
            archive, evidence = fetch_archive(pin, output / "downloads", cache)
            dest = output / pin["destination"]
            evidence["files"] = extract_archive(archive, dest, f"{pin['name']}-{pin['commit']}")
            license_path = dest / pin["license_file"]
            if not license_path.is_file():
                raise ValueError(f"Missing upstream license: {pin['name']}")
            license_name = f"{pin['name']}-{pin['license_file']}"
            for folder in (output / "licenses", output / pin["destination"].split("/")[0] / "licenses"):
                shutil.copyfile(license_path, folder / license_name)
            evidence["license_sha256"] = sha256(license_path)
            report["sources"].append(evidence)
            write_json(output / "PREPARE.json", report)
        env = build_env(output)
        for name in (".npmrc", ".npmrc-global"):
            (output / name).write_text("ignore-scripts=true\nregistry=https://registry.npmjs.org/\n", encoding="utf-8")
        report["node"] = subprocess.check_output([node, "--version"], env=env, text=True, encoding="utf-8").strip()
        report["npm"] = subprocess.check_output([npm, "--version"], env=env, text=True, encoding="utf-8").strip()
        if int(report["node"].lstrip("v").split(".")[0]) < 18:
            raise ValueError("Node.js >=18 is required")
        for area in ("vm-cff", "crypto-fingerprint"):
            root = output / area
            before = sha256(root / "package-lock.json")
            command = [npm, "ci", "--ignore-scripts", "--no-audit", "--no-fund", "--include=dev", "--include=optional",
                       "--cache", str(output / ".cache/npm"), "--userconfig", str(output / ".npmrc"),
                       "--globalconfig", str(output / ".npmrc-global")]
            run_step(output, root, f"{area}-npm-ci", command, env)
            if sha256(root / "package-lock.json") != before:
                raise ValueError("npm changed the fixed lockfile")
            dependency_inventory(root)
            run_step(output, root, f"{area}-build", [node, "scripts/build.cjs"], env)
            if area == "vm-cff":
                scripts = ["verify.cjs"]
            else:
                scripts = ["generate-samples.cjs", "selftest.cjs", "verify-node.cjs", "test-risk-contract.cjs"]
            for script in scripts:
                run_step(output, root, f"{area}-{script}", [node, "scripts/" + script], env)
        # Check upstream trees after running the explicit, task-authored build scripts.
        for source in report["sources"]:
            for file in source["files"]:
                if sha256(output / source["destination"] / file["path"]) != file["sha256"]:
                    raise ValueError("A build modified pinned upstream source")
        report.update(status="complete", ignore_scripts=True, upstream_unmodified=True)
        write_json(output / "PREPARE.json", report)
        files = []
        for path in sorted(output.rglob("*")):
            rel = path.relative_to(output)
            if path.is_file() and not any(p in ("node_modules", ".cache", ".tmp", "logs") for p in rel.parts):
                files.append(f"{sha256(path)}  {rel.as_posix()}")
        (output / "SHA256SUMS").write_text("\n".join(files) + "\n", encoding="utf-8")
        print(json.dumps({"status": "complete", "output": str(output), "sources_verified": len(report["sources"]),
                          "manifest": "SHA256SUMS", "report": "PREPARE.json"}), flush=True)
        return output
    except BaseException as exc:
        report.update(status="failed", error=str(exc))
        write_json(output / "PREPARE.json", report)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="New directory outside the Skill; parent must exist")
    parser.add_argument("--archive-dir", help="Existing read-only cache of the four pinned archive basenames")
    args = parser.parse_args()
    try:
        prepare(args.output, args.archive_dir)
    except (OSError, ValueError, RuntimeError, tarfile.TarError, subprocess.SubprocessError) as exc:
        print(f"prepare: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
