import copy
import json
import os
import subprocess
from typing import Any, Callable

import yaml

from tools.models import Finding

IGNORED_EVENT_DIFF_FILES = {"_template.v1.json"}
HTTP_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}


def _merge_dict_schema(base: dict[str, Any], addition: dict[str, Any]) -> dict[str, Any]:
    """Merge two normalized JSON Schema objects (used when flattening allOf)."""
    merged = copy.deepcopy(base)

    # Merge properties recursively
    if "properties" in addition and isinstance(addition["properties"], dict):
        merged_props = dict(merged.get("properties", {}))
        for k, v in addition["properties"].items():
            if k in merged_props and isinstance(merged_props[k], dict) and isinstance(v, dict):
                merged_props[k] = _merge_dict_schema(merged_props[k], v)
            else:
                merged_props[k] = copy.deepcopy(v)
        merged["properties"] = merged_props

    # Union required fields
    if "required" in addition and isinstance(addition["required"], list):
        merged_req = list(dict.fromkeys([*merged.get("required", []), *addition["required"]]))
        merged["required"] = merged_req

    # Copy scalar constraints (child/later branch overrides base when specified)
    for key in ("type", "enum", "const", "items", "nullable", "format"):
        if key in addition:
            merged[key] = copy.deepcopy(addition[key])

    return merged


