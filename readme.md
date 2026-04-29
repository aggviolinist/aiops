## Create a new repository on the command line
1. touch README.md
2. git init
3. git add README.md
4. git commit -m "first commit"
5. git branch -M main
6. git remote add origin https://github.com/aggviolinist/aiops.git
7. git push -u origin main


## Push an existing repository from the command line
1. git remote add origin https://github.com/aggviolinist/aiops.git
2. git branch -M main
3. git push -u origin main
4. git remote set-url origin https://aggviolinist:tokenxxxxxxxxxxxxxxxx@github.com/aggviolinist/aiops.git

### If .env was already pushed, .gitignore alone won’t fix it.
### Run:
## git rm --cached .env
## git commit -m "Remove .env from tracking"

## Selecting the environment for python
1. python3 -m venv aiops-env
2. source aiops-env/bin/activate
3. pip install pandas
4. pip install scikit-learn
5. python3 aiops_log_analysis.py