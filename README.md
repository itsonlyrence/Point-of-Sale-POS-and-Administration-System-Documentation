# Point-of-Sale (POS) and Administration System Documentation

## Overview

The Point-of-Sale (POS) and Administration System replaces browser `localStorage` with a robust SQL database (SQLite) and includes a Windows installation package for automated database and application configuration. The default system name is **"POS System"**, which can be modified at any time through the **Admin → Settings** menu to suit specific retail environments such as "Aling Nena's Grocery".

---

## 1. System Modifications and Enhancements

* **SQL Database Implementation:** All operational data—including products, categories, suppliers, user accounts, sales records, sale line items, stock adjustments, and audit logs—is stored in `data/pos.db`, a SQLite database generated via `schema.sql`. 
* **Database Engine:** SQLite operates as a lightweight, single-file database engine that eliminates the need for a separate database server installation while supporting standard SQL queries.
* **Python Backend Server:** The backend utilizes `server.py`, developed using the pure Python standard library without requiring external `pip` installations, to serve the web application and expose a REST API. 
* **API Integration:** The front end (`static/index.html`) interacts directly with this API, ensuring data consistency across multiple tills and persistence despite browser cache clearing.
* **Staff Account Management:** Supports the creation of cashier and administrator accounts, account deactivation, password resets, and role assignments.
* **System Settings Tab:** Allows configuration of the system name (displayed on login screens, headers, and receipts) alongside store address, contact information, and receipt footer messages.
* **Category and Supplier Management:** Centralizes inventory classification and vendor tracking.
* **Stock Adjustments:** Enables inventory updates categorized by specific operational reasons (such as deliveries, spoilage, or physical recounts) rather than simple numerical overwrites.
* **Product Archiving:** Features product archiving and restoration instead of permanent deletion to preserve historical sales record accuracy.
* **Checkout Discounts:** Supports the application of discounts during transactions.
* **Sales History and Void/Refund Controls:** Provides admin-only void and refund capabilities that automatically restore inventory levels, alongside a reprint function for historical receipts.
* **Reporting Suite:** Generates reports covering revenue, transaction volumes, items sold, top-performing products, cashier performance metrics, and date-range filters, with CSV export capabilities.
* **Audit Logging:** Tracks administrative actions with timestamps and user attribution.
* **Database Backup Utility:** Offers one-click database backup downloads.
* **Low-Stock Alerts:** Automatically flags inventory shortfalls based on configurable per-product reorder thresholds.
* **Dual Barcode Scanning Options:** Supports hardware USB or handheld barcode scanners that input data directly into the barcode field via keyboard emulation without requiring dedicated drivers, alongside webcam or mobile camera scanning via an integrated interface.
* **Receipt Printing:** Generates a printable receipt preview upon transaction completion formatted for narrow (80mm) thermal receipt paper, with historical receipt reprinting available via **Admin → Sales / Void**.

---

## 2. Windows Installation Guide

### Prerequisites
* **Operating System:** Windows 10 or 11.
* **Runtime:** Python 3.9 or higher (the installation script attempts automatic deployment via `winget` if absent).

### Installation Procedure
1. Copy the `GroceryPOS_Package` directory to the target workstation.
2. Execute **`install.bat`** by double-clicking the file.
3. The installation script performs the following actions:
   * Verifies Python availability and installs it automatically if `winget` is accessible.
   * Deploys application files to `%LOCALAPPDATA%\GroceryPOS`.
   * Automatically establishes and seeds the SQLite database without requiring manual configuration.
   * Generates a **"Grocery POS"** shortcut on the Desktop and Start Menu.
   * Configures optional automatic startup upon user sign-in for dedicated cashier terminals.
4. Launch the application via the **Grocery POS** shortcut to open the web interface at `http://localhost:8080`.

### Default Credentials
| Role | Username | Password |
| :--- | :--- | :--- |
| **Admin** | `admin` | `admin123` |
| **Cashier** | `cashier` | `cashier123` |

> [!NOTE]
> It is strongly recommended to update default credentials immediately via **Admin → Users**, and configure store details and system naming through **Admin → Settings**.

