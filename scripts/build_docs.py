"""Build the Mintlify site from the supplied Recurly ReadMe export."""

from __future__ import annotations

import json
import re
import shutil
import tarfile
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ARCHIVE = ROOT / "scripts/source-assets/recurly-docs-1.0.tar.gz"
SOURCE_TEMP = tempfile.TemporaryDirectory(prefix="recurly-docs-source-")
SOURCE = Path(SOURCE_TEMP.name) / "recurly-docs-1.0"
with tarfile.open(SOURCE_ARCHIVE, "r:gz") as archive:
    archive.extractall(SOURCE_TEMP.name, filter="data")
SPEC = yaml.safe_load((SOURCE / "reference/v1.0.yaml").read_text())
OPERATIONS = {
    op.get("operationId"): f"{method.upper()} {path}"
    for path, methods in SPEC["paths"].items()
    for method, op in methods.items()
    if method.lower() in {"get", "put", "post", "patch", "delete"}
}
OPERATION_TITLES = {
    op.get("operationId"): op.get("summary")
    for methods in SPEC["paths"].values()
    for method, op in methods.items()
    if method.lower() in {"get", "put", "post", "patch", "delete"}
}


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def parse_source(path: Path) -> tuple[dict, str]:
    raw = path.read_text(errors="replace")
    if raw.startswith("---\n"):
        _, front, body = raw.split("---", 2)
        try:
            return yaml.safe_load(front) or {}, body.strip()
        except yaml.YAMLError:
            return {}, raw.strip()
    return {}, raw.strip()


def ordered_children(directory: Path) -> list[Path]:
    order_file = directory / "_order.yaml"
    names = yaml.safe_load(order_file.read_text()) if order_file.exists() else []
    names = names or []
    children = [p for p in directory.iterdir() if p.is_dir() or p.suffix == ".md"]
    keyed = {p.name if p.is_dir() else p.stem: p for p in children}
    ordered = [keyed.pop(str(name)) for name in names if str(name) in keyed]
    return ordered + sorted(keyed.values(), key=lambda p: p.name.lower())


def target(path: Path) -> str:
    parts = path.relative_to(SOURCE).parts
    if parts[0] == "docs":
        return "/".join(["guides", *[slug(p) for p in parts[1:-1]], path.stem])
    if parts[0] == "reference":
        return "/".join(["reference", *[slug(p) for p in parts[1:-1]], path.stem])
    return "/".join([slug(parts[0]), *[slug(p) for p in parts[1:-1]], path.stem])


FILES = [p for section in ("docs", "reference", "recipes", "custom_pages") for p in sorted((SOURCE / section).rglob("*.md"))]
SLUG_ROUTES: dict[tuple[str, str], str] = {}
for p in FILES:
    section = p.relative_to(SOURCE).parts[0]
    if p.stem != "index":
        SLUG_ROUTES.setdefault((section, p.stem), "/" + target(p))


