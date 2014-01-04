#!/usr/bin/python
import cmd
import os
import time
import readline
import threading
import paramiko
import socket
import ConfigParser




# split items in command line into array
def SplitItems(line):
	line = line.strip()
	while line.find('  ') != -1:
		line = line.replace('  ', ' ')
	return filter(lambda x: bool(x), line.split(' '))



# return array of NodeConfig for all nodes in the configuration file
def ParseConfigINI(ConfigFile):
	nodes = []
	config = ConfigParser.ConfigParser()
	config.read([ConfigFile])

	for Node in config.sections():
		nodes.append(
			NodeConfig(
				Name = Node,
				Address = config.get(Node, 'Address'),
				Username = config.get(Node, 'Username'),
				#Password = config.get(Node, 'Password'),
				#Port = config.get(Node, 'Port'),
				))
	return nodes

# command with output
class Command(object):
	def __init__(self, ssh, command):
		self._ssh = ssh
		self._command = command
		self._ready = False
		self._output = []

	def run(self):
		if self._ready:
			return
		stdin, stdout, stderr = self._ssh.exec_command(self._command)
		self._output = map(lambda x: x.rstrip(), stdout.readlines())
		self._ready = True

	def fail(self):
		self._ready = True

	def output(self):
		return self._output

	def ready(self):
		return self._ready

# configuration for ssh node
class NodeConfig(object):
	def __init__(self, **config):
		for item in ('Name', 'Address', 'Group', 'Username', 'Password'):
			setattr(self, item, config.get(item))
		self.Port = int(config.get('Port', 22))
		self.Auto = bool(config.get('Auto'))


# node thread
class Node(threading.Thread):
	# class constructor
	def __init__(self, config):
		threading.Thread.__init__(self)
		self.config = config

		self._connected = False
		self._connecting = False
		self._shutdown = False
		self._commands = []

		# start thread
		self.start()
		
	# request connect
	def connect(self):
		if self._connected or self._connecting:
			return

		self._connecting = True

	def _connect(self):
		if self._connected:
			return

		if self._connecting:
			self.ssh = paramiko.SSHClient()
			self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
			try:
				self.ssh.connect(
					self.config.Address,
					username = self.config.Username,
					password = self.config.Password,
					#look_for_keys = True,
					allow_agent = True,
					)
			except socket.error, e:
				print 'Connect error:', e
				return

			self._connected = True
			self._connecting = False

	# disconnect node
	def disconnect(self):
		if not self._connected:
			return

		self.ssh.close()
		self._connected = False

	# run shell command
	def shrun(self, cmd):
		if not self._connected:
			return False
		self._commands.append(
			Command(
				self.ssh,
				cmd))
		return True

	# wait for last command to complete
	def shwait(self):
		while len(filter(lambda x: not x.ready(), self._commands)):
			time.sleep(0.1)

	# run all pending commands in queue
	def run_command(self):
		for cmd in filter(lambda x: not x.ready(), self._commands):
			try:
				cmd.run()
			except:
				print 'Error running command {}'.format(cmd)
				cmd.fail()

	# exit from thread
	def exit(self):
		self._shutdown = True


	def connected(self):
		return self._connected
		
	# thread main loop
	def run(self):
		while not self._shutdown:
			self._connect()
			if self._connected:
				self.run_command()
			time.sleep(0.1)

	# return last command output
	def last_cmd_output(self):
		return self._commands[-1].output()




# fix method docstrings by removing leading tabs
def docfix(method):
	def callback(*args, **kwarg):
		return method(*args, **kwarg)

	doclines = map(
		lambda x: x.replace('\t\t', '', 1),
		method.__doc__.split('\n'))
	callback.__doc__ = '\n'.join(doclines[1:-1])
	
	return callback


