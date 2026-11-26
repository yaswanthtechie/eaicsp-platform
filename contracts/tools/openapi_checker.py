import copy
import os
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.exceptions import Unresolvable
from referencing.jsonschema import DRAFT202012
import yaml

from tools.formats import build_format_checker
from tools.models import Finding

try:
    from openapi_spec_validator import validate as validate_openapi_spec
except ImportError:  # pragma: no cover
    validate_openapi_spec = None

SPEC_BASE_URI = "urn:openapi:spec"
HTTP_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}


def _to_jsonschema(node: Any) -> Any:
    """Convert an OpenAPI 3.x document/schema into Draft 2020-12 compatible JSON Schema:
    - Rewrite local '#/' $refs to absolute SPEC_BASE_URI pointers so subschemas resolve cleanly.
    - Convert OpenAPI 3.0 `nullable: true` into JSON Schema null unions.
    """
    if isinstance(node, list):
        return [_to_jsonschema(item) for item in node]
    if not isinstance(node, dict):
        return node

    converted = {k: _to_jsonschema(v) for k, v in node.items()}

    if isinstance(converted.get("$ref"), str) and converted["$ref"].startswith("#/"):
        converted["$ref"] = f"{SPEC_BASE_URI}{converted['$ref']}"

    if converted.pop("nullable", False) is True:
        if "type" in converted:
            t = converted["type"]
            if isinstance(t, str) and t != "null":
                converted["type"] = [t, "null"]
            elif isinstance(t, list) and "null" not in t:
                converted["type"] = [*t, "null"]
            if isinstance(converted.get("enum"), list) and None not in converted["enum"]:
                converted["enum"] = [*converted["enum"], None]
        else:
            converted = {"anyOf": [converted, {"type": "null"}]}

    return converted


