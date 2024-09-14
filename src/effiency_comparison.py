import time
import os
import psutil
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Improved simple polling method
def poll_file(file_path, interval=1):
    last_position = 0
    while True:
        time.sleep(interval)
        try:
            with open(file_path, 'r') as file:
                file.seek(last_position)
                new_data = file.read()
                if new_data:
                    last_position = file.tell()
                    # Process new data here (in this case, we're just counting lines)
                    new_lines = new_data.count('\n')
        except IOError:
            pass  # Handle file access errors

# Watchdog method
class Handler(FileSystemEventHandler):
    def __init__(self, file_path):
        self.file_path = file_path
        self.last_position = 0

    def on_modified(self, event):
        if not event.is_directory and event.src_path == self.file_path:
            try:
                with open(self.file_path, 'r') as file:
                    file.seek(self.last_position)
                    new_data = file.read()
                    if new_data:
                        self.last_position = file.tell()
                        # Process new data here (in this case, we're just counting lines)
                        new_lines = new_data.count('\n')
            except IOError:
                pass  # Handle file access errors

def watchdog_monitor(file_path):
    event_handler = Handler(file_path)
    observer = Observer()
    observer.schedule(event_handler, path=os.path.dirname(file_path), recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

def measure_performance(func, duration, *args):
    process = psutil.Process(os.getpid())
    start_time = time.time()
    start_cpu_time = process.cpu_times().user + process.cpu_times().system
    start_memory = process.memory_info().rss

    thread = threading.Thread(target=func, args=args)
    thread.start()
    
    time.sleep(duration)
    
    thread.join(0)  # Non-blocking join
    
    end_time = time.time()
    end_cpu_time = process.cpu_times().user + process.cpu_times().system
    end_memory = process.memory_info().rss

    cpu_usage = (end_cpu_time - start_cpu_time) / (end_time - start_time) * 100
    memory_usage = (end_memory - start_memory) / 1024 / 1024  # Convert to MB

    return cpu_usage, memory_usage



if __name__ == "__main__":
    file_path = "C:\\Users\\Public\\Daybreak Game Company\\Installed Games\\EverQuest\\Logs\\eqlog_Badegg_teek.txt"
    duration = 60  # Measure for 60 seconds

    print("Measuring simple polling method:")
    poll_cpu, poll_memory = measure_performance(poll_file, duration, file_path)
    print(f"CPU Usage: {poll_cpu:.2f}%")
    print(f"Memory Usage: {poll_memory:.2f} MB")

    print("\nMeasuring Watchdog method:")
    watchdog_cpu, watchdog_memory = measure_performance(watchdog_monitor, duration, file_path)
    print(f"CPU Usage: {watchdog_cpu:.2f}%")
    print(f"Memory Usage: {watchdog_memory:.2f} MB")