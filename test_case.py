import io
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

import pandas as pd
from flask import Flask, request
from werkzeug.datastructures import FileStorage

from app import app


class TestApp(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.app = app.test_client()

    def test_index(self):
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)

    def test_form(self):
        response = self.app.get('/form')
        self.assertEqual(response.status_code, 200)

    @patch('pandas.read_csv')
    @patch('pandas.DataFrame.to_csv')
    def test_preprocess(self, to_csv_mock, read_csv_mock):
        # Set up a temporary file to use as the uploaded CSV file
        with tempfile.NamedTemporaryFile(suffix='.csv') as f:
            # Load the train.csv file
            train_csv_path = 'path/to/train.csv'
            train_data = pd.read_csv(train_csv_path)

            # Save the train data to the temporary file
            train_data.to_csv(f.name, index=False)

            # Create a mock file object and add the test CSV data to it
            file_contents = io.BytesIO()
            train_data.to_csv(file_contents, index=False)
            file_contents.seek(0)
            file = FileStorage(file_contents, filename=f.name)

            # Mock the request object and set the uploaded file
            request_mock = Mock()
            request_mock.files = {'file': file}
            with patch('flask.request', request_mock):
                response = self.app.post('/')
                self.assertEqual(response.status_code, 200)

                # Check that the preprocessed CSV data is returned in the download page
                self.assertIn('processed_data', response.data.decode('utf-8'))
                processed_data = response.data.decode('utf-8').split('\n')
                self.assertEqual(processed_data[0], ','.join(train_data.columns))
                for i, row in enumerate(train_data.itertuples(index=False)):
                    self.assertEqual(processed_data[i+1], ','.join(map(str, row)))

    def test_download(self):
        # Set up a temporary file to use as the preprocessed CSV file
        with tempfile.NamedTemporaryFile(suffix='.csv') as f:
            # Load the train.csv file
            train_csv_path = 'train.csv'
            train_data = pd.read_csv(train_csv_path)

            # Save the preprocessed train data to the temporary file
            processed_data = train_data.copy()
            processed_data['col1'] = processed_data['col1'] + 1
            processed_data.to_csv(f.name, index=False)

            # Mock the request object and set the processed data
            request_mock = Mock()
            request_mock.form = {'processed_data': processed_data.to_csv(index=False)}
            with patch('flask.request', request_mock):
                response = self.app.post('/download')
                self.assertEqual(response.status_code, 200)

                # Check that the downloaded file has the expected contents
                downloaded_data = pd.read_csv(io.StringIO(response.data.decode('utf-8')))
                pd.testing.assert_frame_equal(downloaded_data, processed_data)

if __name__ == '__main__':
    unittest.main()
