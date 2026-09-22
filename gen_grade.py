#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_grade.py — gera o scaffold do grade.py a partir dos <CommitPoint/> de um MDX.

Le um arquivo .mdx de aula, extrai os componentes <CommitPoint ... /> na ordem em
que aparecem, reproduz a MESMA numeracao do componente (incluindo as props `n` e
`prefix`) e escreve um grade.py com a lista TAREFAS ja montada: cada tarefa vem
com token, nome (a string `task`), pontos (prop `pontos`/`points`) e um bloco de
`checks` com um TODO para voce completar as verificacoes.

Uso:
    python gen_grade.py aula.mdx                 # imprime o grade.py no stdout
    python gen_grade.py aula.mdx -o grade.py     # grava em arquivo
    python gen_grade.py aula.mdx -o grade.py -f  # sobrescreve se existir
    python gen_grade.py aula.mdx --tarefas-only  # imprime apenas o bloco TAREFAS
    python gen_grade.py aula.mdx --default-points 10 --no-compile-check
    python scripts/gen_grade.py lab-docs/LAB03.mdx -o autograde/grade.py

    # modo verificacao (CI): compara um grade.py existente com o MDX
    python gen_grade.py aula.mdx --check autograde/grade.py
    python gen_grade.py aula.mdx --check autograde/grade.py --strict
    python scripts/gen_grade.py lab-docs/LAB03.mdx --check autograde/grade.py

Observacoes:
- A numeracao segue o componente: TODO CommitPoint consome um numero automatico;
  se a prop `n` estiver presente, ela define o numero exibido (mas o contador
  automatico ainda avanca), exatamente como no componente.
- O parser entende `task="..."`, `task='...'`, `pontos={15}`, `n={3}`,
  `prefix="T"`, `files="..."`, respeitando aspas/chaves (uma string de tarefa
  pode conter `>` ou `/>`).
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path


# --------------------------- extracao do MDX ---------------------------

def _read_quoted(text, i):
    """Le uma string entre aspas a partir de text[i] (que e a aspa). Retorna (valor, j)."""
    q = text[i]
    i += 1
    start = i
    n = len(text)
    while i < n and text[i] != q:
        if text[i] == "\\":
            i += 1
        i += 1
    return text[start:i], i + 1


def _read_braced(text, i):
    """Le uma expressao {...} balanceada a partir de text[i] (que e '{'). Retorna (interno, j)."""
    assert text[i] == "{"
    depth = 0
    start = i
    n = len(text)
    while i < n:
        c = text[i]
        if c in "\"'`":
            _, i = _read_quoted(text, i)
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1:i], i + 1
        i += 1
    return text[start + 1:], i


def parse_attrs(s):
    """Parseia a string de atributos de uma tag JSX. Retorna dict nome -> (tipo, valor)."""
    attrs = {}
    i, n = 0, len(s)
    while i < n:
        while i < n and s[i].isspace():
            i += 1
        m = re.match(r"[A-Za-z_][\w-]*", s[i:])
        if not m:
            break
        name = m.group(0)
        i += m.end()
        while i < n and s[i].isspace():
            i += 1
        if i < n and s[i] == "=":
            i += 1
            while i < n and s[i].isspace():
                i += 1
            if i < n and s[i] in "\"'":
                val, i = _read_quoted(s, i)
                attrs[name] = ("str", val)
            elif i < n and s[i] == "{":
                inner, i = _read_braced(s, i)
                attrs[name] = ("expr", inner.strip())
            else:
                m2 = re.match(r"\S+", s[i:])
                attrs[name] = ("bare", m2.group(0))
                i += m2.end()
        else:
            attrs[name] = ("bool", "true")
    return attrs


def find_commitpoints(text):
    """Acha cada <CommitPoint ...> em ordem e devolve a lista de dicts de atributos."""
    results = []
    for m in re.finditer(r"<CommitPoint\b", text):
        start = m.end()
        i, n = start, len(text)
        attr_str = None
        while i < n:
            c = text[i]
            if c in "\"'`":
                _, i = _read_quoted(text, i)
                continue
            if c == "{":
                _, i = _read_braced(text, i)
                continue
            if c == "/" and i + 1 < n and text[i + 1] == ">":
                attr_str = text[start:i]
                break
            if c == ">":
                attr_str = text[start:i]
                break
            i += 1
        if attr_str is not None:
            results.append(parse_attrs(attr_str))
    return results


# --------------------------- interpretacao dos valores ---------------------------

def as_string(entry):
    if entry is None:
        return None
    kind, val = entry
    if kind == "str":
        return val
    if kind == "expr":
        v = val.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'`":
            return v[1:-1]
        return v
    if kind == "bare":
        return val
    if kind == "bool":
        return True
    return None


