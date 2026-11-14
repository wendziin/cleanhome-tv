#!/data/data/com.termux/files/usr/bin/bash
# Inicia o painel do CleanHome em http://IP_DO_CELULAR:8099
cd "$(dirname "$0")" || exit 1
exec python3 server.py "$@"
