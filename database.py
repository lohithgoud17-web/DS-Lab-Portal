import os
import sqlite3

from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:  # pragma: no cover
    psycopg2 = None
    RealDictCursor = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))

DATABASE_URL = os.getenv('DATABASE_URL')
SQLITE_PATH = os.path.join(BASE_DIR, 'ds_lab.db')


def is_production_environment():
    return os.getenv('FLASK_ENV') == 'production' or os.getenv('APP_ENV') == 'production' or os.getenv('RENDER') == 'true'


def get_database_backend():
    if DATABASE_URL:
        lowered = DATABASE_URL.lower()
        if lowered.startswith('postgres://') or lowered.startswith('postgresql://'):
            return 'postgres'
        if lowered.startswith('mysql://'):
            raise RuntimeError('MySQL is no longer supported. Set DATABASE_URL to a PostgreSQL connection string.')
    if is_production_environment():
        raise RuntimeError('DATABASE_URL is required in production. Configure a Neon PostgreSQL URL before starting the app.')
    return 'sqlite'


def get_connection():
    backend = get_database_backend()
    if backend == 'postgres':
        if psycopg2 is None:
            raise RuntimeError('psycopg2 is required for PostgreSQL support. Install the project dependencies.')
        kwargs = {}
        if 'sslmode=' not in DATABASE_URL.lower():
            kwargs['sslmode'] = 'require'
        conn = psycopg2.connect(DATABASE_URL, **kwargs)
        conn.autocommit = False
        return conn, 'postgres'

    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn, 'sqlite'


def _normalize_sqlite_query(sql):
    return sql.replace('%s', '?')


def _ensure_insert_returning(sql, backend):
    if backend != 'postgres':
        return sql
    upper = sql.strip()
    if not upper.upper().startswith('INSERT '):
        return sql
    if 'RETURNING' in upper.upper():
        return sql
    return f"{sql.rstrip()} RETURNING id"


def query_db(sql, params=None, fetch='all', commit=False):
    conn, backend = get_connection()
    params = params or ()

    try:
        if backend == 'sqlite':
            sqlite_sql = _normalize_sqlite_query(sql)
            cur = conn.cursor()
            cur.execute(sqlite_sql, params)
            if commit:
                conn.commit()
                result = cur.lastrowid
            else:
                if fetch == 'one':
                    row = cur.fetchone()
                    result = dict(row) if row is not None else None
                elif fetch == 'all':
                    result = [dict(r) for r in cur.fetchall()]
                else:
                    result = None
            conn.close()
            return result

        sql_to_run = _ensure_insert_returning(sql, backend)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql_to_run, params)
            if commit:
                conn.commit()
                row = cur.fetchone()
                result = row['id'] if row and 'id' in row else None
            else:
                if fetch == 'one':
                    row = cur.fetchone()
                    result = dict(row) if row is not None else None
                elif fetch == 'all':
                    result = [dict(r) for r in cur.fetchall()]
                else:
                    result = None
        conn.close()
        return result
    except Exception:
        if backend == 'sqlite' and commit:
            conn.rollback()
        elif backend == 'postgres' and conn:
            conn.rollback()
        raise


def generate_sample_pdf(file_path, title, module_title, subtopic_name, overview_text, points):
    """Generates a clean PDF file used in module resources."""
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
    for point in points:
        safe_point = point.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
        stream_content += f"( - {safe_point}) Tj\n0 -16 Td\n"

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
        current = 0
        for chunk in body:
            offsets.append(current)
            f.write(chunk + b'\n')
            current += len(chunk) + 1
        xref_start = current
        f.write(b'xref\n0 7\n0000000000 65535 f \n')
        for off in offsets[1:]:
            f.write(f'{off:010d} 00000 n \n'.encode('latin1'))
        f.write(f'trailer << /Size 7 /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF\n'.encode('latin1'))


