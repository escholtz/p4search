import sqlite3
import matplotlib.pylab as plt
from datetime import date
import wx
import Queue

# The window that pops up when the graph button is clicked
class GraphFrame(wx.MiniFrame):
    def __init__(
            self, parent, ID, title, queryQ, pos=wx.DefaultPosition,
            size=wx.DefaultSize, style=wx.DEFAULT_FRAME_STYLE
            ):

        wx.MiniFrame.__init__(self, parent, ID, title, pos, (810,670), style)
        
        self.queryQ = queryQ

        panel = wx.Panel(self, -1)
        panel.SetBackgroundColour(wx.Color(255,255,255))
        
        self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)
        
        mainBox = wx.BoxSizer(wx.VERTICAL)
        filterBox = wx.BoxSizer(wx.HORIZONTAL)
        
        text = wx.StaticText(panel, -1, "Display checkins by User: ")
        filterBox.Add(text, 0, wx.ALL|wx.ALIGN_CENTER, 0)
        
        # Figure out what years we have checkins for
        # Do we want the min, max instead so we can generate a range?
        query = "SELECT DISTINCT strftime(\"%Y\", date) FROM changes"
        self.resultQ = Queue.Queue()
        self.queryQ.put(['sync', query, self.resultQ])
        results = self.resultQ.get(True)
        data = results[1]
        years = ['All']
        for ele in data:
            years.append(ele[0])
        
        query = "SELECT DISTINCT user FROM changes"
        self.queryQ.put(['sync', query, self.resultQ])
        results = self.resultQ.get(True)
        data = results[1]
        users = []
        for ele in data:
            users.append(ele[0])
        users.sort()
        users.insert(0, 'All')
        
        self.userCombo = wx.ComboBox(panel, -1, size=(140, -1), choices=users, style=wx.CB_READONLY)
        self.userCombo.SetStringSelection('All')
        filterBox.Add(self.userCombo, 0, wx.ALL|wx.ALIGN_CENTER, 0)
        
        text = wx.StaticText(panel, -1, " during Year: ")
        filterBox.Add(text, 0, wx.ALL|wx.ALIGN_CENTER, 0)
        
        self.yearCombo = wx.ComboBox(panel, -1, size=(50, -1), choices=years, style=wx.CB_READONLY)
        self.yearCombo.SetStringSelection('All')
        filterBox.Add(self.yearCombo, 0, wx.ALL|wx.ALIGN_CENTER, 0)
        
        text = wx.StaticText(panel, -1, " grouped by: ")
        filterBox.Add(text, 0, wx.ALL|wx.ALIGN_CENTER, 0)
        
        xaxis = ['Year', 'Month', 'Weekday', 'Hour']
        self.xaxisCombo = wx.ComboBox(panel, -1, size=(80, -1), choices=xaxis, style=wx.CB_READONLY)
        self.xaxisCombo.SetStringSelection('Year')
        filterBox.Add(self.xaxisCombo, 0, wx.ALL|wx.ALIGN_CENTER, 0)
        
        button = wx.Button(panel, 0, "Generate")
        filterBox.Add(button, -1, wx.LEFT|wx.ALIGN_CENTER, 40)
        self.Bind(wx.EVT_BUTTON, self.OnGenerate, button)
        
        button = wx.Button(panel, -1, "Save")
        filterBox.Add(button, 0, wx.LEFT|wx.ALIGN_CENTER, 10)
        self.Bind(wx.EVT_BUTTON, self.OnSave, button)
        
        self.picture = wx.StaticBitmap(panel)
        self.Graph('temp.png', 'all', 'all', 'year')
        self.bitmap = wx.Bitmap('temp.png')
        self.picture.SetFocus()
        self.picture.SetBitmap(self.bitmap)
        
        mainBox.Add(filterBox, 0, wx.ALL|wx.ALIGN_CENTER, 5)
        mainBox.Add(self.picture, 0, wx.ALL|wx.ALIGN_CENTER, 5)
        panel.SetSizer(mainBox)

        self.SetMinSize((810,670))
        self.SetMaxSize((810,670))
    
    def OnSave(self, event):
        wildcard = "PNG File (*.png)|*.png|All files (*.*)|*.*"
        dlg = wx.FileDialog(self, message="Save file as ...", defaultFile="graph.png", style=wx.SAVE, wildcard=wildcard)
        dlg.SetFilterIndex(0)
        
        if dlg.ShowModal() == wx.ID_OK:
            path = dlg.GetPath()
            filename = dlg.GetFilename()
            shutil.copyfile('temp.png', path)
        dlg.Destroy()
    
    def OnGenerate(self, event):
        self.Graph('temp.png', self.yearCombo.GetValue().lower(), self.userCombo.GetValue().lower(), self.xaxisCombo.GetValue().lower())
        self.bitmap = wx.Bitmap('temp.png')
        self.picture.SetBitmap(self.bitmap)

    def OnCloseWindow(self, event):
        self.GetParent().win = None
        self.Destroy()
    
    # Generates a graph of a Perforce database using matplotlib.
    # Arguments:
    #   filename - a string specifying what the graph should be saved as
    #   year - a string. only include changelists from this year as datapoints. 'all' includes all years.
    #   developer - a string. only include changelists submitted by this user. 'all' includes all users.
    #   xaxis - possible values: 'year', 'month', 'weekday', 'hour'
    def Graph(self, filename, year, user, xaxis):

        # Build the SQL query
        query = "SELECT strftime(\""
        
        # We only care about the portion of the date the graph is based on. (year, month, weekday, or hour)
        if xaxis == 'year':
            query += '%Y'
        elif xaxis == 'month':
            query += '%m'
        elif xaxis == 'weekday':
            query += '%w'
        elif xaxis == 'hour':
            query += '%H'
        
        query += "\", date) FROM changes"
        
        # Filters by user and date
        if user != 'all' or year != 'all':
            query += ' WHERE'
        
        if user != 'all':
            query += ' user=\'' + user + '\''
            if year != 'all':
                query += ' AND '
        
        if year != 'all':
            query += ' date >= \'' + year + '-01-01 00:00:00\' AND date <= \'' + year + '-12-31 23:59:59\''
        
        # Execute the SQL query
        self.queryQ.put(['sync', query, self.resultQ])
        results = self.resultQ.get(True)
        data = results[1]
        
        # Setup bins that we sort the data into
        bins = []
        if xaxis == 'weekday':
            labels = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
            for i in xrange(0, 7):
                bins.append(0)
        elif xaxis == 'hour':
            labels = ['12am', '', '', '3am', '', '', '6am', '', '', '9am', '', '', '12pm', '', '', '3pm', '', '', '6pm', '', '', '9pm', '', '', '12am' ]
            # I think hour range is technically 00-24, not sure why
            for i in xrange(0, 25):
                bins.append(0)
        elif xaxis == 'month':
            labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
            for i in xrange(0, 12):
                bins.append(0)
        
        # Loop over the change lists returned by 
        for ele in data:
            val = int(ele[0])
            
            # Sort years into bins where bin[0] stores the current year, bin[1] stores last year, etc.
            if xaxis == 'year':
                val = date.today().year - val
                if val >= 0:
                    while len(bins) <= val:
                        bins.append(0)
            elif xaxis == 'month':
                val -= 1
            
            bins[val] += 1
        
        # Generate labels for year graph
        if xaxis == 'year':
            labels = []
            for i in xrange(0, len(bins)):
                labels.append( str(date.today().year - i) )
            # Reverse the order that year values and labels are stored in
            labels.reverse()
            bins.reverse()
        
        
        sum = 0
        for i in bins:
            sum += i
        
        if sum > 0:
            for i in xrange(0, len(bins)):
                bins[i] = float(bins[i]) / float(sum)
        
        # Alternate bar colors between two shades of blue
        colors = []
        for i in range(0, len(bins)):
            if i % 2 == 0:
                colors.append('#4D89F9')
            else:
                colors.append('#C6D9FD')

        xaxis = xaxis[0].upper() + xaxis[1:]
        plt.clf()
        
        if xaxis == 'Hour':
            align = 'edge'
        else:
            align = 'center'
        
        plt.bar(left=range(0,len(bins)), height=bins, align=align, linewidth=1, color=colors)
        plt.xlabel(xaxis)
        plt.ylabel('% of Checkins (Matching Filters)')
        plt.xlim(-1, len(bins))
        plt.title('Checkins by User: ' + user + ' during Year: ' + year + ' (Sample Size=' + str(len(data)) +')')
        plt.xticks(range(0,len(labels)), labels)
        plt.savefig(filename)