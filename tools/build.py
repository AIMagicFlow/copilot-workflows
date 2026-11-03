#!/usr/bin/env python3
"""Build importable, localized packages for each vertical.

For every vertical and locale this produces, under dist/<vertical>/<version>/:

  <UniqueName>_<version>_<locale>.zip            Power Platform solution (import in make.powerapps.com)
  <UniqueName>_<version>_<locale>_sharepoint.zip SharePoint setup kit (CSV-with-schema lists + quickstart)

Source files contain {{kind:arg}} tokens that are resolved per locale:

  {{t:key.path}}          string from shared/i18n/<locale>.yaml + verticals/<v>/i18n/<locale>.yaml
  {{lcid}} {{locale}}     Dataverse language code (1033, 3082) / locale id (en, es)
  {{version}}             solution version from vertical.yaml
  {{list:ListKey}}        localized SharePoint list title
  {{prompt:name}}         rendered prompt file (prompt files may use {{include:path}} and {{t:...}})
  {{promptVersion:name}}  prompt version (a whole-string token becomes a JSON number)

Usage:
  python3 tools/build.py                       # all verticals, all locales
  python3 tools/build.py trend-researcher --locale es
  python3 tools/build.py trend-researcher --release   # also write the upload set to dist/release/ (see README)
"""
import argparse
import hashlib
import io
import json
import re
import shutil
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

import yaml

ROOT = Path(__file__).resolve().parent.parent
TOKEN = re.compile(r"\{\{([A-Za-z]+)(?::([^{}]+))?\}\}")
ZIP_DATE = (1980, 1, 1, 0, 0, 0)  # fixed timestamps -> reproducible zips
SP_BUILTIN_FIELDS = {"ID", "Title", "Created", "Modified", "Author", "Editor"}


class BuildError(Exception):
    pass


# --------------------------------------------------------------------------- loading

def flatten(tree, prefix=""):
    out = {}
    for key, value in tree.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict):
            out.update(flatten(value, path + "."))
        else:
            out[path] = str(value)
    return out


def load_yaml(path):
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


class Vertical:
    def __init__(self, root, vertical_id):
        self.root = root
        self.dir = root / "verticals" / vertical_id
        if not (self.dir / "vertical.yaml").exists():
            raise BuildError(f"unknown vertical '{vertical_id}' (no {self.dir}/vertical.yaml)")
        self.manifest = load_yaml(self.dir / "vertical.yaml")
        self.id = self.manifest["id"]
        self.unique_name = self.manifest["solution"]["uniqueName"]
        self.version = str(self.manifest["solution"]["version"])
        self.locales = self.manifest["locales"]
        self.lists = [load_yaml(p) for p in sorted((self.dir / "sharepoint" / "lists").glob("*.yaml"))]
        libraries = self.dir / "sharepoint" / "libraries.yaml"
        self.libraries = load_yaml(libraries).get("libraries", []) if libraries.exists() else []

    def strings(self, locale):
        merged = {}
        for path in (self.root / "shared" / "i18n" / f"{locale}.yaml",
                     self.dir / "i18n" / f"{locale}.yaml"):
            if path.exists():
                merged.update(flatten(load_yaml(path)))
        return merged

    def list_by_key(self, key):
        for lst in self.lists:
            if lst["list"] == key:
                return lst
        raise BuildError(f"unknown SharePoint list '{key}'")

    def env_list_map(self):
        """Env var schema name -> list key, derived from '{{list:X}}' default values."""
        out = {}
        for path in (self.dir / "solution" / "environmentvariabledefinitions").glob("*/environmentvariabledefinition.xml"):
            el = ET.parse(path).getroot()
            default = el.findtext("defaultvalue") or ""
            m = re.fullmatch(r"\{\{list:([^{}]+)\}\}", default.strip())
            if m:
                out[el.get("schemaname")] = m.group(1)
        return out

    def env_library_map(self):
        """Env var schema name -> library urlName, derived from '{{library:X}}' default values."""
        out = {}
        for path in (self.dir / "solution" / "environmentvariabledefinitions").glob("*/environmentvariabledefinition.xml"):
            el = ET.parse(path).getroot()
            default = el.findtext("defaultvalue") or ""
            m = re.fullmatch(r"\{\{library:([^{}]+)\}\}", default.strip())
            if m:
                out[el.get("schemaname")] = m.group(1)
        return out

    def library_by_key(self, key):
        for lib in self.libraries:
            if lib["urlName"] == key:
                return lib
        raise BuildError(f"unknown SharePoint library '{key}'")

    def file_tag(self, locale):
        return f"{self.unique_name}_{self.version.replace('.', '_')}_{locale}"


