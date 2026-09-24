from pathlib import Path
import secrets, shutil
root=Path('/root/services/animation-pipeline')
var=root/'var';var.mkdir(exist_ok=True)
env=Path('/etc/animation-pipeline.env')
if not env.exists():
 token=secrets.token_urlsafe(36)
 env.write_text('ANIMATION_API_TOKEN='+token+'\nANIMATION_PAID_ENABLED=0\nANIMATION_MAX_STAGE_USD=0\n')
 env.chmod(0o600)
 access=root/'artifacts/owner-access.txt';access.write_text('Animation Werkstatt: https://huecki.com/animation/ui/\nAPI-Token (privat, nicht weitergeben):\n'+token+'\n');access.chmod(0o600)
unit=Path('/etc/systemd/system/animation-pipeline.service')
assert not unit.exists(), 'Review existing service before replacement'
unit.write_text('''[Unit]
Description=Animation Pipeline API
After=network.target
[Service]
Type=simple
WorkingDirectory=/root/services/animation-pipeline
EnvironmentFile=/etc/animation-pipeline.env
Environment=ANIMATION_DATA_DIR=/root/services/animation-pipeline/var
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=/root/services/animation-pipeline/.venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 4386 --workers 1 --no-access-log
Restart=on-failure
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/root/services/animation-pipeline/var
UMask=0077
[Install]
WantedBy=multi-user.target
''')
p=Path('/etc/nginx/sites-available/huecki.com');text=p.read_text()
assert 'location ^~ /animation/' not in text
backup=root/'deployment/nginx-before-ui.conf';shutil.copy2(p,backup)
anchor='    # Waldlicht isolated static game release.'
assert text.count(anchor)==1
block='''    location = /animation { return 302 /animation/ui/; }
    location = /animation/ { return 302 /animation/ui/; }
    location ^~ /animation/ {
        client_max_body_size 21m;
        proxy_pass http://127.0.0.1:4386/;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 60s;
        add_header X-Robots-Tag "noindex, nofollow" always;
        add_header Cache-Control "no-store" always;
    }

'''
p.write_text(text.replace(anchor,block+anchor))
print('Installed isolated service, private token and /animation/ route; paid calls disabled.')
