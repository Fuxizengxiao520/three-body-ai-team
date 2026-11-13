"""任务卡、消息与产出物的轻量数据结构。"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path


def timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def identifier(prefix: str) -> str:
    return prefix + "-" + uuid.uuid4().hex[:8]


@dataclass
class TaskCard:
    id: str
    owner: str
    objective: str
    acceptance: list[str]
    inputs: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Message:
    id: str
    ts: str
    sender: str
    receiver: str
    kind: str
    subject: str
    payload: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Artifact:
    id: str
    ts: str
    owner: str
    kind: str
    task_id: str
    content: str
    tokens: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def append_jsonl(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(obj, ensure_ascii=False) + "\n")


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows
