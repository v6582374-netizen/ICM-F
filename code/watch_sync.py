#!/usr/bin/env python3
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ZH_DIR = ROOT / "zh" / "sections"
EN_DIR = ROOT / "en" / "sections"
ZH_MAIN = ROOT / "zh" / "main.tex"
EN_MAIN = ROOT / "en" / "main.tex"

API_URL = os.environ.get("DEEPSEEK_API_BASE", "https://api.deepseek.com/v1")
MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")


def _request_with_retry(payload: dict) -> dict:
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not set")

    request = urllib.request.Request(
        url=f"{API_URL.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    max_retries = 5
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(request) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504):
                sleep_s = 2 ** attempt
                print(f"[watch] HTTP {exc.code}. Retry in {sleep_s}s...", file=sys.stderr)
                time.sleep(sleep_s)
                continue
            raise RuntimeError(f"HTTP Error {exc.code}: {exc.reason}") from exc
        except urllib.error.URLError as exc:
            sleep_s = 2 ** attempt
            print(f"[watch] Network error: {exc.reason}. Retry in {sleep_s}s...", file=sys.stderr)
            time.sleep(sleep_s)
            continue

    raise RuntimeError("HTTP Error 429: Too Many Requests")


def _translate_latex(content: str) -> str:
    system_prompt = (
        "You are a professional academic translator for MCM/ICM papers. "
        "Translate Chinese to English. Preserve LaTeX commands, math, citations, "
        "labels, refs, file paths, and code. Translate text inside section titles, "
        "captions, and paragraphs while keeping the LaTeX structure unchanged. "
        "Do not add or remove content. Output only the translated LaTeX."
    )
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Translate the following LaTeX content:\n\n{content}"},
        ],
        "temperature": 0.2,
    }
    data = _request_with_retry(payload)
    return data["choices"][0]["message"]["content"].strip()


def _translate_title(title_text: str) -> str:
    system_prompt = (
        "Translate the following Chinese paper title to concise academic English. "
        "Return only the translated title text, no quotes or extra punctuation."
    )
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": title_text},
        ],
        "temperature": 0.2,
    }
    data = _request_with_retry(payload)
    return data["choices"][0]["message"]["content"].strip()


def _sync_section(zh_path: Path) -> None:
    rel = zh_path.relative_to(ZH_DIR)
    en_path = EN_DIR / rel
    content = zh_path.read_text(encoding="utf-8")
    translated = _translate_latex(content)
    en_path.parent.mkdir(parents=True, exist_ok=True)
    en_path.write_text(translated.rstrip() + "\n", encoding="utf-8")
    print(f"[watch] {zh_path} -> {en_path}")


def _extract_inputs(zh_main: str) -> list[str]:
    inputs = []
    for line in zh_main.splitlines():
        stripped = line.strip()
        if stripped.startswith(r"\input{sections/") and stripped.endswith("}"):
            inputs.append(stripped)
    return inputs


def _sync_main() -> None:
    zh_main = ZH_MAIN.read_text(encoding="utf-8")
    en_main = EN_MAIN.read_text(encoding="utf-8")

    title_match = re.search(r"\\title\{(.+?)\}", zh_main)
    if title_match:
        translated_title = _translate_title(title_match.group(1))
        en_main = re.sub(r"\\title\{.+?\}", f"\\\\title{{{translated_title}}}", en_main, count=1)

    inputs = _extract_inputs(zh_main)
    inputs_block = "\n".join(inputs)

    begin_marker = "% BEGIN AUTO INPUTS (synced from zh/main.tex)"
    end_marker = "% END AUTO INPUTS"
    if begin_marker in en_main and end_marker in en_main:
        pattern = re.compile(
            re.escape(begin_marker) + r".*?" + re.escape(end_marker),
            re.DOTALL,
        )
        replacement = f"{begin_marker}\n{inputs_block}\n{end_marker}"
        en_main = pattern.sub(replacement, en_main, count=1)
    else:
        raise RuntimeError("Auto-input markers not found in en/main.tex")

    EN_MAIN.write_text(en_main.rstrip() + "\n", encoding="utf-8")
    print(f"[watch] {ZH_MAIN} -> {EN_MAIN}")


def _init_en_main_markers() -> None:
    if not EN_MAIN.exists():
        return
    content = EN_MAIN.read_text(encoding="utf-8")
    if "% BEGIN AUTO INPUTS (synced from zh/main.tex)" in content:
        return
    inputs = _extract_inputs(content)
    inputs_block = "\n".join(inputs)
    replaced = content.replace(
        inputs_block,
        f"% BEGIN AUTO INPUTS (synced from zh/main.tex)\n{inputs_block}\n% END AUTO INPUTS",
    )
    EN_MAIN.write_text(replaced.rstrip() + "\n", encoding="utf-8")


def main() -> int:
    _init_en_main_markers()

    watch_targets = {ZH_MAIN} | set(ZH_DIR.glob("*.tex"))
    last_mtime: dict[Path, float] = {}
    for path in watch_targets:
        if path.exists():
            last_mtime[path] = path.stat().st_mtime

    print("[watch] Watching zh/main.tex and zh/sections/*.tex ...")
    while True:
        time.sleep(1.0)
        for path in list(watch_targets):
            if not path.exists():
                continue
            mtime = path.stat().st_mtime
            if last_mtime.get(path) == mtime:
                continue
            last_mtime[path] = mtime
            try:
                if path == ZH_MAIN:
                    _sync_main()
                elif path.suffix == ".tex":
                    _sync_section(path)
            except Exception as exc:
                print(f"[watch] Error syncing {path}: {exc}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
