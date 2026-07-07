# -*- coding: utf-8 -*-
"""Formula and GP-lineage visualization helpers."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from textwrap import wrap


@dataclass
class ExprNode:
    label: str
    children: list["ExprNode"] = field(default_factory=list)


def _strip_outer(s: str) -> str:
    s = s.strip()
    while s.startswith("(") and s.endswith(")"):
        depth = 0
        ok = True
        for i, ch in enumerate(s):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0 and i != len(s) - 1:
                    ok = False
                    break
        if ok:
            s = s[1:-1].strip()
        else:
            break
    return s


def _split_top_commas(s: str) -> list[str]:
    out, buf, depth = [], [], 0
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            out.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    if buf:
        out.append("".join(buf).strip())
    return out


def _find_top_binary(s: str):
    depth = 0
    # Low-precedence first, right-to-left to preserve broad splits.
    for ops in (["+", "-"], ["*", "/"]):
        depth = 0
        for i in range(len(s) - 1, -1, -1):
            ch = s[i]
            if ch == ")":
                depth += 1
            elif ch == "(":
                depth -= 1
            elif depth == 0 and ch in ops:
                if ch == "-" and (i == 0 or s[i - 1] in "+-*/("):
                    continue
                return i, ch
    return None


def parse_expr_tree(expr: str) -> ExprNode:
    s = _strip_outer(expr)
    if s.startswith("-") and not re.match(r"^-\d", s):
        return ExprNode("NEGATE", [parse_expr_tree(s[1:])])
    found = _find_top_binary(s)
    if found:
        i, op = found
        label = {"+": "ADD", "-": "SUBTRACT", "*": "MULTIPLY", "/": "DIVIDE"}[op]
        return ExprNode(label, [parse_expr_tree(s[:i]), parse_expr_tree(s[i + 1:])])

    m = re.match(r"^([A-Z_]+)\((.*)\)$", s)
    if m:
        op, inside = m.group(1), m.group(2)
        children = []
        for arg in _split_top_commas(inside):
            if re.fullmatch(r"-?\d+(\.\d+)?", arg):
                children.append(ExprNode(f"window={arg}"))
            else:
                children.append(parse_expr_tree(arg))
        return ExprNode(op, children)
    return ExprNode(s)


def _safe_label(text: str) -> str:
    return str(text).replace('"', "'").replace("$", "＄")


def write_formula_tree(expr: str, out_md: Path, out_png: Path | None = None, title: str = "Formula Tree"):
    root = parse_expr_tree(expr)
    lines = [f"# {title}", "", "```mermaid", "flowchart TD"]
    counter = 0

    def walk(node: ExprNode, parent=None):
        nonlocal counter
        nid = f"N{counter}"
        counter += 1
        lines.append(f'  {nid}["{_safe_label(node.label)}"]')
        if parent is not None:
            lines.append(f"  {parent} --> {nid}")
        for child in node.children:
            walk(child, nid)
        return nid

    walk(root)
    lines += ["```", "", f"- **Expression:** `{expr}`"]
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(lines), encoding="utf-8")
    if out_png is not None:
        _write_expr_png(root, out_png, title, expr)


def _tree_positions(root: ExprNode):
    positions = {}
    labels = {}
    edges = []
    leaf_x = 0

    def assign(node: ExprNode, depth=0):
        nonlocal leaf_x
        node_id = len(labels)
        labels[node_id] = node.label
        child_ids = [assign(c, depth + 1) for c in node.children]
        for cid in child_ids:
            edges.append((node_id, cid))
        if child_ids:
            x = sum(positions[cid][0] for cid in child_ids) / len(child_ids)
        else:
            x = leaf_x
            leaf_x += 1
        positions[node_id] = (x, -depth)
        return node_id

    assign(root)
    return positions, labels, edges


def _visual_label(label: str) -> str:
    mapping = {
        "ADD": "add",
        "SUBTRACT": "sub",
        "MULTIPLY": "mul",
        "DIVIDE": "div",
        "NEGATE": "neg",
    }
    if label in mapping:
        return mapping[label]
    if re.fullmatch(r"[A-Z_]+", label):
        return label.lower()
    if label.startswith("window="):
        return label.replace("window=", "p=")
    return label


def _write_expr_png(root: ExprNode, out_png: Path, title: str, expr: str = ""):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Ellipse, Rectangle

    pos, labels, edges = _tree_positions(root)
    max_x = max((p[0] for p in pos.values()), default=1)
    min_y = min((p[1] for p in pos.values()), default=-1)
    fig_w = max(11, max_x * 1.35 + 2)
    fig_h = max(7, abs(min_y) * 1.3 + 2.6)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.axis("off")
    ax.set_title(title.replace("$", r"\$"), fontsize=12, fontweight="bold", pad=16)
    y_offset = -0.9
    if expr:
        x0, x1 = -1.0, max_x + 1.0
        ax.add_patch(Rectangle((x0, 0.65), x1 - x0, 0.42, facecolor="#eefbd2", edgecolor="#d0e8a0", lw=0.8))
        ax.text((x0 + x1) / 2, 0.86, expr.replace("$", r"\$"), ha="center", va="center",
                fontsize=8, family="monospace")
    for a, b in edges:
        x1, y1 = pos[a]
        x2, y2 = pos[b]
        y1 += y_offset
        y2 += y_offset
        ax.annotate("", xy=(x2, y2 + 0.16), xytext=(x1, y1 - 0.16),
                    arrowprops=dict(arrowstyle="-|>", lw=0.9, color="#222222"))
    for nid, (x, y) in pos.items():
        y += y_offset
        label_raw = _visual_label(str(labels[nid])).replace("$", r"\$")
        label = "\n".join(wrap(label_raw, width=16))
        is_op = bool(ExprNode) and str(labels[nid]).split("(")[0].isupper()
        fc = "#3f73d8" if is_op or str(labels[nid]) in {"ADD", "SUBTRACT", "MULTIPLY", "DIVIDE", "NEGATE"} else "#75a9f0"
        ell = Ellipse((x, y), width=1.18, height=0.48, facecolor=fc, edgecolor="#1e2a44", lw=1.1)
        ax.add_patch(ell)
        ax.text(x, y, label, ha="center", va="center", fontsize=8.5, color="#111111", family="serif")
    ax.set_xlim(-1, max_x + 1)
    ax.set_ylim(min_y + y_offset - 1, 1.2)
    fig.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=130)
    plt.close(fig)


def write_lineage_tree(records: list[dict], out_md: Path, out_png: Path | None = None, title: str = "GP Lineage"):
    out_md.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# {title}", "", "```mermaid", "flowchart TD"]
    rec_by_id = {r["id"]: r for r in records}
    for r in records:
        score = r.get("score")
        score_txt = "" if score is None else f"\\nIC={score:+.4f}"
        label = f"{r['id']}\\n{r.get('op','?')}\\ngen={r.get('gen','?')}{score_txt}"
        lines.append(f'  {r["id"]}["{_safe_label(label)}"]')
    for r in records:
        for p in r.get("parents", []):
            if p in rec_by_id:
                lines.append(f"  {p} --> {r['id']}")
    lines += ["```", "", "## Nodes", ""]
    for r in records:
        lines.append(f"- `{r['id']}` gen={r.get('gen')} op={r.get('op')} score={r.get('score')} expr=`{r.get('expr','')}`")
    out_md.write_text("\n".join(lines), encoding="utf-8")
    if out_png is not None:
        _write_lineage_png(records, out_png, title)


def _write_lineage_png(records: list[dict], out_png: Path, title: str):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    levels = {}
    for r in records:
        levels.setdefault(int(r.get("gen", 0)), []).append(r)
    fig, ax = plt.subplots(figsize=(max(12, max(len(v) for v in levels.values()) * 1.6), max(7, len(levels) * 1.5)))
    ax.axis("off")
    ax.set_title(title, fontsize=12, fontweight="bold")
    pos = {}
    for gen, rows in sorted(levels.items()):
        n = len(rows)
        for i, r in enumerate(rows):
            x = i - (n - 1) / 2
            y = -gen
            pos[r["id"]] = (x, y)
    for r in records:
        for p in r.get("parents", []):
            if p in pos and r["id"] in pos:
                x1, y1 = pos[p]
                x2, y2 = pos[r["id"]]
                ax.plot([x1, x2], [y1, y2], color="#999999", lw=0.7)
    for r in records:
        x, y = pos[r["id"]]
        score = r.get("score")
        label = f"{r['id']}\n{r.get('op')}\n" + (f"{score:+.3f}" if score is not None else "")
        fc = "#e8f1fb" if r.get("is_best") else "#f7f7f7"
        ax.text(x, y, label, ha="center", va="center", fontsize=7,
                bbox=dict(boxstyle="round,pad=0.25", fc=fc, ec="#555555", lw=0.7))
    xs = [p[0] for p in pos.values()] or [0]
    ys = [p[1] for p in pos.values()] or [0]
    ax.set_xlim(min(xs) - 1, max(xs) + 1)
    ax.set_ylim(min(ys) - 1, 1)
    fig.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=130)
    plt.close(fig)
