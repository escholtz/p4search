import threading
import sqlite3
import Queue
import wx

class DBThread(threading.Thread):
    """
    This thread is used to run SQL queries. It allows the UI to remain
    responsive during queries that may take several seconds.
    (Note: the fetch part of the query is usually the slow part. The execute
    part is comparatively fast.)
    The user communicates with this thread via an input Queue. Queries should be
    put into the input Queue using the form:
      ["sync", "SELECT * FROM changes", output Queue]
      ["async", "SELECT * FROM changes", output Queue]
    """
    
    SQL_CREATE_TABLE = ("CREATE TABLE changes (client TEXT, user TEXT, "
        "date DATETIME, change INT primary key, description TEXT)")
    
    # TODO: Are these the proper indices to create?
    SQL_CREATE_INDEX = ("CREATE INDEX idx ON changes (client, user, date, "
        "change, description)")
    
    def __init__(self, inputQueue):
        threading.Thread.__init__(self)
        
        self._inputQueue = inputQueue
        self._outputQueue = None
        
        self._queryType = ""
        self._queryString = ""
        
        self._sqlCursor = None
        self._sqlConn = None
        
        self.setDaemon(True)
        self.start()
        
    def run(self):
        self._connect()
        doneFetch = False
        while 1:
            try:
                query = self._inputQueue.get(doneFetch)
                
                # Check if the thread has been signaled to close
                if query is None:
                    self._outputQueue.put(None)
                    break
                
                self._queryType = query[0]
                self._queryString = query[1]
                self._outputQueue = query[2]
                doneFetch = False
                self._sqlCursor.execute(self._queryString)
            except Exception:
                if not doneFetch:
                    if self._queryType == "async":
                        result = self._sqlCursor.fetchmany(200)
                        self._outputQueue.put(result)
                        wx.WakeUpIdle() # Triggers wx Idle events
                        if len(result) == 0:
                            doneFetch = True
                    else:
                        result = self._sqlCursor.fetchall()
                        self._outputQueue.put(result)
                        wx.WakeUpIdle() # Triggers wx Idle events
                        doneFetch = True

    def _connect(self):
        # TODO: Try loading database completely into memory
        # Setup sqlite database
        sqlConn = sqlite3.connect('p4db')
        sqlConn.text_factory = str
        sqlCursor = sqlConn.cursor()

        # Create the changes table if it doesn't exist
        sqlCursor.execute("SELECT name FROM sqlite_master")
        if(sqlCursor.fetchone() == None):
            sqlCursor.execute(DBThread.SQL_CREATE_TABLE)
            sqlCursor.execute(DBThread.SQL_CREATE_INDEX)
        
        self._sqlCursor = sqlCursor
        self._sqlConn = sqlConn
