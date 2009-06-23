import P4
import time
import ConfigParser
import Queue
import os

import wx
import wx.lib.mixins.listctrl as ListMix
from wx.lib.embeddedimage import PyEmbeddedImage
from wx.lib.splitter import MultiSplitterWindow
from wx.lib.wordwrap import wordwrap

# Does the graphing
import p4graph
from dbthread import *

import p4sync

# Encoded version of the magnifier icon
magnifier = PyEmbeddedImage(
	"iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABHNCSVQICAgIfAhkiAAAAk1J"
	"REFUOI2VkF9Ik1EYxt9zzvftc479UdNszm/OtKYoNpMarT9EXgRzdtGddFnQRdBNiEHQbeRF"
	"FyV0EQYFg6ggWF0UUagUc2Fhf3Q2aRfODHIunR6+s31np4tmrfEJ9cDLywsPP573QVDUwMBA"
	"FWOsC2PsBAALAGwUCoWviqJMh8PhDGwhBAAQCoU8jprao/uP9bft8fW0uOrs9ZrGViZjk3PP"
	"Hz/8+CP9/WUkEkkaAUgwGKyy2quDJ09fONzc2tbh3m6vxQhLJlm2NjV53PXNnda56Smsqg3J"
	"RCKhlQMw57x7X29/u9WxzV1lUWRUTFWMh9yuHS0Hj5/o5Jx3GyWQcrlc4+6OvSoAwFKGsqUM"
	"sHJTe1eP5/7t642GAF3X7RXmymrOBQAAeBtstrKWxGKayrqu240AmDFGeZ5lAQC8LpvV0FTI"
	"ZxljdCtAKv721RLGmOh5Xig3iIJAH6ZeLzLGUoYASumbu7duzAu6nM4V39gUISBtrGVy4dGb"
	"SYRQwghA0uk0pRvrqy+ePnHUVDuQd9dOi6WywprPa9lnkUdfzp09835oaPBSNBpNqaq6mEql"
	"Vv+u6I/qCCFHEEItQggbQmhNCDFPCPlkNptPhcP3Lg4PX71M6fqDWCw2Y5RmS5lMplan03lt"
	"bCwq+vr6rwQCAf/vF/4FwDlf0TRteWJiHEZGRs/Pzs5Qm80iLywsfP6vJISQXr//wJ14/Jvw"
	"+XyDAL86QACAi2kkAJBLtlxySwAgYYwPKYqiSpI0ns1m36EySOmQso1LfJvlr/8EK/Hiayip"
	"MLwAAAAASUVORK5CYII=")

# Start thread for performing SQL queries
queryQ = Queue.Queue()

# Use this as the background color for panels since it seems to be inconsistent across windows versions
backgroundColor = wx.Color(240,240,240)

# Panel used to display details of a single changelist (the changelist that is selected)
class DescriptionPanel(wx.Panel):
	def __init__(self, parent):
		wx.Panel.__init__(self, parent, style=wx.BORDER_SUNKEN)
		self.SetBackgroundColour(wx.Color(255,255,255))
		self.text = wx.TextCtrl(self, -1, "", style=wx.TE_MULTILINE|wx.TE_READONLY|wx.NO_BORDER|wx.TE_RICH2)
		sizer = wx.BoxSizer(wx.VERTICAL)
		sizer.Add(self.text, 1, wx.EXPAND)
		self.SetSizer(sizer)

# Panel that contains the table of changes and the description window found below it
class ChangeListPanel(wx.Panel):
	def __init__(self, parent):
		wx.Panel.__init__(self, parent, -1)
		
		self.splitter = MultiSplitterWindow(self, style=wx.SP_LIVE_UPDATE)
		self.splitter.SetOrientation(wx.VERTICAL)
		sizer = wx.BoxSizer(wx.VERTICAL)
		
		sizer.Add(self.splitter, 1, wx.EXPAND)
		self.SetSizer(sizer)
		
		p2 = DescriptionPanel(self.splitter)
		
		panel = wx.Panel(self.splitter, -1)
		siz = wx.BoxSizer(wx.VERTICAL)
		self.p1 = ChangesList(panel, p2.text)
		siz.Add(self.p1, 1, wx.EXPAND)
		panel.SetSizer(siz)
		
		self.splitter.AppendWindow(panel, 500)
		
		self.splitter.AppendWindow(p2, 200)

