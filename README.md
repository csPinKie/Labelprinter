# 🖨️ Raspberry Pi Label Server (Zebra GK420d)

This project turns a Raspberry Pi (2 Zero W) into a fully automated print server for shipping labels. It monitors a network folder that runs on the pi itself, automatically detects common German shipping carriers (DHL, Hermes, etc.) by filename, crops the PDFs to the correct size, and prints them on the Zebra GK420d (you can change it to any pritner you want).
---

##  Quick Start

1. **Open the Network Folder:**
   - Windows: `\\<IP-OF-YOUR-PI>\LabelPrinter`
   - Mac: `smb://<IP-OF-YOUR-PI>/LabelPrinter`

2. **Drop a PDF:**
   - Copy your label PDF into the **`input`** folder.

3. **Magic:**
   - The original file is immediately backed up to the `original` folder.
   - The PDF is analyzed and cropped/rotated based on the filename.
   - The printer outputs the label (4x6 inch).
   - The processed file is moved to the `processed` folder.

---

## Folder Structure

The Samba share `LabelPrinter` contains three subfolders:

| Folder | Description |
| :--- | :--- |
| **`input`** | **Drop files here.** The watchdog monitors this folder for new PDFs. |
| **`processed`** | Contains the **cropped/final** PDFs after successful printing. |
| **`original`** | Contains the **unmodified A4 originals** as a backup. |

---

## Automated Logic (Modes)

The script checks the filename to determine how to process the label:

| Type / Keyword | Action | Details |
| :--- | :--- | :--- |
| **DHL** <br>`"DHL-Paketmarke"` | **Crop** | Removes typical A4 margins, keeps only the label area. |
| **Hermes** <br>`"Hermes"`, `"Paketschein_"` | **Crop + Rotate** | Cuts off the bottom half of the A4 page and **rotates** the label by 90° so it fits the 4x6 portrait format. |
| **Return Label** <br>`"Rücksende-Etikett"` | **Crop** | Fallback for older Hermes return labels (bottom crop). |
| **Stamp** <br>`"Briefmarken"` | **Crop + Scale** | Isolates the stamp (e.g., Internetmarke) and scales it up. |
| **Amazon / Other** | **Direct Copy** | No modification, printed via `fit-to-page`. |

> **Note:** All print jobs are sent to CUPS with the `-o fit-to-page` option to ensure they fill the 4x6 inch label.

---

## Hardware Warning: USB Cables & Disconnect Issues

**Highly Recommended:** Use a standard **USB-B to Micro-USB cable** (or a standard USB-B cable with a simple OTG adapter) to connect the Zebra printer to the Raspberry Pi. Almost all Zebra GK420d printers have a square USB-B port hidden on the back. 

### The "CH340S Adapter" Bug
If you are using a **USB-to-Parallel adapter cable** (often recognized as `QinHeng Electronics CH340S` when running `lsusb`), you will likely experience random printer freezes where CUPS gets stuck on `"Waiting for printer to become available"`. 

**The Cause:** The cheap microchip inside these adapter cables crashes completely when Linux (CUPS) tries to establish a bidirectional connection to check the printer status.

### The Workaround (usbreset trick)
If you *must* use this adapter cable, you need to configure the Pi to virtually "unplug and replug" the cable via software exactly one second before every print job:

1. **Install usbutils:**
   ```bash
   sudo apt install usbutils
   ```
2. **Find your cable's Hardware ID:** Run lsusb and look for the ID of your CH340 adapter (e.g., 1a86:7584).

3. **Enable the old printer driver permanently:**
These cables require the old usblp kernel module to survive reboots:

   ```Bash
   echo "usblp" | sudo tee -a /etc/modules
   ```
4. **Update the Python Script:**
In your python script, right before the lp print command is executed, add this to wake up the cable:

```python
import subprocess
# Virtually unplug and replug the adapter cable to wake it up
subprocess.run(["sudo", "usbreset", "1a86:7584"])
   
# ... (your normal lp print command goes here) ...
```    


## Technical Setup & Maintenance

### Paths on the Pi
- **Python Script:** `/home/admin/print_watchdog.py`
- **Label Directory:** `/home/admin/labels/`
- **System Service:** `/etc/systemd/system/labelprinter.service`

### Important Commands (SSH)

**Check Status (Is the service running?):**
```bash
sudo systemctl status labelprinter.service
```
### Restart Service (After code changes):
```bash
sudo systemctl restart labelprinter.service
```
View Logs (Debugging):
```bash
# Live logs (Exit with CTRL+C)
journalctl -u labelprinter.service -f
```

Edit Script:
```bash
nano /home/admin/print_watchdog.py
```


## Installation / Disaster Recovery
If you need to set up the system from scratch:
Install Dependencies:
```bash
sudo apt install cups python3-pip
pip install watchdog pypdf --break-system-packages
```
### Configure CUPS:
- **Web Interface:** https://<IP>:631
- **Driver:** Zebra ZPL Label Printer
- **Name:** Zebra_GK420d 
- **Media Size:** 4x6 inch (or 100x150mm)

### Configure Samba:
- Config file: /etc/samba/smb.conf
- Create share [LabelPrinter] pointing to /home/admin/labels (guest ok = yes).

### Setup Service:
- Create /etc/systemd/system/labelprinter.service.
- Enable it: sudo systemctl enable labelprinter.service.