import argparse
from collections import ChainMap
from pathlib import Path
import re
import shutil
from typing import Tuple

import markdown


class Template:
    def __init__(self, html: str, default_params: dict = None):
        self._default_params = default_params
        self._html = html

    def format(self, content: str, **params):
        cm = ChainMap(params, self._default_params or {})
        return self._html.format(content=content, **cm)


TEMPLATES = {}


def load_templates(path: Path) -> None:
    for fn in path.glob("*.html"):
        with fn.open(encoding="utf8") as f:
            source = f.read()
        params, html = extract_config(source)
        template = Template(html, params)
        TEMPLATES[fn.name.split(".")[0]] = template


def strip_quotes(string: str) -> str:
    if string.startswith('"') and string.endswith('"'):
        return string[1:-1]
    return string


def parse_params(params_string: str) -> dict:
    if not params_string:
        return {}
    key_value_pairs = re.findall(
        r'(?:^|,)\s*(".*?"|\w+)\s*:\s*(".*?"|\w+)\s*', params_string
    )
    return {strip_quotes(k): strip_quotes(v) for k, v in key_value_pairs}


def extract_config(source: str) -> Tuple[str, dict]:
    groups = re.match(
        r"(?:\s*<!--\s*(?P<params>.*?)\s*-->\n?)?(?P<content>.*)", source, re.DOTALL
    ).groupdict()

    params = parse_params(groups.get("params"))
    content = groups.get("content") or ""
    return params, content


def apply_template(
    template_name: str, content_html: str, config: dict = None, depth: int = 0
) -> str:
    return TEMPLATES[template_name].format(
        content=content_html, root="../" * depth, **config
    )


def compile_from_source(source: str, depth: int = 0) -> str:
    config, content_source = extract_config(source)
    content_html = markdown.markdown(content_source)
    html = apply_template(
        config.get("template", "default"), content_html, config, depth=depth
    )
    return html


def compile_md_to_file(source_path: Path, target_path: Path, depth: int = 0) -> None:
    with source_path.open(encoding="utf8") as f:
        source = f.read()

    compiled = compile_from_source(source, depth=depth)

    with target_path.open("w", encoding="utf8") as f:
        f.write(compiled)


def target_is_newer(source: Path, target: Path):
    return target.exists() and target.stat().st_mtime >= source.stat().st_mtime


def compile_all_files(source_root: Path, target_root: Path) -> None:
    for source_path in source_root.glob("**/*.*"):
        if not source_path.is_file():
            continue

        source_filename = source_path.name
        extension = source_path.suffix

        rel_path = source_path.relative_to(source_root)
        rel_dir = rel_path.parent
        depth = len(rel_dir.parents)

        target_dir = target_root / rel_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        if extension == ".md":
            target_filename = f"{source_path.stem}.html"
            target_path = target_dir / target_filename

            if target_is_newer(source_path, target_path):
                continue

            print("md", rel_path, "->", rel_dir / target_filename)
            compile_md_to_file(source_path, target_path, depth=depth)
        else:
            target_path = target_dir / source_filename

            if target_is_newer(source_path, target_path):
                continue

            print("cp", rel_path, "->", rel_path)
            shutil.copyfile(source_path, target_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "base_dir", type=Path, help="base dir containing src/content and src/templates",
    )
    parser.add_argument(
        "-o",
        "--output",
        dest="output_dir",
        type=Path,
        help="root dir of generated files (optional; default is {root_dir}/dist)",
    )
    args = parser.parse_args()

    load_templates(args.base_dir / "src/templates")
    compile_all_files(
        args.base_dir / "src/content", args.output_dir or args.base_dir / "dist"
    )


if __name__ == "__main__":
    main()