# --------------------------------------------------------------------------- rendering

class Renderer:
    def __init__(self, vertical, locale):
        self.v = vertical
        self.locale = locale
        self.lcid = str(vertical.locales[locale]["lcid"])
        self.strings = vertical.strings(locale)
        self.prompts = vertical.manifest.get("prompts", {})

    def resolve(self, kind, arg, where):
        if kind == "t":
            if arg not in self.strings:
                raise BuildError(f"{where}: missing i18n key '{arg}' for locale '{self.locale}'")
            return self.strings[arg]
        if kind == "lcid":
            return self.lcid
        if kind == "locale":
            return self.locale
        if kind == "version":
            return self.v.version
        if kind == "list":
            return self.v.list_by_key(arg)["title"][self.locale]
        if kind == "library":
            return self.v.library_by_key(arg)["title"][self.locale]
        if kind == "promptVersion":
            return int(self.prompt_meta(arg, where)["version"])
        if kind == "prompt":
            path = self.v.dir / self.prompt_meta(arg, where)["file"]
            return self.text(path.read_text(encoding="utf-8"), where=str(path), prompt=True)
        if kind == "include":
            return (self.v.root / arg).read_text(encoding="utf-8").rstrip("\n")
        raise BuildError(f"{where}: unknown token kind '{kind}'")

    def prompt_meta(self, name, where):
        if name not in self.prompts:
            raise BuildError(f"{where}: unknown prompt '{name}'")
        return self.prompts[name]

    def text(self, text, where, xml=False, prompt=False):
        def sub(m):
            kind, arg = m.group(1), m.group(2)
            if kind == "include" and not prompt:
                raise BuildError(f"{where}: include is only allowed in prompt files")
            value = str(self.resolve(kind, arg, where))
            return escape(value, {'"': "&quot;"}) if xml else value
        # Includes first so included text can carry its own tokens.
        if prompt:
            text = re.sub(r"\{\{include:([^{}]+)\}\}", lambda m: self.resolve("include", m.group(1), where), text)
        return TOKEN.sub(sub, text)

    def json_value(self, node, where):
        if isinstance(node, dict):
            return {k: self.json_value(v, where) for k, v in node.items()}
        if isinstance(node, list):
            return [self.json_value(v, where) for v in node]
        if isinstance(node, str):
            m = TOKEN.fullmatch(node)
            if m and m.group(1) == "promptVersion":
                return self.resolve("promptVersion", m.group(2), where)
            return self.text(node, where)
        return node


# --------------------------------------------------------------------------- solution

def render_solution(vertical, locale):
    """Return {zip entry name: bytes} for the localized solution."""
    r = Renderer(vertical, locale)
    src = vertical.dir / "solution"
    files = {}
    for path in sorted(p for p in src.rglob("*") if p.is_file()):
        name = path.relative_to(src).as_posix()
        raw = path.read_text(encoding="utf-8")
        if path.suffix == ".json":
            bom = raw.startswith("\ufeff")
            doc = r.json_value(json.loads(raw.lstrip("\ufeff")), name)
            out = ("\ufeff" if bom else "") + json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
        else:
            out = r.text(raw, name, xml=path.suffix == ".xml")
        files[name] = out.encode("utf-8")
    export_workflow_names(files)
    validate_solution(vertical, files)
    return files


WORKFLOW_FILE = re.compile(
    r'(<Workflow WorkflowId="\{([0-9a-f-]{36})\}"[^>]*>\s*<JsonFileName>/Workflows/)([A-Za-z0-9_]+)(\.json</JsonFileName>)')


