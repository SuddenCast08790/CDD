#!/usr/bin/env python3
"""
C-- compiler (reference implementation, v-4)
=============================================
Forked-from-GCC spirit: we took C and chopped. Hard.

Pipeline:  .ccm source -> tokenize -> parse (indentation blocks)
           -> emit ANSI C -> invoke system cc -> native binary.

Chopped away: semicolons, for-loops, ==, !=, &&, ||, {}, return,
#include, NULL, switch, ?: , int/char/float, // and /* */ comments.
Created instead: `is`, `isnt`, `&also`, `|else&`, `loop..until`,
`skip`, `halt`, `back`, `shout`, `borrow`, `pick/case/thunk`,
`p^` deref, `maybe(a,b,c)`, string interpolation `{expr}`, `nothing`.
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile

VERSION = "C-- v-4 (the one that ate for-loops)"

# ---------------------------------------------------------------- helpers
class CmmError(Exception):
    def __init__(self, line, msg):
        super().__init__(f"line {line}: {msg}")
        self.line, self.msg = line, msg


KEYWORDS = {
    "func", "loop", "until", "if", "elif", "else", "unless", "skip",
    "halt", "back", "borrow", "pick", "case", "thunk", "default",
    "while", "let", "is", "isnt", "nothing", "maybe", "shout",
    "text", "num", "none", "bool", "true", "false", "not", "new",
}

BIN_OP_WORDS = [
    ("&also", "&&"), ("|else&", "||"),
    (" isnt ", " != "), (" is ", " == "),
]

TYPE_MAP = {"num": "long", "text": "const char*", "bool": "int",
            "none": "void"}

# ---------------------------------------------------------------- lexing-ish
def strip_comment(line):
    """Remove a trailing `#` comment, respecting string literals."""
    out, in_str, esc = [], False, False
    for ch in line:
        if esc:
            out.append(ch); esc = False; continue
        if ch == "\\" and in_str:
            out.append(ch); esc = True; continue
        if ch == '"':
            in_str = not in_str
        if ch == "#" and not in_str:
            break
        out.append(ch)
    return "".join(out)


def split_args(s):
    """Split 'a, b, "x, y"' on top-level commas."""
    parts, buf, depth, in_str, esc = [], [], 0, False, False
    for ch in s:
        if esc:
            buf.append(ch); esc = False; continue
        if ch == "\\" and in_str:
            buf.append(ch); esc = True; continue
        if ch == '"':
            in_str = not in_str
        if not in_str:
            if ch in "([{": depth += 1
            if ch in ")]}": depth -= 1
            if ch == "," and depth == 0:
                parts.append("".join(buf)); buf = []; continue
        buf.append(ch)
    if "".join(buf).strip():
        parts.append("".join(buf))
    return [p.strip() for p in parts]


def convert_expr(expr):
    """Translate C-- expression syntax into C."""
    # protect string literals from keyword surgery
    strings = []
    def stash(m):
        strings.append(m.group(0))
        return f"\x00{len(strings)-1}\x00"
    expr = re.sub(r'"(?:[^"\\]|\\.)*"', stash, expr)

    # arithmetic word operators (before `is`, so `this is` stays safe)
    expr = re.sub(r"\bmod\b", "%", expr)
    expr = expr.replace("&also", "&&").replace("|else&", "||")
    expr = re.sub(r"\bisnt\b", "!=", expr)
    expr = re.sub(r"\bis\b", "==", expr)
    expr = re.sub(r"\bnot\b", "!", expr)
    expr = re.sub(r"\bnothing\b", "NULL", expr)
    expr = re.sub(r"\btrue\b", "1", expr)
    expr = re.sub(r"\bfalse\b", "0", expr)

    # maybe(a, b, c) -> ((a) ? (b) : (c))
    def fix_maybe(m):
        args = split_args(m.group(1))
        if len(args) != 3:
            raise CmmError(0, f"maybe() wants 3 args, got {len(args)}")
        return f"(({args[0]}) ? ({args[1]}) : ({args[2]}))"
    while re.search(r"\bmaybe\(", expr):
        expr = re.sub(r"\bmaybe\(([^()]*(?:\([^()]*\)[^()]*)*)\)",
                      fix_maybe, expr)

    # pointer deref: ident^ -> (*ident) ; also (expr)^
    expr = re.sub(r"([A-Za-z_][A-Za-z0-9_]*)\^", r"(*\1)", expr)
    expr = re.sub(r"\)\^", ")", expr)  # weak forgiveness

    # unprotect strings
    expr = re.sub(r"\x00(\d+)\x00", lambda m: strings[int(m.group(1))], expr)
    return expr.strip()


def guess_fmt(expr):
    """Pick a printf conversion for an interpolated expression."""
    e = expr.strip()
    if re.match(r'^"', e):
        return "%s"
    if re.search(r"[/*]|mod\b", e) or re.match(r"^-?\d+$", e):
        return "%ld"
    if re.match(r"^\.?[-\d]+$", e) and "." in e:
        return "%g"
    if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", e):
        return "__FMT__"          # resolved per-function via declared types
    if re.search(r"[<>]", e):
        return "%d"               # comparisons yield ints
    return "%s"                   # function calls etc.: assume text


def resolve_fmt(fmt, argdecls):
    """Replace __FMT__ placeholders using known variable types."""
    out, i = [], 0
    parts = re.split(r"(__FMT__)", fmt)
    fi = 0
    for p in parts:
        if p == "__FMT__":
            t = argdecls.get(fi, "long")
            out.append("%ld" if t in ("long", "int") else "%s")
            fi += 1
        else:
            if p.count("%") and p not in ("%s", "%ld", "%g", "%d"):
                pass
            out.append(p)
            fi += p.count("%s") + p.count("%ld") + p.count("%g") \
                 + p.count("%d")
    return "".join(out)


def interpolate(lit, emit_stmt):
    """'a {x} b' -> printf pieces with per-expression conversions."""
    pieces = re.split(r"(?<!\\)\{([^{}]+)\}(?<!\\)", lit)
    fmt, args = "", []
    for idx, p in enumerate(pieces):
        if idx % 2 == 0:
            fmt += p
        else:
            e = convert_expr(p)
            fmt += guess_fmt(e)
            args.append(e)
    return fmt, args


def infer_type(raw):
    raw = raw.strip()
    if re.match(r'^"', raw):
        return "const char*"
    if re.match(r"^[-\d]+\.\d+", raw):
        return "double"
    if re.match(r"^[-\d]+$", raw):
        return "long"
    if raw in ("true", "false"):
        return "int"
    if raw.startswith("&"):
        return "long*"
    if re.search(r"[<>]|==|!=|&&|\|\|", raw):
        return "int"
    return "long"


# ---------------------------------------------------------------- parser
class Node:
    def __init__(self, kind, **kw):
        self.kind = kind
        self.__dict__.update(kw)


def tokenize(src):
    """Yield (indent, lineno, text) for logical lines (joins \\ continuations)."""
    raw = src.splitlines()
    joined = []
    buf, buf_indent, buf_line = "", None, None
    for i, line in enumerate(raw, 1):
        stripped_full = strip_comment(line)
        content = stripped_full.rstrip()
        if content.endswith("\\"):
            if buf is None or buf == "":
                buf_indent = len(content) - len(content.lstrip())
                buf_line = i
            buf += content[:-1] + " "
            continue
        if buf:
            joined.append((buf_indent, buf_line, (buf + content).strip()))
            buf = ""
            # fallthrough to also record current line? no: continuation merged.
            continue
        t = stripped_full.strip()
        if not t:
            continue
        indent = len(stripped_full) - len(stripped_full.lstrip())
        joined.append((indent, i, t))
    if buf:
        joined.append((buf_indent, buf_line, buf.strip()))
    return joined


def parse_block(tokens, pos, base_indent, stop=None):
    """stop: predicate(text) that ends the block when seen at base_indent."""
    body = []
    while pos < len(tokens):
        indent, ln, text = tokens[pos]
        if indent < base_indent:
            break
        if indent == base_indent and stop and stop(text):
            break
        if indent > base_indent and body:
            raise CmmError(ln, "inconsistent indentation "
                               "(we chopped tabs too)")
        node, pos = parse_statement(tokens, pos, indent)
        body.append(node)
    return body, pos


def parse_statement(tokens, pos, indent):
    _, ln, text = tokens[pos]
    words = text

    def child_block(pos):
        nxt = tokens[pos] if pos < len(tokens) else None
        if nxt and nxt[0] > indent:
            return parse_block(tokens, pos, nxt[0])
        # inline block after colon on same line? not supported (chopped)
        raise CmmError(ln, f"`{words.split()[0]}` expects an indented block")

    # ---- borrow ----
    if words.startswith("borrow "):
        m = re.match(r"borrow\s+<([\w/]+)>", words)
        if not m:
            raise CmmError(ln, "borrow wants <header>, e.g. borrow <stdio>")
        return Node("borrow", header=m.group(1), line=ln), pos + 1

    # ---- func ----
    if words.startswith("func "):
        m = re.match(r"func\s+(\w+)\(([^)]*)\)\s*->\s*(\w+)\s*:$", words)
        if not m:
            raise CmmError(ln,
                "func needs `name(params) -> type:` (colon required, "
                "because we chopped almost everything else)")
        name, params_s, ret = m.groups()
        params = []
        for p in split_args(params_s):
            if not p:
                continue
            pm = re.match(r"(\w+)\s+is\s+(\w+)$", p)
            if not pm:
                raise CmmError(ln, f"param `{p}` must read `name is type`")
            pname, ptype = pm.groups()
            params.append((pname, ptype))
        body, npos = child_block(pos + 1)
        return Node("func", name=name, params=params, ret=ret,
                    body=body, line=ln), npos

    # ---- let / assignment ----
    m = re.match(r"let\s+(\w+)\s+(?:is|=)\s+(.+)$", words)
    if m:
        target, val = m.groups()
        return Node("let", target=target, val=convert_expr(val),
                    raw_val=val, line=ln), pos + 1
    m = re.match(r"(\w+)\s*=\s*(.+)$", words)
    if m and m.group(1) not in KEYWORDS:
        target, val = m.groups()
        return Node("assign", target=target, val=convert_expr(val),
                    line=ln), pos + 1

    # ---- back ----
    m = re.match(r"back(?:\s+(.*))?$", words)
    if m:
        v = m.group(1)
        return Node("back", val=convert_expr(v) if v else None,
                    line=ln), pos + 1

    # ---- skip / halt ----
    if words in ("skip", "halt"):
        return Node(words, line=ln), pos + 1

    # ---- loop X from A to B: ... until COND ----
    m = re.match(r"loop\s+(\w+)\s+from\s+(.+?)\s+to\s+(.+?):$", words)
    if m:
        var, start, stop = m.groups()
        body, npos = child_block(pos + 1)
        # find matching `until` at same indent
        if npos >= len(tokens) or tokens[npos][0] != indent:
            raise CmmError(ln, "loop lost its `until` (we chop orphans)")
        _, uln, utext = tokens[npos]
        um = re.match(r"until\s+(.+)$", utext)
        if not um:
            raise CmmError(uln, "expected `until <cond>` to close loop")
        cond = convert_expr(um.group(1))
        return Node("loop", var=var, start=convert_expr(start),
                    stop=convert_expr(stop), cond=cond, body=body,
                    line=ln), npos + 1

    # ---- while ----
    m = re.match(r"while\s+(.+?):$", words)
    if m:
        body, npos = child_block(pos + 1)
        return Node("while", cond=convert_expr(m.group(1)), body=body,
                    line=ln), npos

    # ---- bare shout on its own line after keyword? handled by raw path ----

    # ---- unless ----
    m = re.match(r"unless\s+(.+?):$", words)
    if m:
        body, npos = child_block(pos + 1)
        return Node("if", cond=f"!({convert_expr(m.group(1))})",
                    body=body, orelse=[], line=ln), npos

    # ---- if / elif / else ----
    m = re.match(r"if\s+(.+?):$", words)
    if m:
        body, npos = child_block(pos + 1)
        orelse = []
        if npos < len(tokens) and tokens[npos][0] == indent and \
           re.match(r"(elif|else)", tokens[npos][2]):
            orelse, npos = parse_statement(tokens, npos, indent) \
                if False else (None, npos)
            # handled below via chain
            kind, npos2 = _attach_else(tokens, npos, indent)
            return Node("ifchain", head=Node("if",
                        cond=convert_expr(m.group(1)), body=body,
                        orelse=None), tail=kind, line=ln), npos2
        return Node("if", cond=convert_expr(m.group(1)), body=body,
                    orelse=orelse, line=ln), npos
    m = re.match(r"elif\s+(.+?):$", words)
    if m:
        body, npos = child_block(pos + 1)
        tail = None
        if npos < len(tokens) and tokens[npos][0] == indent and \
           re.match(r"(elif|else)\b", tokens[npos][2]):
            tail, npos = _attach_else(tokens, npos, indent)
        return Node("elif", cond=convert_expr(m.group(1)), body=body,
                    tail=tail, line=ln), npos
    if words == "else:":
        body, npos = child_block(pos + 1)
        return Node("else", body=body, line=ln), npos

    # ---- pick / case / thunk ----
    m = re.match(r"pick\s+(.+?):$", words)
    if m:
        subject = convert_expr(m.group(1))
        nxt = tokens[pos + 1] if pos + 1 < len(tokens) else None
        if not nxt or nxt[0] <= indent:
            raise CmmError(ln, "pick expects indented `case ... thunk:`")
        cind = nxt[0]
        cases, default = [], None
        npos = pos + 1
        is_case = lambda t: re.match(r"(case\s|default\s)", t)
        while npos < len(tokens) and tokens[npos][0] == cind and \
              is_case(tokens[npos][2]):
            _, cln, ct = tokens[npos]
            cm = re.match(r"case\s+(.+?)\s+thunk:$", ct)
            dm = re.match(r"default thunk:$", ct)
            if cm:
                vals = [convert_expr(v) for v in split_args(cm.group(1))]
                cbody, npos = parse_block(tokens, npos + 1,
                                          tokens[npos + 1][0]) \
                    if npos + 1 < len(tokens) and \
                       tokens[npos + 1][0] > cind else ([], npos + 1)
                cases.append((vals, cbody))
            elif dm:
                if npos + 1 < len(tokens) and tokens[npos + 1][0] > cind:
                    default, npos = parse_block(tokens, npos + 1,
                                                tokens[npos + 1][0])
                else:
                    raise CmmError(cln, "empty default thunk")
            else:
                raise CmmError(cln, "inside pick: only `case v thunk:` "
                                    "or `default thunk:` survive")
        return Node("pick", subject=subject, cases=cases,
                    default=default, line=ln), npos

    # ---- shout(...) with interpolation ----
    m = re.match(r"shout\((.*)\)$", words)
    if m:
        args = split_args(m.group(1))
        if not args:
            raise CmmError(ln, "shout() with no voice?")
        first = args[0]
        sm = re.match(r'^"((?:[^"\\]|\\.)*)"$', first)
        if sm and "{" in first:
            fmt, extra = interpolate(sm.group(1), None)
            all_args = [convert_expr(a) for a in extra] + \
                       [convert_expr(a) for a in args[1:]]
            argtypes = [infer_type(e) for e in extra] + \
                       [infer_type(a) for a in args[1:]]
            return Node("call", fn="printf",
                        argstr='"%s"' % fmt +
                        ("".join(", " + a for a in all_args)),
                        argtypes=argtypes, interp=True,
                        line=ln), pos + 1
        converted = [convert_expr(a) for a in args]
        return Node("call", fn="printf", argstr=", ".join(converted),
                    line=ln), pos + 1

    # ---- generic call / statement ----
    sm = re.match(r"shout\((.*)\)$", words)
    if sm:
        pass  # unreachable: matched above; keep for clarity
    txt = words
    fm = re.match(r"^(\w+)\s+((?:\\S+\\s+)*\\S+)$", txt)
    if fm and fm.group(1) in ("shout",):
        pass
    return Node("raw", text=convert_stmt(txt), line=ln), pos + 1


def convert_stmt(txt):
    """Handle statements like `unless x: shout(\"...{y}\")` tail fragments."""
    return convert_expr(txt)


def _attach_else(tokens, pos, indent):
    """Parse trailing elif-chain / else as `tail` nodes."""
    _, ln, text = tokens[pos]
    node, npos = parse_statement(tokens, pos, indent)
    return node, npos


# ---------------------------------------------------------------- codegen
class Emitter:
    def __init__(self):
        self.borrows = []
        self.funcs = []
        self.top = []
        self.tmp = 0

    def fresh(self, p="t"):
        self.tmp += 1
        return f"__cmm_{p}{self.tmp}"

    def stmts(self, body, ind):
        return "\n".join(self.stmt(n, ind) for n in body)

    def stmt(self, n, ind):
        I = "    " * ind
        k = n.kind
        if k == "borrow":
            if n.header not in self.borrows:
                self.borrows.append(n.header)
            return ""
        if k == "let":
            ctype = infer_type(n.raw_val)
            return f"{I}{ctype} {n.target} = {n.val};"
        if k == "assign":
            return f"{I}{n.target} = {n.val};"
        if k == "back":
            return f"{I}return {n.val};" if n.val else f"{I}return;"
        if k == "skip":
            return f"{I}continue;"
        if k == "halt":
            return f"{I}break;"
        if k == "call":
            return f"{I}{n.fn}({n.argstr});"
        if k == "raw":
            txt = n.text
            if txt.endswith(";"):
                txt = txt[:-1]
            return f"{I}{txt};"
        if k == "if":
            s = f"{I}if ({n.cond}) {{\n{self.stmts(n.body, ind+1)}\n{I}}}"
            if n.orelse:
                s += " else {\n" + self.stmts(n.orelse, ind+1) + f"\n{I}}}"
            return s
        if k == "ifchain":
            s = (f"{I}if ({n.head.cond}) {{\n"
                 f"{self.stmts(n.head.body, ind+1)}\n{I}}}")
            s += self.else_tail(n.tail, ind)
            return s
        if k == "while":
            return (f"{I}while ({n.cond}) {{\n"
                    f"{self.stmts(n.body, ind+1)}\n{I}}}")
        if k == "loop":
            v = n.var
            stop = getattr(n, "stop", None)
            cond = f"!({n.cond})"
            if stop:
                cond = f"!({v} > {stop}) && !({n.cond})"
            return (f"{I}for (long {v} = {n.start}; {cond}; {v}++) {{\n"
                    f"{self.stmts(n.body, ind+1)}\n{I}}}")
        if k == "pick":
            s = f"{I}switch ({n.subject}) {{\n"
            for vals, cbody in n.cases:
                for vv in vals:
                    s += f"{I}case {vv}:\n"
                s += self.stmts(cbody, ind + 1) + f"\n{I}break;\n"
            if n.default:
                s += f"{I}default:\n" + self.stmts(n.default, ind + 1) \
                     + f"\n{I}break;\n"
            s += f"{I}}}"
            return s
        if k == "func":
            raise AssertionError("func emitted at statement level")
        raise CmmError(getattr(n, "line", 0), f"cannot emit {k}")

    def else_tail(self, tail, ind):
        I = "    " * ind
        if tail is None:
            return ""
        if tail.kind == "else":
            return f" else {{\n{self.stmts(tail.body, ind+1)}\n{I}}}"
        if tail.kind == "elif":
            s = f" else if ({tail.cond}) {{\n" \
                f"{self.stmts(tail.body, ind+1)}\n{I}}}"
            s += self.else_tail(tail.tail, ind)
            return s
        raise CmmError(tail.line, "stray else-tail")


    def func_def(self, n):
        ret = TYPE_MAP.get(n.ret, n.ret)
        params = ", ".join(
            (TYPE_MAP.get(t, t) + " " + p).replace("const char* ",
                                                   "const char* ")
            for p, t in n.params) or "void"
        body = self.stmts(n.body, 1)
        return f"{ret} {n.name}({params}) {{\n{body}\n}}"

    def collect_decls(self, body, env):
        for n in body:
            k = n.kind
            if k == "let":
                env[n.target] = infer_type(n.raw_val)
            elif k in ("if", "ifchain", "while", "loop", "pick"):
                sub = []
                if k == "if":
                    sub = list(n.body) + list(n.orelse or [])
                elif k == "ifchain":
                    sub = list(n.head.body)
                elif k in ("while", "loop"):
                    sub = list(n.body)
                elif k == "pick":
                    for vals, cbody in n.cases:
                        sub += list(cbody)
                    if n.default:
                        sub += list(n.default)
                self.collect_decls(sub, env)

    def norm_header(self, h):
        return h if h.endswith(".h") or "/" in h else h + ".h"

    def resolve_interp(self, body, env):
        """Second pass: fill __FMT__ placeholders using declared types."""
        for n in body:
            k = n.kind
            if k == "call" and getattr(n, "interp", False):
                fmt, rest = n.argstr.split('"', 1)[0], None
                # argstr looks like: "<fmt>" , args...
                m = re.match(r'"((?:[^"\\]|\\.)*)"(.*)$', n.argstr)
                if m:
                    fmt = m.group(1)
                    idx = 0
                    def repl(mm):
                        nonlocal idx
                        t = env.get("__args__", {})
                        ty = n.argtypes[idx] if idx < len(n.argtypes) else "long"
                        idx += 1
                        return "%ld" if ty in ("long", "int") else (
                            "%g" if ty == "double" else "%s")
                    fmt = re.sub(r"__FMT__", repl, fmt)
                    n.argstr = '"%s"%s' % (fmt, m.group(2))
            elif k == "let":
                env[n.target] = infer_type(n.raw_val)
            elif k == "if":
                self.resolve_interp(n.body, env)
                if n.orelse:
                    self.resolve_interp(n.orelse, env)
            elif k == "ifchain":
                self.resolve_interp(n.head.body, env)
                tail = n.tail
                while tail is not None:
                    if tail.kind == "else":
                        self.resolve_interp(tail.body, env)
                        break
                    self.resolve_interp(tail.body, env)
                    tail = getattr(tail, "tail", None)
            elif k in ("while", "loop"):
                self.resolve_interp(n.body, env)
            elif k == "pick":
                for vals, cbody in n.cases:
                    self.resolve_interp(cbody, env)
                if n.default:
                    self.resolve_interp(n.default, env)

    def func_sig(self, n):
        ret = TYPE_MAP.get(n.ret, n.ret)
        params = ", ".join(f"{TYPE_MAP.get(t, t)} {p}"
                           for p, t in n.params) or "void"
        return f"{ret} {n.name}({params})"

    def emit(self, program):
        funcs = [n for n in program if n.kind == "func"]
        others = [n for n in program if n.kind != "func"]
        if not any(f.name == "main" for f in funcs):
            raise CmmError(0, "no `func main() -> num:` — "
                              "we chopped the entry point's alternatives")
        headers = ["stdio.h", "stdlib.h", "string.h"]
        for h in self.borrows:
            hh = self.norm_header(h)
            if hh not in headers:
                headers.append(hh)
        prelude = "\n".join(f"#include <{h}>" for h in headers)

        # per-function type environment incl. params; then resolve interp
        for f in funcs:
            env = {}
            for pname, ptype in f.params:
                env[pname] = TYPE_MAP.get(ptype, ptype)
            self.collect_decls(f.body, env)
            self.resolve_interp(f.body, env)

        out = [prelude, "",
               "/* Generated by the C-- compiler (v-4).",
               "   Semicolons were imported back under protest.",
               "   for-loops remain deleted. The board regrets nothing. */",
               ""]
        decls = [f"{self.func_sig(f)};" for f in reversed(funcs)]
        out.append("\n".join(decls))
        out.append("")
        for f in funcs:
            out.append(self.func_def(f))
            out.append("")
        return "\n".join(out)



def compile_c_to_c(source_text):
    tokens = tokenize(source_text)
    program, pos = parse_block(tokens, 0, 0)
    em = Emitter()
    # first pass borrows
    for n in program:
        if n.kind == "borrow":
            if n.header not in em.borrows:
                em.borrows.append(n.header)
    c_code = em.emit(program)
    return c_code


def main():
    ap = argparse.ArgumentParser(prog="ccmm", description=VERSION)
    ap.add_argument("input", help=".ccm source file")
    ap.add_argument("-o", "--output", default=None)
    ap.add_argument("--emit-c", action="store_true",
                    help="print generated C and exit")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--version", action="store_true")
    args = ap.parse_args()
    if args.version:
        print(VERSION)
        return
    src = open(args.input, encoding="utf-8").read()
    try:
        c_code = compile_c_to_c(src)
    except CmmError as e:
        print(f"c--: error: {e}", file=sys.stderr)
        sys.exit(1)
    if args.emit_c:
        print(c_code)
        return
    out = args.output or os.path.splitext(args.input)[0]
    with tempfile.NamedTemporaryFile("w", suffix=".c", delete=False,
                                     encoding="utf-8") as f:
        f.write(c_code)
        cfile = f.name
    cc = os.environ.get("CC", "cc")
    r = subprocess.run([cc, "-std=c11", "-w", cfile, "-o", out])
    os.unlink(cfile)
    if r.returncode != 0:
        print("c--: backend cc rejected our C. This is fine.",
              file=sys.stderr)
        sys.exit(r.returncode)
    if args.run:
        sys.exit(subprocess.run([out]).returncode)
    print(f"c--: compiled {args.input} -> {out}")


if __name__ == "__main__":
    main()
