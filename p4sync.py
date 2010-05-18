import time
import ConfigParser
import P4
import sqlite3
import threading

# Thread that connects to Perforce server, grabs changelists, and inserts
# them into the local database
class SyncThread(threading.Thread):
    def __init__(self, syncQ, password):
        threading.Thread.__init__(self)
        self.syncQ = syncQ
        self.password = str(password)
        self.setDaemon(True)
        self.start()
        
    def run(self):
        try:
            config = ConfigParser.ConfigParser()
            config.read('settings.ini')
            server = config.get("Perforce", "Server")
            username = config.get("Perforce", "Username")
            depot = config.get("Perforce", "Depot")

            p4 = P4.P4()
            p4.user = username
            p4.password = self.password
            p4.port = server
            
            connected = False
            p4.connect()
            connected = True
            
            p4.run_login()
            
            # Setup sqlite database connection
            dbConn = sqlite3.connect('p4db')
            dbConn.text_factory = str
            dbCursor = dbConn.cursor()
            
            # Check if we have any changes
            query = "SELECT MAX(change) FROM changes"
            dbCursor.execute(query)
            result = dbCursor.fetchone()
            
            localMaxCL = 0
            if result[0] is not None:
                localMaxCL = result[0]

            p4changes = p4.run("changes","-l","-m 1",depot)
            if p4changes is None:
                # Error - changes command failed
                self.syncQ.put([-1, "Failed. Depot specified correctly?"])
                return

            # find out how many new changelists there are
            serverMaxCL = int(p4changes[0]['change'])
            newCLCount = serverMaxCL - localMaxCL
            
            if newCLCount > 0:
                # grab new changelists and insert them
                arg = "-m " + str(newCLCount)
                p4changes = p4.run("changes", "-l", arg, depot)
                
                # Reset so we can store the actual number of new changelists
                # (There are gaps and some changelists are pending)
                newCLCount = 0
                if p4changes is not None:
                    for change in p4changes:
                        if change['status'] == 'submitted':
                            newCLCount += 1
                            dbCursor.execute("INSERT INTO changes VALUES (?,?,?,?,?)", (change['client'], change['user'], time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(change['time']))), str(change['change']), change['desc']))            
                    dbConn.commit()
        except Exception, inst:
            if not connected:
                self.syncQ.put([-1, "Connect to server failed."])
            for e in p4.errors:
                self.syncQ.put([-1, e])
                return
            print Exception
            print inst
            self.syncQ.put([-1, "Failed."])
            return

        self.syncQ.put([newCLCount, ""])
        return