# The table of changes
class ChangesList(wx.ListCtrl, ListMix.ListCtrlAutoWidthMixin):
	def __init__(self, parent, desc=None):
		wx.ListCtrl.__init__(
			self, parent, -1, 
			style=wx.LC_REPORT|wx.LC_VIRTUAL|wx.LC_HRULES|wx.LC_VRULES
			)
		ListMix.ListCtrlAutoWidthMixin.__init__(self)
		
		self.resultCount = None
		self.desc = desc
		self.queryCount = 0
		self.resultQ = Queue.Queue()
		self.Refresh()
		
		self.lastQuery = "SELECT * FROM changes"
		self.orderedBy = "Change"
		self.orderedDescending = False
		self.columns = ["Client", "User", "Date", "Change", "Description"]
		colWidths = [75, 75, 125, 60, 500]
		
		for i in xrange(0, len(self.columns)):
			self.InsertColumn(i, self.columns[i])
			self.SetColumnWidth(i,colWidths[i])
		
		self.Bind(wx.EVT_LIST_COL_CLICK, self.OnColClick, self)
		self.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnItemSelected, self)
		self.Bind(wx.EVT_IDLE, self.OnIdle)
	
	
	def OnIdle(self, event):
		try:
			# Look for results without blocking
			results = self.resultQ.get(False)
			if results != None and len(results[1]) > 0: # and results[0] == self.queryCount
				self.search.extend(results[1])
				self.SetItemCount(len(self.search))
				self.resultCount.SetValue(str(len(self.search)) + " Results")
				event.RequestMore(True)
			else:
				self.resultCount.SetValue(str(len(self.search)) + " Results")
		except Exception:
			return
	
	def OnItemSelected(self, event):
		self.currentItem = event.m_itemIndex
		if self.desc is not None:
			self.desc.SetValue("Change:\t" + str(self.search[self.currentItem][3]) + "\n"
							"Client:\t" + self.search[self.currentItem][0] + "\n"
							"User:\t" + self.search[self.currentItem][1] + "\n"
							"Date:\t" + self.search[self.currentItem][2] + "\n\n"
							"Description:\n" + self.search[self.currentItem][4] + "\n")

	def OnColClick(self, event):
		if self.columns[event.GetColumn()] == self.orderedBy:
			self.orderedDescending = not self.orderedDescending
		else:
			self.orderedBy = self.columns[event.GetColumn()]
			self.orderedDescending = False
		
		#if self.columns[event.GetColumn()] == 'Client' or self.columns[event.GetColumn()] == 'User':
		#	query = self.lastQuery + ' ORDER BY UPPER(' + self.columns[event.GetColumn()] + ')'
		#else:
		query = self.lastQuery + ' ORDER BY ' + self.columns[event.GetColumn()]
		
		if self.orderedDescending:
			query = query + ' DESC'
		
		self.resultQ = Queue.Queue()
		queryQ.put(["async", query, self.resultQ])
		#self.queryCount += 1
		self.SetItemCount(0)
		self.resultCount.SetValue("0 Results")
		self.search = []
		
	def OnGetItemText(self, item, col):
		if self.search != None:
			if col == 4:
				return self.search[item][col].replace('\n',' ')
			return self.search[item][col]
		else:
			return 'Unknown'

	def Refresh(self):
		self.resultQ = Queue.Queue()
		queryQ.put(["async", 'SELECT * FROM changes', self.resultQ]) # ORDER BY change DESC
		#self.queryCount += 1
		self.SetItemCount(0)
		#self.resultCount.SetValue("0 Results")
		self.search = []
	
	def DoSearch(self, searchString):
		# TODO: prevent sql injection problems
		self.lastQuery = searchString
		self.SetItemCount(0)
		self.resultCount.SetValue("0 Results")
		self.resultQ = Queue.Queue()
		queryQ.put(["async", self.lastQuery, self.resultQ])
		#self.queryCount += 1
		self.search = []
		self.SetItemCount(0)
	