def normalize_schema(
    schema: Any,
    ref_resolver: Callable[[str], dict[str, Any] | None] | None = None,
    _visited: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    """Resolve local $refs and flatten allOf so diffing compares effective fields."""
    if not isinstance(schema, dict):
        return {}

    result: dict[str, Any] = {}

    if "$ref" in schema and isinstance(schema["$ref"], str) and ref_resolver is not None:
        ref = schema["$ref"]
        if ref not in _visited:
            resolved = ref_resolver(ref)
            if isinstance(resolved, dict):
                result = normalize_schema(resolved, ref_resolver, _visited | {ref})

    if "allOf" in schema and isinstance(schema["allOf"], list):
        for branch in schema["allOf"]:
            norm_branch = normalize_schema(branch, ref_resolver, _visited)
            result = _merge_dict_schema(result, norm_branch)

    # Merge direct keys from this node (excluding $ref and allOf)
    direct: dict[str, Any] = {}
    for key in ("type", "enum", "const", "required", "nullable", "format"):
        if key in schema:
            direct[key] = copy.deepcopy(schema[key])

    if "properties" in schema and isinstance(schema["properties"], dict):
        direct["properties"] = {
            prop_name: normalize_schema(prop_schema, ref_resolver, _visited)
            for prop_name, prop_schema in schema["properties"].items()
        }

    if "items" in schema and isinstance(schema["items"], dict):
        direct["items"] = normalize_schema(schema["items"], ref_resolver, _visited)

    return _merge_dict_schema(result, direct)


def _effective_types(schema: dict[str, Any]) -> set[str]:
    raw_type = schema.get("type")
    if isinstance(raw_type, str):
        types = {raw_type}
    elif isinstance(raw_type, list):
        types = {t for t in raw_type if isinstance(t, str)}
    else:
        types = set()
    if schema.get("nullable") is True and types:
        types.add("null")
    return types


def diff_schemas(
    old_schema: dict[str, Any],
    new_schema: dict[str, Any],
    rel_file: str,
    field_prefix: str = "",
) -> list[Finding]:
    """Detect breaking changes between two normalized schemas of the same version."""
    findings: list[Finding] = []
    current_field = field_prefix or "<root>"

    # 1. Type changed
    old_types = _effective_types(old_schema)
    new_types = _effective_types(new_schema)
    if (old_types or new_types) and old_types != new_types:
        findings.append(
            Finding(
                file=rel_file,
                field=current_field,
                rule="type_changed",
                message=(
                    f"Type changed from {sorted(old_types) or ['<any>']} "
                    f"to {sorted(new_types) or ['<any>']}."
                ),
            )
        )

    # 2. Enum value removed (or const changed)
    if "enum" in old_schema and isinstance(old_schema["enum"], list):
        if "enum" in new_schema and isinstance(new_schema["enum"], list):
            removed_values = [v for v in old_schema["enum"] if v not in new_schema["enum"]]
            if removed_values:
                findings.append(
                    Finding(
                        file=rel_file,
                        field=current_field,
                        rule="enum_value_removed",
                        message=f"Enum value(s) removed: {removed_values}.",
                    )
                )

    if "const" in old_schema and new_schema.get("const") != old_schema["const"]:
        findings.append(
            Finding(
                file=rel_file,
                field=current_field,
                rule="enum_value_removed",
                message=(
                    f"Const value changed from {old_schema['const']!r} "
                    f"to {new_schema.get('const')!r}."
                ),
            )
        )

    # 3. Required field removed / renamed, and field becoming required
    old_props = old_schema.get("properties") if isinstance(old_schema.get("properties"), dict) else {}
    new_props = new_schema.get("properties") if isinstance(new_schema.get("properties"), dict) else {}
    old_req = set(old_schema.get("required") or [])
    new_req = set(new_schema.get("required") or [])

    for prop in sorted(old_req):
        prop_path = f"{field_prefix}.{prop}" if field_prefix else prop
        if prop not in new_props:
            findings.append(
                Finding(
                    file=rel_file,
                    field=prop_path,
                    rule="required_field_removed",
                    message=f"Required field '{prop_path}' was removed or renamed.",
                )
            )
        elif prop not in new_req:
            findings.append(
                Finding(
                    file=rel_file,
                    field=prop_path,
                    rule="required_field_removed",
                    message=f"Required field '{prop_path}' is no longer required.",
                )
            )

    for prop in sorted(new_req - old_req):
        prop_path = f"{field_prefix}.{prop}" if field_prefix else prop
        findings.append(
            Finding(
                file=rel_file,
                field=prop_path,
                rule="field_became_required",
                message=f"Field '{prop_path}' became required in the same version.",
            )
        )

    # 4. Recurse into shared properties and array items
    for prop in sorted(set(old_props) & set(new_props)):
        prop_path = f"{field_prefix}.{prop}" if field_prefix else prop
        findings.extend(diff_schemas(old_props[prop], new_props[prop], rel_file, prop_path))

    if isinstance(old_schema.get("items"), dict) and isinstance(new_schema.get("items"), dict):
        items_path = f"{field_prefix}[]" if field_prefix else "[]"
        findings.extend(
            diff_schemas(old_schema["items"], new_schema["items"], rel_file, items_path)
        )

    return findings


def _make_openapi_resolver(spec: dict[str, Any]) -> Callable[[str], dict[str, Any] | None]:
    def _resolve(ref: str) -> dict[str, Any] | None:
        if not ref.startswith("#/"):
            return None
        target: Any = spec
        for token in ref[2:].split("/"):
            token = token.replace("~1", "/").replace("~0", "~")
            if isinstance(target, dict) and token in target:
                target = target[token]
            else:
                return None
        return target if isinstance(target, dict) else None

    return _resolve


def diff_openapi(
    old_spec: dict[str, Any],
    new_spec: dict[str, Any],
    rel_file: str,
) -> list[Finding]:
    """Detect breaking changes between two OpenAPI YAML documents."""
    findings: list[Finding] = []
    old_res = _make_openapi_resolver(old_spec)
    new_res = _make_openapi_resolver(new_spec)

    # 1. Compare components.schemas
    old_schemas = (old_spec.get("components") or {}).get("schemas") or {}
    new_schemas = (new_spec.get("components") or {}).get("schemas") or {}
    for name, old_s in sorted(old_schemas.items()):
        if name not in new_schemas:
            findings.append(
                Finding(
                    file=rel_file,
                    field=f"components.schemas.{name}",
                    rule="required_field_removed",
                    message=f"Component schema '{name}' was removed.",
                )
            )
            continue
        findings.extend(
            diff_schemas(
                normalize_schema(old_s, old_res),
                normalize_schema(new_schemas[name], new_res),
                rel_file,
                f"components.schemas.{name}",
            )
        )

    # 2. Compare paths, methods, request/response schemas, and parameters
    old_paths = old_spec.get("paths") or {}
    new_paths = new_spec.get("paths") or {}

    for path_key, old_path_item in sorted(old_paths.items()):
        if not isinstance(old_path_item, dict):
            continue
        if path_key not in new_paths or not isinstance(new_paths[path_key], dict):
            findings.append(
                Finding(
                    file=rel_file,
                    field=f"paths.{path_key}",
                    rule="endpoint_removed",
                    message=f"Path '{path_key}' was removed.",
                )
            )
            continue

        new_path_item = new_paths[path_key]
        for method, old_op in sorted(old_path_item.items()):
            if method.lower() not in HTTP_METHODS or not isinstance(old_op, dict):
                continue
            op_loc = f"paths.{path_key}.{method.lower()}"
            new_op = new_path_item.get(method)
            if not isinstance(new_op, dict):
                findings.append(
                    Finding(
                        file=rel_file,
                        field=op_loc,
                        rule="endpoint_removed",
                        message=f"Operation '{method.upper()} {path_key}' was removed.",
                    )
                )
                continue

            # Compare parameters by (name, in)
            old_params = {
                (p.get("name"), p.get("in")): p
                for p in (old_op.get("parameters") or [])
                if isinstance(p, dict)
            }
            new_params = {
                (p.get("name"), p.get("in")): p
                for p in (new_op.get("parameters") or [])
                if isinstance(p, dict)
            }
            for key, new_p in new_params.items():
                old_p = old_params.get(key)
                if new_p.get("required") and (old_p is None or not old_p.get("required")):
                    findings.append(
                        Finding(
                            file=rel_file,
                            field=f"{op_loc}.parameters.{key[0]}",
                            rule="field_became_required",
                            message=f"Parameter '{key[0]}' ({key[1]}) became required.",
                        )
                    )
            for key, old_p in old_params.items():
                if key in new_params and isinstance(old_p.get("schema"), dict) and isinstance(new_params[key].get("schema"), dict):
                    findings.extend(
                        diff_schemas(
                            normalize_schema(old_p["schema"], old_res),
                            normalize_schema(new_params[key]["schema"], new_res),
                            rel_file,
                            f"{op_loc}.parameters.{key[0]}",
                        )
                    )

            # Compare requestBody schemas
            old_rb = (old_op.get("requestBody") or {}).get("content") or {}
            new_rb = (new_op.get("requestBody") or {}).get("content") or {}
            for mime, old_media in old_rb.items():
                if mime in new_rb and isinstance(old_media, dict) and isinstance(new_rb[mime], dict):
                    if isinstance(old_media.get("schema"), dict) and isinstance(new_rb[mime].get("schema"), dict):
                        findings.extend(
                            diff_schemas(
                                normalize_schema(old_media["schema"], old_res),
                                normalize_schema(new_rb[mime]["schema"], new_res),
                                rel_file,
                                f"{op_loc}.requestBody.{mime}",
                            )
                        )

            # Compare response schemas
            old_resps = old_op.get("responses") or {}
            new_resps = new_op.get("responses") or {}
            for status, old_resp in old_resps.items():
                if status not in new_resps or not isinstance(old_resp, dict) or not isinstance(new_resps[status], dict):
                    continue
                old_content = old_resp.get("content") or {}
                new_content = new_resps[status].get("content") or {}
                for mime, old_media in old_content.items():
                    if mime in new_content and isinstance(old_media, dict) and isinstance(new_content[mime], dict):
                        if isinstance(old_media.get("schema"), dict) and isinstance(new_content[mime].get("schema"), dict):
                            findings.extend(
                                diff_schemas(
                                    normalize_schema(old_media["schema"], old_res),
                                    normalize_schema(new_content[mime]["schema"], new_res),
                                    rel_file,
                                    f"{op_loc}.responses.{status}.{mime}",
                                )
                            )

    return findings


def _run_git(args: list[str], cwd: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _git_show_text(repo_root: str, git_ref: str, git_path: str) -> str | None:
    proc = _run_git(["show", f"{git_ref}:{git_path}"], cwd=repo_root)
    if proc.returncode != 0:
        return None
    return proc.stdout


def _make_event_ref_resolver_from_disk(events_dir: str) -> Callable[[str], dict[str, Any] | None]:
    cache: dict[str, dict[str, Any]] = {}
    if os.path.isdir(events_dir):
        for fname in os.listdir(events_dir):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(events_dir, fname)
            if not os.path.isfile(fpath):
                continue
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    cache[fname] = data
                    if "$id" in data:
                        cache[data["$id"]] = data
            except (json.JSONDecodeError, OSError):
                continue

    return lambda ref: cache.get(ref)


def _make_event_ref_resolver_from_git(
    repo_root: str, git_ref: str, git_events_dir: str
) -> Callable[[str], dict[str, Any] | None]:
    cache: dict[str, dict[str, Any]] = {}
    ls_proc = _run_git(["ls-tree", "--name-only", git_ref, f"{git_events_dir}/"], cwd=repo_root)
    if ls_proc.returncode == 0:
        for line in ls_proc.stdout.splitlines():
            git_path = line.strip()
            if not git_path.endswith(".json"):
                continue
            raw = _git_show_text(repo_root, git_ref, git_path)
            if raw is None:
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict):
                fname = git_path.rsplit("/", 1)[-1]
                cache[fname] = data
                if "$id" in data:
                    cache[data["$id"]] = data

    return lambda ref: cache.get(ref)


def check_breaking_changes(contracts_dir: str, against_ref: str) -> list[Finding]:
    """Compare changed event schemas and OpenAPI specs against `against_ref`."""
    abs_contracts = os.path.abspath(contracts_dir)
    root_proc = _run_git(["rev-parse", "--show-toplevel"], cwd=abs_contracts)
    if root_proc.returncode != 0:
        return [
            Finding(
                file="<git>",
                field="<ref>",
                rule="git_error",
                message=f"Unable to locate git repository root: {root_proc.stderr.strip()}",
            )
        ]
    repo_root = os.path.abspath(root_proc.stdout.strip())

    # Verify ref exists
    verify_proc = _run_git(["rev-parse", "--verify", f"{against_ref}^{{commit}}"], cwd=repo_root)
    if verify_proc.returncode != 0:
        return [
            Finding(
                file="<git>",
                field=against_ref,
                rule="invalid_git_ref",
                message=f"Git ref '{against_ref}' not found. Run 'git fetch' or pass a valid ref.",
            )
        ]

    rel_contracts = os.path.relpath(abs_contracts, repo_root).replace("\\", "/")
    prefix = "" if rel_contracts == "." else f"{rel_contracts}/"
    git_events_dir = f"{prefix}events"
    git_openapi_dir = f"{prefix}openapi"

    diff_proc = _run_git(
        ["diff", "--name-status", "--no-renames", against_ref, "--", git_events_dir, git_openapi_dir],
        cwd=repo_root,
    )
    if diff_proc.returncode != 0:
        return [
            Finding(
                file="<git>",
                field=against_ref,
                rule="git_error",
                message=f"git diff failed: {diff_proc.stderr.strip()}",
            )
        ]

    findings: list[Finding] = []
    old_event_resolver = _make_event_ref_resolver_from_git(repo_root, against_ref, git_events_dir)
    new_event_resolver = _make_event_ref_resolver_from_disk(os.path.join(abs_contracts, "events"))

    for line in diff_proc.stdout.splitlines():
        if not line.strip():
            continue
        status, git_path = line.split("\t", 1)
        rel_contract_file = git_path[len(prefix) :] if prefix and git_path.startswith(prefix) else git_path

        # Ignore example files and non-schema docs
        if rel_contract_file.startswith("events/examples/"):
            continue

        is_event_schema = (
            rel_contract_file.startswith("events/")
            and rel_contract_file.count("/") == 1
            and rel_contract_file.endswith(".json")
        )
        is_openapi_yaml = (
            rel_contract_file.startswith("openapi/")
            and rel_contract_file.endswith((".yaml", ".yml"))
        )
        if not (is_event_schema or is_openapi_yaml):
            continue

        if is_event_schema and os.path.basename(rel_contract_file) in IGNORED_EVENT_DIFF_FILES:
            continue

        # New file (e.g., *.v2.json next to *.v1.json) -> always passes
        if status == "A":
            continue

        # Existing contract file deleted -> breaking
        if status == "D":
            findings.append(
                Finding(
                    file=rel_contract_file,
                    field="<file>",
                    rule="contract_removed",
                    message=(
                        f"Existing contract '{rel_contract_file}' was deleted. "
                        "Keep old versions intact and add a new version file instead."
                    ),
                )
            )
            continue

        if status != "M":
            continue

        old_raw = _git_show_text(repo_root, against_ref, git_path)
        new_full_path = os.path.join(repo_root, *git_path.split("/"))
        if old_raw is None or not os.path.isfile(new_full_path):
            continue

        with open(new_full_path, "r", encoding="utf-8") as f:
            new_raw = f.read()

        if is_event_schema:
            try:
                old_schema = json.loads(old_raw)
                new_schema = json.loads(new_raw)
            except json.JSONDecodeError:
                continue
            old_norm = normalize_schema(old_schema, old_event_resolver)
            new_norm = normalize_schema(new_schema, new_event_resolver)
            findings.extend(diff_schemas(old_norm, new_norm, rel_contract_file))

        elif is_openapi_yaml:
            try:
                old_spec = yaml.safe_load(old_raw)
                new_spec = yaml.safe_load(new_raw)
            except yaml.YAMLError:
                continue
            if isinstance(old_spec, dict) and isinstance(new_spec, dict):
                findings.extend(diff_openapi(old_spec, new_spec, rel_contract_file))

    return findings