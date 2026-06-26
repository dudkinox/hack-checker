# Python Screen Capture

Small command-line tool and Tkinter app for capturing screenshots. The Tkinter app can analyze an 8x8 checkers board from a selected screen region and update the recommended move in real time.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

Capture all monitors:

```bash
python screen_capture.py
```

Save to a specific file:

```bash
python screen_capture.py -o screenshots/desktop.png
```

Capture the primary monitor only:

```bash
python screen_capture.py --monitor 1
```

Capture every 5 seconds, 10 times:

```bash
python screen_capture.py -o screenshots --interval 5 --count 10
```

Run continuously until you stop it:

```bash
python screen_capture.py -o screenshots --interval 5 --count 0
```

On macOS, allow Terminal or your editor to record the screen in:
System Settings -> Privacy & Security -> Screen & System Audio Recording.

## Checkers Advisor Tkinter

Run the app:

```bash
./run_checkers_advisor.sh
```

Basic flow:

1. Click `เลือกพื้นที่หน้าจอ`.
2. Drag a square around the 8x8 board.
3. Release the mouse. Real-time analysis starts automatically.
4. Choose which side is yours: `ล่าง` or `บน`.
5. Choose your piece color, or keep `อัตโนมัติ`.

Use `หยุดเรียลไทม์` to pause, or `เริ่มเรียลไทม์` to resume with the same selected screen region. Use `จับภาพนิ่ง` or `เปิดภาพ` when you only want to analyze one still image.

The result image uses:

- Green circles for your pieces.
- Red circles for opponent pieces.
- Yellow ring and arrow for the recommended move.
- Blue square for the destination.
- Orange X marks for captured pieces.

If detection misses pieces, increase `ความไว`. If it marks empty squares as pieces, decrease it. You can also choose `สีเข้ม` or `สีอ่อน`, then analyze again.

If the result becomes black, make sure the app window is not covering the game board. The app will try to move itself away after selection, but you can still drag it elsewhere. On macOS, also allow Screen Recording for Terminal or your editor.
