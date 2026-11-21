"""Motor UCI mínimo para pruebas: emite info MultiPV realista.

No juega de verdad; siempre propone e2e4 (legal en la posición inicial,
que es la que usan los tests). Sirve para verificar que el panel acumula
varias líneas MultiPV y que la parada cooperativa funciona.
"""
import sys
import threading
import time

STATE = {"multipv": 1, "stop": threading.Event()}


def emit(line: str) -> None:
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def think(infinite: bool) -> None:
    depth = 1
    while not STATE["stop"].is_set():
        for rank in range(1, STATE["multipv"] + 1):
            emit(
                f"info depth {depth} seldepth {depth + 2} multipv {rank} "
                f"score cp {30 - rank * 7} nodes {depth * 1000} nps 50000 "
                f"pv e2e4 e7e5 g1f3 b8c6"
            )
        depth += 1
        if not infinite and depth > 6:
            break
        time.sleep(0.02)
    emit("bestmove e2e4")


def main() -> None:
    for raw in sys.stdin:
        line = raw.strip()
        if line == "uci":
            emit("id name FakeEngine 1.0")
            emit("id author Chess Games Manager Tests")
            emit("option name MultiPV type spin default 1 min 1 max 5")
            emit("uciok")
        elif line == "isready":
            emit("readyok")
        elif line.startswith("setoption"):
            parts = line.split()
            if "MultiPV" in parts:
                try:
                    STATE["multipv"] = int(parts[-1])
                except ValueError:
                    pass
        elif line.startswith("go"):
            STATE["stop"].clear()
            threading.Thread(target=think, args=("infinite" in line,), daemon=True).start()
        elif line == "stop":
            STATE["stop"].set()
        elif line == "quit":
            STATE["stop"].set()
            return


if __name__ == "__main__":
    main()