def export_workflow_names(files):
    """Rename source flows (Workflows/<Name>.json) to the export layout (<Name>-<WORKFLOWID>.json).

    Source keeps readable names; the zip keeps the file names Power Platform itself exports.
    """
    def rename(m):
        source = f"Workflows/{m.group(3)}.json"
        if source not in files:
            return m.group(0)
        stem = f"{m.group(3)}-{m.group(2).upper()}"
        files[f"Workflows/{stem}.json"] = files.pop(source)
        return f"{m.group(1)}{stem}{m.group(4)}"
    xml = files["customizations.xml"].decode("utf-8")
    files["customizations.xml"] = WORKFLOW_FILE.sub(rename, xml).encode("utf-8")


def flow_actions(actions):
    """Yield every action (recursing into scopes, loops, conditions, switches)."""
    for name, action in actions.items():
        yield name, action
        yield from flow_actions(action.get("actions", {}))
        yield from flow_actions(action.get("else", {}).get("actions", {}))
        for case in action.get("cases", {}).values():
            yield from flow_actions(case.get("actions", {}))
        yield from flow_actions(action.get("default", {}).get("actions", {}))


VARIABLE_ACTIONS = {"SetVariable", "AppendToStringVariable", "AppendToArrayVariable", "IncrementVariable",
                    "DecrementVariable"}
FILE_WRITE_OPERATIONS = {"CreateFile", "CopyFileAsync"}
PARAMETER_REF = re.compile(r"@parameters\('[^']*'\)")


def flow_strings(node):
    """Yield every string value in a JSON document."""
    if isinstance(node, dict):
        for value in node.values():
            yield from flow_strings(value)
    elif isinstance(node, list):
        for value in node:
            yield from flow_strings(value)
    elif isinstance(node, str):
        yield node


def action_parameters(node):
    inputs = node.get("inputs")
    return inputs.get("parameters", {}) if isinstance(inputs, dict) else {}


def action_operation(node):
    inputs = node.get("inputs")
    return inputs.get("host", {}).get("operationId") if isinstance(inputs, dict) else None


def lint_flow(name, definition, params, library_for_env, url_names):
    """Flow rules for designer artifacts and unsafe shapes. Returns a list of error strings."""
    errors = []

    # Triggers read the site and list from environment variables, never literals.
    trigger_libraries = []
    for trigger_name, trigger in definition.get("triggers", {}).items():
        tp = action_parameters(trigger)
        for key in ("dataset", "table"):
            if key in tp and not PARAMETER_REF.fullmatch(str(tp[key])):
                errors.append(f"{name}: trigger {trigger_name} has a literal {key}; use @parameters(...)")
        if PARAMETER_REF.fullmatch(str(tp.get("table", ""))):
            schema = params.get(tp["table"][13:-2], {}).get("metadata", {}).get("schemaName")
            if schema in library_for_env:
                trigger_libraries.append((trigger_name, library_for_env[schema]))

    for action_name, action in flow_actions(definition.get("actions", {})):
        p = action_parameters(action)
        # A path that starts with '/' must start with a library urlName.
        for key in ("folderPath", "path", "destinationFolderPath"):
            value = p.get(key)
            if isinstance(value, str) and value.startswith("/") and value.split("/")[1] not in url_names:
                errors.append(f"{name}: {action_name} {key} '{value}' does not start with a library urlName "
                              f"({', '.join(sorted(url_names))})")
        # Writing into the library a file trigger watches starts the flow again.
        operation = action_operation(action)
        if operation in FILE_WRITE_OPERATIONS:
            target = p.get("destinationFolderPath" if operation == "CopyFileAsync" else "folderPath")
            for trigger_name, library in trigger_libraries:
                if isinstance(target, str) and target.split("/")[1:2] == [library]:
                    errors.append(f"{name}: {action_name} writes to /{library}, the library trigger "
                                  f"{trigger_name} watches; every write would start the flow again")
        if action.get("type") == "SetVariable":
            own = action.get("inputs", {}).get("name")
            value = json.dumps(action.get("inputs", {}).get("value"))
            if own and re.search(r"variables\('%s'\)" % re.escape(own), value):
                errors.append(f"{name}: {action_name} sets variable '{own}' from itself; use Compose, then Set variable")
        if action.get("type") == "Foreach":
            inner = [n for n, a in flow_actions(action.get("actions", {})) if a.get("type") in VARIABLE_ACTIONS]
            repetitions = action.get("runtimeConfiguration", {}).get("concurrency", {}).get("repetitions")
            if inner and repetitions != 1:
                errors.append(f"{name}: loop {action_name} changes variables ({', '.join(inner)}) but does not "
                              "run sequentially (runtimeConfiguration.concurrency.repetitions: 1)")

    # Exactly one line break, at the end: the designer adds it when Enter is pressed in a field.
    for text in flow_strings(definition):
        if text.count("\n") == 1 and text.endswith("\n"):
            errors.append(f"{name}: value ends in a stray line break (designer artifact): {text.strip()[:60]!r}")
    return errors


