import socket
import time
import threading
import sys

def connect_and_hold(i, host, port):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(15)
        s.connect((host, port))
        print(f"[{i}] Connected")
        # Hold connection open without sending data
        time.sleep(12)
        s.close()
        print(f"[{i}] Closed gracefully")
    except socket.timeout:
        print(f"[{i}] Disconnected by server (Timeout) - SUCCESS")
    except Exception as e:
        print(f"[{i}] Connection failed/closed: {e}")

def main():
    host = 'localhost'
    port = 5000
    threads = []
    
    print(f"Starting 30 connections to {host}:{port}...")
    print("Expectation: Connections should time out after 10 seconds.")
    
    for i in range(30):
        t = threading.Thread(target=connect_and_hold, args=(i, host, port))
        threads.append(t)
        t.start()
        time.sleep(0.1)
        
    for t in threads:
        t.join()
        
    print("Test finished.")

if __name__ == "__main__":
    main()
