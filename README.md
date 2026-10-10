# DS LAB Portal – Data Science Laboratory

A complete, responsive **Data Science Laboratory Portal** featuring two primary sections: **Modules** and **Lab Execution**, built with Python Flask, MySQL / SQLite, and clean HTML/CSS/JS modeled after the reference design at [datalab-pyya.onrender.com](https://datalab-pyya.onrender.com/).

[![GitHub Repo](https://img.shields.io/badge/GitHub-DS--Lab--Portal-blue?logo=github)](https://github.com/lohithgoud17-web/DS-Lab-Portal)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0+-black?logo=flask)](https://palletsprojects.com/p/flask/)
[![Render Deploy](https://img.shields.io/badge/Deploy-Render-46E3B7?logo=render&logoColor=white)](https://render.com/)

---

## Key Features

1. **Top Navigation with Symbols**:
   * Brand: **DS LAB | Data Science Laboratory** with logo.
   * Primary navigation aligned to the left beside the brand:
     * **Home** (House symbol ⌂)
     * **Modules** (Book symbol 📖)
     * **Lab Execution** (Code brackets symbol `</>`)
   * Student profile pill (**Lohith Goud**, Roll: `22DS101`).

2. **Student Profile / ID Card**:
   * Prominently displayed on the Home page with student photo, name, register number, section, branch, faculty name, and GitHub repository link.
   * **Edit Profile** modal with instant photo upload and persistent storage.

3. **Modules Section (5 Syllabus Modules)**:
   * **Module I** – Data Science Fundamentals (5 Subtopics)
   * **Module II** – Python for Data Science (5 Subtopics)
   * **Module III** – Data Visualization (5 Subtopics)
   * **Module IV** – Statistics and Machine Learning (5 Subtopics)
   * **Module V** – Advanced Data Science (5 Subtopics)
   * **+ Add Topic & PDF**: Upload a new title, description, and attached PDF file directly into any module.
   * Expandable accordion module cards.
   * Dynamic real-time search across module titles, numbers, and subtopic names.
   * Every subtopic includes:
     * **Read PDF**: Embedded document reader with scrolling, zooming, and "Open in New Tab".
     * **Download PDF**: Direct download of verified PDF laboratory manuals.

4. **Lab Execution Section**:
   * Comprehensive list of executed laboratory experiments with cover images and status tags.
   * **+ Add Experiment** modal supporting code file uploads, output plot image uploads, and terminal execution logs.
   * Dynamic search by experiment number, title, and description.
   * **Split-Layout Experiment View (`/experiment/<id>`)**:
     * **Header Banner**: Experiment Title, Experiment #, Student Name, Register Number, Execution Status, and direct GitHub repo link.
     * **Left Side — Output & Results**:
       * Visualization plot card with **🔍 View Full** zoom modal and **Download** button.
       * Terminal console output / stdout execution logs.
       * Detailed methodology and findings notes.
       * Sub-experiment tasks (e.g. Part 1A, 1B).
     * **Right Side — Executed Code**:
       * Dark code editor pane with automated line numbers.
       * Language tag (Python Script).
       * **Copy Code** button with clipboard confirmation.
       * **Download .py** button for direct file download.
       * **Upload Executed Code & Output** modal to replace or update code scripts and output results.

5. **Administrator Resource Management**:
   * Protected route at `/admin/resources` with session-based authentication at `/admin/login`.
   * Default credentials: `admin` / `admin123`.
   * Curriculum and PDF management tools.

---

## Technology Stack

* **Frontend**: HTML5, CSS3 (CSS Custom Properties, Responsive Grid & Flexbox, Sora & IBM Plex Sans typography), JavaScript (ES6+ AJAX & Dynamic DOM).
* **Backend**: Python Flask 3.x, Gunicorn (WSGI).
* **Database**: MySQL (PyMySQL) with automatic SQLite fallback (`ds_lab.db`) when MySQL is inactive.
* **File Storage**: Organized file structure under `uploads/modules/module_1` to `module_5`, `uploads/experiments`, and `uploads/students`.

---

## Directory Structure

```
DS-Lab-Portal/
├── app.py                  # Main Flask application & routes
├── database.py             # Database connector, migrations & PDF seeder
├── database.sql            # MySQL schema DDL & seed queries
├── requirements.txt        # Python package dependencies
├── Procfile                # Gunicorn deployment config for Render / Heroku
├── render.yaml             # 1-Click Render blueprint config
├── test_portal.py          # Automated test suite (11 test suites)
├── .env.example            # Environment template
├── .gitignore              # Git ignore rules
├── README.md               # Documentation
│
├── templates/
│   ├── base.html           # Header with symbols & student profile
│   ├── index.html          # Home page with ID card & overview cards
│   ├── modules.html        # 5 Modules accordion view & Add Topic modal
│   ├── module_details.html # Dedicated module syllabus view
│   ├── pdf_viewer.html     # Embedded PDF reader page
│   ├── lab_execution.html  # Experiments list, toolbar & Add Experiment modal
│   ├── experiment_details.html # Two-column split layout (Output left, Code right)
│   ├── admin_login.html    # Administrator sign-in
│   └── admin_resources.html # Administrator PDF upload & curriculum manager
│
├── static/
│   ├── css/
│   │   └── style.css       # Clean, responsive design system
│   ├── js/
│   │   └── app.js          # Interactive features & search
│   └── images/
│       ├── logo.svg
│       ├── default_student.svg
│       └── exp1_cover.svg
│
└── uploads/
    ├── modules/            # Subtopic PDF files (module_1 to module_5)
    ├── experiments/        # Uploaded code files, output plots, and media
    └── students/           # Uploaded profile photos
```

---

## How to Run Locally

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Database (Optional)
If running a local MySQL server:
1. Update `.env` with your credentials:
   ```env
   DB_HOST=localhost
   DB_PORT=3306
   DB_USER=root
   DB_PASSWORD=your_password
   DB_NAME=ds_lab
   ```
2. Import `database.sql`:
   ```bash
   mysql -u root -p < database.sql
   ```

*Note: If MySQL is not running, the application automatically uses local SQLite (`ds_lab.db`) with complete feature parity and zero configuration required.*

### 3. Start the Server
```bash
python app.py
```
Open your browser and navigate to:
**http://127.0.0.1:5000**

### 4. Run Automated Tests
```bash
python test_portal.py
```
All 11 tests will execute and verify all pages, layouts, PDF streaming, and CRUD operations.

---

## How to Deploy Online (Free on Render)

The project includes `Procfile` and `render.yaml` preconfigured for free cloud deployment on [Render](https://render.com/):

1. Go to [Render Dashboard](https://dashboard.render.com/).
2. Click **New +** → **Web Service**.
3. Connect your GitHub repository:
   `https://github.com/lohithgoud17-web/DS-Lab-Portal`
4. Set the following settings (auto-detected if using Blueprints):
   * **Runtime**: Python 3
   * **Build Command**: `pip install -r requirements.txt`
   * **Start Command**: `gunicorn app:app`
5. Click **Deploy Web Service**. Your portal will be live at `https://<your-service-name>.onrender.com`!
