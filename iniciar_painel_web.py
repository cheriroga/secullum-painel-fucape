import sys
import webbrowser
from pathlib import Path

if sys.stdout is None or sys.stderr is None:
    # rodando via pythonw (sem console, ex.: .bat silencioso) — sys.stdout/stderr
    # ficam None e qualquer log (inclusive do uvicorn) derruba o processo na hora
    caminho_log = Path(__file__).resolve().parent / "webapp_data" / "servidor.log"
    caminho_log.parent.mkdir(parents=True, exist_ok=True)
    log = open(caminho_log, "a", encoding="utf-8")
    sys.stdout = log
    sys.stderr = log

import uvicorn

from webapp.main import iniciar_monitor_heartbeat

HOST = "127.0.0.1"
PORTA = 8000


def main() -> None:
    webbrowser.open(f"http://{HOST}:{PORTA}/")
    iniciar_monitor_heartbeat()
    uvicorn.run("webapp.main:app", host=HOST, port=PORTA)


if __name__ == "__main__":
    main()