# The panel on the left that contains the search box and the search options
class SearchPanel(wx.Panel):
	def __init__(self, parent, id):
		wx.Panel.__init__(self, parent, id)
		box = wx.BoxSizer(wx.VERTICAL)
		
		self.search = wx.SearchCtrl(self, size=(150,-1), style=wx.TE_PROCESS_ENTER)
		box.Add(self.search, 0, wx.ALL|wx.ALIGN_CENTER_HORIZONTAL, 5)
		
		self.searchButton = wx.Button(self, -1, "Search", style=wx.BU_EXACTFIT)
		box.Add(self.searchButton, 0, wx.ALL|wx.ALIGN_CENTER_HORIZONTAL, 0)
		
		self.resultCount = wx.TextCtrl(self, -1, "0 Results",style=wx.TE_READONLY|wx.NO_BORDER|wx.TE_CENTRE)
		self.resultCount.SetBackgroundColour(backgroundColor)
		box.Add(self.resultCount, 0, wx.ALL|wx.ALIGN_BOTTOM|wx.ALIGN_CENTER_HORIZONTAL, 5)
		
		# StaticBox and check boxes for the selecting the columns you want to search
		staticBox = wx.StaticBox(self, -1, "Search Columns")
		bsizer = wx.StaticBoxSizer(staticBox, wx.VERTICAL)
		
		box.Add(bsizer, 0, wx.ALL|wx.ALIGN_CENTER_HORIZONTAL, 10)
		
		border = wx.BoxSizer(wx.VERTICAL)
		bsizer.Add(border, 0, wx.LEFT | wx.RIGHT, 10)
		
		self.CheckBoxes = []
		
		cb = wx.CheckBox(self, -1, "Client")
		border.Add(cb, 0, wx.ALL, 5)
		self.CheckBoxes.append(cb)
		
		cb = wx.CheckBox(self, -1, "User")
		cb.SetValue(True)
		border.Add(cb, 0, wx.ALL, 5)
		self.CheckBoxes.append(cb)
		
		cb = wx.CheckBox(self, -1, "Date")
		border.Add(cb, 0, wx.ALL, 5)
		self.CheckBoxes.append(cb)
		
		cb = wx.CheckBox(self, -1, "Change")
		border.Add(cb, 0, wx.ALL, 5)
		self.CheckBoxes.append(cb)
		
		cb = wx.CheckBox(self, -1, "Description")
		cb.SetValue(True)
		border.Add(cb, 0, wx.ALL, 5)
		self.CheckBoxes.append(cb)
		
		# Other settings
		staticBox = wx.StaticBox(self, -1, "Settings")
		bsizer = wx.StaticBoxSizer(staticBox, wx.VERTICAL)
		
		box.Add(bsizer, 0, wx.ALL|wx.ALIGN_CENTER_HORIZONTAL, 10)
		
		border = wx.BoxSizer(wx.VERTICAL)
		bsizer.Add(border, 0, wx.LEFT | wx.RIGHT, 10)
		
		self.SubstringsCB = wx.CheckBox(self, -1, "Search Substrings")
		self.SubstringsCB.SetValue(True)
		border.Add(self.SubstringsCB, 0, wx.ALL, 5)
		
		self.updateButton = wx.Button(self, -1, "Sync", style=wx.BU_EXACTFIT)
		box.Add(self.updateButton, 0, wx.ALL|wx.ALIGN_BOTTOM|wx.ALIGN_CENTER_HORIZONTAL, 2)
		
		self.graphButton = wx.Button(self, -1, "Graph", style=wx.BU_EXACTFIT)
		box.Add(self.graphButton, 0, wx.ALL|wx.ALIGN_BOTTOM|wx.ALIGN_CENTER_HORIZONTAL, 2)
		
		self.aboutButton = wx.Button(self, -1, "About", style=wx.BU_EXACTFIT)
		box.Add(self.aboutButton, 0, wx.ALL|wx.ALIGN_BOTTOM|wx.ALIGN_CENTER_HORIZONTAL, 2)
		
		self.Bind(wx.EVT_BUTTON, self.OnGraph, self.graphButton)
		self.Bind(wx.EVT_BUTTON, self.OnAbout, self.aboutButton)
		
		self.SetBackgroundColour(backgroundColor)
		
		self.SetSizer(box)
		
		self.win = None
		
	def OnAbout(self, evt):
		info = wx.AboutDialogInfo()
		info.Name = "Perforce Changelist Search"
		info.Version = "0.2"
		info.Copyright = "Developed by Eddie Scholtz (2009)"
		info.Description = wordwrap(
			"\nQuestions? Comments? Requests? Bugs?\n\n			 eddie@eddiescholtz.com",
			350, wx.ClientDC(self))
		info.WebSite = ("http://www.EddieScholtz.com", "http://www.EddieScholtz.com")
		about = wx.AboutBox(info)

	def OnGraph(self, evt):
		if self.win is None:
			self.win = p4graph.GraphFrame(self, -1, "Perforce Graph", queryQ, style = wx.DEFAULT_FRAME_STYLE)
			self.win.Show(True)
		else:
			self.win.Show(True)

