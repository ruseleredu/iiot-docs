#!/usr/bin/env python3
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
TAREFAS = [
  # T1 — arquivos: .
  {"token": "T1", "nome": "pio project init", "pontos": 5, "checks": [
      # TODO: defina as verificacoes desta tarefa
      # {"tipo": "contem", "arquivo": "src/main.cpp", "padrao": r"...", "desc": "..."},
      {"tipo": "compila", "desc": "projeto compila"},
  ]},
]
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
    out = git(["log", "--format=%H%x1f%s"]).stdout.strip("\n")
    res = []
    if out:
        for line in out.split("\n"):
            h, _, s = line.partition("\x1f")
            res.append((h, s))
    return res


ALL = commits()


def commit_da_tarefa(token):
    pat = re.compile(r"^\s*" + re.escape(token) + r"\b")
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
            linhas.append(f"| {tar['token']} — {tar['nome']} | **{estado}** `{sha[:7]}` \"{subj[:32]}\" | {pts} / {tar['pontos']} |")
            linhas.append(f"| | {' · '.join(detalhes)} | |")
        finally:
            git(["worktree", "remove", "--force", tmp])
            shutil.rmtree(tmp, ignore_errors=True)

    nota = round(10 * total / total_max, 2) if total_max else 0
    md = "\n".join(
        [f"# Boletim — {GROUP}", "",
         f"**Nota: {nota} / 10**  ({total} de {total_max} pontos)", "",
         "| Tarefa | Situacao | Pontos |", "|---|---|---|"] + linhas) + "\n"

    print(md)
    pathlib.Path("GRADE.md").write_text(md, encoding="utf-8")
    pathlib.Path("nota.csv").write_text(f"{GROUP},{nota},{total},{total_max}\n", encoding="utf-8")

    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(md)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.write(f"nota={nota}\n")


if __name__ == "__main__":
    main()
