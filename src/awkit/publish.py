"""Validate a trusted static build and atomically select an immutable version."""

import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sqlite3
import tempfile
from urllib.parse import unquote, urlsplit

from .review import relative_file


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def local_file(root, name):
    rel = relative_file(name)
    path = root / rel
    for part in [path, *path.parents]:
        if part == root.parent:
            break
        if part.is_symlink() or getattr(part, "is_junction", lambda: False)():
            raise ValueError(f"연결 파일은 발행할 수 없습니다: {name}")
    if not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError(f"파일을 찾을 수 없습니다: {name}")
    return path


class Inventory(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.ids, self.links = set(), []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "base" or "srcset" in attrs or "srcdoc" in attrs:
            raise ValueError("base, srcset, srcdoc는 현재 발행 검사에서 지원하지 않습니다.")
        if attrs.get("id"):
            self.ids.add(attrs["id"])
        if tag == "a" and attrs.get("name"):
            self.ids.add(attrs["name"])
        for key in ("href", "src", "poster", "data"):
            if attrs.get(key):
                self.links.append((attrs[key], tag == "a" and key == "href"))
        if attrs.get("style"):
            self.links.extend(css_links(attrs["style"]))


def css_links(text):
    if re.search(r"@import\b", text, re.I):
        raise ValueError("CSS @import를 합친 결과물을 발행하세요.")
    return [(match.group(2).strip(), False) for match in
            re.finditer(r"url\(\s*(['\"]?)(.*?)\1\s*\)", text, re.I)]


def validate(files):
    if "index.html" not in files:
        raise ValueError("허용 목록에 index.html이 필요합니다.")
    inventory = {name: Inventory(data.decode("utf-8")) for name, data in files.items()
                 if name.lower().endswith((".html", ".htm"))}
    links = {name: item.links for name, item in inventory.items()}
    for name, data in files.items():
        if name.lower().endswith(".css"):
            links[name] = css_links(data.decode("utf-8"))
        elif name in inventory:
            for style in re.findall(r"<style\b[^>]*>(.*?)</style\s*>", data.decode("utf-8"), re.I | re.S):
                links[name].extend(css_links(style))
    for source, references in links.items():
        for href, external_link in references:
            parts = urlsplit(href)
            if parts.scheme or parts.netloc:
                if external_link and parts.scheme.lower() in ("https", "http", "mailto", "tel"):
                    continue
                raise ValueError(f"외부 자원이나 지원하지 않는 주소입니다: {source}: {href}")
            decoded = unquote(parts.path)
            if decoded.startswith("/") or "\\" in decoded or ":" in decoded:
                raise ValueError(f"상대경로를 사용하세요: {source}: {href}")
            components = list(PurePosixPath(source).parent.parts)
            if not decoded:
                target = source
            else:
                for part in decoded.split("/"):
                    if part == "..":
                        if not components:
                            raise ValueError(f"발행 폴더 밖을 가리킵니다: {href}")
                        components.pop()
                    elif part not in ("", "."):
                        components.append(part)
                target = "/".join(components)
                if decoded.endswith("/"):
                    target += "/index.html" if target else "index.html"
            if target not in files:
                raise ValueError(f"허용 목록에 없는 연결입니다: {source}: {href}")
            if parts.fragment and target in inventory and unquote(parts.fragment) not in inventory[target].ids:
                raise ValueError(f"문서 안의 위치를 찾을 수 없습니다: {source}: {href}")


class Publisher:
    def __init__(self, output, project):
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", project):
            raise ValueError("프로젝트 이름에는 소문자, 숫자, 밑줄과 하이픈을 사용하세요.")
        raw_output = Path(output).absolute()
        if any(p.is_symlink() or getattr(p, "is_junction", lambda: False)()
               for p in [raw_output, *raw_output.parents]):
            raise ValueError("발행 폴더에 연결 경로를 사용할 수 없습니다.")
        self.output, self.project = raw_output.resolve(), project

    def _lock(self):
        self.output.mkdir(parents=True, exist_ok=True)
        marker = self.output / ".awkit-publisher.sqlite3"
        if not marker.exists() and any(self.output.iterdir()):
            raise ValueError("새 발행 폴더를 사용하세요. 기존 파일이 있습니다.")
        if marker.is_symlink():
            raise ValueError("발행 상태 파일에 연결 경로를 사용할 수 없습니다.")
        connection = sqlite3.connect(marker, timeout=1)
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("CREATE TABLE IF NOT EXISTS project (name TEXT NOT NULL)")
            row = connection.execute("SELECT name FROM project").fetchone()
            if row and row[0] != self.project:
                raise ValueError("다른 프로젝트의 발행 폴더입니다.")
            if not row:
                connection.execute("INSERT INTO project VALUES (?)", (self.project,))
                connection.commit()
                connection.execute("BEGIN IMMEDIATE")
            for child in (self.output / "versions", self.output / "index.html"):
                if child.is_symlink() or getattr(child, "is_junction", lambda: False)():
                    raise ValueError("발행 경로에 연결 파일을 사용할 수 없습니다.")
            return connection
        except BaseException:
            connection.close()
            raise

    def _verify(self, version):
        if not re.fullmatch(r"[a-f0-9]{64}", version):
            raise ValueError("발행 버전의 전체 해시를 지정하세요.")
        folder = self.output / "versions" / version
        manifest = json.loads(local_file(folder, "manifest.json").read_text(encoding="utf-8"))
        if manifest.get("project") != self.project or digest(encoded(manifest)) != version:
            raise ValueError("프로젝트나 발행 manifest가 일치하지 않습니다.")
        files = {}
        for name, checksum in manifest["files"].items():
            files[name] = local_file(folder, name).read_bytes()
            if digest(files[name]) != checksum:
                raise ValueError(f"발행 파일이 변경됐습니다: {name}")
        actual = {p.relative_to(folder).as_posix() for p in folder.rglob("*") if not p.is_dir()}
        if actual != set(files) | {"manifest.json"}:
            raise ValueError("발행 버전에 등록되지 않은 파일이 있습니다.")
        validate(files)
        return manifest

    def _activate(self, version):
        target = f"versions/{version}/index.html"
        text = ("<!doctype html><html lang='ko'><meta charset='utf-8'>"
                f"<meta name='awkit-version' content='{version}'>"
                f"<meta http-equiv='refresh' content='0;url={target}'>"
                "<title>발행 문서</title>"
                f"<a href='{target}'>발행 문서 열기</a></html>")
        fd, temporary = tempfile.mkstemp(prefix=".entry-", dir=self.output)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(text)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.output / "index.html")
        finally:
            Path(temporary).unlink(missing_ok=True)

    def publish(self, source, names):
        source = Path(source).absolute()
        if not names or len(names) != len(set(names)) or "manifest.json" in names:
            raise ValueError("중복 없이 파일 목록을 지정하고 manifest.json은 제외하세요.")
        files = {name: local_file(source, name).read_bytes() for name in names}
        validate(files)
        manifest = {"schema": 1, "project": self.project,
                    "files": {name: digest(data) for name, data in files.items()}}
        version = digest(encoded(manifest))
        connection = self._lock()
        try:
            versions = self.output / "versions"
            versions.mkdir(exist_ok=True)
            destination = versions / version
            if not destination.exists():
                temporary = Path(tempfile.mkdtemp(prefix=".incoming-", dir=versions))
                try:
                    for name, data in files.items():
                        target = temporary / name
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(data)
                    (temporary / "manifest.json").write_bytes(encoded(manifest))
                    temporary.rename(destination)
                finally:
                    if temporary.exists():
                        shutil.rmtree(temporary)
            self._verify(version)
            self._activate(version)
            connection.commit()
        finally:
            connection.close()
        return {"status": "published", "version": version, "entry": str(self.output / "index.html")}

    def restore(self, version):
        connection = self._lock()
        try:
            self._verify(version)
            self._activate(version)
            connection.commit()
        finally:
            connection.close()
        return {"status": "restored", "version": version, "entry": str(self.output / "index.html")}
