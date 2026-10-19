"""在各自操作系统构建免安装应用，并验证打包后的程序。"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NAME = "Mars竞赛助手"


def run(*args: str | Path, **kwargs: object) -> None:
    subprocess.run([str(arg) for arg in args], check=True, **kwargs)


def build(output: Path) -> Path:
    system = platform.system()
    if system not in {"Darwin", "Windows"}:
        raise RuntimeError("请在 Windows 或 macOS 上构建；不能交叉生成另一个系统的应用")
    machine = platform.machine().lower()
    architecture = {"amd64": "x64", "x86_64": "x64", "aarch64": "arm64"}.get(machine, machine)
    if architecture not in {"x64", "arm64"} or (system == "Windows" and architecture != "x64"):
        raise RuntimeError(f"尚未配置此构建架构：{system} {machine}")
    for filename in ("mars_app.py", "xxxx.py", "题库.xlsx", "桌面版使用说明.md"):
        if not (ROOT / filename).is_file():
            raise FileNotFoundError(filename)
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    label = f"{'macOS' if system == 'Darwin' else 'Windows'}-{architecture}"
    stem = f"{NAME}-{label}-免安装"
    # 工作目录放在本地临时目录，避免云同步目录阻塞大量中间文件。
    with tempfile.TemporaryDirectory(prefix="mars-desktop-build-") as directory:
        work = Path(directory)
        source = work / "source"
        source.mkdir()
        for filename in ("mars_app.py", "xxxx.py", "题库.xlsx"):
            shutil.copy2(ROOT / filename, source / filename)
        command = [
            sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
            "--windowed", "--onedir", "--name", NAME,
            "--distpath", str(work / "dist"), "--workpath", str(work / "build"),
            "--specpath", str(work), "--add-data", f"{source / '题库.xlsx'}{os.pathsep}.",
            "--collect-all", "ddddocr", "--collect-all", "onnxruntime", "--collect-all", "PySide6",
        ]
        if system == "Darwin":
            command += ["--osx-bundle-identifier", "local.mars.desktop"]
        command.append(str(source / "mars_app.py"))
        run(*command, cwd=source)
        delivery = work / stem
        delivery.mkdir()
        if system == "Darwin":
            app = delivery / f"{NAME}.app"
            run("ditto", work / "dist" / app.name, app)
            run("codesign", "--force", "--deep", "--sign", "-", app)
            run("codesign", "--verify", "--deep", "--strict", app)
            executable = app / "Contents" / "MacOS" / NAME
        else:
            app = delivery / NAME
            shutil.copytree(work / "dist" / NAME, app)
            executable = app / f"{NAME}.exe"
        report = work / "self-test.json"
        environment = os.environ.copy()
        for key in ("PYTHONHOME", "PYTHONPATH", "TCL_LIBRARY", "TK_LIBRARY"):
            environment.pop(key, None)
        run(executable, "--self-test", "--self-test-report", report,
            cwd=delivery, env=environment, timeout=180)
        result = json.loads(report.read_text(encoding="utf-8"))
        if not result.get("ok") or not result.get("frozen"):
            raise RuntimeError("打包后自检未通过")
        shutil.copy2(ROOT / "桌面版使用说明.md", delivery / "使用说明.md")
        # 自检与打包成功之前不更新交付目录。
        archive = work / f"{stem}.zip"
        if system == "Darwin":
            run("ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", delivery, archive)
        else:
            shutil.make_archive(str(archive.with_suffix("")), "zip", work, stem)
        destination = output / archive.name
        shutil.copy2(archive, destination)
        with destination.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        result.update({"archive": destination.name, "sha256": digest})
        (output / f"{stem}.self-test.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        (output / f"{stem}.sha256").write_text(f"{digest}  {destination.name}\n", encoding="utf-8")
        print(f"已生成并通过本机自检：{destination}", flush=True)
        return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist" / "desktop")
    build(parser.parse_args().output)
