#!/usr/bin/env python3
"""用 GitHub REST API 建仓并同步文件，绕开 github.com 网页域名。

可重复运行，内容未变的文件跳过，变化的文件带 sha 更新。
token 只从环境变量或本机文件读取，不写入仓库、日志或标准输出。
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.github.com"
ROOT = Path(__file__).resolve().parent.parent
TOKEN_FILE = Path.home() / ".workbuddy" / "github_pat"


class ApiError(RuntimeError):
    pass


def load_token() -> str:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token and TOKEN_FILE.exists():
        token = TOKEN_FILE.read_text(encoding="utf-8").strip()
    if not token:
        raise ApiError("缺少 token，设置 GITHUB_TOKEN 或写入 " + str(TOKEN_FILE))
    return token


def request(method: str, path: str, token: str, payload=None, tolerate=()):
    data = (
        json.dumps(payload, ensure_ascii=False).encode("utf-8")
        if payload is not None
        else None
    )
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + token,
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "three-body-ai-team-publisher",
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(
        API + path, data=data, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read().decode("utf-8")
            return response.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as error:
        if error.code in tolerate:
            return error.code, {}
        detail = error.read().decode("utf-8")[:300]
        raise ApiError(
            method + " " + path + " 返回 " + str(error.code) + " " + detail
        ) from error
    except urllib.error.URLError as error:
        raise ApiError("网络失败 " + str(error)) from error


def tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="通过 GitHub API 发布本项目")
    parser.add_argument(
        "--owner",
        default=os.environ.get("GITHUB_OWNER", "Fuxizengxiao520"),
        help="GitHub 用户名，也可用 GITHUB_OWNER 覆盖",
    )
    parser.add_argument("--repo", default="three-body-ai-team")
    parser.add_argument("--private", action="store_true", help="建为私有仓库，默认公开")
    parser.add_argument(
        "--dry-run", action="store_true", help="只列出将上传的文件，不需要 token"
    )
    args = parser.parse_args(argv)

    files = tracked_files()
    if args.dry_run:
        print("目标 https://github.com/" + args.owner + "/" + args.repo)
        print("可见性", "private" if args.private else "public")
        print("文件", len(files))
        for path in files:
            print("  ", path)
        ready = bool(os.environ.get("GITHUB_TOKEN")) or TOKEN_FILE.exists()
        print("token", "已配置" if ready else "未配置")
        return 0

    token = load_token()
    _, me = request("GET", "/user", token)
    login = me.get("login", "")
    if not login or login.lower() != args.owner.lower():
        raise ApiError(
            "token 所属账号 " + (login or "未知") + " 与 --owner " + args.owner + " 不一致，已停止"
        )

    status, _ = request(
        "GET", "/repos/" + args.owner + "/" + args.repo, token, tolerate=(404,)
    )
    if status == 404:
        request(
            "POST",
            "/user/repos",
            token,
            {
                "name": args.repo,
                "description": "三体 AI 团队，本地可运行的多智能体协作最小闭环",
                "private": args.private,
                "auto_init": False,
            },
        )
        print("仓库已创建")
    else:
        print("仓库已存在，跳过创建")

    changed = 0
    for path in files:
        local_bytes = (ROOT / path).read_bytes()
        endpoint = "/repos/" + args.owner + "/" + args.repo + "/contents/" + path
        status, existing = request("GET", endpoint, token, tolerate=(404,))
        if status == 200 and isinstance(existing, dict):
            remote_bytes = base64.b64decode(existing.get("content") or "")
            if remote_bytes == local_bytes:
                print("未变化", path)
                continue
        payload = {
            "message": "sync " + path,
            "content": base64.b64encode(local_bytes).decode("ascii"),
        }
        if status == 200 and isinstance(existing, dict) and existing.get("sha"):
            payload["sha"] = existing["sha"]
        request("PUT", endpoint, token, payload)
        changed += 1
        print("已同步", path)

    print("本次变更", changed, "个文件")
    print("完成 https://github.com/" + args.owner + "/" + args.repo)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ApiError as error:
        print("错误 " + str(error), file=sys.stderr)
        raise SystemExit(1)