# The dialog that pops up when the connection button is clicked
class ConnectionDialog(wx.Dialog):
	def __init__(self, parent, ID, title):
		wx.Dialog.__init__(self, parent, ID, title)
		
		outer = wx.BoxSizer(wx.VERTICAL)
		
		# Flags and timer used for sync process
		self.UpdatePressed = False
		self.ReadyToSync = False
		self.CloseAfterTimer = False
		self.Timer = 0.0
		self.syncQ = Queue.Queue()
		
		# TODO: This is just copied from the top
		try:
			config = ConfigParser.ConfigParser()
			config.read('settings.ini')
			server = config.get("Perforce", "Server")
			username = config.get("Perforce", "Username")
			depot = config.get("Perforce", "Depot")
			#saveDir = config.get("Perforce","SaveDir")
		except Exception:
			server = "Name:Port"
			username = ""
			depot = "//..."
			#saveDir = os.getcwd()
				
		staticBox = wx.StaticBox(self, -1)
		bsizer = wx.StaticBoxSizer(staticBox, wx.VERTICAL)
		
		sizer = wx.GridBagSizer(5, 5)
		
		bsizer.Add(sizer, 0, wx.ALL, border=5)
		outer.Add(bsizer, 0, flag=wx.ALIGN_CENTER|wx.ALL, border=5)
		
		label = wx.StaticText(self, -1, "Server:")
		sizer.Add(label, (0,0), flag=wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_RIGHT|wx.ALL, border=2)

		self.Server = wx.TextCtrl(self, -1, server, size=(180,-1))
		sizer.Add(self.Server, (0,1), flag=wx.ALIGN_CENTER|wx.ALL, border=2)

		label = wx.StaticText(self, -1, "Username:")
		sizer.Add(label, (1,0), flag=wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_RIGHT|wx.ALL, border=2)

		self.Username = wx.TextCtrl(self, -1, username, size=(180,-1))
		sizer.Add(self.Username, (1,1), flag=wx.ALIGN_CENTER|wx.ALL, border=2)

		label = wx.StaticText(self, -1, "Password:")
		sizer.Add(label, (2,0), flag=wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_RIGHT|wx.ALL, border=2)

		self.Password = wx.TextCtrl(self, -1, "", size=(180,-1), style=wx.TE_PASSWORD)
		sizer.Add(self.Password, (2,1), flag=wx.ALIGN_CENTER|wx.ALL, border=2)
		
		label = wx.StaticText(self, -1, "Depot:")
		sizer.Add(label, (3,0), flag=wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_RIGHT|wx.ALL, border=2)

		self.Depot = wx.TextCtrl(self, -1, depot, size=(180,-1))
		sizer.Add(self.Depot, (3,1), flag=wx.ALIGN_CENTER|wx.ALL, border=2)
		
		cfu = wx.BoxSizer(wx.HORIZONTAL)
		bsizer.Add(cfu, flag=wx.ALIGN_CENTER_HORIZONTAL|wx.ALL, border=2)
		
		#label = wx.StaticText(self, -1, "Save Directory:")
		#sizer.Add(label, (4,0), flag=wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_RIGHT|wx.ALL, border=2)
		
		#self.SaveDir = wx.TextCtrl(self, -1, saveDir, size=(180,-1))
		#sizer.Add(self.SaveDir, (4,1), flag=wx.ALIGN_CENTER|wx.ALL, border=2)
		
		#b = wx.Button(self, -1, "Change")#, (50,50))
		#self.Bind(wx.EVT_BUTTON, self.OnButton, b)	
		
		self.testConnection = wx.TextCtrl(self, -1, "", size=(300, -1), style=wx.TE_READONLY|wx.NO_BORDER|wx.TE_CENTRE)
		self.testConnection.SetBackgroundColour(backgroundColor)
		bsizer.Add(self.testConnection, flag=wx.ALIGN_CENTER|wx.ALL, border=2)
		
		buttons = wx.BoxSizer(wx.HORIZONTAL)
		bsizer.Add(buttons, flag=wx.ALIGN_CENTER|wx.ALL, border=2)

		self.updateButton = wx.Button(self, -1, "Sync", style=wx.BU_EXACTFIT)
		buttons.Add(self.updateButton, flag=wx.ALIGN_CENTER|wx.ALL, border=2)
		
		self.cancelButton = wx.Button(self, -1, "Cancel", style=wx.BU_EXACTFIT)
		buttons.Add(self.cancelButton, flag=wx.ALIGN_CENTER|wx.ALL, border=2)
		
		self.Bind(wx.EVT_BUTTON, self.OnUpdate, self.updateButton)
		self.Bind(wx.EVT_BUTTON, self.OnCancel, self.cancelButton)
		self.Bind(wx.EVT_IDLE, self.OnIdle)
		
		sizer.AddGrowableRow(5)
		sizer.AddGrowableRow(6)
		
		self.SetBackgroundColour(backgroundColor)

		self.SetSizer(outer)
		outer.Fit(self)
		
	def OnCancel(self, event):
		self.EndModal(wx.ID_CANCEL)
		
	def OnUpdate(self, event):
		self.updateButton.Disable()
		self.testConnection.SetValue("Syncing...")
		
		config = ConfigParser.ConfigParser()
		config.add_section("Perforce")
		
		config.set("Perforce", "Username", self.Username.GetValue())
		config.set("Perforce", "Server", self.Server.GetValue())
		config.set("Perforce", "Password", self.Password.GetValue())
		
		depot = self.Depot.GetValue()
		if len(depot) == 0:
			depot = "//..."
		config.set("Perforce", "Depot", depot)
		file = open("settings.ini", "w")
		
		'''
		saveDir = self.SaveDir.GetValue()
		if len(saveDir) == 0:
			saveDir = os.cwd()
		elif saveDir[0] == '%':
			index = saveDir.rfind('%')
			var = saveDir[1:index]
			saveDir = os.environ[var]
			if len(saveDir) > index:
				saveDir += saveDir[index+1:]
			
			print saveDir
			#print foo
		config.set("Perforce", "SaveDir", saveDir)
		'''
		
		config.write(file)
		file.close()
		
		self.thread = p4sync.SyncThread(self.syncQ)

	def OnIdle(self, event):
		#result = None
		try:
			if self.thread is not None:
				result = self.syncQ.get(False)
				self.thread.join()
				self.thread = None
				
				if result == 1:
					self.testConnection.SetValue("Failed.")
				else:
					self.testConnection.SetValue("Received " + str(result - 2) + " new changes.")
					self.CloseAfterTimer = True
					self.Timer = time.time()			
				self.updateButton.Enable()
			else:
				if self.CloseAfterTimer and time.time() - self.Timer > 2.0:
					self.CloseAfterTimer = False
					self.EndModal(wx.ID_OK)
				elif self.CloseAfterTimer:
					event.RequestMore(True)
		except Exception:
			return
		
