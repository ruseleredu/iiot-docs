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

    # modo correcao em lote: org + lab (+ grupos) definem tudo
    #   MDX:      labs/LAB03.mdx            (--labs-dir)
    #   rubrica:  autograde/lab03-grade.py  (--autograde-dir; gerada do MDX se nao existir)
    #   repos:    lab03-grupo-*             (--grupos a b  -> lab03-grupo-a, lab03-grupo-b)
    python scripts/gen_grade.py --corrigir MINHA-ORG --lab 3
    python scripts/gen_grade.py --corrigir MINHA-ORG --lab 3 --grupos a b --publicar nenhum
    python scripts/gen_grade.py --corrigir MINHA-ORG --lab 3 --publicar commit
    python scripts/gen_grade.py --lab 3 --check          # confere autograde/lab03-grade.py
    # autenticacao: GITHUB_TOKEN / GH_TOKEN, ou `gh auth token` se o gh CLI estiver logado

Observacoes:
- A numeracao segue o componente: TODO CommitPoint consome um numero automatico;
  se a prop `n` estiver presente, ela define o numero exibido (mas o contador
  automatico ainda avanca), exatamente como no componente.
- O parser entende `task="..."`, `task='...'`, `pontos={15}`, `n={3}`,
  `prefix="T"`, `files="..."`, respeitando aspas/chaves (uma string de tarefa
  pode conter `>` ou `/>`).
