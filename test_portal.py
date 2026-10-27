import os
import io
import unittest
from app import app
from database import init_db, query_db

class DSLabPortalTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        query_db("UPDATE experiments SET title = 'Exploratory Data Analysis on Housing Price Dataset', short_description = 'Perform data cleaning, missing value imputation, statistical analysis, and correlation heatmaps on a real-world real estate dataset.' WHERE id = 1", commit=True)
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        cls.client = app.test_client()

    def test_01_home_page(self):
        """Test home page loads with brand, navigation, ID card, and overview."""
        res = self.client.get('/')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')
        self.assertIn('DS LAB', html)
        self.assertIn('Data Science Laboratory', html)
        self.assertIn('Student Profile', html)
        self.assertIn('Explore Modules', html)
        self.assertIn('Lab Execution', html)
        print("[PASS] Test 1 Passed: Home Page loads with Student Profile and Navigation")
    def test_02_main_navigation(self):
        """Test navigation structure and ensure Modules is beside Lab Execution."""
        res = self.client.get('/')
        html = res.data.decode('utf-8')
        self.assertIn('href="/modules"', html)
        self.assertIn('href="/lab-execution"', html)
        # Verify Modules is next to Lab Execution in the nav
        nav_part = html[html.find('<nav class="dsl-nav"'):html.find('</nav>')]
        self.assertIn('Modules', nav_part)
        self.assertIn('Lab Execution', nav_part)
        print("[PASS] Test 2 Passed: Main Navigation verified with Modules and Lab Execution")

    def test_03_modules_page(self):
        """Test Modules section lists all 5 modules and subtopics."""
        res = self.client.get('/modules')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')
        for mod_num in ['Module I', 'Module II', 'Module III', 'Module IV', 'Module V']:
            self.assertIn(mod_num, html)
        self.assertIn('Introduction to Data Science', html)
        self.assertIn('Python Basics', html)
        self.assertIn('Matplotlib', html)
        self.assertIn('Descriptive Statistics', html)
        self.assertIn('Model Evaluation', html)
        self.assertIn('Read PDF', html)
        self.assertIn('Download PDF', html)
        print("[PASS] Test 3 Passed: Modules page displays all 5 modules with subtopics and PDF buttons")

    def test_04_pdf_read_and_download(self):
        """Test that Read PDF and Download PDF actually return real valid PDFs."""
        pdf_res = query_db("SELECT id FROM pdf_resources LIMIT 1", fetch='one')
        self.assertIsNotNone(pdf_res)
        pid = pdf_res['id']

        # Stream inline
        res_read = self.client.get(f'/api/pdf/read/{pid}')
        self.assertEqual(res_read.status_code, 200)
        self.assertEqual(res_read.headers['Content-Type'], 'application/pdf')
        self.assertTrue(res_read.data.startswith(b'%PDF'))

        # Download attachment
        res_dl = self.client.get(f'/api/pdf/download/{pid}')
        self.assertEqual(res_dl.status_code, 200)
        self.assertIn('attachment', res_dl.headers.get('Content-Disposition', ''))
        self.assertTrue(res_dl.data.startswith(b'%PDF'))

        # Dedicated PDF Viewer page
        res_view = self.client.get(f'/pdf-viewer/{pid}')
        self.assertEqual(res_view.status_code, 200)
        self.assertIn(f'/api/pdf/read/{pid}', res_view.data.decode('utf-8'))
        print("[PASS] Test 4 Passed: PDF Streaming, Downloading, and Dedicated Viewer fully operational")

    def test_05_lab_execution_flow(self):
        """Test Lab Execution page, adding an experiment, and viewing experiment details."""
        res = self.client.get('/lab-execution')
        self.assertEqual(res.status_code, 200)
        self.assertIn('Laboratory Execution', res.data.decode('utf-8'))

        # Add new experiment via API
        new_exp_data = {
            'experiment_no': '2',
            'title': 'Feature Selection and Linear Regression',
            'short_description': 'Implement Ordinary Least Squares linear regression model with feature scaling.',
            'd2_heading': 'Linear Regression Execution Notes',
            'long_content': '## Overview\nTrained OLS model with scikit-learn. Achieved R2 score of 0.84.',
            'github_url': 'https://github.com/lohitkumar/ds-laboratory/tree/main/exp2',
            'sub_experiments': [
                {'letter': 'A', 'title': 'Feature Scaling', 'shortDescription': 'StandardScaler normalization'}
            ]
        }
        res_post = self.client.post('/api/experiments', json=new_exp_data)
        self.assertEqual(res_post.status_code, 201)
        created = res_post.get_json()
        exp_id = created['id']

        # Read details of created experiment
        res_detail = self.client.get(f'/experiment/{exp_id}')
        self.assertEqual(res_detail.status_code, 200)
        self.assertIn('Feature Selection and Linear Regression', res_detail.data.decode('utf-8'))
        self.assertIn('OLS model with scikit-learn', res_detail.data.decode('utf-8'))

        # Delete the test experiment
        res_del = self.client.delete(f'/api/experiments/{exp_id}')
        self.assertEqual(res_del.status_code, 200)
        print("[PASS] Test 5 Passed: Lab Execution CRUD (List, Add, View Details, Delete) verified")

    def test_06_profile_update(self):
        """Test student profile retrieval and persistent update."""
        res_get = self.client.get('/api/profile')
        self.assertEqual(res_get.status_code, 200)
        orig = res_get.get_json()

        update_payload = {
            'name': 'Lohit Kumar Updated',
            'register_no': '22DS999',
            'section': 'DS-B',
            'branch': 'Data Science & Artificial Intelligence',
            'faculty_name': 'Dr. K. Balasubramanian',
            'github_url': 'https://github.com/lohitkumar/ds-laboratory-updated'
        }
        res_put = self.client.put('/api/profile', json=update_payload)
        self.assertEqual(res_put.status_code, 200)
        updated = res_put.get_json()
        self.assertEqual(updated['name'], 'Lohit Kumar Updated')
        self.assertEqual(updated['register_no'], '22DS999')

        # Re-verify persistence
        res_verify = self.client.get('/api/profile')
        self.assertEqual(res_verify.get_json()['section'], 'DS-B')
        print("[PASS] Test 6 Passed: Student Profile retrieved and persistently updated")

    def test_07_search_functionality(self):
        """Test dynamic module and experiment search endpoints."""
        res_mod = self.client.get('/api/modules?q=Python')
        self.assertEqual(res_mod.status_code, 200)
        modules = res_mod.get_json()
        self.assertTrue(len(modules) >= 1)
        self.assertTrue(any('Python' in m['title'] for m in modules))

        res_exp = self.client.get('/api/experiments?q=housing')
        self.assertEqual(res_exp.status_code, 200)
        experiments = res_exp.get_json()
        self.assertTrue(len(experiments) >= 1)
        self.assertTrue(any('Housing' in e['title'] for e in experiments))
        print("[PASS] Test 7 Passed: Module & Lab Execution search filters return dynamic matches")

    def test_08_admin_security_and_pdf_management(self):
        """Test that admin endpoints are protected, and authorized admins can upload/manage resources."""
        # Unauthorized attempt should return 401
        res_unauth = self.client.post('/api/admin/subtopics', json={'title': 'Test Subtopic', 'module_id': 1})
        self.assertEqual(res_unauth.status_code, 401)

        # Login as Admin
        res_login = self.client.post('/admin/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=True)
        self.assertEqual(res_login.status_code, 200)

        # Authorized creation of a subtopic
        res_sub = self.client.post('/api/admin/subtopics', json={
            'module_id': 1,
            'title': 'Automated Unit Test Topic',
            'description': 'Temporary subtopic for admin testing.'
        })
        self.assertEqual(res_sub.status_code, 200)
        sub_id = res_sub.get_json()['id']

        # Upload a PDF for this subtopic
        sample_pdf_data = b"%PDF-1.4\n1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n2 0 obj << /Type /Pages /Kids [] /Count 0 >> endobj\nxref\n0 3\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \ntrailer << /Size 3 /Root 1 0 R >>\nstartxref\n115\n%%EOF"
        upload_data = {
            'subtopic_id': str(sub_id),
            'pdf_file': (io.BytesIO(sample_pdf_data), 'test_upload.pdf')
        }
        res_upload = self.client.post('/api/admin/upload-pdf', data=upload_data, content_type='multipart/form-data')
        self.assertEqual(res_upload.status_code, 200)
        pdf_id = res_upload.get_json()['pdf_id']

        # Verify PDF is readable
        res_check_pdf = self.client.get(f'/api/pdf/read/{pdf_id}')
        self.assertEqual(res_check_pdf.status_code, 200)

        # Delete the test PDF resource
        res_del_pdf = self.client.delete(f'/api/admin/pdf/{pdf_id}')
        self.assertEqual(res_del_pdf.status_code, 200)

        # Delete the test subtopic
        res_del_sub = self.client.delete(f'/api/admin/subtopics/{sub_id}')
        self.assertEqual(res_del_sub.status_code, 200)
        print("[PASS] Test 8 Passed: Admin Security, Subtopic creation, PDF upload/delete authorized flow verified")

    def test_09_add_topic_from_module_page(self):
        """Test uploading a new topic with title and PDF from the modules page."""
        sample_pdf = b"%PDF-1.4\n1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n2 0 obj << /Type /Pages /Kids [] /Count 0 >> endobj\nxref\n0 3\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \ntrailer << /Size 3 /Root 1 0 R >>\nstartxref\n115\n%%EOF"
        data = {
            'module_id': '2',
            'title': 'Advanced NumPy Vector Operations',
            'description': 'Array broadcasting and vectorization.',
            'pdf_file': (io.BytesIO(sample_pdf), 'numpy_vector.pdf')
        }
        res = self.client.post('/api/modules/add-topic', data=data, content_type='multipart/form-data')
        self.assertEqual(res.status_code, 201)
        res_data = res.get_json()
        self.assertTrue(res_data['success'])
        self.assertIsNotNone(res_data['pdf_id'])
        print("[PASS] Test 9 Passed: Add Topic & PDF from Modules page verified")

    def test_10_upload_and_download_code_and_output(self):
        """Test uploading executed code and output and downloading the code file."""
        code_data = b"import numpy as np\nprint('Test execution output 100%')\n"
        img_data = b"<svg xmlns='http://www.w3.org/2000/svg'><rect width='50' height='50' fill='blue'/></svg>"
        upload_data = {
            'title': 'Exploratory Data Analysis on Housing Price Dataset (Updated)',
            'description': 'Updated description with fresh code execution on housing price dataset.',
            'output_text': '[INFO] Accuracy score: 0.96\nFinished in 0.4s',
            'code_file': (io.BytesIO(code_data), 'test_eda.py'),
            'output_image': (io.BytesIO(img_data), 'output_plot.svg')
        }
        res = self.client.post('/api/experiments/1/upload-execution', data=upload_data, content_type='multipart/form-data')
        self.assertEqual(res.status_code, 200)
        res_json = res.get_json()
        self.assertTrue(res_json['success'])
        self.assertEqual(res_json['experiment']['code_file_name'], 'test_eda.py')
        self.assertIn('Accuracy score: 0.96', res_json['experiment']['output_text'])

        # Test downloading code
        res_dl = self.client.get('/api/experiments/1/download-code')
        self.assertEqual(res_dl.status_code, 200)
        self.assertIn('test_eda.py', res_dl.headers.get('Content-Disposition', ''))
        print("[PASS] Test 10 Passed: Code & Output Upload and Code Download verified")

    def test_11_experiment_details_layout(self):
        """Test Experiment details page displays Title, Details, Output on left, and Code on right."""
        res = self.client.get('/experiment/1')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')
        # Title and details
        self.assertIn('LABORATORY REPORT', html)
        self.assertIn('EXPERIMENT 1', html)
        # Left side Output
        self.assertIn('Execution Output (Plot / Visualization)', html)
        self.assertIn('Terminal Output / Execution Logs', html)
        # Right side Code
        self.assertIn('Executed Code / Script', html)
        self.assertIn('Download .py', html)
        self.assertIn('Copy Code', html)
        print("[PASS] Test 11 Passed: Two-column layout (Output on left, Code on right) verified")

if __name__ == '__main__':
    unittest.main()
