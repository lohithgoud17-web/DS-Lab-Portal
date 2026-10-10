-- ==========================================================
-- DS LAB PORTAL - DATABASE SCHEMA & INITIAL DATA (MySQL)
-- Database: ds_lab
-- ==========================================================

CREATE DATABASE IF NOT EXISTS ds_lab CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE ds_lab;

-- ----------------------------------------------------------
-- 1. Students Table (Profile / ID Card)
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS students (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL DEFAULT 'Data Science Scholar',
    register_no VARCHAR(50) NOT NULL DEFAULT '22DS101',
    section VARCHAR(20) NOT NULL DEFAULT 'DS-A',
    branch VARCHAR(50) NOT NULL DEFAULT 'Data Science & AI',
    faculty_name VARCHAR(100) NOT NULL DEFAULT 'Dr. S. Ramanathan',
    photo_url VARCHAR(500) DEFAULT '/static/images/default_student.png',
    github_url VARCHAR(500) DEFAULT 'https://github.com/datascience-student/lab-work',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ----------------------------------------------------------
-- 2. Modules Table
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS modules (
    id INT AUTO_INCREMENT PRIMARY KEY,
    module_number VARCHAR(20) NOT NULL,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ----------------------------------------------------------
-- 3. Subtopics Table
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS subtopics (
    id INT AUTO_INCREMENT PRIMARY KEY,
    module_id INT NOT NULL,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    display_order INT DEFAULT 1,
    FOREIGN KEY (module_id) REFERENCES modules(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ----------------------------------------------------------
-- 4. PDF Resources Table
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS pdf_resources (
    id INT AUTO_INCREMENT PRIMARY KEY,
    subtopic_id INT NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (subtopic_id) REFERENCES subtopics(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ----------------------------------------------------------
-- 5. Experiments Table (Lab Execution)
-- ----------------------------------------------------------
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

-- ----------------------------------------------------------
-- 6. Experiment Media Table (Images & Videos)
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS experiment_media (
    id INT AUTO_INCREMENT PRIMARY KEY,
    experiment_id INT NOT NULL,
    media_type VARCHAR(50) NOT NULL, -- 'image' or 'video'
    media_url VARCHAR(500) NOT NULL,
    FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ----------------------------------------------------------
-- 7. Sub-Experiments Table (Optional sub-tasks A, B, etc.)
-- ----------------------------------------------------------
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

-- ----------------------------------------------------------
-- 8. Administrators Table
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS admins (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ==========================================================
-- SEED INITIAL DATA
-- ==========================================================

-- Default Student Profile
INSERT INTO students (id, name, register_no, section, branch, faculty_name, photo_url, github_url)
VALUES (1, 'Lohit Kumar', '22DS101', 'DS-A', 'Data Science & AI', 'Dr. S. Ramanathan', '/static/images/default_student.png', 'https://github.com/lohitkumar/ds-laboratory')
ON DUPLICATE KEY UPDATE name=VALUES(name);

-- Default Admin (admin / admin123)
-- SHA256 of 'admin123' or pbkdf2 hash
INSERT INTO admins (id, username, password_hash)
VALUES (1, 'admin', 'scrypt:32768:8:1$y6Xk$f4e5a9ff2ee0c9684c3ea8a68ca2a3e0eb96eb4c7b8c73d9d300ad8c874df1cf')
ON DUPLICATE KEY UPDATE username=VALUES(username);

-- Five Modules
INSERT INTO modules (id, module_number, title, description) VALUES
(1, 'Module I', 'Module I – Data Science Fundamentals', 'Introduction to the foundations of Data Science, lifecycle methodologies, data types, acquisition, and preprocessing workflows.'),
(2, 'Module II', 'Module II – Python for Data Science', 'Core programming in Python tailored for data processing, vectorized computations with NumPy, tabular data manipulation with Pandas, and data cleaning routines.'),
(3, 'Module III', 'Module III – Data Visualization', 'Principles of graphical data representation, visual analytics using Matplotlib and Seaborn, exploratory data analysis (EDA), and data interpretation.'),
(4, 'Module IV', 'Module IV – Statistics and Machine Learning', 'Inferential and descriptive statistics, probability theory, correlation, regression models, supervised classification, and unsupervised clustering.'),
(5, 'Module V', 'Module V – Advanced Data Science', 'Model evaluation metrics, decision trees, ensemble learning techniques, feature engineering strategies, and neural networks / deep learning foundations.')
ON DUPLICATE KEY UPDATE title=VALUES(title);

-- Subtopics for Module I
INSERT INTO subtopics (module_id, title, description, display_order) VALUES
(1, 'Introduction to Data Science', 'Definition, scope, applications, and role of data scientists in modern engineering.', 1),
(1, 'Data Science Lifecycle', 'Phases: Problem formulation, data acquisition, data preparation, modeling, evaluation, and deployment.', 2),
(1, 'Types of Data', 'Structured, unstructured, semi-structured, categorical, numerical, and time-series data formats.', 3),
(1, 'Data Collection', 'Web scraping, REST API data ingestion, relational databases, CSV/JSON pipelines, and sensors.', 4),
(1, 'Data Preprocessing', 'Handling missing values, outlier detection, data standardization, scaling, and categorical encoding.', 5);

-- Subtopics for Module II
INSERT INTO subtopics (module_id, title, description, display_order) VALUES
(2, 'Python Basics', 'Control flow, functional programming, list comprehensions, and Python file I/O operations.', 1),
(2, 'NumPy', 'N-dimensional arrays, broadcasting, universal functions, indexing, and vector operations.', 2),
(2, 'Pandas', 'Series, DataFrame structures, indexing, filtering, grouping, aggregation, and merging datasets.', 3),
(2, 'Data Cleaning', 'Detecting nulls, deduplication, type casting, string manipulation, and regex validation.', 4),
(2, 'Data Manipulation', 'Reshaping, pivot tables, multi-indexing, and time-series date parsing in Pandas.', 5);

-- Subtopics for Module III
INSERT INTO subtopics (module_id, title, description, display_order) VALUES
(3, 'Matplotlib', 'Line plots, scatter plots, bar charts, histograms, custom styling, subplots, and export.', 1),
(3, 'Seaborn', 'Statistical visualization, heatmaps, pairplots, violin plots, distribution plots, and color palettes.', 2),
(3, 'Exploratory Data Analysis', 'Univariate, bivariate, and multivariate analysis pipelines to uncover distributions and patterns.', 3),
(3, 'Charts and Graphs', 'Choosing the optimal visualization type for numerical vs categorical business metrics.', 4),
(3, 'Data Interpretation', 'Extracting domain insights, detecting anomalies, and formulating data-driven hypotheses.', 5);

-- Subtopics for Module IV
INSERT INTO subtopics (module_id, title, description, display_order) VALUES
(4, 'Descriptive Statistics', 'Measures of central tendency (mean, median, mode), dispersion (variance, std dev, IQR), and skewness.', 1),
(4, 'Probability', 'Conditional probability, Bayes Theorem, discrete/continuous distributions, and Central Limit Theorem.', 2),
(4, 'Correlation and Regression', 'Pearson/Spearman correlation coefficients, Ordinary Least Squares (OLS) simple and multiple linear regression.', 3),
(4, 'Supervised Learning', 'Logistic regression, k-nearest neighbors (KNN), Naive Bayes classification pipelines.', 4),
(4, 'Unsupervised Learning', 'K-Means clustering, hierarchical clustering, and Principal Component Analysis (PCA).', 5);

-- Subtopics for Module V
INSERT INTO subtopics (module_id, title, description, display_order) VALUES
(5, 'Model Evaluation', 'Confusion matrix, precision, recall, F1-score, ROC-AUC curves, cross-validation, and bias-variance tradeoff.', 1),
(5, 'Decision Trees', 'Entropy, Information Gain, Gini Impurity, classification and regression tree (CART) building.', 2),
(5, 'Ensemble Learning', 'Bagging, Random Forests, Boosting (AdaBoost, Gradient Boosting, XGBoost), and voting classifiers.', 3),
(5, 'Feature Engineering', 'Feature extraction, interaction terms, polynomial features, dimensionality reduction, and selection.', 4),
(5, 'Introduction to Deep Learning', 'Perceptrons, multi-layer feedforward neural networks, activation functions, backpropagation, and PyTorch/TensorFlow.', 5);

-- Sample Initial Experiment
INSERT INTO experiments (id, experiment_no, title, short_description, cover_image, d2_heading, long_content, github_url)
VALUES (
    1,
    '1',
    'Exploratory Data Analysis on Housing Price Dataset',
    'Perform data cleaning, missing value imputation, statistical analysis, and correlation heatmaps on a real-world real estate dataset.',
    '/static/images/exp1_cover.svg',
    'Experiment 1: Methodology and Code Execution',
    '## Objective\nTo inspect, clean, and visualize the California Housing dataset to identify key features determining median house values.\n\n## Implementation Details\n1. Loaded data using pandas.read_csv()\n2. Checked null counts and imputed missing values using median strategy.\n3. Plotted correlation matrix using seaborn heatmap.\n4. Identified median_income as the strongest positive predictor.',
    'https://github.com/lohitkumar/ds-laboratory/tree/main/exp1'
)
ON DUPLICATE KEY UPDATE title=VALUES(title);
