"""
Standalone TSPL sender — called by agent.py via subprocess.
This avoids Flask threading issues with win32print.

Usage: python tspl_sender.py <printer_name> <tspl_file_path>
"""
import sys
import os

def send_win32print(printer_name, tspl_bytes):
    """Send raw bytes via win32print."""
    import win32print
    h = win32print.OpenPrinter(printer_name)
    try:
        win32print.StartDocPrinter(h, 1, ('TSPL Label', None, 'RAW'))
        win32print.StartPagePrinter(h)
        written = win32print.WritePrinter(h, tspl_bytes)
        win32print.EndPagePrinter(h)
        win32print.EndDocPrinter(h)
        print(f'OK:{written}')
        return True
    except Exception as e:
        print(f'ERROR:{e}', file=sys.stderr)
        return False
    finally:
        win32print.ClosePrinter(h)


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('Usage: python tspl_sender.py <printer_name> <tspl_file>', file=sys.stderr)
        sys.exit(1)

    printer_name = sys.argv[1]
    tspl_file = sys.argv[2]

    with open(tspl_file, 'rb') as f:
        tspl_bytes = f.read()

    if not send_win32print(printer_name, tspl_bytes):
        sys.exit(1)
