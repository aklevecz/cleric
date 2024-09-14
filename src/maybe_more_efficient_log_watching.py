import time
import os

def tail_log_file(file_path, callback, check_interval=1.0):
    last_modified = os.path.getmtime(file_path)
    
    with open(file_path, 'r') as file:
        file.seek(0, os.SEEK_END)
        while True:
            line = file.readline()
            if line:
                callback(line.strip())
            else:
                time.sleep(check_interval)
                current_position = file.tell()
                current_modified = os.path.getmtime(file_path)
                
                if current_modified > last_modified:
                    # File was modified, seek to the last known position
                    file.seek(current_position)
                    last_modified = current_modified
                elif os.path.getsize(file_path) < current_position:
                    # File was truncated or rotated
                    file.seek(0)
                    last_modified = current_modified
                else:
                    file.seek(current_position)

def process_line(line):
    # Process the line here
    print(f"New line: {line}")

if __name__ == "__main__":
    log_file_path = "path/to/your/logfile.log"
    tail_log_file(log_file_path, process_line)