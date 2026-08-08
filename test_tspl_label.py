"""
TSPL Label Printer — Test script for thermal printer connectivity.
Tries all 3 send methods to find which one works.
"""

import sys
import os
import platform
import subprocess
import tempfile

SYSTEM = platform.system()

# EXACT same simple test that printed before
SIMPLE_TEST = "SIZE 100 mm, 150 mm\r\nGAP 2 mm, 0 mm\r\nDIRECTION 1\r\nCLS\r\nTEXT 50,50,\"4\",0,1,1,\"TEST PRINT OK\"\r\nTEXT 50,120,\"3\",0,1,1,\"100x150mm\"\r\nPRINT 1,1\r\n"

FULL_LABEL = "SIZE 100 mm, 150 mm\r\nGAP 2 mm, 0 mm\r\nDIRECTION 1\r\nCLS\r\nTEXT 50,30,\"4\",0,1,1,\"Test Product\"\r\nTEXT 50,80,\"3\",0,1,1,\"Sample\"\r\nBAR 30,120,740,2\r\nTEXT 50,140,\"4\",0,1,1,\"Width: 1200 mm\"\r\nTEXT 50,190,\"4\",0,1,1,\"Height: 800 mm\"\r\nBAR 30,240,740,2\r\nTEXT 50,260,\"3\",0,1,1,\"Position: Living Room\"\r\nTEXT 50,300,\"3\",0,1,1,\"Quantity: 2\"\r\nTEXT 50,340,\"3\",0,1,1,\"Order: #CMD-0042\"\r\nTEXT 50,380,\"3\",0,1,1,\"Client: John Smith\"\r\nQRCODE 520,260,H,6,A,0,\"https://example.com/label/123\"\r\nBAR 30,480,740,2\r\nTEXT 50,500,\"4\",0,1,1,\"1200 x 800 mm | Qty: 2\"\r\nTEXT 50,560,\"3\",0,1,1,\"OF #57 - PrintBridge\"\r\nPRINT 1,1\r\n"


def get_printers():
    if SYSTEM == "Windows":
        import win32print
        flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        return [p["pPrinterName"] for p in win32print.EnumPrinters(flags, None, 2)]
    r = subprocess.run(["lpstat", "-a"], capture_output=True, text=True, timeout=5)
    return [l.split()[0] for l in r.stdout.strip().split("\n") if l.strip()]


def method_win32print(raw_bytes, printer):
    """Method 1: win32print RAW"""
    import win32print
    h = win32print.OpenPrinter(printer)
    try:
        win32print.StartDocPrinter(h, 1, ("TSPL", None, "RAW"))
        win32print.StartPagePrinter(h)
        win32print.WritePrinter(h, raw_bytes)
        win32print.EndPagePrinter(h)
        win32print.EndDocPrinter(h)
        return True
    except Exception as e:
        print(f"    Error: {e}")
        return False
    finally:
        win32print.ClosePrinter(h)


def method_copy(raw_bytes, printer):
    """Method 2: COPY to USB port"""
    import win32print
    h = win32print.OpenPrinter(printer)
    info = win32print.GetPrinter(h, 2)
    port = info.get("pPortName", "USB001")
    win32print.ClosePrinter(h)

    tmp = tempfile.NamedTemporaryFile(suffix=".bin", delete=False, mode="wb")
    tmp.write(raw_bytes)
    tmp.close()
    try:
        r = subprocess.run(f'copy /b "{tmp.name}" "{port}"',
                          shell=True, capture_output=True, text=True, timeout=15)
        return r.returncode == 0
    except:
        return False
    finally:
        os.unlink(tmp.name)


