import os
import csv
import logging

class CSVLogger:
    def __init__(self, directory, date_str, base_filename, header):
        """
        Initializes the CSV Logger.
        
        Args:
            directory (str): Path to the log directory.
            date_str (str): Date string (YYYYMMDD).
            base_filename (str): base filename.
            header (list): List of column names.
        """
        self.directory = directory
        self.header = header
        
        # Construct filename: YYYYMMDD_basefilename.csv
        # Example: /directory/20251216_base_filename.csv
        self.filename = f"{date_str}_{base_filename}.csv"
        self.filepath = os.path.join(self.directory, self.filename)
        
        try:
            os.makedirs(self.directory, exist_ok=True)
        except OSError as e:
            logging.error(f"Could not create log directory {self.directory}: {e}")

    def __enter__(self):
        try:
            file_exists = os.path.isfile(self.filepath)
            self.file = open(self.filepath, mode='a', newline='')
            self.writer = csv.DictWriter(self.file, fieldnames=self.header)
            
            if not file_exists:
                self.writer.writeheader()
                
            return self
        except IOError as e:
            logging.error(f"Failed to open CSV file {self.filepath}: {e}")
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        if hasattr(self, 'file') and self.file:
            self.file.close()

    def save(self, data_dict):
        """
        Writes a row to the CSV file.
        Filters the input dictionary to ensure only keys present in the header are written.
        """
        if hasattr(self, 'writer') and self.writer:
            row = {k: data_dict.get(k, '') for k in self.header}
            self.writer.writerow(row)