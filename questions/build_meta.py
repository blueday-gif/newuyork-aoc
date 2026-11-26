"""100가지 질문 원문(story_01_100_questions.md)을 문항별 메타데이터로 바꾼다.
출력: questions/meta/questions.json
원문을 고치면 이 스크립트를 다시 돌린다. 문항별 해설(content/)과 통계(data/)는 건드리지 않는다.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "reports" / "stories" / "story_01_100_questions.md"
OUT = Path(__file__).resolve().parent / "meta" / "questions.json"

text = SRC.read_text(encoding="utf-8")
body = text.split("## 참고한 자료")[0]

parts = []
questions = []
part = None
cur = None
for line in body.splitlines():
    m = re.match(r"^## (\d+)부\. (.+?) \((\d+)–(\d+)\)\s*$", line)
    if m:
        part = {"no": int(m.group(1)), "title": m.group(2), "first": int(m.group(3)), "last": int(m.group(4))}
        parts.append(part)
        cur = None
        continue
    # 제목 줄 뒤에 답이 이어 붙은 경우가 있다: **49. [답] 질문?** 답...
    m = re.match(r"^\*\*(\d+)\. \[(답|결합|함정)\] (.+?)\*\*\s*(.*)$", line)
    if m:
        cur = {"id": int(m.group(1)), "part": part["no"], "tag": m.group(2),
               "title": m.group(3).strip(), "answer": m.group(4).strip()}
        questions.append(cur)
        continue
    if cur is not None and line.strip() and not line.startswith("---"):
        cur["answer"] += ("\n\n" if cur["answer"] else "") + line.strip()

ids = [q["id"] for q in questions]
assert ids == list(range(1, 101)), f"문항 번호가 1–100이 아니다: {len(ids)}개"
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps({"parts": parts, "questions": questions}, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"{len(parts)}부, {len(questions)}문항 → {OUT}")
