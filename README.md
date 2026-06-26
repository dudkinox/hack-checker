# Python Screen Capture

Small command-line tool and Tkinter app for capturing screenshots. The Tkinter app can help analyze an 8x8 checkers board from a screenshot and draw a recommended move.

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
python checkers_advisor_tk.py
```

Basic flow:

1. Click `จับหน้าจอ` or `เปิดภาพ`.
2. Drag a square around the 8x8 board.
3. Choose which side is yours: `ล่าง` or `บน`.
4. Choose your piece color, or keep `อัตโนมัติ`.
5. Click `วิเคราะห์`.

The result image uses:

- Green circles for your pieces.
- Red circles for opponent pieces.
- Yellow ring and arrow for the recommended move.
- Blue square for the destination.
- Orange X marks for captured pieces.

If detection misses pieces, increase `ความไว`. If it marks empty squares as pieces, decrease it. You can also choose `สีเข้ม` or `สีอ่อน`, then analyze again.
