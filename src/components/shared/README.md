# docusaurus-shared-components
docusaurus-shared-components

## Add Remote

```bash
git remote add shared-components https://github.com/ruseleredu/docusaurus-shared-components.git
```

## Add Subtrees

```bash
git subtree add --prefix=src/components/shared shared-components main --squash
```

## List existing remotes

```bash
git remote -v
```

## Pull Updates

```bash
git subtree pull --prefix=src/components/shared shared-components main --squash
```

## Push Changes

```bash
git subtree push --prefix=src/components/shared shared-components main
```

## Reset all tracked files to match the latest commit:

```bash
git reset --hard HEAD
```
## Substituir totalmente o conteúdo do subtree pelo remoto sem merge


```bash
git rm -r src/components/shared
git commit -m "Remove local shared-components subtree"

git subtree add --prefix=src/components/shared shared-components main --squash
```

Se houver mais conflitos:

```bash
git checkout --theirs .
git add .
git commit -m "Accept subtree version"
```

## Remove remote

```bash
git remote remove shared-components
```

## Add another remote

```bash
git remote add shared-scripts https://github.com/ruseleredu/docusaurus-shared-scripts.git
```

---