def as_number(entry):
    s = as_string(entry)
    if s is None or s is True:
        return None
    try:
        return int(str(s).strip())
    except ValueError:
        try:
            return float(str(s).strip())
        except ValueError:
            return None


# --------------------------- montagem das tarefas ---------------------------

def build_tasks(cps, default_points):
    tasks = []
    counter = 0
    for attrs in cps:
        counter += 1                       # todo CommitPoint consome um numero automatico
        n_val = as_number(attrs.get("n"))
        numero = n_val if n_val is not None else counter
        prefix = as_string(attrs.get("prefix")) or "T"
        token = f"{prefix}{numero}"
        task = as_string(attrs.get("task")) or ""
        pontos = as_number(attrs.get("pontos"))
        if pontos is None:
            pontos = as_number(attrs.get("points"))
        pontos_definido = pontos is not None
        if pontos is None:
            pontos = default_points
        files = as_string(attrs.get("files")) or "."
        tasks.append({
            "token": token,
            "nome": task.strip(),
            "pontos": pontos,
            "pontos_definido": pontos_definido,
            "files": files,
        })
    return tasks


# --------------------------- geracao do codigo ---------------------------

def py_str(s):
    return json.dumps(s, ensure_ascii=False)


def render_tarefas(tasks, compile_check):
    linhas = ["TAREFAS = ["]
    for t in tasks:
        arq = t["files"].split()[0] if t["files"] and t["files"] != "." else "src/main.cpp"
        nota_pts = "" if t["pontos_definido"] else "  ·  pontos nao definidos no MDX (usando default)"
        linhas.append(f'  # {t["token"]} — arquivos: {t["files"]}{nota_pts}')
        linhas.append(
            f'  {{"token": {py_str(t["token"])}, "nome": {py_str(t["nome"])}, '
            f'"pontos": {t["pontos"]}, "checks": ['
        )
        linhas.append("      # TODO: defina as verificacoes desta tarefa")
        linhas.append(
            f'      # {{"tipo": "contem", "arquivo": {py_str(arq)}, '
            f'"padrao": r"...", "desc": "..."}},'
        )
        if compile_check:
            linhas.append('      {"tipo": "compila", "desc": "projeto compila"},')
        linhas.append("  ]},")
    linhas.append("]")
    return "\n".join(linhas)


ENGINE_HEADER = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Autograder gerado por gen_grade.py a partir dos <CommitPoint/> do MDX da aula.
Complete os `checks` de cada tarefa (as descricoes e pontos ja vieram do MDX).

Variaveis de ambiente:
    REPO_DIR  -> caminho do repo do grupo ja clonado (default ".")
    STUDENT   -> identificacao (ex.: "ORG/lab00-grupo-a"); so o final aparece.