def rewrite_links(body: str) -> str:
    def replace(match: re.Match) -> str:
        prefix, section, stem = match.groups()
        route = SLUG_ROUTES.get((section, stem))
        return prefix + route if route else match.group(0)

    body = re.sub(r'(["(=])https?://docs\.recurly\.com/(?:recurly-subscriptions/)?(docs|reference)/([a-zA-Z0-9-]+)', replace, body)
    body = re.sub(r'(["(=])/(docs|reference)/([a-zA-Z0-9-]+)', replace, body)
    legacy_links = {
        "/docs/api": "https://recurly.com/developers/api/v2021-02-25/index.html",
        "/docs/recurly-js": "/guides/recurly-js/overview-recurlyjs",
        "/docs/testing": "/guides/getting-started/sandbox-features-to-discover",
        "/docs/api-changelog": "/guides/getting-started/recurly-subscriptions-changelog",
        "/docs/dunning": "/guides/churn-management/involuntary-churn/dunning-management",
        "/docs/add-ons": "/guides/plans-pricing-promotions/plan-structure/add-ons/index",
        "/docs/email-templates": "/guides/subscriber-management/lifecycle-communications/email-templates/index",
        "/docs/checkout": "/guides/hosted-pages/checkout/index",
        "/docs/transactions#section-fraud-velocity-checks": "/guides/payment-orchestration/gateway-configuration-and-features/fraud-management#fraud-velocity-rules",
        "/docs/hosted": "/guides/hosted-pages/hosted-payment-pages",
        "/docs/export-overview#coupons": "/guides/reporting-analytics/data-imports-and-exports/export-overview/coupons-export",
        "/docs/export-overview#coupon_redemptions": "/guides/reporting-analytics/data-imports-and-exports/export-overview/coupons-redemption",
        "/docs/dunning-management": "/guides/churn-management/involuntary-churn/dunning-management",
        "/docs/invoices#section-origins": "/guides/recurring-billing/invoices-1/invoices",
        "/developers/reference/recurly-js": "/guides/recurly-js/overview-recurlyjs",
        "docs.recurly.com/recurly-subscriptions/reference": "https://recurly.com/developers/api/v2021-02-25/index.html",
        "/developers/api/latest/index.html": "https://recurly.com/developers/api/v2021-02-25/index.html",
        "paypay-integration-guide": "/guides/api-guides/integration-guides/apac-payment-methods/paypay-integration-guide",
        "overview-recurlyjs": "/guides/recurly-js/overview-recurlyjs",
        "/upgrades-downgrades.html": "/guides/subscriber-management/subscriptions/index",
        "/recurlyjs.html": "/guides/recurly-js/overview-recurlyjs",
        "/api/subscriptions": "/reference/recurly-v2-api/subscriptions/index",
        "/api/transactions": "/reference/recurly-v2-api/transactions/index",
        "/api/billing-info": "/reference/recurly-v2-api/billing-info/index",
        "/transparent- post/subscriptions": "/guides/security-compliance/transparent-post-subscription",
        "/transparent-post/transactions": "/guides/security-compliance/transparent-post-transactions",
        "/transparent-post/billing-info": "/guides/security-compliance/transparent-post-update-billing-info",
        "/transparent-post/retrieving-results": "/guides/security-compliance/transparent-post-retrieving-results",
        "/recurlyjs": "/guides/recurly-js/overview-recurlyjs",
        "/api/basics/authentication": "/guides/integration-methods/api-keys",
        "/developers/reference/webhooks/#updated-subscription": "/guides/webhooks/notifications/subscription-notifications",
    }
    for old, new in sorted(legacy_links.items(), key=lambda item: len(item[0]), reverse=True):
        for opener in ('href="', "href='", "]("):
            body = body.replace(opener + old, opener + new)
    body = body.replace('title="API changelog"', 'title="Product changelog"')
    return re.sub(r"\]\(([^)]+?)\.md(#[^)]+)?\)", lambda m: f"]({m.group(1)}{m.group(2) or ''})", body)


