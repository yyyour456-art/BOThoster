import os
import time
from config import STORAGE_DIR

running_bots = {}       
file_expiry = {}        
file_owners = {}        
waiting_for_custom = {} 

def delete_file_and_process(filename):
    if filename in running_bots:
        try:
            running_bots[filename].terminate()
        except Exception as e:
            print(f"Termination error: {e}")
        del running_bots[filename]
    
    path = os.path.join(STORAGE_DIR, filename)
    if os.path.exists(path):
        try:
            os.remove(path)
        except Exception as e:
            print(f"File remove error: {e}")
            
    if filename in file_expiry:
        del file_expiry[filename]
    if filename in file_owners:
        del file_owners[filename]

def cleanup_files():
    now = time.time()
    for filename, expiry in list(file_expiry.items()):
        if expiry != -1 and now > expiry:
            delete_file_and_process(filename)
            print(f"🗑️ Expired file deleted: {filename}")
