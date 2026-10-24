#!/usr/bin/env python3
"""Generuje SYNTETYCZNY zrzut definicji narzędzi MCP (kształt odpowiedzi tools/list:
name, description, inputSchema). To NIE jest zrzut prawdziwego serwera - nazwy i opisy
są zmyślone na potrzeby demonstracji, styl "gadatliwy" vs "zwięzły" dobrałem celowo.

Użycie: python3 -B gen_mcp_fixture.py mcp_tools.json
"""
import json
import sys

BOILERPLATE = ("Use this tool when you need to work with the tracker. Make sure to provide all "
               "required parameters. This tool returns JSON. If the request fails, inspect the "
               "error message and retry with corrected parameters. ")


def prop(desc=None, typ="string", **extra):
    p = {"type": typ, **extra}
    if desc:
        p["description"] = desc
    return p


def tool(name, desc, props, required=()):
    return {"name": name, "description": desc,
            "inputSchema": {"type": "object", "properties": props, "required": list(required)}}


def chatty_server():
    """Gadatliwy serwer 'tracker': długie opisy, powtarzalny wstęp, parametry bez opisów."""
    common = {
        "owner": prop("The account or organization that owns the repository, for example a user name."),
        "repo": prop("The name of the repository, without the owner prefix and without any URL parts."),
    }
    tools = []
    for action, extra in [
        ("list_issues", {"state": prop("Filter by state.", enum=["open", "closed", "all"]),
                         "labels": prop("Comma separated label names."), "page": prop(None, "integer"),
                         "per_page": prop(None, "integer"), "sort": prop(), "direction": prop(),
                         "since": prop(), "assignee": prop(), "creator": prop()}),
        ("get_issue", {"number": prop("Issue number.", "integer")}),
        ("create_issue", {"title": prop("Issue title."), "body": prop("Issue body in Markdown."),
                          "assignees": prop(None, "array", items={"type": "string"}),
                          "labels": prop(None, "array", items={"type": "string"})}),
        ("update_issue", {"number": prop("Issue number.", "integer"), "title": prop(), "body": prop(),
                          "state": prop(None, enum=["open", "closed"])}),
        ("add_comment", {"number": prop("Issue number.", "integer"), "body": prop("Comment in Markdown.")}),
        ("list_pull_requests", {"state": prop(None, enum=["open", "closed", "all"]), "head": prop(),
                                "base": prop(), "page": prop(None, "integer")}),
        ("get_pull_request_diff", {"number": prop("Pull request number.", "integer")}),
        ("search_code", {"query": prop("Search query using the code search syntax.")}),
    ]:
        desc = (BOILERPLATE + f"Action: {action.replace('_', ' ')}. The result contains all fields "
                "returned by the upstream API, including nested objects, so it can be large. "
                "Prefer narrow filters. Rate limits apply.")
        tools.append(tool("tracker_" + action, desc, {**common, **extra}, ["owner", "repo"]))
    return {"tools": tools}


def lean_server():
    """Zwięzły serwer 'db': krótkie opisy, każdy parametr opisany."""
    return {"tools": [
        tool("db_query", "Run a read-only SQL query; returns up to `limit` rows as JSON.",
             {"sql": prop("SELECT statement."), "limit": prop("Max rows (default 50).", "integer")}, ["sql"]),
        tool("db_describe", "Columns and types of one table.",
             {"table": prop("Table name, optionally schema-qualified.")}, ["table"]),
        tool("db_explain", "Estimated execution plan (no execution).",
             {"sql": prop("SELECT statement.")}, ["sql"]),
    ]}


def docs_server():
    return {"tools": [
        tool("docs_search", "Full-text search over the internal docs; returns titles and ids only.",
             {"query": prop("Search terms.")}, ["query"]),
        tool("docs_get", "Fetch one document by id (Markdown).",
             {"id": prop("Document id from docs_search.")}, ["id"]),
    ]}


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "mcp_tools.json"
    data = {"_note": "SYNTETYCZNE definicje (gen_mcp_fixture.py) - nie zrzut prawdziwego serwera MCP",
            "servers": {"tracker": chatty_server(), "db": lean_server(), "docs": docs_server()}}
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    n = sum(len(s["tools"]) for s in data["servers"].values())
    print(f"Zapisano {n} narzędzi w {len(data['servers'])} serwerach -> {out}")


if __name__ == "__main__":
    main()
