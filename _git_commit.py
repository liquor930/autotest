"""git commit and verify"""
import subprocess, os

repo = r'D:\code\AutoTest'
log = []

def run(cmd):
    r = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, shell=True)
    return r.stdout + r.stderr

log.append("=== STATUS BEFORE ===")
log.append(run('git status --short'))

log.append("\n=== ADD + COMMIT ===")
run('git add -A')
log.append(run('git commit -m "chore: review reports, fix scripts, test artifacts"'))

log.append("\n=== PUSH ===")
log.append(run('git push'))

log.append("\n=== LOG ===")
log.append(run('git log --oneline -5'))

with open(r'D:\code\AutoTest\_git_done.txt', 'w') as f:
    f.write('\n'.join(log))

print("DONE")
