import os
import sqlite3
import pymysql
from pymysql.cursors import DictCursor
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

# Load environment variables
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))

DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = int(os.getenv('DB_PORT', 3306))
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_NAME = os.getenv('DB_NAME', 'ds_lab')
SQLITE_PATH = os.path.join(BASE_DIR, 'ds_lab.db')

_USE_SQLITE = False

def get_connection():
    """
    Attempts to connect to MySQL. If MySQL is unavailable,
    falls back cleanly to SQLite for seamless local execution.
    """
    global _USE_SQLITE
    if _USE_SQLITE:
        conn = sqlite3.connect(SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn, 'sqlite'

    try:
        # First ensure database exists in MySQL
        conn_server = pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            charset='utf8mb4',
            cursorclass=DictCursor,
            connect_timeout=2
        )
        with conn_server.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        conn_server.commit()
        conn_server.close()

        conn = pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            charset='utf8mb4',
            cursorclass=DictCursor,
            autocommit=False
        )
        return conn, 'mysql'
    except Exception as e:
        print(f"[Database Notice] MySQL connection to {DB_HOST}:{DB_PORT}/{DB_NAME} not available ({e}).")
        print(f"[Database Notice] Using local SQLite database at {SQLITE_PATH} with full feature parity.")
        _USE_SQLITE = True
        conn = sqlite3.connect(SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn, 'sqlite'

def query_db(sql, params=None, fetch='all', commit=False):
    """
    Unified database query executor supporting both MySQL (%s) and SQLite (?).
    Returns dictionary / list of dictionaries, or lastrowid on insert.
    """
    conn, engine = get_connection()
    params = params or ()
    
    if engine == 'sqlite':
        # Adapt SQL placeholders: %s -> ?
        sqlite_sql = sql.replace('%s', '?')
        # Adapt auto_increment / timestamps if present in DDL
        cur = conn.cursor()
        try:
            cur.execute(sqlite_sql, params)
            if commit:
                conn.commit()
                last_id = cur.lastrowid
                conn.close()
                return last_id
            
            if fetch == 'one':
                row = cur.fetchone()
                result = dict(row) if row else None
            elif fetch == 'all':
                result = [dict(r) for r in cur.fetchall()]
            else:
                result = None
            conn.close()
            return result
        except Exception as e:
            if commit:
                conn.rollback()
            conn.close()
            raise e
    else:
        # MySQL engine
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                if commit:
                    conn.commit()
                    last_id = cur.lastrowid
                    conn.close()
                    return last_id

                if fetch == 'one':
                    result = cur.fetchone()
                elif fetch == 'all':
                    result = cur.fetchall()
                else:
                    result = None
                conn.close()
                return result
        except Exception as e:
            if commit:
                conn.rollback()
            conn.close()
            raise e

def generate_sample_pdf(file_path, title, module_title, subtopic_name, overview_text, points):
    """
    Generates a clean, valid PDF 1.4 document for laboratory subtopics.
    """
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    stream_content = f"""BT
/F1 18 Tf
50 740 Td
({title}) Tj
/F1 13 Tf
0 -26 Td
({module_title}) Tj
/F2 11 Tf
0 -20 Td
(Topic: {subtopic_name}) Tj
0 -28 Td
/F1 11 Tf
(OVERVIEW & LEARNING OBJECTIVES) Tj
/F2 10 Tf
0 -20 Td
({overview_text}) Tj
0 -25 Td
/F1 11 Tf
(KEY TOPIC CONCEPTS & METHODOLOGY) Tj
/F2 10 Tf
0 -18 Td
"""
    for pt in points:
        safe_pt = pt.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
        stream_content += f"( - {safe_pt}) Tj\n0 -16 Td\n"

    stream_content += """0 -20 Td
/F1 11 Tf
(LABORATORY PRACTICE / IMPLEMENTATION NOTES) Tj
/F2 10 Tf
0 -18 Td
(1. Follow standard Python and Data Science coding practices.) Tj
0 -15 Td
(2. Document all exploratory findings and statistical hypotheses.) Tj
0 -15 Td
(3. Keep datasets and outputs organized in your repository workspace.) Tj
0 -25 Td
/F2 9 Tf
(DS LAB Portal | Department of Data Science | Academic Manual) Tj
ET
"""
    stream_bytes = stream_content.encode('latin1', errors='replace')
    length = len(stream_bytes)

    body = [
        b'%PDF-1.4',
        b'1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj',
        b'2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj',
        b'3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >> endobj',
        b'4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >> endobj',
        b'5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj',
        f'6 0 obj << /Length {length} >>\nstream\n'.encode('latin1') + stream_bytes + b'\nendstream\nendobj'
    ]

    with open(file_path, 'wb') as f:
        offsets = []
        cur = 0
        for b in body:
            offsets.append(cur)
            f.write(b + b'\n')
            cur += len(b) + 1
        xref_start = cur
        f.write(b'xref\n0 7\n0000000000 65535 f \n')
        for off in offsets[1:]:
            f.write(f'{off:010d} 00000 n \n'.encode('latin1'))
        f.write(f'trailer << /Size 7 /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF\n'.encode('latin1'))

def init_db():
    """
    Initializes database tables, indices, default records,
    and starter PDF documents if not yet present.
    """
    conn, engine = get_connection()
    cursor = conn.cursor()

    if engine == 'mysql':
        # Create MySQL tables
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL DEFAULT 'Data Science Scholar',
            register_no VARCHAR(50) NOT NULL DEFAULT '22DS101',
            section VARCHAR(20) NOT NULL DEFAULT 'DS-A',
            branch VARCHAR(50) NOT NULL DEFAULT 'Data Science & AI',
            faculty_name VARCHAR(100) NOT NULL DEFAULT 'Dr. S. Ramanathan',
            photo_url VARCHAR(500) DEFAULT '/static/images/default_student.png',
            github_url VARCHAR(500) DEFAULT 'https://github.com/lohitkumar/ds-laboratory',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB;
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS modules (
            id INT AUTO_INCREMENT PRIMARY KEY,
            module_number VARCHAR(20) NOT NULL,
            title VARCHAR(200) NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB;
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS subtopics (
            id INT AUTO_INCREMENT PRIMARY KEY,
            module_id INT NOT NULL,
            title VARCHAR(200) NOT NULL,
            description TEXT,
            display_order INT DEFAULT 1,
            FOREIGN KEY (module_id) REFERENCES modules(id) ON DELETE CASCADE
        ) ENGINE=InnoDB;
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS pdf_resources (
            id INT AUTO_INCREMENT PRIMARY KEY,
            subtopic_id INT NOT NULL,
            file_name VARCHAR(255) NOT NULL,
            file_path VARCHAR(500) NOT NULL,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (subtopic_id) REFERENCES subtopics(id) ON DELETE CASCADE
        ) ENGINE=InnoDB;
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS experiments (
            id INT AUTO_INCREMENT PRIMARY KEY,
            experiment_no VARCHAR(20) NOT NULL,
            title VARCHAR(200) NOT NULL,
            short_description TEXT,
            cover_image VARCHAR(500) DEFAULT '',
            d2_heading VARCHAR(200) DEFAULT 'Experiment Details & Implementation',
            long_content LONGTEXT,
            code_file_name VARCHAR(255) DEFAULT '',
            code_file_path VARCHAR(500) DEFAULT '',
            code_content LONGTEXT,
            output_image VARCHAR(500) DEFAULT '',
            output_text LONGTEXT,
            github_url VARCHAR(500) DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB;
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS experiment_media (
            id INT AUTO_INCREMENT PRIMARY KEY,
            experiment_id INT NOT NULL,
            media_type VARCHAR(50) NOT NULL,
            media_url VARCHAR(500) NOT NULL,
            FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE
        ) ENGINE=InnoDB;
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS sub_experiments (
            id INT AUTO_INCREMENT PRIMARY KEY,
            experiment_id INT NOT NULL,
            letter VARCHAR(10) NOT NULL,
            title VARCHAR(200) NOT NULL,
            short_description TEXT,
            d2_heading VARCHAR(200) DEFAULT 'Sub-Experiment Details',
            long_content LONGTEXT,
            cover_image VARCHAR(500) DEFAULT '',
            video_url VARCHAR(500) DEFAULT '',
            github_url VARCHAR(500) DEFAULT '',
            completed BOOLEAN DEFAULT TRUE,
            FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE
        ) ENGINE=InnoDB;
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB;
        """)
        conn.commit()

    else:
        # SQLite schema
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL DEFAULT 'Data Science Scholar',
            register_no TEXT NOT NULL DEFAULT '22DS101',
            section TEXT NOT NULL DEFAULT 'DS-A',
            branch TEXT NOT NULL DEFAULT 'Data Science & AI',
            faculty_name TEXT NOT NULL DEFAULT 'Dr. S. Ramanathan',
            photo_url TEXT DEFAULT '/static/images/default_student.png',
            github_url TEXT DEFAULT 'https://github.com/lohitkumar/ds-laboratory',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS modules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_number TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS subtopics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            display_order INTEGER DEFAULT 1,
            FOREIGN KEY (module_id) REFERENCES modules(id) ON DELETE CASCADE
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS pdf_resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subtopic_id INTEGER NOT NULL,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (subtopic_id) REFERENCES subtopics(id) ON DELETE CASCADE
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS experiments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            experiment_no TEXT NOT NULL,
            title TEXT NOT NULL,
            short_description TEXT,
            cover_image TEXT DEFAULT '',
            d2_heading TEXT DEFAULT 'Experiment Details & Implementation',
            long_content TEXT,
            code_file_name TEXT DEFAULT '',
            code_file_path TEXT DEFAULT '',
            code_content TEXT DEFAULT '',
            output_image TEXT DEFAULT '',
            output_text TEXT DEFAULT '',
            github_url TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS experiment_media (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            experiment_id INTEGER NOT NULL,
            media_type TEXT NOT NULL,
            media_url TEXT NOT NULL,
            FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS sub_experiments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            experiment_id INTEGER NOT NULL,
            letter TEXT NOT NULL,
            title TEXT NOT NULL,
            short_description TEXT,
            d2_heading TEXT DEFAULT 'Sub-Experiment Details',
            long_content TEXT,
            cover_image TEXT DEFAULT '',
            video_url TEXT DEFAULT '',
            github_url TEXT DEFAULT '',
            completed BOOLEAN DEFAULT 1,
            FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        conn.commit()

    # Migration check: Ensure new columns exist in existing tables
    try:
        new_cols = [
            ("code_file_name", "TEXT DEFAULT ''"),
            ("code_file_path", "TEXT DEFAULT ''"),
            ("code_content", "TEXT DEFAULT ''"),
            ("output_image", "TEXT DEFAULT ''"),
            ("output_text", "TEXT DEFAULT ''")
        ]
        if engine == 'sqlite':
            cursor.execute("PRAGMA table_info(experiments)")
            existing_cols = [row[1] for row in cursor.fetchall()]
            for col_name, col_def in new_cols:
                if col_name not in existing_cols:
                    cursor.execute(f"ALTER TABLE experiments ADD COLUMN {col_name} {col_def}")
            conn.commit()
        else:
            for col_name, col_def in new_cols:
                try:
                    cursor.execute(f"ALTER TABLE experiments ADD COLUMN IF NOT EXISTS {col_name} {col_def}")
                except Exception:
                    pass
            conn.commit()
    except Exception as e:
        print("[Migration Notice] Column check:", e)

    conn.close()

    # Seed data
    seed_initial_data()

def seed_initial_data():
    """
    Seeds default student profile, admin credentials, 5 modules,
    subtopics, sample PDFs, and initial laboratory experiment.
    """
    # 1. Admin
    admin_user = os.getenv('ADMIN_USERNAME', 'admin')
    admin_pass = os.getenv('ADMIN_PASSWORD', 'admin123')
    existing_admin = query_db("SELECT id FROM admins WHERE username = %s", (admin_user,), fetch='one')
    if not existing_admin:
        pw_hash = generate_password_hash(admin_pass)
        query_db("INSERT INTO admins (username, password_hash) VALUES (%s, %s)", (admin_user, pw_hash), commit=True)

    # 2. Student Profile
    student = query_db("SELECT id FROM students WHERE id = 1", fetch='one')
    if not student:
        query_db("""
        INSERT INTO students (id, name, register_no, section, branch, faculty_name, photo_url, github_url)
        VALUES (1, %s, %s, %s, %s, %s, %s, %s)
        """, (
            'Lohith Goud',
            '22DS101',
            'DS-A',
            'Data Science & AI',
            'Dr. S. Ramanathan',
            '/static/images/default_student.svg',
            'https://github.com/lohithgoud/ds-laboratory'
        ), commit=True)
    else:
        # Keep name in sync with Lohith Goud if default was set
        query_db("UPDATE students SET name = 'Lohith Goud', photo_url = '/static/images/default_student.svg' WHERE id = 1 AND name = 'Data Science Scholar'", commit=True)

    # 3. Five Modules & Subtopics
    modules_spec = [
        {
            "id": 1,
            "module_number": "Module I",
            "title": "Module I – Data Science Fundamentals",
            "description": "Introduction to the foundations of Data Science, lifecycle methodologies, data types, acquisition, and preprocessing workflows.",
            "subtopics": [
                ("Introduction to Data Science", "Definition, domain scope, real-world applications, and core skill matrix of data scientists."),
                ("Data Science Lifecycle", "Systematic phases: Problem formulation, data acquisition, data preparation, exploratory analysis, modeling, evaluation, and deployment."),
                ("Types of Data", "Structured, semi-structured, unstructured, quantitative continuous/discrete, and qualitative nominal/ordinal data."),
                ("Data Collection", "Data ingestion through web scraping, REST APIs, SQL databases, sensor streams, and public datasets."),
                ("Data Preprocessing", "Data cleaning, imputation of missing entries, outlier mitigation, scaling, normalization, and one-hot encoding.")
            ]
        },
        {
            "id": 2,
            "module_number": "Module II",
            "title": "Module II – Python for Data Science",
            "description": "Core programming in Python tailored for data processing, vectorized computations with NumPy, tabular manipulation with Pandas, and cleaning routines.",
            "subtopics": [
                ("Python Basics", "Core syntax, data structures (lists, tuples, dicts), functions, list comprehensions, and error handling."),
                ("NumPy", "N-dimensional arrays, broadcasting, vectorized math, array reshaping, slicing, and linear algebra routines."),
                ("Pandas", "Series and DataFrame data structures, indexing, filtering, column manipulations, and merging/joining tables."),
                ("Data Cleaning", "Handling null values, deduplication, string cleaning, type conversions, and handling datetime columns."),
                ("Data Manipulation", "Aggregations with groupby, pivot tables, multi-indexing, and reshaping with melt and stack.")
            ]
        },
        {
            "id": 3,
            "module_number": "Module III",
            "title": "Module III – Data Visualization",
            "description": "Principles of graphical data representation, visual analytics using Matplotlib and Seaborn, exploratory data analysis (EDA), and data interpretation.",
            "subtopics": [
                ("Matplotlib", "Figure architecture, line plots, scatter charts, bar graphs, histograms, customizing axes, legends, and styling."),
                ("Seaborn", "High-level statistical plots, heatmaps, pairplots, violin plots, boxplots, distribution analysis, and aesthetics."),
                ("Exploratory Data Analysis", "Univariate, bivariate, and multivariate visualization techniques to uncover patterns and anomalies."),
                ("Charts and Graphs", "Selecting the right visualization for categorical, numerical, and time-series variables."),
                ("Data Interpretation", "Formulating data-driven conclusions, reporting findings, and avoiding deceptive graphical representations.")
            ]
        },
        {
            "id": 4,
            "module_number": "Module IV",
            "title": "Module IV – Statistics and Machine Learning",
            "description": "Inferential and descriptive statistics, probability theory, correlation, regression models, supervised classification, and unsupervised clustering.",
            "subtopics": [
                ("Descriptive Statistics", "Measures of central tendency (mean, median, mode), spread (variance, standard deviation, IQR), and skewness."),
                ("Probability", "Probability axioms, conditional probability, Bayes theorem, normal distribution, and Central Limit Theorem."),
                ("Correlation and Regression", "Pearson and Spearman correlation, Ordinary Least Squares simple and multiple linear regression models."),
                ("Supervised Learning", "Classification algorithms: Logistic Regression, k-Nearest Neighbors (KNN), and Naive Bayes."),
                ("Unsupervised Learning", "Clustering methods: K-Means, hierarchical clustering, and Principal Component Analysis (PCA).")
            ]
        },
        {
            "id": 5,
            "module_number": "Module V",
            "title": "Module V – Advanced Data Science",
            "description": "Model evaluation metrics, decision trees, ensemble learning techniques, feature engineering strategies, and neural networks / deep learning foundations.",
            "subtopics": [
                ("Model Evaluation", "Confusion matrix, precision, recall, F1-score, ROC-AUC curve, k-fold cross-validation, and bias-variance tradeoff."),
                ("Decision Trees", "Information gain, entropy, Gini impurity, splitting criteria, pruning, and CART algorithms."),
                ("Ensemble Learning", "Bagging with Random Forest, Boosting algorithms (AdaBoost, Gradient Boost, XGBoost), and voting classifiers."),
                ("Feature Engineering", "Feature selection, polynomial feature generation, interaction terms, and dimensionality reduction."),
                ("Introduction to Deep Learning", "Biological vs artificial neurons, multilayer perceptrons, activation functions, and backpropagation foundations.")
            ]
        }
    ]

    for mod in modules_spec:
        existing_mod = query_db("SELECT id FROM modules WHERE id = %s", (mod['id'],), fetch='one')
        if not existing_mod:
            query_db("""
            INSERT INTO modules (id, module_number, title, description)
            VALUES (%s, %s, %s, %s)
            """, (mod['id'], mod['module_number'], mod['title'], mod['description']), commit=True)
        else:
            query_db("""
            UPDATE modules SET module_number = %s, title = %s, description = %s WHERE id = %s
            """, (mod['module_number'], mod['title'], mod['description'], mod['id']), commit=True)

        # Check subtopics
        for idx, (sub_title, sub_desc) in enumerate(mod['subtopics'], start=1):
            existing_sub = query_db(
                "SELECT id FROM subtopics WHERE module_id = %s AND title = %s",
                (mod['id'], sub_title), fetch='one'
            )
            if not existing_sub:
                sub_id = query_db("""
                INSERT INTO subtopics (module_id, title, description, display_order)
                VALUES (%s, %s, %s, %s)
                """, (mod['id'], sub_title, sub_desc, idx), commit=True)
            else:
                sub_id = existing_sub['id']

            # Ensure valid PDF exists for this subtopic
            existing_pdf = query_db("SELECT id, file_path FROM pdf_resources WHERE subtopic_id = %s", (sub_id,), fetch='one')
            
            # Format folder and file
            mod_folder = f"module_{mod['id']}"
            safe_filename = f"{sub_title.lower().replace(' ', '_').replace('/', '_')}.pdf"
            rel_path = f"uploads/modules/{mod_folder}/{safe_filename}"
            abs_path = os.path.join(BASE_DIR, rel_path)

            if not os.path.exists(abs_path) or not existing_pdf:
                # Generate sample PDF
                points = [
                    f"Understanding {sub_title} in modern Data Science workflows.",
                    f"Detailed breakdown: {sub_desc}",
                    "Mathematical formulas, code examples, and laboratory execution guidelines.",
                    "Common pitfalls, edge cases, and best practices in practical applications."
                ]
                generate_sample_pdf(
                    abs_path,
                    "DATA SCIENCE LABORATORY MANUAL",
                    mod['title'],
                    sub_title,
                    sub_desc,
                    points
                )
                
                if not existing_pdf:
                    query_db("""
                    INSERT INTO pdf_resources (subtopic_id, file_name, file_path)
                    VALUES (%s, %s, %s)
                    """, (sub_id, safe_filename, rel_path), commit=True)

    # 4. Sample Experiment 1
    sample_code_path = os.path.join(BASE_DIR, 'uploads', 'experiments', 'code', 'housing_eda_execution.py')
    code_text = ""
    if os.path.exists(sample_code_path):
        with open(sample_code_path, 'r', encoding='utf-8') as f:
            code_text = f.read()

    sample_output_text = """[STEP 1] Loading California Housing Dataset...
Dataset Dimensions: (20640, 10)

First 5 Records:
   longitude  latitude  housing_median_age  total_rooms  total_bedrooms  population  households  median_income  median_house_value
0    -122.23     37.88                41.0        880.0           129.0       322.0       126.0         8.3252            452600.0
1    -122.22     37.86                21.0       7099.0          1106.0      2401.0      1138.0         8.3014            358500.0
2    -122.24     37.85                52.0       1467.0           190.0       496.0       177.0         7.2574            352100.0

[STEP 2] Checking Missing Values:
total_bedrooms: 207 null rows detected.
-> Imputed missing total_bedrooms with median: 435.0

[STEP 3] Summary Statistics of Numerical Features:
                     mean          std         min          50%          max
median_income      3.8706       1.8998      0.4999       3.5348      15.0001
median_house_value 206855.8    115395.6    14999.0     179700.0     500001.0

[STEP 4] Correlation with Median House Value:
median_house_value    1.000000
median_income         0.688075
total_rooms           0.134153
housing_median_age    0.105623
households            0.065843
total_bedrooms        0.049686
population           -0.024650
longitude            -0.045967
latitude             -0.144160

[STEP 5] Generating Seaborn Correlation Heatmap...
-> Plot saved to output_heatmap.png
[COMPLETED] Experiment 1 executed successfully with exit code 0."""

    existing_exp = query_db("SELECT id, code_content FROM experiments WHERE id = 1", fetch='one')
    if not existing_exp:
        query_db("""
        INSERT INTO experiments (id, experiment_no, title, short_description, cover_image, d2_heading, long_content, code_file_name, code_file_path, code_content, output_image, output_text, github_url)
        VALUES (1, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            '1',
            'Exploratory Data Analysis on Housing Price Dataset',
            'Perform data cleaning, missing value imputation, statistical analysis, and correlation heatmaps on a real-world real estate dataset.',
            '/static/images/exp1_cover.svg',
            'Experiment 1: Methodology and Code Execution',
            """## Objective
To inspect, clean, and visualize the California Housing dataset to identify key features determining median house values.

## Key Steps Executed
1. **Data Ingestion**: Loaded California Housing CSV dataset using pandas.read_csv().
2. **Missing Value Analysis**: Inspected columns with missing total_bedrooms; applied median imputation.
3. **Distribution Analysis**: Computed mean, variance, and generated distribution histograms.
4. **Correlation Matrix**: Constructed Pearson correlation heatmap using seaborn; confirmed median_income is strongly correlated (+0.68) with median_house_value.

## Conclusion
Exploratory data analysis revealed strong positive linear dependency between household income and property valuation. Log transformation was applied to long-tailed features for model preparation.""",
            'housing_eda_execution.py',
            'uploads/experiments/code/housing_eda_execution.py',
            code_text,
            '/static/images/exp1_cover.svg',
            sample_output_text,
            'https://github.com/lohithgoud/ds-laboratory/tree/main/exp1'
        ), commit=True)
    else:
        # Update existing experiment with sample code and output if empty
        if not existing_exp.get('code_content'):
            query_db("""
            UPDATE experiments SET 
                code_file_name = %s,
                code_file_path = %s,
                code_content = %s,
                output_image = %s,
                output_text = %s
            WHERE id = 1
            """, (
                'housing_eda_execution.py',
                'uploads/experiments/code/housing_eda_execution.py',
                code_text,
                '/static/images/exp1_cover.svg',
                sample_output_text
            ), commit=True)

        # Seed sub-experiments 1A and 1B
        query_db("""
        INSERT INTO sub_experiments (experiment_id, letter, title, short_description, d2_heading, long_content, cover_image, completed)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            1,
            'A',
            'Data Cleaning & Imputation',
            'Handling missing attributes and detecting numerical outliers in housing data.',
            'Sub-Experiment 1A: Data Cleaning Pipeline',
            'Detailed data cleaning steps: checking df.isna().sum(), imputing missing values with SimpleImputer(strategy="median"), and clipping extreme values.',
            '/static/images/exp1_cover.svg',
            1
        ), commit=True)

        query_db("""
        INSERT INTO sub_experiments (experiment_id, letter, title, short_description, d2_heading, long_content, cover_image, completed)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            1,
            'B',
            'Correlation Heatmap & Feature Selection',
            'Visualizing feature relationships using Seaborn heatmap and pairplot.',
            'Sub-Experiment 1B: Correlation Analysis',
            'Generated heatmap with sns.heatmap(df.corr(), annot=True, cmap="coolwarm") to evaluate multi-collinearity among housing attributes.',
            '/static/images/exp1_cover.svg',
            1
        ), commit=True)

    print("[Database Ready] Schema and initial data verified successfully.")

if __name__ == '__main__':
    init_db()