# command processor
class Pash(cmd.Cmd):
	def __init__(self):
		cmd.Cmd.__init__(self)
		#self.prompt = '\001\033[00;36m\002pash>\001\033[0m\002 '
		self.SetPrompt()
		self.nodes = []
		
		self.confdir = os.path.join(os.path.expanduser('~'), '.pash')
		self.histfile = os.path.join(self.confdir, 'history')
		if not os.path.isdir(self.confdir):
			os.makedirs(self.confdir)

	
	# set colored prompt
	def SetPrompt(self, name=None):
		self.prompt = '\001\033[00;36m\002pash>\001\033[0m\002 '
		if name:
			self.prompt = '\001\033[00;36m\002pash@{}>\001\033[0m\002 '.format(name)


	# get list of platform names configured in .ini files
	def BundleNames(self):
		Root = os.path.abspath(os.path.join(os.path.expanduser('~'), '.pash'))
		Bundles = []
		for DirPath, DirNames, FileNames in os.walk(Root):
			for FileName in FileNames:
				if FileName.endswith('.ini'):
					Bundles.append(FileName[:-4])
		return Bundles


	def do_use(self, line):
		'''
		Usage: use platform

		(Re)load configuration from local file or remote server;
		This command makes the daemon to read nodes.xml and hosts
		files either from local files in current directory or
		from a remote host.
		'''
		Items = SplitItems(line)
		# disconnect nodes currently connected group (if any)
		for node in self.nodes:
			node.disconnect()
		for node in self.nodes:
			node.exit()
		self.nodes = []

		SearchName = '.'.join((Items[0], 'ini'))
		IniFile = []
		Root = os.path.abspath(os.path.join(os.path.expanduser('~'), '.pash'))
		for DirPath, DirNames, FileNames in os.walk(Root):
			if SearchName in FileNames:
				IniFile = os.path.join(DirPath, SearchName)
				self.platform = Items[0]
				break

		if IniFile:
			print 'Loading platform configuration...'
			for NodeConfig in ParseConfigINI(IniFile):
				node = Node(NodeConfig)
				node.connect()
				self.nodes.append(node)
				#self.nodes.append(Node(NodeConfig))
				self.SetPrompt(Items[0])
			print

		

	def complete_use(self, text, line, begidx, endidx):
		return filter(lambda x: x.startswith(text), self.BundleNames())


	# make sure history file is used
	def cmdloop(self):
		# load command history
		if os.path.exists(self.histfile):
			readline.read_history_file(self.histfile)

		# automatically connect nodes at startup
		for node in self.nodes:
			if node.config.Auto:
				self.selected.append(node)
				node.connect()

		cmd.Cmd.cmdloop(self)

		# save command history
		readline.write_history_file(self.histfile)


	@docfix
	def do_shell(self, line):
		'''
		Usage: shell command

			Execute a shell command on all selected nodes. Further, command will only
			be executed on connected nodes only.
			As a shortcut to "shell" command, "!" can be used (without quotes).
		'''
		for node in filter(lambda n: n.connected(), self.nodes):
			node.shrun(line)

		for node in filter(lambda n: n.connected(), self.nodes):
			node.shwait()

		# calculate node names length
		maxlen = max(map(lambda x: len(x.config.Name), self.nodes)) + 14
		template = '{{:>{}}}: {{}}'.format(maxlen)

		# print command output
		for node in filter(lambda n: n.connected(), self.nodes):
			for line in node.last_cmd_output():
				print template.format('\033[0;35m{}\033[0m'.format(node.config.Name), line)



	# connect to a node or a group
	@docfix
	def do_connect(self, line):
		'''
		Usage: connect [node1] [node2] [GROUP1] [GROUP2] [...]

			Connect nodes that are configured but no ssh connection
			has been made yet.
			The reason node is not yet connected can either be that
			the node has not been configured to autoconnect at startup
			or because a new node has just been added with the "add"
			command.
		'''
		items = SplitItems(line)

		for item in items:
			for node in self.nodes:
				if item == node.config.Name:
					print 'connecting to node:', node.config.Name
					node.connect()

	# disconnect from node
	@docfix
	def do_disconnect(self, line):
		'''
		Usage: disconnect [node1] [node2] [GROUP1] [GROUP2] [...]

			Terminate ssh connection to nodes.
		'''
		items = SplitItems(line)

		for item in items:
			for node in self.nodes:
				if item == node.config.Name:
					print 'disconnecting node:', node.config.Name
					node.disconnect()


	def PrintHeader(self, Header):
		print Header
		print '=' * len(Header)


	def ListBundles(self):
		self.PrintHeader('Available Node Groups')
		for Bundle in self.BundleNames():
			print '  {}'.format(Bundle)


	def ListNodes(self):
		if not len(self.nodes):
			print 'No nodes configured.'
			return

		hsize = max(
			max(
				map(
					lambda x: len(x.config.Name),
					self.nodes)),
			8)
		asize = max(
			max(
				map(
					lambda x: len(x.config.Address),
					self.nodes)),
			7)

		template = '{:>%d}  {:<%d}  {:<3}' % (hsize, asize)
		print template.format('Hostname', 'Address', 'CON')
		print template.format('-'*hsize, '-'*asize, '-'*3, '-'*3, '-'*3)
		for node in self.nodes:
			print template.format(
				node.config.Name,
				node.config.Address,
				{True:'Yes', False:'No'}[node.connected()],
				)


	@docfix
	def do_list(self, line):
		'''
		Usage: list [bundles]
		
			Display a list of all bundles or all nodes 
			within the currently selected bundle and
			node connection status.

			When displaying nodes within a bundle, the
			following fields are shown:
				Hostname	Name (or hostname) of the node
				Address		Node IP address
				CON		Connection status - ("Yes" for connected,
						"No" for disconnected)
		'''
		Items = SplitItems(line)

		# list groups
		if not len(self.nodes) or (len(Items) > 0 and 'bundles'.startswith(Items[0].lower())):
			self.ListBundles()
			return

		self.ListNodes()


	# exit main loop
	def exit(self):
		# shutdown threads
		for node in self.nodes:
			node.exit()
		print
		return True


	# ignore empty lines
	def emptyline(self):
		pass


	# default command action
	def default(self, line):
		if line == 'EOF':
			return self.exit()

		rest = ''
		command = line
		if line.find(' ') != -1:
			command, rest = line.split(' ', 1)

		# short commands
		PossibleCommands = filter(
			lambda x: x.startswith(command),
			map(lambda x: x[3:], filter(lambda x: x.startswith('do_'), dir(self))))

		if len(PossibleCommands) == 1:
			Command = getattr(self, 'do_{}'.format(PossibleCommands.pop()))
			return Command(rest)
		if len(PossibleCommands):
			print '*** Unknown syntax: {}'.format(command)
			print '    Maybe you meant one of these: {}'.format(','.join(PossibleCommands))
			return

		# unknown command
		print '*** Unknown syntax: {}'.format(command)


# main program
if __name__ == '__main__':
	p = Pash()
	p.cmdloop()
