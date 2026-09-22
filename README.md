# docusaurus-shared-scripts

docusaurus-shared-scripts

## Add Remote

```bash
git remote add shared-scripts https://github.com/ruseleredu/docusaurus-shared-scripts.git
```

## Add Subtrees

```bash
git subtree add --prefix=scripts shared-scripts main --squash
```

## List existing remotes

```bash
git remote -v
```

## Pull Updates

```bash
git subtree pull --prefix=scripts shared-scripts main --squash
```

## Push Changes

```bash
git subtree push --prefix=scripts shared-scripts main
```

## List existing remotes

```bash
git remote remove shared-scripts
```

## Add another remote

```bash
git remote add shared-components https://github.com/ruseleredu/docusaurus-shared-components.git
```

---

# Scripts

```bash
node scripts/generate-emojis.js
```

```bash
node scripts/download-katex.js
```
