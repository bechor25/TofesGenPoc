from __future__ import annotations

import json
from typing import Any


def extract_json(text: str) -> dict[str, Any]:
    start = text.find("{")
    while start != -1:
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : i + 1]
                    try:
                        result = json.loads(candidate)
                    except json.JSONDecodeError:
                        break
                    if isinstance(result, dict):
                        return result
                    break
        start = text.find("{", start + 1)
    raise ValueError("no JSON object found in text")