FILTER_FIELD = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s+(?:eq|ne|gt|ge|lt|le)\s")


def validate_solution(vertical, files):
    errors = []
    for name, data in files.items():
        text = data.decode("utf-8").lstrip("\ufeff")
        if TOKEN.search(text):
            errors.append(f"{name}: unresolved token {TOKEN.search(text).group(0)}")
        try:
            json.loads(text) if name.endswith(".json") else ET.fromstring(text)
        except (ValueError, ET.ParseError) as exc:
            errors.append(f"{name}: does not parse: {exc}")
    if errors:
        raise BuildError("\n".join(errors))

    customizations = ET.fromstring(files["customizations.xml"].decode("utf-8").lstrip("\ufeff"))
    conn_refs = {c.get("connectionreferencelogicalname") for c in customizations.iter("connectionreference")}
    env_vars = {n.split("/")[1] for n in files if n.startswith("environmentvariabledefinitions/")}
    list_for_env = vertical.env_list_map()
    library_for_env = vertical.env_library_map()
    url_names = {lib["urlName"] for lib in vertical.libraries}

    manifest = ET.fromstring(files["solution.xml"].decode("utf-8").lstrip("﻿"))
    root_ids = {r.get("id").lower() for r in manifest.iter("RootComponent") if r.get("type") == "29"}
    for wf in customizations.iter("Workflow"):
        wf_id = wf.get("WorkflowId")
        if wf_id.lower() not in root_ids:
            errors.append(f"solution.xml: workflow {wf_id} is not a RootComponent in solution.xml")
        json_name = wf.findtext("JsonFileName").lstrip("/")
        if json_name not in files:
            errors.append(f"customizations.xml: workflow file {json_name} is missing")

    for name in (n for n in files if n.startswith("Workflows/")):
        flow = json.loads(files[name].decode("utf-8").lstrip("\ufeff"))
        props = flow["properties"]
        definition = props["definition"]
        params = definition.get("parameters", {})
        for ref in props.get("connectionReferences", {}).values():
            logical = ref.get("connection", {}).get("connectionReferenceLogicalName")
            if logical not in conn_refs:
                errors.append(f"{name}: connection reference '{logical}' is not in customizations.xml")
            # connectionName is a connection instance in the tenant the flow was exported from.
            # Import binds through the connection reference; a stale instance ID only leaks tenant data.
            if "connectionName" in ref:
                errors.append(f"{name}: connection reference '{logical}' carries a tenant connectionName")
        body = json.dumps(definition)
        for key in set(re.findall(r"parameters\('([^'$][^']*)'\)", body)):
            schema = params.get(key, {}).get("metadata", {}).get("schemaName")
            if not schema:
                errors.append(f"{name}: @parameters('{key}') has no definition.parameters entry")
            elif schema not in env_vars:
                errors.append(f"{name}: parameter '{key}' points to missing env var '{schema}'")
        errors.extend(lint_flow(name, definition, params, library_for_env, url_names))
        for action_name, action in flow_actions(definition.get("actions", {})):
            p = action_parameters(action)
            m = re.fullmatch(r"@parameters\('[^']*'\)", str(p.get("table", "")))
            if not m:
                continue
            schema = params.get(p["table"][13:-2], {}).get("metadata", {}).get("schemaName")
            if schema not in list_for_env:
                continue
            lst = vertical.list_by_key(list_for_env[schema])
            known = SP_BUILTIN_FIELDS | {f["name"] for f in lst["fields"]}
            used = {k[5:] for k in p if k.startswith("item/")}
            used |= set(FILTER_FIELD.findall(p.get("$filter", "")))
            for field in sorted(used - known):
                errors.append(f"{name}: {action_name} uses '{field}' which is not a field of list {lst['list']}")
    if errors:
        raise BuildError("\n".join(errors))


# --------------------------------------------------------------------------- SharePoint kit

def field_xml(field, display):
    n, d = field["name"], quoteattr(display)
    fid = "{%s}" % field.get("id", "")
    t = field["type"]
    if field.get("builtin") and n == "Title":
        return ('<Field ID="{fa564e0f-0c70-4ab9-b863-0177e6ddd247}" Type="Text" Name="Title" '
                f'DisplayName={d} Required="FALSE" SourceID="http://schemas.microsoft.com/sharepoint/v3" '
                'StaticName="Title" FromBaseType="TRUE" MaxLength="255" />')
    flags = ""
    if field.get("unique"):
        flags = ' CustomFormatter="" Required="FALSE" EnforceUniqueValues="TRUE" Indexed="TRUE" MaxLength="255"'
    elif field.get("indexed"):
        flags = ' Indexed="TRUE"'
    if field.get("required") and not field.get("unique"):
        flags += ' Required="TRUE"'
    if t == "Text":
        return f'<Field Type="Text" DisplayName={d} Name="{n}" ID="{fid}" StaticName="{n}"{flags} />'
    if t == "Number":
        if "default" in field:
            return (f'<Field Type="Number" DisplayName={d} Name="{n}" ID="{fid}" StaticName="{n}"{flags}>'
                    f'<Default>{escape(str(field["default"]))}</Default></Field>')
        return f'<Field Type="Number" DisplayName={d} Name="{n}" ID="{fid}" StaticName="{n}"{flags} />'
    if t == "Note":
        return ('<Field AppendOnly="FALSE" ClientSideComponentId="00000000-0000-0000-0000-000000000000" '
                f'DisplayName={d} Format="Dropdown" IsolateStyles="FALSE" Name="{n}" RichText="FALSE" '
                f'RichTextMode="Compatible" Title={d} Type="Note" ID="{fid}" StaticName="{n}"{flags} />')
    if t == "DateTime":
        return (f'<Field Type="DateTime" DisplayName={d} Required="FALSE" EnforceUniqueValues="FALSE" '
                f'Indexed="FALSE" Format="DateTime" FriendlyDisplayFormat="Disabled" ID="{fid}" '
                f'StaticName="{n}" Name="{n}" CustomFormatter="" CalType="0" />')
    if t == "Boolean":
        return (f'<Field Type="Boolean" DisplayName={d} EnforceUniqueValues="FALSE" Indexed="FALSE" '
                f'ID="{fid}" StaticName="{n}" Name="{n}"><Default>{int(field.get("default", 0))}</Default></Field>')
    if t in ("Choice", "MultiChoice"):
        choices = "".join(f"<CHOICE>{escape(c)}</CHOICE>" for c in field.get("choices", []))
        default = f"<Default>{escape(str(field['default']))}</Default>" if "default" in field else ""
        if t == "Choice":
            head = f'Type="Choice" DisplayName={d} Format="Dropdown" FillInChoice="FALSE"'
        else:
            head = f'Type="MultiChoice" DisplayName={d} FillInChoice="FALSE"'
        return (f'<Field {head} Name="{n}" ID="{fid}" StaticName="{n}"{flags}>'
                f'<CHOICES>{choices}</CHOICES>{default}</Field>')
    raise BuildError(f"field {n}: unsupported type {t}")


