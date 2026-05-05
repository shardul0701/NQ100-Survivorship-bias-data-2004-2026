# Push this repo to GitHub

Create an empty GitHub repo first, for example:

```text
nasdaq100-point-in-time-universe
```

Then run these commands from the unzipped folder:

```bash
git init
git add .
git commit -m "Add point-in-time Nasdaq-100 universe files from 2004 to 2026"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/nasdaq100-point-in-time-universe.git
git push -u origin main
```

If Git says the remote already exists:

```bash
git remote set-url origin https://github.com/YOUR_USERNAME/nasdaq100-point-in-time-universe.git
git push -u origin main
```