def method_powershell(raw_bytes, printer):
    """Method 3: PowerShell .NET raw send"""
    tmp = tempfile.NamedTemporaryFile(suffix=".bin", delete=False, mode="wb")
    tmp.write(raw_bytes)
    tmp.close()
    escaped_path = tmp.name.replace("\\", "\\\\")
    escaped_printer = printer.replace("'", "''")
    ps = f"""
Add-Type -TypeDefinition @'
using System;using System.Runtime.InteropServices;
public class RP {{
    [StructLayout(LayoutKind.Sequential)]public struct DI {{[MarshalAs(UnmanagedType.LPStr)]public string n;[MarshalAs(UnmanagedType.LPStr)]public string o;[MarshalAs(UnmanagedType.LPStr)]public string d;}}
    [DllImport("winspool.drv",SetLastError=true,CharSet=CharSet.Ansi)]public static extern bool OpenPrinter(string s,out IntPtr h,IntPtr p);
    [DllImport("winspool.drv",SetLastError=true)]public static extern bool StartDocPrinter(IntPtr h,int l,ref DI d);
    [DllImport("winspool.drv",SetLastError=true)]public static extern bool StartPagePrinter(IntPtr h);
    [DllImport("winspool.drv",SetLastError=true)]public static extern bool WritePrinter(IntPtr h,byte[] b,int c,out int w);
    [DllImport("winspool.drv",SetLastError=true)]public static extern bool EndPagePrinter(IntPtr h);
    [DllImport("winspool.drv",SetLastError=true)]public static extern bool EndDocPrinter(IntPtr h);
    [DllImport("winspool.drv",SetLastError=true)]public static extern bool ClosePrinter(IntPtr h);
    public static bool Send(string pn,byte[] data){{IntPtr h;if(!OpenPrinter(pn,out h,IntPtr.Zero))return false;var di=new DI{{n="TSPL",d="RAW"}};StartDocPrinter(h,1,ref di);StartPagePrinter(h);int w;WritePrinter(h,data,data.Length,out w);EndPagePrinter(h);EndDocPrinter(h);ClosePrinter(h);return w>0;}}
}}
'@
$b=[System.IO.File]::ReadAllBytes("{escaped_path}")
$r=[RP]::Send("{escaped_printer}",$b)
Write-Output $r
"""
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                          capture_output=True, text=True, timeout=30)
        return "True" in r.stdout
    except:
        return False
    finally:
        os.unlink(tmp.name)


if __name__ == "__main__":
    print("=" * 50)
    print("  TSPL Label Printer")
    print("=" * 50)

    printers = get_printers()
    print("\n  Printers:")
    for i, p in enumerate(printers):
        print(f"    [{i}] {p}")

    if len(sys.argv) > 1:
        printer = sys.argv[1]
    else:
        c = input("\n  Pick number: ").strip()
        printer = printers[int(c)] if c.isdigit() and int(c) < len(printers) else c

    print(f"\n  Printer: {printer}")

    methods = [
        ("win32print RAW", method_win32print),
        ("COPY to port", method_copy),
        ("PowerShell .NET", method_powershell),
    ]

    # Step 1: Find which method works with simple test
    print("\n  STEP 1: Finding working method with simple test...\n")
    working_method = None
    raw = SIMPLE_TEST.encode("ascii")

    for name, func in methods:
        print(f"  Trying {name}...")
        try:
            func(raw, printer)
        except Exception as e:
            print(f"    Failed: {e}")
            continue
        ans = input(f"    Did it print? (y/n): ").strip().lower()
        if ans == "y":
            working_method = (name, func)
            print(f"    >>> Method '{name}' works!")
            break

    if not working_method:
        print("\n  No method worked. Check printer connection.")
        sys.exit(1)

    # Step 2: Send full label with working method
    print(f"\n  STEP 2: Sending full label via {working_method[0]}...\n")
    print("  Label content:")
    print(FULL_LABEL)
    print()

    working_method[1](FULL_LABEL.encode("ascii"), printer)
    ans = input("  Did the full label print? (y/n): ").strip().lower()

    if ans == "y":
        print("\n  SUCCESS! Full label printed.")
    else:
        # Try without QRCODE
        print("\n  Trying without QR code...")
        NO_QR = FULL_LABEL.replace('QRCODE 520,260,H,6,A,0,"https://example.com/label/123"\r\n', '')
        working_method[1](NO_QR.encode("ascii"), printer)
        ans = input("  Did it print without QR? (y/n): ").strip().lower()
        if ans == "y":
            print("  >>> QRCODE command is not supported on your printer.")
        else:
            print("  >>> Issue is not QR. May need simpler commands. Check printer manual.")