def render_list_csv(vertical, lst, locale):
    """SharePoint 'CSV with schema' file: create the list with New > List > From CSV."""
    fields = lst["fields"]
    schema = [field_xml(f, f["display"][locale]) for f in fields]
    title_display = next(f["display"][locale] for f in fields if f["name"] == "Title")
    link_title = (vertical.root / "shared" / "sharepoint" / "linktitle-field.xml").read_text(encoding="utf-8").strip()
    schema.append(link_title.replace("{{display}}", escape(title_display, {'"': "&quot;"})))
    buf = io.StringIO()
    buf.write("ListSchema=" + json.dumps({"schemaXmlList": schema}, ensure_ascii=False, separators=(",", ":")) + "\r\n")
    buf.write(",".join('"%s"' % f["display"][locale].replace('"', '""') for f in fields) + "\r\n")
    for row in lst.get("seed", {}).get(locale, []):
        if set(row) - {f["display"]["en"] for f in fields}:
            seed_rows(lst, locale)  # raises with the unknown column names
        # Same quoting as SharePoint's own export: non-empty cells quoted, empty cells bare.
        cells = [str(row.get(f["display"]["en"], "")) for f in fields]
        buf.write(",".join('"%s"' % c.replace('"', '""') if c else "" for c in cells) + "\r\n")
    return ("\ufeff" + buf.getvalue()).encode("utf-8")


PNP_NS = "http://schemas.dev.office.com/PnP/2022/09/ProvisioningSchema"
GENERIC_LIST_FEATURE = "00bfea71-de22-43b2-a848-c05709900100"
DOC_LIBRARY_FEATURE = "00bfea71-e717-4e80-aa17-d0c71b360101"
TITLE_FIELD_ID = "fa564e0f-0c70-4ab9-b863-0177e6ddd247"


def list_url(lst):
    """Lists are created at a stable English URL; only the title is localized."""
    return f"Lists/{lst['list']}"


def seed_rows(lst, locale):
    """Seed rows keyed by internal name, with values normalized per field type."""
    by_en = {f["display"]["en"]: f for f in lst["fields"]}
    rows = []
    for row in lst.get("seed", {}).get(locale, []):
        unknown = set(row) - set(by_en)
        if unknown:
            raise BuildError(f"list {lst['list']}: seed uses unknown columns {sorted(unknown)}")
        values = {}
        for display, value in row.items():
            field = by_en[display]
            value = str(value)
            if field["type"] == "Boolean":
                value = "true" if value.strip().lower() in ("1", "true", "yes") else "false"
            values[field["name"]] = value
        rows.append(values)
    return rows


def render_pnp_template(vertical, locale):
    """PnP provisioning template (Invoke-PnPSiteTemplate). PnP creates list fields with
    AddFieldInternalNameHint, so the Name attributes below become the real internal names."""
    strings = vertical.strings(locale)
    a = lambda v: quoteattr(str(v))  # noqa: E731
    out = ['<?xml version="1.0" encoding="utf-8"?>',
           f'<pnp:Provisioning xmlns:pnp="{PNP_NS}" Generator="copilot-workflows tools/build.py" '
           f'DisplayName={a(strings["solution.name"])} Version="1.0">',
           '  <pnp:Preferences Generator="copilot-workflows tools/build.py" />',
           f'  <pnp:Templates ID="{vertical.id}-templates">',
           f'    <pnp:ProvisioningTemplate ID="{vertical.id}" Version="1" Scope="RootSite" '
           f'DisplayName={a(strings["solution.name"])} Description={a(strings["solution.description"])}>',
           '      <pnp:Lists>']
    for lib in vertical.libraries:
        out.append(f'        <pnp:ListInstance Title={a(lib["title"][locale])} '
                   f'Description={a(lib["description"][locale])} TemplateType="101" Url={a(lib["urlName"])} '
                   f'OnQuickLaunch="true" EnableVersioning="true" TemplateFeatureID="{DOC_LIBRARY_FEATURE}"'
                   + ('>' if lib.get("folders") else ' />'))
        if lib.get("folders"):
            out.append('          <pnp:Folders>')
            out.extend(f'            <pnp:Folder Name={a(folder)} />' for folder in lib["folders"])
            out.append('          </pnp:Folders>')
            out.append('        </pnp:ListInstance>')
    for lst in vertical.lists:
        fields = lst["fields"]
        title = next(f for f in fields if f["name"] == "Title")
        custom = [f for f in fields if not f.get("builtin")]
        out.append(f'        <pnp:ListInstance Title={a(lst["title"][locale])} '
                   f'Description={a(lst["description"][locale])} TemplateType="100" Url={a(list_url(lst))} '
                   f'OnQuickLaunch="true" EnableVersioning="true" EnableAttachments="false" '
                   f'TemplateFeatureID="{GENERIC_LIST_FEATURE}">')
        out.append('          <pnp:Views>')
        out.append(f'            <View DisplayName={a(strings["sharepoint.allItemsView"])} DefaultView="TRUE" '
                   'MobileView="TRUE" MobileDefaultView="TRUE" Type="HTML" BaseViewID="1"><Query />'
                   '<ViewFields><FieldRef Name="LinkTitle" />'
                   + "".join(f'<FieldRef Name="{f["name"]}" />' for f in custom)
                   + '</ViewFields><RowLimit Paged="TRUE">30</RowLimit></View>')
        out.append('          </pnp:Views>')
        out.append('          <pnp:Fields>')
        out.extend(f'            {field_xml(f, f["display"][locale])}' for f in custom)
        out.append('          </pnp:Fields>')
        out.append('          <pnp:FieldRefs>')
        out.append(f'            <pnp:FieldRef ID="{TITLE_FIELD_ID}" Name="Title" '
                   f'DisplayName={a(title["display"][locale])} Required="false" />')
        out.append('          </pnp:FieldRefs>')
        rows = seed_rows(lst, locale)
        if rows:
            # KeyColumn + Skip: re-running the template never duplicates or overwrites seed rows.
            out.append('          <pnp:DataRows KeyColumn="Title" UpdateBehavior="Skip">')
            for row in rows:
                out.append('            <pnp:DataRow>'
                           + "".join(f'<pnp:DataValue FieldName="{k}">{escape(v)}</pnp:DataValue>'
                                     for k, v in row.items())
                           + '</pnp:DataRow>')
            out.append('          </pnp:DataRows>')
        out.append('        </pnp:ListInstance>')
    out += ['      </pnp:Lists>', '    </pnp:ProvisioningTemplate>', '  </pnp:Templates>', '</pnp:Provisioning>', '']
    xml = "\n".join(out)
    ET.fromstring(xml.encode("utf-8"))
    return xml.encode("utf-8")