"""
import os, re, subprocess, tempfile, shutil, pathlib

REPO = os.environ.get("REPO_DIR", ".")
STUDENT = os.environ.get("STUDENT", "grupo")
GROUP = STUDENT.rsplit("/", 1)[-1]

# =====================================================================
# Rubrica gerada automaticamente. Ajuste os `checks` conforme necessario.
# Tipos de verificacao: contem | nao_contem | compila
# =====================================================================
'''

ENGINE_BODY = '''
# =====================================================================


def sh(args, cwd=None):
    try:
        return subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    except FileNotFoundError:
        class R:
            returncode = 127; stdout = ""; stderr = f"{args[0]} nao encontrado"
        return R()


def git(args):
    return sh(["git", "-C", REPO] + args)


def commits():
    out = git(["log", "--format=%H%x1f%s"]).stdout.strip("\\n")
    res = []
    if out:
        for line in out.split("\\n"):
            h, _, s = line.partition("\\x1f")
            res.append((h, s))
    return res


ALL = commits()


def commit_da_tarefa(token):
    pat = re.compile(r"^\\s*" + re.escape(token) + r"\\b")
    for h, s in ALL:
        if pat.search(s):
            return h, s
    return None, None


def ler(arquivo, base):
    p = pathlib.Path(base) / arquivo
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return None


def roda_check(chk, base):
    t = chk["tipo"]
    if t == "contem":
        txt = ler(chk["arquivo"], base)
        return txt is not None and re.search(chk["padrao"], txt) is not None
    if t == "nao_contem":
        txt = ler(chk["arquivo"], base)
        return txt is not None and re.search(chk["padrao"], txt) is None
    if t == "compila":
        return sh(["pio", "run", "-d", base]).returncode == 0
    return False


def main():
    linhas, total, total_max = [], 0.0, 0
    for tar in TAREFAS:
        total_max += tar["pontos"]
        sha, subj = commit_da_tarefa(tar["token"])
        if not sha:
            linhas.append(f"| {tar['token']} — {tar['nome']} | :x: sem commit | 0 / {tar['pontos']} |")
            continue
        if not tar["checks"]:
            linhas.append(f"| {tar['token']} — {tar['nome']} | :warning: sem checks definidos | 0 / {tar['pontos']} |")
            continue
        tmp = tempfile.mkdtemp(prefix="wt-")
        add = git(["worktree", "add", "--detach", tmp, sha])
        if add.returncode != 0:
            shutil.rmtree(tmp, ignore_errors=True)
            linhas.append(f"| {tar['token']} — {tar['nome']} | :x: erro no checkout | 0 / {tar['pontos']} |")
            continue
        try:
            n = len(tar["checks"]); passou = 0; detalhes = []
            for chk in tar["checks"]:
                ok = roda_check(chk, tmp)
                passou += 1 if ok else 0
                detalhes.append(("[x] " if ok else "[ ] ") + chk["desc"])
            pts = round(tar["pontos"] * passou / n, 2)
            total += pts
            estado = "OK" if passou == n else ("PARCIAL" if passou else "FALHOU")
            linhas.append(f"| {tar['token']} — {tar['nome']} | **{estado}** `{sha[:7]}` \\"{subj[:32]}\\" | {pts} / {tar['pontos']} |")
            linhas.append(f"| | {' · '.join(detalhes)} | |")
        finally:
            git(["worktree", "remove", "--force", tmp])
            shutil.rmtree(tmp, ignore_errors=True)

    nota = round(10 * total / total_max, 2) if total_max else 0
    md = "\\n".join(
        [f"# Boletim — {GROUP}", "",
         f"**Nota: {nota} / 10**  ({total} de {total_max} pontos)", "",
         "| Tarefa | Situacao | Pontos |", "|---|---|---|"] + linhas) + "\\n"

    print(md)
    pathlib.Path("GRADE.md").write_text(md, encoding="utf-8")
    pathlib.Path("nota.csv").write_text(f"{GROUP},{nota},{total},{total_max}\\n", encoding="utf-8")

    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(md)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.write(f"nota={nota}\\n")


if __name__ == "__main__":
    main()
'''


def load_tarefas_from_py(path):
    """Le a lista TAREFAS de um grade.py SEM executar o modulo (ast.literal_eval)."""
    import ast
    tree = ast.parse(Path(path).read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        targets = []
        value = None
        if isinstance(node, ast.Assign):
            targets = node.targets
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
            value = node.value
        for tgt in targets:
            if isinstance(tgt, ast.Name) and tgt.id == "TAREFAS" and value is not None:
                try:
                    return ast.literal_eval(value)
                except Exception as e:  # noqa: BLE001
                    raise ValueError(f"nao consegui ler TAREFAS de {path}: {e}")
    raise ValueError(f"TAREFAS nao encontrado em {path}")


def check_divergences(mdx_tasks, py_tarefas):
    """Compara tarefas do MDX com as do grade.py. Retorna (erros, avisos)."""
    erros, avisos = [], []

    mdx_tokens = [t["token"] for t in mdx_tasks]
    py_tokens = [t.get("token", "") for t in py_tarefas]

    # duplicatas
    for nome_fonte, toks in (("MDX", mdx_tokens), ("grade.py", py_tokens)):
        dups = sorted({x for x in toks if toks.count(x) > 1})
        if dups:
            erros.append(f"tokens repetidos em {nome_fonte}: {', '.join(dups)}")

    mdx_by = {t["token"]: t for t in mdx_tasks}
    py_by = {t.get("token", ""): t for t in py_tarefas}

    # presenca
    for tok in mdx_tokens:
        if tok not in py_by:
            nome = mdx_by[tok]["nome"]
            erros.append(f"{tok} — presente no MDX (\"{nome}\") e ausente no grade.py")
    for tok in py_tokens:
        if tok not in mdx_by:
            erros.append(f"{tok} — presente no grade.py e ausente no MDX")

    # comparacoes por token compartilhado
    for tok in mdx_tokens:
        if tok not in py_by:
            continue
        mt, pt = mdx_by[tok], py_by[tok]

        # pontos (so quando o MDX define)
        if mt.get("pontos_definido"):
            if mt["pontos"] != pt.get("pontos"):
                erros.append(
                    f"{tok} — pontos divergentes: MDX={mt['pontos']} vs grade.py={pt.get('pontos')}"
                )

        # checks vazios
        checks = pt.get("checks") or []
        if len(checks) == 0:
            erros.append(f"{tok} — sem checks definidos no grade.py")

        # nome (aviso)
        nome_mdx = (mt.get("nome") or "").strip()
        nome_py = (pt.get("nome") or "").strip()
        if nome_mdx != nome_py:
            avisos.append(f"{tok} — nome difere: MDX=\"{nome_mdx}\" vs grade.py=\"{nome_py}\"")

    # ordem (aviso) — considerando so os tokens comuns
    comuns = set(mdx_tokens) & set(py_tokens)
    ordem_mdx = [t for t in mdx_tokens if t in comuns]
    ordem_py = [t for t in py_tokens if t in comuns]
    if ordem_mdx != ordem_py:
        avisos.append(f"ordem difere: MDX={ordem_mdx} vs grade.py={ordem_py}")

    return erros, avisos


def run_check(mdx_tasks, grade_path, strict):
    """Executa a comparacao e imprime o relatorio. Retorna o codigo de saida."""
    try:
        py_tarefas = load_tarefas_from_py(grade_path)
    except (FileNotFoundError, ValueError) as e:
        print(f"ERRO: {e}", file=sys.stderr)
        return 2

    erros, avisos = check_divergences(mdx_tasks, py_tarefas)

    linhas = []
    if erros:
        linhas.append(f"Erros ({len(erros)}):")
        linhas += [f"  ✗ {e}" for e in erros]
    if avisos:
        linhas.append(f"Avisos ({len(avisos)}):")
        linhas += [f"  ! {a}" for a in avisos]
    if not erros and not avisos:
        linhas.append("✓ grade.py e MDX estao sincronizados.")

    relatorio = "\n".join(linhas)
    print(relatorio, file=sys.stderr)

    # resumo para o GitHub Actions, se disponivel
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write("## Sincronizacao MDX × grade.py\n\n")
            f.write(("```\n" + relatorio + "\n```\n") if (erros or avisos) else "✓ Sincronizados.\n")

    if erros:
        return 1
    if avisos and strict:
        return 1
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Gera o scaffold do grade.py a partir dos <CommitPoint/> de um MDX.")
    ap.add_argument("mdx", help="arquivo .mdx da aula")
    ap.add_argument("-o", "--output", help="arquivo de saida (default: stdout)")
    ap.add_argument("-f", "--force", action="store_true", help="sobrescreve o arquivo de saida se existir")
    ap.add_argument("--tarefas-only", action="store_true", help="imprime apenas o bloco TAREFAS")
    ap.add_argument("--default-points", type=int, default=10, help="pontos quando o CommitPoint nao define (default: 10)")
    ap.add_argument("--no-compile-check", action="store_true", help="nao inclui o check 'compila' por padrao")
    ap.add_argument("--check", metavar="GRADE_PY", help="compara um grade.py existente com o MDX e reporta divergencias (nao gera nada)")
    ap.add_argument("--strict", action="store_true", help="em --check, faz avisos tambem falharem (exit != 0)")
    args = ap.parse_args(argv)

    src = Path(args.mdx)
    if not src.is_file():
        ap.error(f"arquivo nao encontrado: {src}")

    text = src.read_text(encoding="utf-8")
    cps = find_commitpoints(text)
    if not cps:
        print("Nenhum <CommitPoint/> encontrado no arquivo.", file=sys.stderr)
        return 1

    tasks = build_tasks(cps, args.default_points)

    # avisos uteis
    tokens = [t["token"] for t in tasks]
    dups = {tok for tok in tokens if tokens.count(tok) > 1}
    if dups:
        print(f"AVISO: tokens repetidos: {', '.join(sorted(dups))}", file=sys.stderr)
    sem_pts = [t["token"] for t in tasks if not t["pontos_definido"]]
    if sem_pts:
        print(f"AVISO: sem 'pontos' no MDX (usando {args.default_points}): {', '.join(sem_pts)}", file=sys.stderr)

    # resumo no stderr
    print(f"{len(tasks)} tarefa(s) extraida(s):", file=sys.stderr)
    for t in tasks:
        print(f"  {t['token']:>4}  {t['pontos']:>3} pts  {t['nome']}", file=sys.stderr)

    # modo comparacao: nao gera nada, apenas reporta divergencias
    if args.check:
        return run_check(tasks, args.check, args.strict)

    bloco = render_tarefas(tasks, compile_check=not args.no_compile_check)
    conteudo = bloco + "\n" if args.tarefas_only else ENGINE_HEADER + bloco + ENGINE_BODY

    if args.output:
        out = Path(args.output)
        if out.exists() and not args.force:
            ap.error(f"{out} ja existe (use -f para sobrescrever)")
        out.write_text(conteudo, encoding="utf-8")
        print(f"gravado: {out}", file=sys.stderr)
    else:
        sys.stdout.write(conteudo)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())