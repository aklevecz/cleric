log_file_path =r"C:\Users\Public\Daybreak Game Company\Installed Games\EverQuest\Logs\eqlog_Badegg_teek.txt"

import time
from press import duck, cast_ch
from red_percentage import get_percentage_of_guy

def tail_log_file(log_file_path, num_lines=10):
    with open(log_file_path, 'r') as file:
        while True:
            file.seek(0, 2)  # Move the cursor to the end of the file
            file_size = file.tell()
            buffer_size = 1024
            if file_size < buffer_size:   
                buffer_size = file_size
            file.seek(file_size - buffer_size)
            lines = file.readlines()
            if len(lines) > num_lines:
                lines = lines[-num_lines:]
            for line in lines:
                if "Go egg" in line:
                    cast_ch()
                    time.sleep(9)
                    percentage = get_percentage_of_guy('badegg')
                    if (percentage > 85):
                        duck()
                    print(f"Red progress: {percentage:.2f}%")
                # print(line, end='')
            time.sleep(2)  # Wait for 2 seconds before reading the file again

# Example usage
tail_log_file(log_file_path, num_lines=10)