import time
import os
import subprocess
import shutil
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pypdf import PdfReader, PdfWriter

# --- KONFIGURATION RASPBERRY PI ---
BASE_DIR = "/home/admin/labels"
WATCH_DIR = os.path.join(BASE_DIR, "input")
PROCESSED_DIR = os.path.join(BASE_DIR, "processed")
ORIGINAL_DIR = os.path.join(BASE_DIR, "original")

# Name exakt wie im CUPS
PRINTER_NAME = "Zebra_GK420d"

# Umrechnung mm in points
MM_TO_PT = 2.83465


def crop_pdf(input_path, output_path, left, top, right, bottom, use_mm=False):
    print(f"   -> Croppe PDF: {os.path.basename(input_path)}")
    reader = PdfReader(input_path)
    writer = PdfWriter()
    page = reader.pages[0]

    factor = MM_TO_PT if use_mm else 1
    c_left = left * factor
    c_top = top * factor
    c_right = right * factor
    c_bottom = bottom * factor

    current_left = page.mediabox.left
    current_bottom = page.mediabox.bottom
    current_right = page.mediabox.right
    current_top = page.mediabox.top

    new_upper_right_x = current_right - c_right
    new_upper_right_y = current_top - c_top
    new_lower_left_x = current_left + c_left
    new_lower_left_y = current_bottom + c_bottom

    page.cropbox.upper_right = (new_upper_right_x, new_upper_right_y)
    page.cropbox.lower_left = (new_lower_left_x, new_lower_left_y)
    page.mediabox.upper_right = (new_upper_right_x, new_upper_right_y)
    page.mediabox.lower_left = (new_lower_left_x, new_lower_left_y)

    writer.add_page(page)
    with open(output_path, "wb") as f:
        writer.write(f)


def scale_stamp(input_path, output_path):
    print(f"   -> Skaliere Briefmarke...")
    reader = PdfReader(input_path)
    writer = PdfWriter()
    page = reader.pages[0]
    writer.add_page(page)
    with open(output_path, "wb") as f:
        writer.write(f)


class LabelHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory: return
        if not event.src_path.lower().endswith('.pdf'): return

        print(f"\n[EVENT] Datei erkannt: {event.src_path}")
        time.sleep(2)  # Wartezeit für vollständigen Kopiervorgang
        self.process_file(event.src_path)

    def process_file(self, file_path):
        filename = os.path.basename(file_path)

        # Original sichern
        original_backup = os.path.join(ORIGINAL_DIR, filename)
        shutil.copy(file_path, original_backup)
        print(f"Original gesichert nach: {original_backup}")

        final_print_file = os.path.join(PROCESSED_DIR, filename)

        # --- LOGIK ---
        if "DHL-Paketmarke" in filename:
            print("Modus: DHL Crop")
            crop_pdf(file_path, final_print_file, 20, 65, 20, 485)

        elif "Rücksende-Etikett" in filename:
            # Alte Hermes Logik (Fallback)
            print("Modus: Hermes Rücksende-Etikett Crop")
            crop_pdf(file_path, final_print_file, 20, 180, 20, 25, use_mm=True)

        elif "Hermes" in filename or "Paketschein_" in filename:
            print("Modus: Hermes/Paketschein (Mitte Oben) -> Crop & Rotate")

            # 1. Croppen (Deine getesteten Werte)
            crop_pdf(file_path, final_print_file, 20, 10, 24, 165, use_mm=True)

            # 2. Drehen (WICHTIG für den Pi/Drucker, damit es 4x6 passt)
            try:
                reader = PdfReader(final_print_file)
                writer = PdfWriter()
                page = reader.pages[0]
                page.rotate(90)  # 90 Grad drehen
                writer.add_page(page)
                with open(final_print_file, "wb") as f:
                    writer.write(f)
                print("   -> Label rotiert.")
            except Exception as e:
                print(f"   -> Fehler bei Rotation: {e}")

        elif "Briefmarken" in filename:
            print("Modus: Briefmarke")
            temp_crop = os.path.join(PROCESSED_DIR, "temp_" + filename)
            crop_pdf(file_path, temp_crop, 0, 30, 340, 670)
            scale_stamp(temp_crop, final_print_file)
            if os.path.exists(temp_crop): os.remove(temp_crop)

        elif "ShipperLabel" in filename:
            print("Modus: Amazon (Direct Copy)")
            shutil.copy(file_path, final_print_file)

        else:
            print("Modus: Standard (Direct Copy)")
            shutil.copy(file_path, final_print_file)

        # --- DRUCKEN (ECHT) ---
        print(f"Sende an Drucker '{PRINTER_NAME}'...")
        # fit-to-page zieht das gecroppte PDF auf das Label
        cmd = ["lp", "-d", PRINTER_NAME, "-o", "fit-to-page", final_print_file]

        try:
            subprocess.run(cmd, check=True)
            print("Druckauftrag gesendet.")
        except subprocess.CalledProcessError as e:
            print(f"FEHLER beim Drucken: {e}")

        # Aufräumen
        if os.path.exists(file_path):
            os.remove(file_path)
        print("Input bereinigt.\n")


if __name__ == "__main__":
    # Ordner sicherstellen
    for d in [WATCH_DIR, PROCESSED_DIR, ORIGINAL_DIR]:
        if not os.path.exists(d):
            os.makedirs(d)

    observer = Observer()
    handler = LabelHandler()
    observer.schedule(handler, WATCH_DIR, recursive=False)
    observer.start()

    print("-" * 50)
    print(f"RASPBERRY PI LABEL SERVER LÄUFT")
    print(f"Überwache: {WATCH_DIR}")
    print("-" * 50)

    # Startup-Check: Liegengebliebene Dateien verarbeiten
    files = [f for f in os.listdir(WATCH_DIR) if f.lower().endswith('.pdf')]
    if files:
        print(f"Start-Check: {len(files)} alte Dateien gefunden. Verarbeite...")
        for f in files:
            handler.process_file(os.path.join(WATCH_DIR, f))

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()