def render_expected_schema(vertical, locale):
    """What provision.ps1 checks after applying the template (or after a CSV import)."""
    doc = {
        "libraries": [{"url": lib["urlName"], "title": lib["title"][locale], "folders": list(lib.get("folders", []))}
                      for lib in vertical.libraries],
        "lists": [{
            "title": lst["title"][locale],
            "url": list_url(lst),
            "fields": [{"name": f["name"], "type": f["type"], "display": f["display"][locale],
                        "unique": bool(f.get("unique"))}
                       for f in lst["fields"] if not f.get("builtin")],
        } for lst in vertical.lists],
    }
    return (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def render_provision_script(vertical, locale):
    r = Renderer(vertical, locale)
    path = vertical.root / "shared" / "sharepoint" / "provision.ps1"
    text = r.text(path.read_text(encoding="utf-8"), where=str(path))
    # Windows PowerShell and pwsh both read UTF-8 with BOM reliably.
    return ("\ufeff" + text).encode("utf-8")


def render_sharepoint_kit(vertical, locale):
    files = {}
    for lst in vertical.lists:
        files[f"lists/{lst['title'][locale]}.csv"] = render_list_csv(vertical, lst, locale)
    files["pnp/sharepoint-template.pnp.xml"] = render_pnp_template(vertical, locale)
    files["pnp/expected-schema.json"] = render_expected_schema(vertical, locale)
    files["pnp/provision.ps1"] = render_provision_script(vertical, locale)
    notes = render_upgrade_notes(vertical, locale)
    if notes:
        files[f"upgrade-{vertical.version}.{locale}.md"] = notes
    for doc in ("docs/quickstart.{loc}.md", "settings/deployment-settings.example.json"):
        path = vertical.dir / doc.format(loc=locale)
        if path.exists():
            files[path.name] = path.read_bytes()
    return files


def upgrade_entries(vertical, locale):
    """Lists and fields whose 'since' equals the current version, as rows for the upgrade notes."""
    rows = []
    for lst in vertical.lists:
        title = lst["title"][locale]
        new_list = str(lst.get("since", "")) == vertical.version
        for f in lst["fields"]:
            if f.get("builtin"):
                continue
            if new_list or str(f.get("since", "")) == vertical.version:
                rows.append((title, f, new_list))
    return rows


def render_upgrade_notes(vertical, locale):
    """Per-release notes for CSV-path customers: which columns to add by hand. Empty when nothing is new."""
    rows = upgrade_entries(vertical, locale)
    if not rows and not any(str(lib.get("since", "")) == vertical.version for lib in vertical.libraries):
        return b""
    t = vertical.strings(locale)
    out = [f"# {t['upgrade.title'].format(version=vertical.version)}", "", t["upgrade.intro"], "",
           f"**{t['upgrade.renameRule']}**", ""]
    new_libs = [lib for lib in vertical.libraries if str(lib.get("since", "")) == vertical.version]
    if new_libs:
        out += [t["upgrade.newLibraries"], ""]
        for lib in new_libs:
            folders = ", ".join(lib.get("folders", []))
            out.append(f"- {lib['title'][locale]} (`{lib['urlName']}`)"
                       + (f": {t['upgrade.folders']} {folders}" if folders else ""))
        out.append("")
    new_lists = [lst["title"][locale] for lst in vertical.lists if str(lst.get("since", "")) == vertical.version]
    if new_lists:
        out += [t["upgrade.newLists"], ""] + [f"- {name}" for name in new_lists] + [""]
    cols = ("list", "internalName", "type", "choices", "displayName")
    out.append("| " + " | ".join(t[f"upgrade.col.{c}"] for c in cols) + " |")
    out.append("|" + " --- |" * len(cols))
    for title, f, _ in rows:
        cells = [title, f"`{f['name']}`", f["type"], ", ".join(f.get("choices", [])), f["display"][locale]]
        out.append("| " + " | ".join(c.replace("|", "\\|") for c in cells) + " |")
    return ("\n".join(out) + "\n").encode("utf-8")


# --------------------------------------------------------------------------- packaging

def write_zip(path, files):
    path.parent.mkdir(parents=True, exist_ok=True)
    order = sorted(files, key=lambda n: (n != "[Content_Types].xml", n))
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in order:
            info = zipfile.ZipInfo(name, ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, files[name])
    return path


def build(vertical, locales, out_root):
    out_dir = out_root / vertical.id / vertical.version
    built = []
    for locale in locales:
        if locale not in vertical.locales:
            raise BuildError(f"{vertical.id}: locale '{locale}' is not declared in vertical.yaml")
        tag = vertical.file_tag(locale)
        built.append(write_zip(out_dir / f"{tag}.zip", render_solution(vertical, locale)))
        built.append(write_zip(out_dir / f"{tag}_sharepoint.zip", render_sharepoint_kit(vertical, locale)))
    return built


def release(vertical, built, out_root, force):
    target = out_root / "release" / vertical.id / vertical.version
    if target.exists() and not force:
        raise BuildError(f"{target} already exists: bump solution.version in vertical.yaml (or pass --force)")
    target.mkdir(parents=True, exist_ok=True)
    sums = []
    for path in built:
        shutil.copy2(path, target / path.name)
        sums.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}")
    (target / "SHA256SUMS").write_text("\n".join(sorted(sums, key=lambda s: s.split()[1])) + "\n")
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("verticals", nargs="*", help="vertical ids (default: all)")
    parser.add_argument("--locale", action="append", help="locale to build (repeatable; default: all declared)")
    parser.add_argument("--out", default=str(ROOT / "dist"), help="output directory (default: dist/)")
    parser.add_argument("--release", action="store_true", help="write the upload set to <out>/release/<vertical>/<version>/")
    parser.add_argument("--force", action="store_true", help="with --release, overwrite an existing release folder")
    args = parser.parse_args(argv)

    ids = args.verticals or sorted(p.name for p in (ROOT / "verticals").iterdir() if (p / "vertical.yaml").exists())
    try:
        for vid in ids:
            vertical = Vertical(ROOT, vid)
            built = build(vertical, args.locale or list(vertical.locales), Path(args.out))
            for path in built:
                print(f"built   {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")
            if args.release:
                print(f"release {release(vertical, built, Path(args.out), args.force)}")
    except BuildError as exc:
        print(f"build failed:\n{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
