"""Capture explicit page routes at several widths; Playwright is optional."""

from html import escape
import json
from pathlib import Path
from urllib.parse import urljoin, urlsplit


CHECKS = """() => {
  const issues = [];
  if (document.documentElement.scrollWidth > innerWidth + 1) issues.push('horizontal-overflow');
  for (const element of document.querySelectorAll('button,input,select,textarea,a[href]')) {
    const box = element.getBoundingClientRect();
    const style = getComputedStyle(element);
    if (box.width && box.height && style.display !== 'none' && style.visibility !== 'hidden'
        && (box.left < -1 || box.right > innerWidth + 1)) {
      issues.push('control-outside-viewport'); break;
    }
  }
  return issues;
}"""


def load_config(path):
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(config, dict) or not isinstance(config.get("base_url"), str):
        raise ValueError("The configuration must be an object with a base_url string.")
    base = urlsplit(config.get("base_url", ""))
    if (base.scheme not in ("http", "https") or not base.hostname or base.username or base.password
            or base.query or base.fragment or base.path not in ("", "/")):
        raise ValueError("base_url must be an HTTP or HTTPS origin without credentials, path, query or fragment.")
    widths, pages = config.get("widths", [320, 1440]), config.get("pages")
    if (not isinstance(widths, list) or not 1 <= len(widths) <= 6 or
            any(type(w) is not int or not 240 <= w <= 3840 for w in widths) or len(set(widths)) != len(widths)):
        raise ValueError("widths must list 1 to 6 distinct integers between 240 and 3840.")
    if not isinstance(pages, list) or not 1 <= len(pages) <= 20:
        raise ValueError("pages must list 1 to 20 pages.")
    for page in pages:
        if not isinstance(page, dict):
            raise ValueError("Each page needs name and path.")
        route = page.get("path", "")
        if not isinstance(route, str) or not route.startswith("/") or route.startswith("//") or "\\" in route:
            raise ValueError("A page path starts with / and stays on the same server.")
        if not isinstance(page.get("name"), str) or not page["name"]:
            raise ValueError("Each page needs a name.")
    timeout = config.get("timeout_ms", 15000)
    if type(timeout) is not int or not 1 <= timeout <= 120000:
        raise ValueError("timeout_ms must be an integer between 1 and 120000.")
    return config, widths, pages


def sheet(rows):
    sections = []
    for row in rows:
        issues = ", ".join(row["issues"]) or "자동 검사에서 발견한 문제 없음"
        picture = f"<a href='{row['image']}'><img src='{row['image']}' alt='화면 전체 캡처'></a>" if row.get("image") else ""
        sections.append(f"<section><h2>{escape(row['name'])} · {row['width']}px</h2>"
                        f"<p>{escape(issues)}</p>{picture}</section>")
    return ("<!doctype html><html lang='ko'><meta charset='utf-8'><meta name='viewport' content='width=device-width'>"
            "<title>화면 검토 시트</title><style>body{margin:24px;font:16px/1.6 sans-serif;color:#203040;background:#f2f5f8}"
            "h1{font-size:28px}h2{font-size:18px}main{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px;align-items:start}"
            "section{background:white;border:1px solid #c8d4df;padding:16px;min-width:0}img{max-width:100%;height:auto;display:block}"
            "p{overflow-wrap:anywhere}@media(max-width:700px){main{grid-template-columns:1fr}}</style><h1>화면 검토 시트</h1><p>이미지를 누르면 전체 크기로 열립니다. "
            "자동 검사는 가로 넘침과 화면 밖 조작 요소를 확인합니다.</p><main>" + "".join(sections) + "</main></html>")


def capture(config_path, output, channel=None):
    config, widths, pages = load_config(config_path)
    try:
        from playwright.sync_api import sync_playwright, Error
    except ImportError as exc:
        raise ValueError("Screen capture needs the optional dependency agent-work-kit[ui].") from exc
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError("The output folder must be empty.")
    base = config["base_url"]
    origin = urlsplit(base)
    rows = []
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(**({"channel": channel} if channel else {}))
        except Error as exc:
            raise ValueError("Could not start the browser. Check the installation and the channel option.") from exc
        try:
            for number, item in enumerate(pages, 1):
                for width in widths:
                    row = {"name": item["name"], "width": width, "issues": [], "image": None}
                    rows.append(row)
                    context = browser.new_context(viewport={"width": width, "height": 900},
                                                  service_workers="block", accept_downloads=False)
                    def restrict(route):
                        url = urlsplit(route.request.url)
                        if (url.scheme, url.netloc) == (origin.scheme, origin.netloc) and route.request.method in ("GET", "HEAD"):
                            route.continue_()
                        else:
                            if "resource-blocked" not in row["issues"]:
                                row["issues"].append("resource-blocked")
                            route.abort()
                    context.route("**/*", restrict)
                    context.route_web_socket("**/*", lambda socket: socket.close())
                    page = context.new_page()
                    page.set_default_timeout(config.get("timeout_ms", 15000))
                    page.on("dialog", lambda dialog: dialog.dismiss())
                    try:
                        response = page.goto(urljoin(base, item["path"]), wait_until="load")
                        row["http_status"] = response.status if response else None
                        if response is None or response.status >= 400:
                            row["issues"].append("http-error")
                        # Bound font readiness by the normal locator timeout.
                        page.wait_for_function("!document.fonts || document.fonts.status === 'loaded'")
                        row["issues"].extend(page.evaluate(CHECKS))
                        row["image"] = f"page-{number:02d}-{width}.png"
                        page.screenshot(path=str(output / row["image"]), full_page=True, animations="disabled")
                    except Error:
                        row["issues"].append("capture-error")
                        row["image"] = None
                    finally:
                        context.close()
            (output / "index.html").write_text(sheet(rows), encoding="utf-8")
            result = {"status": "failed" if any(row["issues"] for row in rows) else "passed", "captures": rows,
                      "entry": str(output / "index.html")}
            (output / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            preview = browser.new_page(viewport={"width": 1440, "height": 900})
            preview.goto((output / "index.html").as_uri(), wait_until="load")
            preview.screenshot(path=str(output / "sheet.png"), full_page=True)
            return result
        finally:
            browser.close()
