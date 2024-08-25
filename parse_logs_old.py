import time
import os
import hashlib
import threading
from press import cast_ch, duck, sit
from red_percentage import get_percentage_of_guy

def cast_or_duck_ch():
    # Simulate a keystroke or any other action
    print("Casting spell...")
    cast_ch()
    time.sleep(9)
    percentage = get_percentage_of_guy("badegg")
    print(f"Red progress: {percentage:.2f}%")
    if percentage > 85:
        duck()
        sit()
    else:
        time.sleep(2)
        sit()

def tail_log_file(log_file_path, num_lines=10, match_string="ERROR"):
    processed_lines = set()

    def hash_line(line):
        return hashlib.md5(line.encode()).hexdigest()

    def get_last_lines(file, num_lines):
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        buffer_size = 1024
        data = []
        while len(data) < num_lines and file_size > 0:
            if file_size < buffer_size:
                buffer_size = file_size
            file.seek(file_size - buffer_size)
            data = file.readlines() + data
            file_size -= buffer_size
        return data[-num_lines:]

    with open(log_file_path, 'r') as file:
        while True:
            lines = get_last_lines(file, num_lines)
            for line in lines:
                line_hash = hash_line(line)
                if line_hash not in processed_lines:
                    if match_string in line:
                        threading.Thread(target=cast_or_duck_ch).start()
                        print(line, end='')
                    processed_lines.add(line_hash)
            time.sleep(2)  # Wait for 2 seconds before reading the file again

# Example usage
tail_log_file(log_file_path, num_lines=10, match_string="Go egg")