import webbrowser

import uvicorn

HOST = "127.0.0.1"
PORTA = 8000


def main() -> None:
    webbrowser.open(f"http://{HOST}:{PORTA}/")
    uvicorn.run("webapp.main:app", host=HOST, port=PORTA)


if __name__ == "__main__":
    main()