def normalize_body(body: str, escape_mustache: bool = False) -> str:
    # Full HTML email templates and stylesheet scratch pages are source assets,
    # not renderable documentation. Show their source without executing it.
    if body.lstrip().startswith("<html ") or body.lstrip().startswith("<HTMLBlock>{`") or re.match(r"\s*body\s*\{", body):
        return "```html\n" + body.replace("```", "'''" ) + "\n```"
    # The export table pages embed an entire HTML document solely for a
    # download button. Preserve the useful link and the surrounding article.
    body = re.sub(
        r"<!DOCTYPE html>\s*<html\b[\s\S]*?</html>",
        lambda m: re.search(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', m.group(0), re.S).expand(r"[\2](\1)")
        if re.search(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', m.group(0), re.S)
        else "",
        body,
        flags=re.I,
    )
    # Keep literal examples inside fenced code intact.
    body = re.sub(r"(?<!`)(`{6})(?!`)", "```\n\n```", body)
    body = re.sub(r"(?<!\n)(?<!`)(```)(?!`)", r"\n\n\1", body)
    chunks = re.split(r"(^```[^\n]*\n[\s\S]*?^```[ \t]*(?:\n|$))", body, flags=re.M)
    return "".join(chunk if chunk.startswith("```") else normalize_prose(chunk, escape_mustache) for chunk in chunks).strip()


def normalize_prose(body: str, escape_mustache: bool = False) -> str:
    # ReadMe's HTMLBlock container is not a Mintlify component. Its content is.
    body = re.sub(r"<HTMLBlock>\{`([\s\S]*?)`\}</HTMLBlock>", lambda m: m.group(1), body)
    body = re.sub(r"<style\b[^>]*>[\s\S]*?</style>", "", body, flags=re.I)
    body = re.sub(r"<script\b[^>]*>[\s\S]*?</script>", "", body, flags=re.I)
    if escape_mustache:
        body = (body.replace("{{{", "&#123;&#123;&#123;")
                .replace("}}}", "&#125;&#125;&#125;")
                .replace("{{", "&#123;&#123;").replace("}}", "&#125;&#125;"))
    body = body.replace(r"\`\`\`", "")
    body = body.replace("<        <div", "<div").replace("0 <div", "<div")
    body = body.replace("<strong><em>Note:</strong>", "<strong><em>Note:</em></strong>")
    body = body.replace("</p></a>", "</p>").replace("</strong>.</a>", "</strong>.</p>")
    # Source HTML includes multiline list items and anchors that MDX treats as
    # separate Markdown blocks. Keep each tag's text in one HTML block.
    body = re.sub(r"(<li\b[^>]*>)([\s\S]*?)(</li>)", lambda m: m.group(1) + re.sub(r"\s*\n\s*", " ", m.group(2)) + m.group(3), body)
    body = re.sub(r"(<a\b[^>]*>)([\s\S]*?)(</a>)", lambda m: m.group(1) + re.sub(r"\s*\n\s*", " ", m.group(2)) + m.group(3), body)
    if not escape_mustache:
        body = re.sub(r"<code>\{\{([^<]*?)\}\}</code>", r"<code>&#123;&#123;\1&#125;&#125;</code>", body)
    body = re.sub(r"<Cards\b[^>]*>", "<CardGroup cols={2}>", body).replace("</Cards>", "</CardGroup>")
    body = re.sub(r"\sclass=", " className=", body)
    body = re.sub(r"\sfor=", " htmlFor=", body)
    body = re.sub(r"\sallowfullscreen(?=[\s>/])", " allowFullScreen", body, flags=re.I)
    body = re.sub(r"\sframeborder=", " frameBorder=", body, flags=re.I)
    body = re.sub(r"\sallowtransparency=", " allowTransparency=", body, flags=re.I)
    body = re.sub(r"\sautoplay(?=[\s>/])", " autoPlay", body, flags=re.I)
    body = re.sub(r"<(img|br|hr|meta|link|input|source)(\b[^>]*?)(?<!/)>", r"<\1\2 />", body, flags=re.I)
    body = re.sub(r'(<div\b[^>]*>)(?=[^\n<]+\n\n)', r"\1\n\n", body)
    body = re.sub(r"(</(?:li|ul|ol)>)(?=</)", r"\1\n", body)
    body = body.replace("<!--", "{/*").replace("-->", "*/}")
    body = rewrite_links(body)
    return body


def write_page(path: Path) -> dict:
    front, body = parse_source(path)
    title = str(front.get("title") or path.stem.replace("-", " ").title())
    title = title.replace("\n", " ")
    if body.startswith("# " + title):
        body = body.split("\n", 1)[1].lstrip()
    # Repair a handful of malformed tags in the export before MDX parsing.
    stem = path.stem
    if stem == "getting-started-recurly":
        # The source iframe renders as a blank block when Wistia cannot embed.
        # Keep the tour available as a prominent link instead.
        tour = '''<a className="recurly-tour" href="https://fast.wistia.net/embed/iframe/7pxncbd7vd?videoFoam=true" target="_blank" rel="noopener noreferrer">
  <span className="recurly-tour-play" aria-hidden="true">▶</span>
  <span className="recurly-tour-copy"><strong>Watch the Recurly product tour</strong><span>See the platform in action</span></span>
  <span className="recurly-tour-arrow" aria-hidden="true">↗</span>
</a>'''
        body = re.sub(r'<div class="rp-video"[\s\S]*?</div>', tour, body, count=1)
    if stem == "payment-descriptors":
        body = body.replace("`AcmeInc*One-Time Payment`</div>", "`AcmeInc*One-Time Payment`\n\n</div>")
    if stem == "copy-of-plans":
        body = body.replace("`<div>`", "&lt;div&gt;")
    if stem == "free-trial-management":
        body = body.replace('alt="" />\n  </div>\n</span>', 'alt="" />\n  </a>\n</span>')
    if stem == "navigate-acquire-pricing-plans-201-advanced-models":
        body = body.replace("</strong>.</a>", "</strong>.</p>")
    if stem in {"navigate-acquire-pricing-plans-201-segmentation", "navigate-launch-phase-two", "navigate-retain-dunning-101-analytics", "navigate-retain-dunning-101-review"}:
        body += "\n</div>"
    if stem == "define-request-templates":
        body = body.replace("{{Recurly.field}}", "&#123;&#123;Recurly.field&#125;&#125;")
    if stem == "paypay":
        body = body.replace("to get started.</div>", "to get started.\n\n</div>")
    if stem == "index" and path.parent.name == "wallet":
        body = body.replace("\n  </Tab>", "\n\n</Tab>")
    def flatten_between(start: str, end: str) -> None:
        nonlocal body
        a = body.find(start)
        if a < 0:
            return
        b = body.find(end, a + len(start))
        if b < 0:
            return
        b += len(end)
        body = body[:a] + re.sub(r"\s*\n\s*", " ", body[a:b]) + body[b:]
    if stem == "sepa-retries":
        flatten_between('<ul class="rp-list">', '</ul>\n  </li>\n</ul>')
    if stem == "renewal-declines":
        flatten_between('  <li>The overall invoice count', '</ul>\n  </li>\n</ul>')
    if stem == "dunning-effectiveness" and path.relative_to(SOURCE).parts[0] == "docs":
        flatten_between("<ul class=\"rp-list\">\n  <li><strong>Successful retries", '</ul>\n  </li>\n</ul>')
    if stem in {"adyen", "checkoutcom", "worldpaydlocal-latam-support"}:
        marker = {"adyen": "Two settings require", "checkoutcom": "Best practices before", "worldpaydlocal-latam-support": "New MasterCard and ELO"}[stem]
        a = body.find(marker)
        if a >= 0:
            a = body.rfind("<div>", 0, a)
            b = body.find("</div>", a) + len("</div>")
            if a >= 0 and b > a:
                body = body[:a] + re.sub(r"\s*\n\s*", " ", body[a:b]) + body[b:]
    if stem == "tsys":
        flatten_between("<div><h4>Establish your TSYS", "</ul>\n</div>")
    if stem == "churn-analysis" and path.relative_to(SOURCE).parts[0] == "docs":
        flatten_between("<div><strong><i class=\"fa-solid fa-circle-info\" aria-hidden=\"true\"></i> Drills", "</ol>\n</div>")
    dest = ROOT / (target(path) + ".mdx")
    dest.parent.mkdir(parents=True, exist_ok=True)
    section = path.relative_to(SOURCE).parts[0]
    operation = (front.get("api") or {}).get("operationId") if isinstance(front.get("api"), dict) else None
    if operation in OPERATIONS and OPERATION_TITLES.get(operation):
        title = OPERATION_TITLES[operation]
    metadata = {"title": title}
    if operation in OPERATIONS:
        metadata["openapi"] = f"/openapi/recurly-v2.yaml {OPERATIONS[operation]}"
    elif operation:
        body = body or f"API operation: `{operation}`."
    if section == "docs" and path.stem == "recurly-subscriptions-changelog":
        metadata["rss"] = True
    normalized = normalize_body(body, stem == "index" and path.parent.name == "email-templates")
    if stem in {"sepa-retries", "renewal-declines"}:
        start = "<li>An active Recurly account" if stem == "sepa-retries" else "<li>The overall invoice count"
        a = normalized.find(start)
        b = normalized.find("</ul>\n  </li>", a) if a >= 0 else -1
        if b < 0 and a >= 0:
            b = normalized.find("</ul> </li>", a)
        if b >= 0:
            b += len("</ul>\n  </li>") if normalized[b:b+len("</ul>\n  </li>")] == "</ul>\n  </li>" else len("</ul> </li>")
            normalized = normalized[:a] + re.sub(r"\s*\n\s*", " ", normalized[a:b]) + normalized[b:]
        normalized = normalized.replace("</li> </ul>\n", "</li>\n</ul>\n")
    if stem in {"adyen", "checkoutcom", "worldpaydlocal-latam-support", "tsys", "churn-analysis"}:
        if stem == "tsys":
            normalized = normalized.replace("then proceed to Step 2.</li>\n</ul>", "then proceed to Step 2.</li></ul>")
        if stem == "churn-analysis":
            normalized = normalized.replace("<li>Churn count</li>\n</ol>", "<li>Churn count</li></ol>")
        marker = {"adyen": "Two settings require", "checkoutcom": "Best practices before", "worldpaydlocal-latam-support": "New MasterCard and ELO", "tsys": "Establish your TSYS", "churn-analysis": "Drills</strong>"}[stem]
        a = normalized.find(marker)
        if a >= 0:
            close = "</ol>\n</div>" if stem == "churn-analysis" else "</ul>\n</div>"
            b = normalized.find(close, a)
            if b >= 0:
                normalized = normalized[:b] + close.replace("\n", "") + normalized[b + len(close):]
    content = "---\n" + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False).strip() + "\n---\n\n" + normalized + "\n"
    dest.write_text(content)
    if section == "docs":
        source_url = f"https://docs.recurly.com/docs/{path.stem}"
    elif section == "reference":
        source_url = f"https://docs.recurly.com/reference/{path.stem}"
    else:
        source_url = "recurly-docs-1.0/" + str(path.relative_to(SOURCE))
    return {
        "source_url": source_url,
        "source_title": title,
        "source_sidebar_label": title,
        "source_h1": title,
        "source_description": str(front.get("excerpt") or ""),
        "normalized_path": "/" + target(path),
        "nav_section": section,
        "converted_file": str(dest.relative_to(ROOT)),
        "status": "done",
        "notes": "OpenAPI operation" if operation in OPERATIONS else "",
    }


def nav_node(path: Path):
    if path.is_file():
        section = path.relative_to(SOURCE).parts[0]
        front, body = parse_source(path)
        operation = (front.get("api") or {}).get("operationId") if isinstance(front.get("api"), dict) else None
        if (section != "recipes" and front.get("hidden")) or (not body and operation not in OPERATIONS):
            return None
        return target(path)
    pages = [nav_node(child) for child in ordered_children(path)]
    pages = [page for page in pages if page]
    if not pages:
        return None
    landing = [page for page in pages if isinstance(page, str) and (page.endswith("/overview") or page.endswith("/index") or page.endswith("/getting-started"))]
    if landing:
        first = landing[0]
        pages.remove(first)
        pages.insert(0, first)
    name = path.name.strip().replace("-", " ").replace("_", " ").title()
    name = re.sub(r"\bApi\b", "API", name)
    name = re.sub(r"\bSdk\b", "SDK", name)
    return {"group": name, "pages": pages}


def main():
    for name in ("guides", "reference", "recipes", "custom-pages"):
        shutil.rmtree(ROOT / name, ignore_errors=True)
    manifest = [write_page(path) for path in FILES]
    (ROOT / "parity-manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    (ROOT / "openapi").mkdir(exist_ok=True)
    shutil.copyfile(SOURCE / "reference/v1.0.yaml", ROOT / "openapi/recurly-v2.yaml")
    groups = [nav_node(child) for child in ordered_children(SOURCE / "docs")]
    groups = [group for group in groups if group]
    reference = [nav_node(child) for child in ordered_children(SOURCE / "reference")]
    reference = [group for group in reference if group]
    recipes = [node for child in ordered_children(SOURCE / "recipes") if (node := nav_node(child))]
    extra = [node for child in ordered_children(SOURCE / "custom_pages") if (node := nav_node(child))]
    config = {
        "$schema": "https://mintlify.com/docs.json",
        "name": "Recurly Docs",
        "theme": "mint",
        "colors": {"primary": "#0D0D0B", "light": "#FFD706", "dark": "#0D0D0B"},
        "appearance": {"default": "light"},
        "fonts": {"family": "Figtree"},
        "background": {"color": {"light": "#FCFBF7", "dark": "#0D0D0B"}},
        "navigation": {"tabs": [
            {"tab": "Guides", "groups": groups},
            {"tab": "API reference", "groups": [{"group": "Overview", "pages": ["api-reference"]}, *reference]},
            {"tab": "Resources", "groups": [{"group": "Overview", "pages": ["resources"]}, {"group": "Recipes", "pages": recipes}, {"group": "More", "pages": extra}]},
        ]},
        "api": {"playground": {"display": "interactive"}, "examples": {"languages": ["curl", "javascript", "python"]}},
        "contextual": {"options": ["copy", "view", "assistant", "chatgpt", "claude", "perplexity", "grok", "aistudio", "devin", "windsurf", "mcp", "add-mcp", "cursor", "vscode", "devin-mcp"]},
        "navbar": {"links": [{"label": "Recurly", "href": "https://recurly.com"}], "primary": {"type": "button", "label": "Open Recurly", "href": "https://app.recurly.com"}},
    }
    (ROOT / "docs.json").write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n")
    print(f"Generated {len(manifest)} pages")


if __name__ == "__main__":
    main()