def _resolve_local_ref(spec: dict[str, Any], obj: Any) -> Any:
    """Dereference a top-level OpenAPI object (parameter/response/requestBody) if it uses $ref."""
    if not isinstance(obj, dict) or not isinstance(obj.get("$ref"), str):
        return obj
    ref = obj["$ref"]
    if not ref.startswith("#/"):
        return obj
    target: Any = spec
    for token in ref[2:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(target, dict) and token in target:
            target = target[token]
        else:
            return obj
    return target


def _validate_example(
    schema_raw: dict[str, Any],
    example_value: Any,
    registry: Registry,
    format_checker: Any,
    rel_file: str,
    location: str,
) -> list[Finding]:
    findings: list[Finding] = []
    js_schema = _to_jsonschema(copy.deepcopy(schema_raw))
    validator = Draft202012Validator(
        js_schema,
        registry=registry,
        format_checker=format_checker,
    )
    try:
        errors = sorted(
            validator.iter_errors(example_value),
            key=lambda e: [str(p) for p in e.path],
        )
    except Unresolvable as exc:
        return [
            Finding(
                file=rel_file,
                field=location,
                rule="openapi_unresolved_ref",
                message=f"Could not resolve $ref while validating inline example: {exc}",
            )
        ]

    for error in errors:
        subpath = ".".join(str(p) for p in error.path)
        full_field = f"{location}.{subpath}" if subpath else location
        findings.append(
            Finding(
                file=rel_file,
                field=full_field,
                rule="openapi_example_invalid",
                message=error.message,
            )
        )
    return findings


def _collect_schema_inline_examples(
    schema: Any,
    registry: Registry,
    format_checker: Any,
    rel_file: str,
    location: str,
) -> list[Finding]:
    """Recursively validate `example` / `examples` nested inside a schema object."""
    if not isinstance(schema, dict):
        return []

    findings: list[Finding] = []
    if "example" in schema:
        findings.extend(
            _validate_example(
                schema,
                schema["example"],
                registry,
                format_checker,
                rel_file,
                f"{location}.example",
            )
        )
    if isinstance(schema.get("examples"), list):
        for idx, val in enumerate(schema["examples"]):
            findings.extend(
                _validate_example(
                    schema,
                    val,
                    registry,
                    format_checker,
                    rel_file,
                    f"{location}.examples[{idx}]",
                )
            )

    props = schema.get("properties")
    if isinstance(props, dict):
        for prop_name, prop_schema in props.items():
            findings.extend(
                _collect_schema_inline_examples(
                    prop_schema,
                    registry,
                    format_checker,
                    rel_file,
                    f"{location}.properties.{prop_name}",
                )
            )

    if isinstance(schema.get("items"), dict):
        findings.extend(
            _collect_schema_inline_examples(
                schema["items"],
                registry,
                format_checker,
                rel_file,
                f"{location}.items",
            )
        )

    for combiner in ("allOf", "anyOf", "oneOf"):
        branches = schema.get(combiner)
        if isinstance(branches, list):
            for idx, branch in enumerate(branches):
                findings.extend(
                    _collect_schema_inline_examples(
                        branch,
                        registry,
                        format_checker,
                        rel_file,
                        f"{location}.{combiner}[{idx}]",
                    )
                )

    return findings


def _check_media_content(
    content: Any,
    registry: Registry,
    format_checker: Any,
    rel_file: str,
    location: str,
) -> list[Finding]:
    if not isinstance(content, dict):
        return []

    findings: list[Finding] = []
    for media_type, media_obj in content.items():
        if not isinstance(media_obj, dict):
            continue
        schema = media_obj.get("schema")
        if not isinstance(schema, dict):
            continue
        media_loc = f"{location}.content.{media_type}"

        if "example" in media_obj:
            findings.extend(
                _validate_example(
                    schema,
                    media_obj["example"],
                    registry,
                    format_checker,
                    rel_file,
                    f"{media_loc}.example",
                )
            )
        if isinstance(media_obj.get("examples"), dict):
            for ex_name, ex_obj in media_obj["examples"].items():
                if isinstance(ex_obj, dict) and "value" in ex_obj:
                    findings.extend(
                        _validate_example(
                            schema,
                            ex_obj["value"],
                            registry,
                            format_checker,
                            rel_file,
                            f"{media_loc}.examples.{ex_name}",
                        )
                    )

        findings.extend(
            _collect_schema_inline_examples(
                schema,
                registry,
                format_checker,
                rel_file,
                f"{media_loc}.schema",
            )
        )
    return findings


def _check_parameter(
    spec: dict[str, Any],
    param_raw: Any,
    registry: Registry,
    format_checker: Any,
    rel_file: str,
    location: str,
) -> list[Finding]:
    param = _resolve_local_ref(spec, param_raw)
    if not isinstance(param, dict):
        return []
    schema = param.get("schema")
    if not isinstance(schema, dict):
        return []

    findings: list[Finding] = []
    if "example" in param:
        findings.extend(
            _validate_example(
                schema,
                param["example"],
                registry,
                format_checker,
                rel_file,
                f"{location}.example",
            )
        )
    if isinstance(param.get("examples"), dict):
        for ex_name, ex_obj in param["examples"].items():
            if isinstance(ex_obj, dict) and "value" in ex_obj:
                findings.extend(
                    _validate_example(
                        schema,
                        ex_obj["value"],
                        registry,
                        format_checker,
                        rel_file,
                        f"{location}.examples.{ex_name}",
                    )
                )
    findings.extend(
        _collect_schema_inline_examples(
            schema,
            registry,
            format_checker,
            rel_file,
            f"{location}.schema",
        )
    )
    return findings


def check_openapi_file(filepath: str, rel_file: str) -> list[Finding]:
    findings: list[Finding] = []

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            spec = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        return [
            Finding(
                file=rel_file,
                field="<root>",
                rule="yaml_parse_error",
                message=str(exc),
            )
        ]

    if not isinstance(spec, dict):
        return [
            Finding(
                file=rel_file,
                field="<root>",
                rule="openapi_spec_invalid",
                message="OpenAPI YAML root must be a mapping.",
            )
        ]

    # 1. Validate spec structure against OpenAPI 3.0 / 3.1 standard
    if validate_openapi_spec is None:
        return [
            Finding(
                file=rel_file,
                field="<environment>",
                rule="missing_dependency",
                message="Install 'openapi-spec-validator' to validate OpenAPI specs.",
            )
        ]

    try:
        validate_openapi_spec(spec)
    except Exception as exc:
        path = getattr(exc, "path", None)
        field = ".".join(str(p) for p in path) if path else "<root>"
        message = getattr(exc, "message", str(exc))
        findings.append(
            Finding(
                file=rel_file,
                field=field,
                rule="openapi_spec_invalid",
                message=message,
            )
        )
        return findings

    # 2. Validate inline examples against their schemas
    transformed_spec = _to_jsonschema(copy.deepcopy(spec))
    registry = Registry().with_resource(
        SPEC_BASE_URI,
        Resource.from_contents(transformed_spec, default_specification=DRAFT202012),
    )
    format_checker = build_format_checker()

    components = spec.get("components", {})
    if isinstance(components, dict):
        for name, schema in (components.get("schemas") or {}).items():
            findings.extend(
                _collect_schema_inline_examples(
                    schema,
                    registry,
                    format_checker,
                    rel_file,
                    f"components.schemas.{name}",
                )
            )
        for name, param in (components.get("parameters") or {}).items():
            findings.extend(
                _check_parameter(
                    spec,
                    param,
                    registry,
                    format_checker,
                    rel_file,
                    f"components.parameters.{name}",
                )
            )

    for path_key, path_item in (spec.get("paths") or {}).items():
        if not isinstance(path_item, dict):
            continue
        for idx, param in enumerate(path_item.get("parameters") or []):
            findings.extend(
                _check_parameter(
                    spec,
                    param,
                    registry,
                    format_checker,
                    rel_file,
                    f"paths.{path_key}.parameters[{idx}]",
                )
            )

        for method, operation in path_item.items():
            if method.lower() not in HTTP_METHODS or not isinstance(operation, dict):
                continue
            op_loc = f"paths.{path_key}.{method.lower()}"

            for idx, param in enumerate(operation.get("parameters") or []):
                p_name = (
                    param.get("name", f"[{idx}]")
                    if isinstance(param, dict)
                    else f"[{idx}]"
                )
                findings.extend(
                    _check_parameter(
                        spec,
                        param,
                        registry,
                        format_checker,
                        rel_file,
                        f"{op_loc}.parameters.{p_name}",
                    )
                )

            req_body = _resolve_local_ref(spec, operation.get("requestBody"))
            if isinstance(req_body, dict):
                findings.extend(
                    _check_media_content(
                        req_body.get("content"),
                        registry,
                        format_checker,
                        rel_file,
                        f"{op_loc}.requestBody",
                    )
                )

            for status_code, resp_raw in (operation.get("responses") or {}).items():
                resp = _resolve_local_ref(spec, resp_raw)
                if isinstance(resp, dict):
                    findings.extend(
                        _check_media_content(
                            resp.get("content"),
                            registry,
                            format_checker,
                            rel_file,
                            f"{op_loc}.responses.{status_code}",
                        )
                    )

    return findings


def check_openapi_dir(contracts_dir: str) -> list[Finding]:
    openapi_dir = os.path.join(contracts_dir, "openapi")
    if not os.path.isdir(openapi_dir):
        return []

    findings: list[Finding] = []
    for filename in sorted(os.listdir(openapi_dir)):
        if not filename.endswith((".yaml", ".yml")):
            continue
        filepath = os.path.join(openapi_dir, filename)
        if not os.path.isfile(filepath):
            continue
        findings.extend(check_openapi_file(filepath, f"openapi/{filename}"))
    return findings