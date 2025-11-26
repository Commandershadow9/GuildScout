import fcntl
import os
import sys
from pathlib import Path
from typing import Optional

class SingleInstanceLock:
    """
    Ensures that only one instance of the application is running using a file lock.
    """

    def __init__(self, lock_file_name: str = "guildscout.lock"):
        self.lock_file_path = Path(lock_file_name).absolute()
        self.fp: Optional[object] = None

    def acquire(self) -> bool:
        """
        Attempt to acquire the lock.
        Returns True if successful, False if another instance is already running.
        """
        try:
            self.fp = open(self.lock_file_path, 'a+')
            
            # Try to acquire an exclusive lock. 
            # LOCK_NB means non-blocking: raise BlockingIOError if locked.
            fcntl.flock(self.fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            
            # If successful, write the PID
            self.fp.seek(0)
            self.fp.truncate()
            self.fp.write(f"{os.getpid()}\n")
            self.fp.flush()
            
            return True
            
        except (BlockingIOError, IOError):
            # Lock is held by another process
            if self.fp:
                self.fp.close()
                self.fp = None
            return False

    def release(self):
        """
        Release the lock and remove the file.
        """
        if self.fp:
            try:
                # Unlock
                fcntl.flock(self.fp.fileno(), fcntl.LOCK_UN)
                self.fp.close()
                self.fp = None
                
                # Remove the file
                if self.lock_file_path.exists():
                    self.lock_file_path.unlink()
            except Exception as e:
                print(f"Warning: Failed to release lock: {e}")