class MainFrame(wx.Frame):
	def __init__(self, parent, id, title):
		wx.Frame.__init__(self, parent, id, title, size=(1050, 700), pos=(0,0))

		panel = wx.Panel(self, -1)
		self.SearchPanel = SearchPanel(panel, -1)

		box = wx.BoxSizer(wx.HORIZONTAL)
		box.Add(self.SearchPanel, 0, flag=wx.EXPAND, border=5)
		
		foo = ChangeListPanel(panel)
		self.virtlist = foo.p1
		self.virtlist.resultCount = self.SearchPanel.resultCount
		box.Add(foo, 1, flag=wx.EXPAND, border=5)

		panel.SetSizer(box)
		
		self.Bind(wx.EVT_TEXT_ENTER, self.OnDoSearch, self.SearchPanel.search)
		self.Bind(wx.EVT_BUTTON, self.OnDoSearch, self.SearchPanel.searchButton)
		self.Bind(wx.EVT_SEARCHCTRL_CANCEL_BTN, self.OnCancelSearch, self.SearchPanel.search)
		self.Bind(wx.EVT_BUTTON, self.OnUpdate, self.SearchPanel.updateButton)
		
		self.SearchPanel.resultCount.SetValue(str(len(self.virtlist.search)) + " Results")
		
		self.SetIcon(magnifier.GetIcon())
		
		self.SetMinSize((640,480))

		self.Show(True)
		
	def OnDoSearch(self, event):
		self.virtlist.SetItemCount(0)
		
		searchString = self.SearchPanel.search.GetValue()
		sqlQuery = 'SELECT * FROM changes'
		
		if len(searchString) > 0:
			sqlQuery += ' WHERE '		
			boxChecked = False
			for cb in self.SearchPanel.CheckBoxes:
				if cb.GetValue():
					if self.SearchPanel.SubstringsCB.GetValue():
						blarg = '%' + searchString + '%'
					else:
						blarg = searchString
					sqlQuery += cb.GetLabelText() + ' LIKE \'' + blarg + '\' OR '
					boxChecked = True
			
			if not boxChecked:
				return
			else:
				# remove the last ' OR '
				sqlQuery = sqlQuery[:-4]

		self.virtlist.DoSearch(sqlQuery)
		if len(searchString) > 0:
			self.SearchPanel.search.ShowCancelButton(True)
		else:
			self.SearchPanel.search.ShowCancelButton(False)
	
	def OnCancelSearch(self, event):
		self.virtlist.SetItemCount(0)
		self.virtlist.DoSearch('SELECT * FROM changes')
		#self.SearchPanel.resultCount.SetValue(str(len(self.virtlist.search)) + " Results")
		self.SearchPanel.search.ShowCancelButton(False)
		
	def OnUpdate(self, event):
		dlg = ConnectionDialog(self, -1, "Perforce Connection")
		dlg.CenterOnParent()
		val = dlg.ShowModal()
		
		if val == wx.ID_OK:
			self.virtlist.SetItemCount(0)
			self.virtlist.Refresh()
			self.SearchPanel.resultCount.SetValue(str(len(self.virtlist.search)) + " Results")
		
		dlg.Destroy()


class MyApp(wx.App):
	def __init__(self):
		wx.App.__init__(self, redirect=False)
		frame = MainFrame(None, -1, 'Perforce Changelist Search')
		frame.CentreOnScreen()
		DBThread(queryQ, None)
		frame.Show(True)


app = MyApp()
app.MainLoop()