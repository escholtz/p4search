import threading
import sqlite3
import Queue
import wx

class DBThread(threading.Thread):
	def __init__(self, inputQueue, outputQueue):
		threading.Thread.__init__(self)
		
		self.inputQueue = inputQueue
		self.outputQueue = outputQueue
		
		self.queryType = ""
		self.queryString = ""
		
		self.dbCursor = None
		self.dbConn = None
		
		self.startTime = 0.0
		
		self.setDaemon(True)
		self.start()
		
	def run(self):
		self.connect()
		doneFetch = False
		queryCount = 0
		while 1:
			try:
				# Synchronous query format ["sync", "SELECT * FROM changes", output Queue]
				# Asynchronous query format ["async", "SELECT * FROM changes", output Queue]
				query = self.inputQueue.get(doneFetch)
				
				# Check if the thread has been signaled to close
				if query is None:
					self.outputQueue.put(None)
					break
				
				self.queryType = query[0]
				self.queryString = query[1]
				self.outputQueue = query[2]
				query = query[0]
				doneFetch = False
				#queryCount += 1
				self.dbCursor.execute(self.queryString)
			except Exception:
				if not doneFetch:
					if self.queryType == "async":
						result = self.dbCursor.fetchmany(200)
						self.outputQueue.put([queryCount, result])
						wx.WakeUpIdle() # Triggers wx Idle events
						if len(result) == 0:
							doneFetch = True
					else:
						result = self.dbCursor.fetchall()
						self.outputQueue.put([queryCount, result])
						wx.WakeUpIdle() # Triggers wx Idle events
						doneFetch = True


	def connect(self):
		# Setup sqlite database
		dbConn = sqlite3.connect('p4db')
		dbConn.text_factory = str
		dbCursor = dbConn.cursor()

		# Create the changes table if it doesn't exist
		dbCursor.execute("SELECT name FROM sqlite_master")
		if(dbCursor.fetchone() == None):
			dbCursor.execute("CREATE TABLE changes (client TEXT, user TEXT, date DATETIME, change INT primary key, description TEXT)")
			dbCursor.execute("CREATE INDEX idx ON changes (client, user, date, change, description)")
		
		self.dbCursor = dbCursor
		self.dbConn = dbConn
