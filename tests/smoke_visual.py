"""Smoke test visual de la segunda ronda: piezas SVG, comentarios con formato,
explorador en modo rival y motor Stockfish con posición fijada.
"""
import sys
import time
from pathlib import Path

from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from chessstudio.main_window import MainWindow

OUT = Path(__file__).resolve().parent.parent / "capturas"
OUT.mkdir(exist_ok=True)

DEMO_PGN = """[Event "Demostración"]
[Site "https://lichess.org/demo1234"]
[Date "2026.03.10"]
[White "Anna"]
[Black "Boris"]
[Result "1-0"]
[ECO "C50"]

1. e4 { [%eval 0.32] [%clk 0:03:00] [%cal Ge2e4,Gd2d4] [%csl Yf5] La mejor. }
1... e5 { [%eval 0.28] [%clk 0:02:58] [%cal Re7e5] } 2. Nf3 $1 { [%eval 0.35] [%clk 0:02:55] Desarrollo natural. }
2... Nc6 { [%eval 0.30] [%clk 0:02:50] } 3. Bb5 { [%cal Gf1b5] La Española. }
(3. Bc4 { [%eval 0.20] La Italiana. } 3... Bc5) 3... a6 $6 { [%eval 0.55] [%clk 0:02:40] Mejor 3...Nf6. }
4. Ba4 { [%eval 0.60] } 1-0
"""


def pump(app, seconds=0.2):
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def wait_for(app, predicate, timeout=20):
    end = time.time() + timeout
    while time.time() < end:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    return False


def make_rival_pgn(path, n=120):
    lines = []
    openings = ["1. d4 d5 2. c4 e6", "1. e4 c5 2. Nf3 d6", "1. Nf3 d5 2. d4 Nf6"]
    for i in range(n):
        white = "Magnus Carlsen" if i % 2 == 0 else f"Rival{i}"
        black = "Magnus Carlsen" if i % 2 == 1 else f"Oponente{i}"
        lines.append(
            f'[Event "Tata Steel {i}"]\n[White "{white}"]\n[Black "{black}"]\n'
            f'[Result "1-0"]\n[Date "2026.01.{(i % 28) + 1:02d}"]\n[ECO "D35"]\n\n'
            f'{openings[i % 3]} 1-0\n'
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.resize(1380, 880)
    window.show()
    pump(app, 0.3)

    # Base aislada para la demostración (no hereda db/last de otros usos).
    demo_db = OUT / "demo.csdb"
    demo_db.unlink(missing_ok=True)
    window.open_database(demo_db, quiet=True)

    # Partida con flechas y comentarios enriquecidos.
    demo = OUT / "demo.pgn"
    demo.write_text(DEMO_PGN, encoding="utf-8")
    window.db.import_pgn(demo)
    window.refresh_game_list()
    row = window.db.search(limit=1)[0]
    window._open_game_by_id(row.id)
    gw = window.current_game_window()
    gw.doc.goto_next()  # 1. e4
    pump(app, 0.3)

    # Preparar rival -> el explorador queda en modo "Solo rival".
    rival_pgn = OUT / "rival_demo.pgn"
    make_rival_pgn(rival_pgn, 120)
    prep = window.opponent_prep
    prep._start_import(rival_pgn)
    wait_for(app, lambda: prep._prep_db is not None and prep._thread is None)
    window.prep_dock.raise_()
    pump(app, 0.3)
    window.grab().save(str(OUT / "1_piezas_comentarios_rival.png"))
    print("Captura 1: piezas SVG + comentarios con formato + explorador modo rival")

    # Motor Stockfish (si está disponible) con posición fijada.
    stockfish = Path("/usr/games/stockfish")
    if stockfish.exists():
        window.engine_panel.engine_combo.setCurrentText(str(stockfish))
        window.engine_dock.raise_()
        window.engine_panel.start_button.setChecked(True)
        window.engine_panel._toggle(True)
        pump(app, 2.0)
        window.engine_panel.lock_button.setChecked(True)
        window.engine_panel._toggle_lock(True)
        pump(app, 1.0)
        window.grab().save(str(OUT / "2_motor_fijado.png"))
        print("Captura 2: Stockfish analizando con posición fijada")
        window.engine_panel.shutdown()

    window.opponent_prep.shutdown()
    window.close()
    print("SMOKE OK")


if __name__ == "__main__":
    main()