"""
import argparse
import base64
import csv
import datetime
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
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


MARCA_TODO = "# TODO: defina as verificacoes desta tarefa"


def arquivos_da_tarefa(files):
    """files="src/main.cpp, include/botao.h" -> ['src/main.cpp', 'include/botao.h'] ('.' = nenhum)."""
    vistos = []
    for f in re.split(r"[\s,;]+", files or ""):
        f = f.strip().replace("\\", "/")
        while f.startswith("./"):
            f = f[2:]
        if f and f not in (".", "/") and f not in vistos:
            vistos.append(f)
    return vistos


def render_tarefas(tasks, compile_check):
    linhas = ["TAREFAS = ["]
    for t in tasks:
        arquivos = arquivos_da_tarefa(t["files"])
        nota_pts = "" if t["pontos_definido"] else "  ·  pontos nao definidos no MDX (usando default)"
        linhas.append(f'  # {t["token"]} — arquivos: {t["files"]}{nota_pts}')
        linhas.append(
            f'  {{"token": {py_str(t["token"])}, "nome": {py_str(t["nome"])}, '
            f'"pontos": {t["pontos"]}, "checks": ['
        )
        linhas.append(f"      {MARCA_TODO}")
        if arquivos:
            # um `contem` por arquivo do `files`; r"\S" so exige que o arquivo exista e nao esteja vazio
            linhas.append('      # ajuste o "padrao" (regex) de cada arquivo; r"\\S" = existe e nao esta vazio')
            for arq in arquivos:
                linhas.append(
                    f'      {{"tipo": "contem", "arquivo": {py_str(arq)}, '
                    f'"padrao": r"\\S", "desc": {py_str(arq + " existe e nao esta vazio")}}},'
                )
        else:
            linhas.append(
                '      # {"tipo": "contem", "arquivo": "src/main.cpp", "padrao": r"...", "desc": "..."},'
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
        return subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
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
            linhas.append(f"| {tar['token']} — {tar['nome']} | **{estado}** `{sha[:7]}` \\"{subj[:32].replace('|', '/')}\\" | {pts} / {tar['pontos']} |")
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


# --------------------------- correcao em lote ---------------------------
#
# Fluxo: lista os repos do dono no GitHub -> filtra <lab>-grupo-X -> clona cada um
# (historico completo) -> roda o grade.py com REPO_DIR/STUDENT -> publica o boletim
# no proprio repo (issue ou commit) -> grava notas.csv e RESUMO.md consolidados.
#
# GITHUB_API_URL / GITHUB_SERVER_URL permitem apontar para um GitHub Enterprise.

def _api_url():
    return os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")


def _server_url():
    return os.environ.get("GITHUB_SERVER_URL", "https://github.com").rstrip("/")


class GitHubErro(Exception):
    def __init__(self, status, msg):
        super().__init__(f"HTTP {status}: {msg}")
        self.status = status


class GitHub:
    """Cliente minimo da API REST do GitHub (so biblioteca padrao)."""

    def __init__(self, token):
        self.token = token
        self.api = _api_url()

    def req(self, method, path, data=None, params=None):
        url = path if path.startswith("http") else self.api + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        body = json.dumps(data).encode("utf-8") if data is not None else None
        rq = urllib.request.Request(url, data=body, method=method)
        rq.add_header("Accept", "application/vnd.github+json")
        rq.add_header("X-GitHub-Api-Version", "2022-11-28")
        rq.add_header("User-Agent", "gen_grade.py")
        if self.token:
            rq.add_header("Authorization", f"Bearer {self.token}")
        if body is not None:
            rq.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(rq, timeout=60) as r:
                raw = r.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                msg = json.loads(raw).get("message", raw.decode("utf-8", "replace"))
            except Exception:  # noqa: BLE001
                msg = raw.decode("utf-8", "replace")
            raise GitHubErro(e.code, msg) from None
        except urllib.error.URLError as e:
            raise GitHubErro(0, f"falha de rede: {e.reason}") from None

    def paginar(self, path, params=None):
        params = dict(params or {})
        params["per_page"] = 100
        page = 1
        while True:
            params["page"] = page
            lote = self.req("GET", path, params=params) or []
            yield from lote
            if len(lote) < 100:
                return
            page += 1


def obter_token():
    for k in ("GITHUB_TOKEN", "GH_TOKEN"):
        if os.environ.get(k):
            return os.environ[k]
    try:
        r = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except FileNotFoundError:
        pass
    return None


def normalizar_lab(valor):
    """'3', '03', 'lab3', 'LAB03', 'lab-03' -> 'lab03'. Retorna None se nao houver numero."""
    m = re.search(r"(\d+)", str(valor))
    return f"lab{int(m.group(1)):02d}" if m else None


def inferir_lab(mdx_path):
    """labs/LAB03.mdx -> 'lab03'."""
    m = re.search(r"lab[-_ ]?(\d+)", Path(mdx_path).stem, re.IGNORECASE)
    return normalizar_lab(m.group(1)) if m else None


def achar_mdx(lab, labs_dir):
    """Acha o MDX do lab em labs_dir (ex.: lab03 -> labs/LAB03.mdx)."""
    pasta = Path(labs_dir)
    if not pasta.is_dir():
        raise ValueError(f"pasta de labs nao encontrada: {pasta} (use --labs-dir ou passe o MDX)")
    achados = sorted(p for p in pasta.glob("*.mdx") if inferir_lab(p) == lab)
    if not achados:
        raise ValueError(f"nenhum MDX de {lab} em {pasta} (esperado algo como {pasta / (lab.upper() + '.mdx')})")
    if len(achados) > 1:
        raise ValueError(f"mais de um MDX para {lab}: {', '.join(map(str, achados))}; passe o arquivo explicitamente")
    return achados[0]


def nomes_dos_grupos(lab, grupos):
    """['a', 'b', 'lab03-grupo-c'] -> ['lab03-grupo-a', 'lab03-grupo-b', 'lab03-grupo-c']."""
    if not grupos:
        return None
    return [g.lower() if g.lower().startswith(lab) else f"{lab}-grupo-{g.lower()}" for g in grupos]


def listar_repos(gh, dono):
    """Lista os repos de uma organizacao (ou, se nao for org, de um usuario)."""
    try:
        return list(gh.paginar(f"/orgs/{dono}/repos", {"type": "all"}))
    except GitHubErro as e:
        if e.status != 404:
            raise
    return list(gh.paginar(f"/users/{dono}/repos", {"type": "all"}))


def filtrar_repos(repos, lab, padrao, somente=None):
    """Mantem os repos cujo nome casa com o padrao (ex.: lab03-grupo-8), ordenados pelo numero."""
    rx = re.compile("^" + padrao.replace("{lab}", re.escape(lab)) + "$", re.IGNORECASE)
    sel, ignorados = [], []
    for r in repos:
        nome = r["name"]
        if somente and nome.lower() not in somente:
            continue
        if not rx.match(nome):
            continue
        if r.get("archived"):
            ignorados.append(nome)
            continue
        sel.append(r)

    def chave(r):
        # grupo-2 < grupo-10 (numerico); grupo-a < grupo-b (alfabetico); numeros antes de letras
        suf = re.split(r"[-_]", r["name"])[-1].lower()
        return (0, int(suf), "") if suf.isdigit() else (1, 0, suf)

    return sorted(sel, key=chave), ignorados


def _git_env(token):
    """Ambiente do git com o token passado via GIT_CONFIG_* (nao aparece no `ps`
    nem fica gravado no .git/config do clone)."""
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    base = _server_url()
    if token and base.startswith("http"):
        cred = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        env["GIT_CONFIG_COUNT"] = "1"
        env["GIT_CONFIG_KEY_0"] = f"http.{base}/.extraheader"
        env["GIT_CONFIG_VALUE_0"] = f"AUTHORIZATION: basic {cred}"
    return env


def _rmtree(path):
    """rmtree que funciona no Windows: o git grava .git/objects/pack/* como
    somente-leitura, e o shutil.rmtree padrao falha com 'Acesso negado'."""
    def _forcar(func, p, _exc):
        try:
            os.chmod(p, stat.S_IWRITE | stat.S_IREAD)
            func(p)
        except FileNotFoundError:
            pass

    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_forcar)
    else:
        shutil.rmtree(path, onerror=_forcar)


def _run(args, cwd=None, env=None, timeout=None):
    try:
        return subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(args, 124, "", f"tempo esgotado ({timeout}s)")
    except FileNotFoundError:
        return subprocess.CompletedProcess(args, 127, "", f"{args[0]} nao encontrado")


def clonar(dono, nome, destino, env):
    if destino.exists():
        try:
            _rmtree(destino)
        except OSError as e:
            return subprocess.CompletedProcess(
                [], 1, "", f"nao consegui apagar o clone anterior ({e}); "
                           "feche programas com a pasta aberta (VS Code, Explorer) e rode de novo")
    destino.parent.mkdir(parents=True, exist_ok=True)
    url = f"{_server_url()}/{dono}/{nome}.git"
    return _run(["git", "clone", "--quiet", url, str(destino)], env=env)


# variaveis que NAO devem chegar ao grade.py: o check `compila` executa o build do
# aluno (scripts do PlatformIO sao Python arbitrario), entao nada de tokens/segredos.
_ENV_BLOQUEADO = re.compile(r"TOKEN|SECRET|PASSWORD|^GIT_CONFIG_|^ACTIONS_|^GITHUB_(OUTPUT|STEP_SUMMARY|ENV|PATH)$", re.I)


def rodar_grade(grade_py, repo_dir, student, saida, timeout):
    saida.mkdir(parents=True, exist_ok=True)
    for f in ("GRADE.md", "nota.csv"):
        (saida / f).unlink(missing_ok=True)
    env = {k: v for k, v in os.environ.items() if not _ENV_BLOQUEADO.search(k)}
    env.update(REPO_DIR=str(repo_dir.resolve()), STUDENT=student,
               PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    r = _run([sys.executable, str(Path(grade_py).resolve())], cwd=saida, env=env, timeout=timeout)
    md_p, csv_p = saida / "GRADE.md", saida / "nota.csv"
    if r.returncode != 0 or not md_p.exists() or not csv_p.exists():
        erro = (r.stderr or r.stdout or "").strip().splitlines()[-1:] or ["sem saida"]
        return None, None, f"grade.py falhou (exit {r.returncode}): {erro[0]}"
    linha = next(csv.reader([csv_p.read_text(encoding="utf-8").strip()]))
    nota = {"nota": float(linha[1]), "total": float(linha[2]), "total_max": float(linha[3])}
    return md_p.read_text(encoding="utf-8"), nota, None


def _rodape(head):
    agora = datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    return f"\n---\n<sub>Gerado automaticamente por gen_grade.py em {agora} · HEAD `{head[:7]}`</sub>\n"


def publicar_issue(gh, dono, nome, lab, md, nota, head):
    """Cria (ou atualiza) a issue 'Autograde — <lab>' com o boletim.
    Em reexecucoes o corpo e atualizado e um comentario curto notifica o grupo."""
    titulo = f"Autograde — {lab}"
    corpo = md + _rodape(head)
    base = f"/repos/{dono}/{nome}/issues"
    existente = next(
        (i for i in gh.paginar(base, {"state": "open"})
         if "pull_request" not in i and i.get("title") == titulo),
        None,
    )
    if existente is None:
        return gh.req("POST", base, {"title": titulo, "body": corpo})["html_url"]
    num = existente["number"]
    gh.req("PATCH", f"{base}/{num}", {"body": corpo})
    gh.req("POST", f"{base}/{num}/comments",
           {"body": f"Boletim atualizado: **{nota['nota']} / 10** (HEAD `{head[:7]}`). Veja a descricao da issue."})
    return existente["html_url"]


def publicar_commit(clone, arquivo, md, lab, env):
    """Grava o boletim no repo do grupo, commita e faz push no branch padrao."""
    alvo = clone / arquivo
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(md, encoding="utf-8")
    g = ["git", "-C", str(clone)]
    _run(g + ["add", "--", arquivo], env=env)
    if _run(g + ["diff", "--cached", "--quiet"], env=env).returncode == 0:
        return "sem mudancas (boletim igual ao anterior)"
    c = _run(g + ["-c", "user.name=autograde", "-c", "user.email=autograde@users.noreply.github.com",
                  "commit", "--quiet", "-m", f"autograde: boletim {lab} [skip ci]"], env=env)
    if c.returncode != 0:
        raise RuntimeError(f"commit falhou: {c.stderr.strip()}")
    p = _run(g + ["push", "--quiet", "origin", "HEAD"], env=env)
    if p.returncode != 0:
        raise RuntimeError(f"push falhou: {p.stderr.strip()}")
    return f"commit em {arquivo}"


def escapar_mdx(texto):
    """Escapa o que o MDX interpretaria como JSX/expressao ({ } <) fora de `codigo inline`.
    Necessario porque mensagens de commit dos alunos aparecem nos boletins."""
    partes = re.split(r"(`[^`\n]*`)", texto)
    for i in range(0, len(partes), 2):
        partes[i] = partes[i].replace("{", "\\{").replace("}", "\\}").replace("<", "&lt;")
    return "".join(partes)


def gerar_mdx_geral(caminho, lab, dono, resumo_md, resultados, work):
    """Junta RESUMO.md (#) com o GRADE.md de cada grupo (##) num MDX de rascunho do Docusaurus."""
    agora = datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    out = [
        "---",
        f"title: Notas — {lab}",
        f"sidebar_label: Notas {lab}",
        f"description: Resultado do autograde de {lab} ({dono}).",
        "draft: true",
        "---",
        "",
        f":::info[Rascunho]\nGerado por gen_grade.py em {agora}. Com `draft: true`, esta pagina "
        "aparece em `npm start` mas nao entra no build de producao.\n:::",
        "",
        escapar_mdx(resumo_md).rstrip(),
        "",
    ]
    for x in resultados:
        nome = x["repo"]
        grade = work / "boletins" / nome / "GRADE.md"
        if x["nota"] != "" and grade.exists():
            linhas = escapar_mdx(grade.read_text(encoding="utf-8")).rstrip().splitlines()
            # rebaixa um nivel todos os titulos: '# Boletim' -> '## Boletim'
            linhas = [("#" + l) if re.match(r"#{1,5}\s", l) else l for l in linhas]
            if x["link"]:
                linhas.insert(1, f"\n[ver no repositorio]({x['link']})")
            out += linhas + [""]
        else:
            out += [f"## Boletim — {nome}", "", f":::danger\n{escapar_mdx(x['status'])}\n:::", ""]
    Path(caminho).parent.mkdir(parents=True, exist_ok=True)
    Path(caminho).write_text("\n".join(out), encoding="utf-8")


def corrigir_lote(args, tasks):
    lab = args.lab
    grade_py = Path(args.grade)

    # 0) sem grade.py: gera o scaffold a partir do MDX (mesmas opcoes do modo gerador)
    if not grade_py.exists():
        bloco = render_tarefas(tasks, compile_check=not args.no_compile_check)
        grade_py.parent.mkdir(parents=True, exist_ok=True)
        grade_py.write_text(ENGINE_HEADER + bloco + ENGINE_BODY, encoding="utf-8")
        print(f"AVISO: {grade_py} nao existia; gerado a partir de {args.mdx}.", file=sys.stderr)

    # 1) a rubrica precisa estar sincronizada com o MDX antes de corrigir alguem
    try:
        erros, avisos = check_divergences(tasks, load_tarefas_from_py(grade_py))
    except (FileNotFoundError, ValueError) as e:
        print(f"ERRO: {e}", file=sys.stderr)
        return 2
    for a in avisos:
        print(f"  ! {a}", file=sys.stderr)
    if erros:
        for e in erros:
            print(f"  ✗ {e}", file=sys.stderr)
        if not args.forcar:
            print("ERRO: grade.py divergente do MDX; corrija ou use --forcar.", file=sys.stderr)
            return 1

    # rubrica com TODO: corrige para teste, mas nao publica notas para os alunos
    if MARCA_TODO in grade_py.read_text(encoding="utf-8"):
        if args.publicar != "nenhum" and not args.forcar:
            print(f"ERRO: {grade_py} ainda tem checks TODO; nada sera publicado.\n"
                  f"      Complete os checks e apague as linhas '{MARCA_TODO}',\n"
                  "      ou rode com --publicar nenhum para testar.", file=sys.stderr)
            return 1
        print(f"AVISO: {grade_py} ainda tem checks TODO; as notas refletem so os checks ja definidos "
              "(na rubrica gerada: arquivos do `files` existirem" + ("" if args.no_compile_check else " + 'compila'")
              + ").", file=sys.stderr)

    # 2) descoberta dos repositorios
    token = obter_token()
    if not token:
        print("AVISO: sem GITHUB_TOKEN/GH_TOKEN nem `gh auth`; so repos publicos serao vistos "
              "e nada podera ser publicado.", file=sys.stderr)
    gh = GitHub(token)
    try:
        somente = nomes_dos_grupos(lab, args.grupos)
        repos, arquivados = filtrar_repos(listar_repos(gh, args.corrigir), lab, args.padrao_repo, somente)
    except GitHubErro as e:
        print(f"ERRO ao listar repos de {args.corrigir}: {e}", file=sys.stderr)
        return 2
    if arquivados:
        print(f"ignorados (arquivados): {', '.join(arquivados)}", file=sys.stderr)
    if somente:
        faltando = sorted(set(somente) - {r["name"].lower() for r in repos} - {a.lower() for a in arquivados})
        if faltando:
            print(f"AVISO: nao encontrados em {args.corrigir}: {', '.join(faltando)}", file=sys.stderr)
    if not repos:
        print(f"Nenhum repo de {args.corrigir} casa com '{args.padrao_repo.replace('{lab}', lab)}'.", file=sys.stderr)
        return 1
    print(f"\n{len(repos)} repo(s) de {lab} para corrigir (publicar: {args.publicar})", file=sys.stderr)

    work = Path(args.workdir or Path("_autograde") / lab)
    env_git = _git_env(token)
    resultados = []

    # 3) corrige um por um
    for r in repos:
        nome = r["name"]
        res = {"repo": nome, "nota": "", "total": "", "total_max": "", "status": "", "link": ""}
        resultados.append(res)
        print(f"\n▸ {nome}", file=sys.stderr)

        clone = work / "repos" / nome
        c = clonar(args.corrigir, nome, clone, env_git)
        if c.returncode != 0:
            res["status"] = f"erro no clone: {c.stderr.strip()[:200]}"
            print(f"  ✗ {res['status']}", file=sys.stderr)
            continue
        head = _run(["git", "-C", str(clone), "rev-parse", "HEAD"]).stdout.strip() or "0000000"

        md, nota, erro = rodar_grade(grade_py, clone, f"{args.corrigir}/{nome}", work / "boletins" / nome, args.timeout)
        if erro:
            res["status"] = erro
            print(f"  ✗ {erro}", file=sys.stderr)
            continue
        res.update(nota)
        print(f"  nota {nota['nota']} / 10  ({nota['total']} de {nota['total_max']} pts)", file=sys.stderr)

        try:
            if args.publicar == "issue":
                res["link"] = publicar_issue(gh, args.corrigir, nome, lab, md, nota, head)
                res["status"] = "publicado (issue)"
            elif args.publicar == "commit":
                res["status"] = publicar_commit(clone, args.arquivo_boletim, md, lab, env_git)
                res["link"] = f"{_server_url()}/{args.corrigir}/{nome}/blob/HEAD/{args.arquivo_boletim}"
            else:
                res["status"] = "corrigido (nao publicado)"
            print(f"  ✓ {res['status']} {res['link']}".rstrip(), file=sys.stderr)
        except (GitHubErro, RuntimeError) as e:
            res["status"] = f"corrigido, mas falhou ao publicar: {e}"
            print(f"  ✗ {res['status']}", file=sys.stderr)

    # 4) consolidado
    for x in resultados:
        x["status"] = re.sub(r"\s+", " ", x["status"]).replace("|", "/").strip()
    work.mkdir(parents=True, exist_ok=True)
    campos = ["repo", "nota", "total", "total_max", "status", "link"]
    with open(work / "notas.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(resultados)

    linhas = [f"# Autograde — {lab} ({args.corrigir})", "",
              "| Repo | Nota | Pontos | Situacao |", "|---|---|---|---|"]
    for x in resultados:
        repo_md = f"[{x['repo']}]({x['link']})" if x["link"] else x["repo"]
        pts = f"{x['total']} / {x['total_max']}" if x["total_max"] != "" else "—"
        nota_txt = x["nota"] if x["nota"] != "" else "—"
        linhas.append(f"| {repo_md} | {nota_txt} | {pts} | {x['status']} |")
    resumo = "\n".join(linhas) + "\n"
    (work / "RESUMO.md").write_text(resumo, encoding="utf-8")
    mdx_geral = Path(args.mdx_geral or work / f"{lab}-notas.mdx")
    gerar_mdx_geral(mdx_geral, lab, args.corrigir, resumo, resultados, work)
    print(f"rascunho MDX: {mdx_geral}", file=sys.stderr)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(resumo)

    falhas = [x for x in resultados if x["nota"] == "" or "falhou" in x["status"]]
    print(f"\n{len(resultados) - len(falhas)}/{len(resultados)} ok · consolidado em {work / 'notas.csv'} e {work / 'RESUMO.md'}",
          file=sys.stderr)
    return 1 if falhas else 0


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description="Gera o scaffold do grade.py a partir dos <CommitPoint/> de um MDX.")
    ap.add_argument("mdx", nargs="?", help="arquivo .mdx da aula (opcional com --lab: procura em --labs-dir)")
    ap.add_argument("--lab", help="numero do lab: 3, 03, lab3 ou lab03 (default: inferido do nome do MDX)")
    ap.add_argument("--labs-dir", default="labs", help="pasta dos MDX dos labs (default: labs)")
    ap.add_argument("--autograde-dir", default="autograde",
                    help="pasta dos grade.py por lab: <dir>/<lab>-grade.py (default: autograde)")
    ap.add_argument("-o", "--output", help="arquivo de saida (default: stdout)")
    ap.add_argument("-f", "--force", action="store_true", help="sobrescreve o arquivo de saida se existir")
    ap.add_argument("--tarefas-only", action="store_true", help="imprime apenas o bloco TAREFAS")
    ap.add_argument("--default-points", type=int, default=10, help="pontos quando o CommitPoint nao define (default: 10)")
    ap.add_argument("--no-compile-check", action="store_true", help="nao inclui o check 'compila' por padrao")
    ap.add_argument("--check", metavar="GRADE_PY", nargs="?", const="",
                    help="compara um grade.py com o MDX e reporta divergencias (nao gera nada); "
                         "sem valor usa <autograde-dir>/<lab>-grade.py")
    ap.add_argument("--strict", action="store_true", help="em --check, faz avisos tambem falharem (exit != 0)")

    lote = ap.add_argument_group("correcao em lote (--corrigir)")
    lote.add_argument("--corrigir", metavar="DONO",
                      help="org (ou usuario) do GitHub: clona todos os repos <lab>-grupo-X, corrige e publica")
    lote.add_argument("--grade", help="grade.py usado na correcao (default: <autograde-dir>/<lab>-grade.py, "
                                      "gerado a partir do MDX se nao existir)")
    lote.add_argument("--padrao-repo", default=r"{lab}-grupo-[a-z0-9]+",
                      help=r"regex do nome do repo; {lab} e substituido (default: '{lab}-grupo-[a-z0-9]+')")
    lote.add_argument("--grupos", "--repos", dest="grupos", nargs="+", metavar="GRUPO",
                      help="corrige so estes grupos: letras (a b) ou nomes completos (lab03-grupo-a)")
    lote.add_argument("--publicar", choices=["issue", "commit", "nenhum"], default="issue",
                      help="onde postar o boletim no repo do grupo (default: issue)")
    lote.add_argument("--arquivo-boletim", default="GRADE.md",
                      help="caminho do boletim no repo, com --publicar commit (default: GRADE.md)")
    lote.add_argument("--workdir", help="pasta dos clones e resultados (default: _autograde/<lab>)")
    lote.add_argument("--mdx-geral", metavar="ARQ",
                      help="MDX de rascunho (Docusaurus) juntando RESUMO + boletins (default: <workdir>/<lab>-notas.mdx)")
    lote.add_argument("--timeout", type=int, default=900, help="tempo maximo do grade.py por repo, em s (default: 900)")
    lote.add_argument("--forcar", action="store_true", help="corrige mesmo se o grade.py divergir do MDX")
    args = ap.parse_args(argv)
    if args.check is not None and args.corrigir:
        ap.error("use --check ou --corrigir, nao os dois")

    # lab + MDX: um define o outro
    if args.lab:
        args.lab = normalizar_lab(args.lab)
        if not args.lab:
            ap.error("--lab precisa conter um numero (ex.: 3, 03, lab03)")
    elif args.mdx:
        args.lab = inferir_lab(args.mdx)
    if args.mdx:
        src = Path(args.mdx)
        if not src.is_file():
            ap.error(f"arquivo nao encontrado: {src}")
    elif args.lab:
        try:
            src = achar_mdx(args.lab, args.labs_dir)
        except ValueError as e:
            ap.error(str(e))
        args.mdx = str(src)
    else:
        ap.error("informe o MDX da aula ou --lab")

    # grade.py por lab: autograde/lab03-grade.py
    grade_padrao = Path(args.autograde_dir) / f"{args.lab}-grade.py" if args.lab else None
    if args.check == "" or (args.corrigir and not args.grade):
        if grade_padrao is None:
            ap.error("nao consegui inferir o lab pelo nome do MDX; use --lab")
        if args.check == "":
            args.check = str(grade_padrao)
        else:
            args.grade = str(grade_padrao)
    if args.lab:
        print(f"{args.lab}: {src}", file=sys.stderr)

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
    if args.check is not None:
        return run_check(tasks, args.check, args.strict)

    # modo correcao em lote
    if args.corrigir:
        return corrigir_lote(args, tasks)

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