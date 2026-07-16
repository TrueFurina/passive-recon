"""纯被动红线静态闸门（T-P1-8 / V-P1-12,13）。

用标准库 ``ast`` 扫描 ``passive_agent/`` 下所有 .py，检测违反纯被动红线的代码：
  - ``verify=False``（关闭 TLS 校验）
  - 裸 ``requests.`` / ``httpx.`` 主动出站，且同一函数内未通过 R1 合规关隘
    （``compliance_client.check`` / ``_r1_pass`` / ``_check_compliance``）
  - 原始 ``socket.send*`` 发送（DNS 仅 ``socket.getaddrinfo`` 等解析类调用为放行）

导出 ``scan_path(root="passive_agent") -> List[Violation]`` 供测试复用；
CLI 入口：``python scripts/guard_passive.py [root]``，命中即 ``sys.exit(1)``，否则 0。

零新增依赖：仅 ast / os / sys / dataclasses / typing。
"""
from __future__ import annotations

import ast
import os
import sys
from dataclasses import dataclass
from typing import List, Set

# 出站模块根名（裸模块调用视为主动出站）
_EGRESS_MODULES = {"httpx", "requests"}
# 出站会话构造器（实例化后其方法亦视为出站）
_SESSION_CTORS = {
    ("httpx", "Client"),
    ("httpx", "AsyncClient"),
    ("requests", "Session"),
}
# 被动允许的 socket 调用（仅解析，不连接目标）
_ALLOWED_SOCKET = {
    "getaddrinfo", "gethostbyname", "gethostbyname_ex",
    "gethostbyaddr", "getfqdn", "getnameinfo",
}
# 合规关隘调用（视为已通过 R1 fail-closed 校验）
_COMPLIANCE_CALLS = {"check", "_r1_pass", "_check_compliance"}


@dataclass
class Violation:
    """单条违规记录。"""

    file: str
    line: int
    function: str
    kind: str
    message: str

    def __str__(self) -> str:
        return f"[{self.kind}] {self.file}:{self.line} in {self.function}(): {self.message}"


def _is_egress_call(node: ast.Call, egress_locals: Set[str]) -> bool:
    """是否为 httpx/requests 主动出站调用。"""
    f = node.func
    if not isinstance(f, ast.Attribute):
        return False
    val = f.value
    if not isinstance(val, ast.Name):
        return False
    if val.id in _EGRESS_MODULES:
        return True
    if val.id in egress_locals:
        return True
    return False


def _is_raw_socket(node: ast.Call) -> bool:
    """是否为原始 socket 发送（socket.send*）。"""
    f = node.func
    return (
        isinstance(f, ast.Attribute)
        and isinstance(f.value, ast.Name)
        and f.value.id == "socket"
        and f.attr.startswith("send")
    )


def _is_compliance_call(node: ast.Call) -> bool:
    """是否为 R1 合规关隘调用。"""
    f = node.func
    if isinstance(f, ast.Name) and f.id in _COMPLIANCE_CALLS:
        return True
    if isinstance(f, ast.Attribute) and f.attr in _COMPLIANCE_CALLS:
        return True
    return False


def _collect_egress_locals(func: ast.AST) -> Set[str]:
    """收集由 httpx.Client / httpx.AsyncClient / requests.Session 赋值得到的局部变量名。"""
    names: Set[str] = set()
    for n in ast.walk(func):
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            v = n.value
            if isinstance(v, ast.Call) and isinstance(v.func, ast.Attribute):
                fv = v.func.value
                if isinstance(fv, ast.Name) and (fv.id, v.func.attr) in _SESSION_CTORS:
                    names.add(n.targets[0].id)
    return names


def _iter_own_nodes(node: ast.AST):
    """遍历节点直接子节点，但不进入嵌套函数体（避免跨函数污染）。"""
    stack = list(ast.iter_child_nodes(node))
    while stack:
        n = stack.pop()
        yield n
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        stack.extend(ast.iter_child_nodes(n))


def _analyze_function(filepath: str, func: ast.AST) -> List[Violation]:
    """分析单个函数体（不含嵌套函数）的纯被动合规情况。"""
    fname = getattr(func, "name", "<lambda>")
    egress_locals = _collect_egress_locals(func)

    has_egress = False
    has_raw_socket = False
    has_verify_false = False
    has_compliance = False

    for n in _iter_own_nodes(func):
        if not isinstance(n, ast.Call):
            continue
        # verify=False（关闭 TLS 校验）
        for kw in n.keywords:
            if kw.arg == "verify" and isinstance(kw.value, ast.Constant) and kw.value.value is False:
                has_verify_false = True
        if _is_raw_socket(n):
            has_raw_socket = True
        if _is_egress_call(n, egress_locals):
            has_egress = True
        if _is_compliance_call(n):
            has_compliance = True

    violations: List[Violation] = []
    if has_verify_false:
        violations.append(Violation(
            filepath, func.lineno, fname, "verify_false",
            "检测到 verify=False（关闭 TLS 校验），违反纯被动红线",
        ))
    if has_raw_socket:
        violations.append(Violation(
            filepath, func.lineno, fname, "raw_socket_send",
            "检测到原始 socket 发送（socket.send*），属主动出站",
        ))
    if has_egress and not has_compliance:
        violations.append(Violation(
            filepath, func.lineno, fname, "egress_without_compliance",
            "检测到 httpx/requests 出站，但未在同一函数内通过 R1 合规关隘"
            "(check / _r1_pass / _check_compliance)",
        ))
    return violations


def _scan_file(filepath: str) -> List[Violation]:
    try:
        with open(filepath, "r", encoding="utf-8") as fh:
            src = fh.read()
    except Exception:
        return []
    try:
        tree = ast.parse(src, filename=filepath)
    except SyntaxError:
        return []

    out: List[Violation] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.extend(_analyze_function(filepath, node))
    return out


def scan_path(root: str = "passive_agent") -> List[Violation]:
    """扫描 root 目录下所有 .py，返回违例列表（空列表 = 无违例）。"""
    violations: List[Violation] = []
    if not os.path.exists(root):
        return violations
    for dirpath, dirnames, filenames in os.walk(root):
        if "__pycache__" in dirpath:
            continue
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            violations.extend(_scan_file(os.path.join(dirpath, fn)))
    return violations


def main(argv: List[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    root = argv[0] if argv else "passive_agent"
    violations = scan_path(root)
    if violations:
        print(f"[guard_passive] 检测到 {len(violations)} 处纯被动红线违例：")
        for v in violations:
            print(f"  {v}")
        return 1
    print("[guard_passive] OK：未检测到纯被动红线违例。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