### Installation Script Specifications
The installer utilizes a script-based architecture (`install.bat`) rather than a compiled executable file. While database initialization and application setup are fully automated, the process depends on Python availability or the `winget` package manager integrated into modern Windows environments. Legacy Windows builds lacking `winget` require a manual Python installation prior to executing `install.bat`.

---

## 3. Multi-Register Network Configuration

To deploy the system across multiple terminals on a local network:
1. Designate the primary administrative workstation as the server and identify its local IPv4 address via the `ipconfig` utility (e.g., `192.168.1.20`).
2. Launch the application on the designated server workstation.
3. Access the application from secondary register terminals by navigating to `http://[Server-IP]:8080` (e.g., `http://192.168.1.20:8080`) through a standard web browser, avoiding the need for local installations.
4. Configure Windows Firewall permissions to allow `python.exe` network traffic on **Private** networks when prompted.

---

## 4. Backup and Maintenance

* **Application Backup:** Navigate to the **Backup** tab under administrative privileges and select "Download Backup Now" to export a copy of `pos.db`.
* **Manual Backup:** Copy the database file located at `%LOCALAPPDATA%\GroceryPOS\data\pos.db` to an external storage medium or cloud-synced directory on a regular schedule.
* **Uninstallation:** Executing `uninstall.bat` prompts the user to create a system backup on the Desktop prior to complete removal.

---

## 5. Port Configuration

To modify the default network port (8080) in the event of port conflicts:
1. Open `Start-GroceryPOS.bat` located within the installation directory.
2. Replace occurrences of `8080` with an available port number (e.g., `9090`).
3. Update the browser launch command line (`start "" http://localhost:8080/`) to reflect the newly assigned port.

---

## 6. Package Architecture

```text
POS GROCERRY/
├── install.bat          <- Installation script
├── uninstall.bat        <- Removal script with backup prompt
├── README.md            <- Documentation file
└── app/
    ├── server.py        <- Backend REST API and web UI server
    ├── schema.sql       <- Database schema definition
    └── static/
        ├── index.html   <- Application markup
        ├── css/
        │   └── style.css   <- Styling rules for UI components and receipts
        └── js/
            ├── api.js      <- HTTP client wrapper, session state, and settings loader
            ├── auth.js     <- Authentication and interface role control
            ├── scanner.js  <- Webcam barcode integration
            ├── receipt.js  <- Receipt generation, printing, and history reprinting
            ├── cashier.js  <- Product catalog grid, shopping cart, and checkout logic
            ├── admin.js    <- Inventory, user, sales, report, audit, and settings management
            └── main.js     <- Application initialization script
```

The application logic is partitioned into modular files separated by role (markup, styling, and behavior) to streamline maintenance and updates.

## 7. System Limitations and Considerations

* External Dependencies: Visual styling frameworks (Tailwind CSS), icon libraries, and webcam barcode scanning utilities are loaded via Content Delivery Networks (CDNs), requiring an active internet connection during initial execution. Subsequent browser caching permits offline functionality, though fully isolated offline environments require replacing the CDN references in static/index.html with local asset copies. Hardware USB barcode scanners operate entirely offline without external libraries.

* Camera Security Restrictions: Webcam-based barcode scanning requires browser camera permissions and a secure context (localhost or HTTPS) as mandated by browser security policies. Accessing the server locally via http://localhost:8080 is treated as secure by default, whereas accessing the service from secondary workstations over standard HTTP (http://192.168.x.x:8080) may restrict camera functionality depending on browser security enforcement.

* Printing Integration: Receipt generation relies on the native browser print dialog (window.print()). Thermal receipt printers must be configured as standard Windows system printers.

* Session Management: Active user sessions reside in memory and reset if the backend server restarts, requiring cashiers to re-authenticate without resulting in transaction data loss.

* Scalability: The architecture is optimized for small-business operations, where SQLite effectively manages single-store register transaction volumes. Multi-branch deployments or high concurrent write volumes necessitate migrating from SQLite to enterprise relational databases such as MySQL or PostgreSQL, facilitated by server.py isolating database operations within centralized functions.