def _create_schema(cursor, backend):
    if backend == 'postgres':
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL DEFAULT 'Data Science Scholar',
            register_no TEXT NOT NULL DEFAULT '22DS101',
            section TEXT NOT NULL DEFAULT 'DS-A',
            branch TEXT NOT NULL DEFAULT 'Data Science & AI',
            faculty_name TEXT NOT NULL DEFAULT 'Dr. S. Ramanathan',
            photo_url TEXT DEFAULT '/static/images/default_student.svg',
            github_url TEXT DEFAULT 'https://github.com/lohitkumar/ds-laboratory',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        ''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS modules (
            id SERIAL PRIMARY KEY,
            module_number TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        ''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS subtopics (
            id SERIAL PRIMARY KEY,
            module_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            display_order INTEGER DEFAULT 1,
            FOREIGN KEY (module_id) REFERENCES modules(id) ON DELETE CASCADE
        );
        ''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS pdf_resources (
            id SERIAL PRIMARY KEY,
            subtopic_id INTEGER NOT NULL,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (subtopic_id) REFERENCES subtopics(id) ON DELETE CASCADE
        );
        ''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS experiments (
            id SERIAL PRIMARY KEY,
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
        ''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS experiment_media (
            id SERIAL PRIMARY KEY,
            experiment_id INTEGER NOT NULL,
            media_type TEXT NOT NULL,
            media_url TEXT NOT NULL,
            FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE
        );
        ''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS sub_experiments (
            id SERIAL PRIMARY KEY,
            experiment_id INTEGER NOT NULL,
            letter TEXT NOT NULL,
            title TEXT NOT NULL,
            short_description TEXT,
            d2_heading TEXT DEFAULT 'Sub-Experiment Details',
            long_content TEXT,
            cover_image TEXT DEFAULT '',
            video_url TEXT DEFAULT '',
            github_url TEXT DEFAULT '',
            completed BOOLEAN DEFAULT TRUE,
            FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE
        );
        ''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        ''')
        return

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL DEFAULT 'Data Science Scholar',
        register_no TEXT NOT NULL DEFAULT '22DS101',
        section TEXT NOT NULL DEFAULT 'DS-A',
        branch TEXT NOT NULL DEFAULT 'Data Science & AI',
        faculty_name TEXT NOT NULL DEFAULT 'Dr. S. Ramanathan',
        photo_url TEXT DEFAULT '/static/images/default_student.svg',
        github_url TEXT DEFAULT 'https://github.com/lohitkumar/ds-laboratory',
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS modules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        module_number TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS subtopics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        module_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        display_order INTEGER DEFAULT 1,
        FOREIGN KEY (module_id) REFERENCES modules(id) ON DELETE CASCADE
    );
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS pdf_resources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subtopic_id INTEGER NOT NULL,
        file_name TEXT NOT NULL,
        file_path TEXT NOT NULL,
        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (subtopic_id) REFERENCES subtopics(id) ON DELETE CASCADE
    );
    ''')
    cursor.execute('''
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
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS experiment_media (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        experiment_id INTEGER NOT NULL,
        media_type TEXT NOT NULL,
        media_url TEXT NOT NULL,
        FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE
    );
    ''')
    cursor.execute('''
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
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    ''')


def init_db():
    """Ensures the schema exists and applies simple migrations for missing columns."""
    conn, backend = get_connection()
    cursor = conn.cursor()
    _create_schema(cursor, backend)

    if backend == 'postgres':
        for column in ['code_file_name', 'code_file_path', 'code_content', 'output_image', 'output_text']:
            try:
                cursor.execute(f"ALTER TABLE experiments ADD COLUMN IF NOT EXISTS {column} TEXT DEFAULT ''")
            except Exception:
                pass
    else:
        cursor.execute('PRAGMA table_info(experiments)')
        existing = {row[1] for row in cursor.fetchall()}
        for column in ['code_file_name', 'code_file_path', 'code_content', 'output_image', 'output_text']:
            if column not in existing:
                cursor.execute(f'ALTER TABLE experiments ADD COLUMN {column} TEXT DEFAULT ""')

    conn.commit()
    conn.close()
    seed_initial_data()


def seed_initial_data():
    """Seeds the minimum dataset expected by the portal pages and tests."""
    admin_user = os.getenv('ADMIN_USERNAME', 'admin')
    admin_pass = os.getenv('ADMIN_PASSWORD', 'admin123')

    existing_admin = query_db('SELECT id FROM admins WHERE username = %s', (admin_user,), fetch='one')
    if not existing_admin:
        query_db(
            'INSERT INTO admins (username, password_hash) VALUES (%s, %s)',
            (admin_user, generate_password_hash(admin_pass)),
            commit=True,
        )

    student = query_db('SELECT id FROM students WHERE id = 1', fetch='one')
    if not student:
        query_db(
            '''
            INSERT INTO students (id, name, register_no, section, branch, faculty_name, photo_url, github_url)
            VALUES (1, %s, %s, %s, %s, %s, %s, %s)
            ''',
            (
                'Lohith Goud',
                '22DS101',
                'DS-A',
                'Data Science & AI',
                'Dr. S. Ramanathan',
                '/static/images/default_student.svg',
                'https://github.com/lohithgoud/ds-laboratory',
            ),
            commit=True,
        )
    else:
        query_db(
            "UPDATE students SET name = 'Lohith Goud', photo_url = '/static/images/default_student.svg' WHERE id = 1 AND name = 'Data Science Scholar'",
            commit=True,
        )

    module_specs = [
        {
            'id': 1,
            'module_number': 'Module I',
            'title': 'Module I – Data Science Fundamentals',
            'description': 'Introduction to the foundations of Data Science, lifecycle methodologies, data types, acquisition, and preprocessing workflows.',
            'subtopics': [
                ('Introduction to Data Science', 'Definition, domain scope, real-world applications, and core skill matrix of data scientists.'),
                ('Data Science Lifecycle', 'Systematic phases: Problem formulation, data acquisition, data preparation, exploratory analysis, modeling, evaluation, and deployment.'),
                ('Types of Data', 'Structured, semi-structured, unstructured, quantitative continuous/discrete, and qualitative nominal/ordinal data.'),
                ('Data Collection', 'Data ingestion through web scraping, REST APIs, SQL databases, sensor streams, and public datasets.'),
                ('Data Preprocessing', 'Data cleaning, imputation of missing entries, outlier mitigation, scaling, normalization, and one-hot encoding.')
            ]
        },
        {
            'id': 2,
            'module_number': 'Module II',
            'title': 'Module II – Python for Data Science',
            'description': 'Core programming in Python tailored for data processing, vectorized computations with NumPy, tabular manipulation with Pandas, and cleaning routines.',
            'subtopics': [
                ('Python Basics', 'Core syntax, data structures (lists, tuples, dicts), functions, list comprehensions, and error handling.'),
                ('NumPy', 'N-dimensional arrays, broadcasting, vectorized math, array reshaping, slicing, and linear algebra routines.'),
                ('Pandas', 'Series and DataFrame data structures, indexing, filtering, column manipulations, and merging/joining tables.'),
                ('Data Cleaning', 'Handling null values, deduplication, string cleaning, type conversions, and handling datetime columns.'),
                ('Data Manipulation', 'Aggregations with groupby, pivot tables, multi-indexing, and reshaping with melt and stack.')
            ]
        },
        {
            'id': 3,
            'module_number': 'Module III',
            'title': 'Module III – Data Visualization',
            'description': 'Principles of graphical data representation, visual analytics using Matplotlib and Seaborn, exploratory data analysis (EDA), and data interpretation.',
            'subtopics': [
                ('Matplotlib', 'Figure architecture, line plots, scatter charts, bar graphs, histograms, customizing axes, legends, and styling.'),
                ('Seaborn', 'High-level statistical plots, heatmaps, pairplots, violin plots, boxplots, distribution analysis, and aesthetics.'),
                ('Exploratory Data Analysis', 'Univariate, bivariate, and multivariate visualization techniques to uncover patterns and anomalies.'),
                ('Charts and Graphs', 'Selecting the right visualization for categorical, numerical, and time-series variables.'),
                ('Data Interpretation', 'Formulating data-driven conclusions, reporting findings, and avoiding deceptive graphical representations.')
            ]
        },
        {
            'id': 4,
            'module_number': 'Module IV',
            'title': 'Module IV – Statistics and Machine Learning',
            'description': 'Inferential and descriptive statistics, probability theory, correlation, regression models, supervised classification, and unsupervised clustering.',
            'subtopics': [
                ('Descriptive Statistics', 'Measures of central tendency (mean, median, mode), spread (variance, standard deviation, IQR), and skewness.'),
                ('Probability', 'Probability axioms, conditional probability, Bayes theorem, normal distribution, and Central Limit Theorem.'),
                ('Correlation and Regression', 'Pearson and Spearman correlation, Ordinary Least Squares simple and multiple linear regression models.'),
                ('Supervised Learning', 'Classification algorithms: Logistic Regression, k-Nearest Neighbors (KNN), and Naive Bayes.'),
                ('Unsupervised Learning', 'Clustering methods: K-Means, hierarchical clustering, and Principal Component Analysis (PCA).')
            ]
        },
        {
            'id': 5,
            'module_number': 'Module V',
            'title': 'Module V – Advanced Data Science',
            'description': 'Model evaluation metrics, decision trees, ensemble learning techniques, feature engineering strategies, and neural networks / deep learning foundations.',
            'subtopics': [
                ('Model Evaluation', 'Confusion matrix, precision, recall, F1-score, ROC-AUC curve, k-fold cross-validation, and bias-variance tradeoff.'),
                ('Decision Trees', 'Information gain, entropy, Gini impurity, splitting criteria, pruning, and CART algorithms.'),
                ('Ensemble Learning', 'Bagging with Random Forest, Boosting algorithms (AdaBoost, Gradient Boost, XGBoost), and voting classifiers.'),
                ('Feature Engineering', 'Feature selection, polynomial feature generation, interaction terms, and dimensionality reduction.'),
                ('Introduction to Deep Learning', 'Biological vs artificial neurons, multilayer perceptrons, activation functions, and backpropagation foundations.')
            ]
        }
    ]

    for mod in module_specs:
        module_row = query_db('SELECT id FROM modules WHERE id = %s', (mod['id'],), fetch='one')
        if not module_row:
            query_db(
                'INSERT INTO modules (id, module_number, title, description) VALUES (%s, %s, %s, %s)',
                (mod['id'], mod['module_number'], mod['title'], mod['description']),
                commit=True,
            )
        else:
            query_db(
                'UPDATE modules SET module_number = %s, title = %s, description = %s WHERE id = %s',
                (mod['module_number'], mod['title'], mod['description'], mod['id']),
                commit=True,
            )

        for order_index, (subtopic_title, subtopic_desc) in enumerate(mod['subtopics'], start=1):
            subtopic = query_db(
                'SELECT id FROM subtopics WHERE module_id = %s AND title = %s',
                (mod['id'], subtopic_title),
                fetch='one',
            )
            if not subtopic:
                subtopic_id = query_db(
                    'INSERT INTO subtopics (module_id, title, description, display_order) VALUES (%s, %s, %s, %s)',
                    (mod['id'], subtopic_title, subtopic_desc, order_index),
                    commit=True,
                )
            else:
                subtopic_id = subtopic['id']
                query_db(
                    'UPDATE subtopics SET description = %s, display_order = %s WHERE id = %s',
                    (subtopic_desc, order_index, subtopic_id),
                    commit=True,
                )

            pdf_present = query_db('SELECT id FROM pdf_resources WHERE subtopic_id = %s', (subtopic_id,), fetch='one')
            if not pdf_present:
                slug = subtopic_title.lower().replace(' & ', 'and').replace(' ', '_')
                file_name = f'{slug}.pdf'
                folder = os.path.join(BASE_DIR, 'uploads', 'modules', f'module_{mod["id"]}')
                os.makedirs(folder, exist_ok=True)
                file_path = os.path.join(folder, file_name)
                generate_sample_pdf(
                    file_path,
                    subtopic_title,
                    mod['title'],
                    subtopic_title,
                    subtopic_desc,
                    [subtopic_desc, 'Apply the concept to a real dataset', 'Document the outcome and explain the result']
                )
                query_db(
                    'INSERT INTO pdf_resources (subtopic_id, file_name, file_path) VALUES (%s, %s, %s)',
                    (subtopic_id, file_name, os.path.join('uploads', 'modules', f'module_{mod["id"]}', file_name)),
                    commit=True,
                )

    existing_exp = query_db("SELECT id FROM experiments WHERE experiment_no = %s", ('1',), fetch='one')
    if not existing_exp:
        query_db(
            '''
            INSERT INTO experiments (
                experiment_no, title, short_description, cover_image, d2_heading, long_content,
                code_file_name, code_file_path, code_content, output_image, output_text, github_url
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''',
            (
                '1',
                'Exploratory Data Analysis on Housing Price Dataset',
                'Perform data cleaning, missing value imputation, statistical analysis, and correlation heatmaps on a real-world real estate dataset.',
                '/static/images/exp1_cover.svg',
                'Exploratory Data Analysis & Housing Insights',
                '## Overview\nAnalyzed a real estate dataset to uncover distribution, feature relationships, and key pricing drivers.\n\n## Methodology\n- Cleaned missing values\n- Analyzed categorical and numeric patterns\n- Visualized correlation heatmap and price trends\n\n## Findings\nMedian price was strongly associated with location, total area, and number of bedrooms.',
                'eda_housing.py',
                'uploads/experiments/code/eda_housing.py',
                'import pandas as pd\nimport seaborn as sns\n\n# Load and inspect the housing dataset\ndf = pd.read_csv("housing.csv")\nprint(df.head())\nprint(df.describe())\n',
                '/static/images/exp1_cover.svg',
                'Model performance summary: cleaned data, effective inspection of price trends and correlations.',
                'https://github.com/lohitkumar/ds-laboratory/tree/main/exp1',
            ),
            commit=True,
        )

    experiment = query_db("SELECT id FROM experiments WHERE experiment_no = %s", ('1',), fetch='one')
    if experiment:
        sub_rows = query_db('SELECT id FROM sub_experiments WHERE experiment_id = %s', (experiment['id'],), fetch='all')
        if not sub_rows:
            query_db(
                'INSERT INTO sub_experiments (experiment_id, letter, title, short_description, d2_heading, long_content, cover_image) VALUES (%s, %s, %s, %s, %s, %s, %s)',
                (experiment['id'], 'A', 'Dataset inspection', 'Inspect structure, missing values, and overview statistics.', 'Data Cleaning Overview', 'Observed several missing values in the feature set and removed inconsistent entries.', '/static/images/exp1_cover.svg'),
                commit=True,
            )
            query_db(
                'INSERT INTO sub_experiments (experiment_id, letter, title, short_description, d2_heading, long_content, cover_image) VALUES (%s, %s, %s, %s, %s, %s, %s)',
                (experiment['id'], 'B', 'Correlation analysis', 'Analyze relationships between area, rooms, and target price.', 'Feature Relationship Study', 'The strongest positive correlation was found between living area and sale price.', '/static/images/exp1_cover.svg'),
                commit=True,
            )

    try:
        query_db('CREATE INDEX IF NOT EXISTS idx_modules_title ON modules(title)', commit=True)
        query_db('CREATE INDEX IF NOT EXISTS idx_subtopics_module_id ON subtopics(module_id)', commit=True)
        query_db('CREATE INDEX IF NOT EXISTS idx_experiments_no ON experiments(experiment_no)', commit=True)
    except Exception:
        pass


if __name__ == '__main__':
    init_db()