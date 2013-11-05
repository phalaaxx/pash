#!/usr/bin/python
import cmd
import os
import time
import readline
import threading
import paramiko
import socket


# 
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
		self.prompt = '\001\033[00;36m\002pash>\001\033[0m\002 '
		self.nodes = []
		self.selected = []
		
		self.confdir = os.path.join(os.path.expanduser('~'), '.pash')
		self.histfile = os.path.join(self.confdir, 'history')
		self.nodesconf = os.path.join(self.confdir, 'nodes.conf')
		if not os.path.isdir(self.confdir):
			os.makedirs(self.confdir)



	def load_nodes(self):
		if os.path.exists(self.nodesconf):
			with open(self.nodesconf, 'r') as f:
				for line in f:
					line = line.strip()
					if line.startswith('#'):
						continue
					self.do_add(line)

	def save_nodes(self):
		if os.path.isdir(self.confdir):
			with open(self.nodesconf, 'w+') as f:
				for node in map(lambda x: x.config, self.nodes):
					data = 'name={} address={} username={} auto={}'.format(node.Name, node.Address, node.Username, node.Auto)
					data += ' ' + ' '.join(map(lambda x: 'group={}'.format(x), node.Group))
					if node.Password:
						data += ' password={}'.format(node.Password)
					f.write(data)
					f.write('\n')


	# make sure history file is used
	def cmdloop(self):
		# load command history
		if os.path.exists(self.histfile):
			readline.read_history_file(self.histfile)

		# load nodes
		self.load_nodes()

		# automatically connect nodes at startup
		for node in self.nodes:
			if node.config.Auto:
				self.selected.append(node)
				node.connect()

		cmd.Cmd.cmdloop(self)

		# save nodes
		self.save_nodes()

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
		for node in self.selected:
			if node.connected():
				node.shrun(line)

		for node in self.selected:
			if node.connected:
				node.shwait()

		# print command output
		for node in self.selected:
			if node.connected():
				for line in node.last_cmd_output():
					print '{:>20}: {}'.format('\033[0;35m{}\033[0m'.format(node.config.Name), line)

	@docfix
	def do_add(self, line):
		'''
		Usage: add username=... password=... address=... port=...

			Add a node to running configuration. After command shell is closed,
			saved configuration will be updated as well.
			Available options for configuration are:
				name		Unique node name (or hostname). This is only
						used to identify the node amongst all other
						nodes.
				username	Username to use when connecting to the node.
				password	Password for the specified username.
				address		IP address of node.
				port		SSH port at which node's SSH daemon is listening.
				group		The node will be part of the specified group.
						More than one can be specified with separate
						"group=..." arguments.
				auto		Node will automatically connect at startup.
		'''
		while line.find('\t') != -1:
			line = line.replace('\t', ' ')
		while line.find('  ') != -1:
			line = line.replace('  ', ' ')
		items = line.split(' ')

		config = {}
		for item in items:
			if not item.find('='):
				print 'syntax error: {}'.format(line)
				return
			key, value = item.split('=', 1)
			key = key.capitalize()
			if key == 'Group':
				if not config.get('Group'):
					config[key] = []
				config[key].append(value)
			else:
				config[key] = value

		if filter(lambda x: config.get('Name') == x.config.Name, self.nodes):
			print 'node already exists'
			return
		self.nodes.append(Node(NodeConfig(**config)))


	# autocomplete for add command
	def complete_add(self, text, line, begidx, endidx):
		line = line.strip()
		line = line.replace('\t', ' ')
		while line.find('  ') != -1:
			line = line.replace('  ', ' ')
		items = line.split(' ')

		if line.endswith('='):
			return []

		# list of all possible arguments
		full = ['name', 'username', 'password', 'address', 'port', 'group', 'auto']

		# filter out repetitive options (name, username, port, address, noauto)
		for item in items:
			if item.find('=') != -1:
				key, value = item.split('=')
				key = key.lower()
				if not key == 'group' and key in full:
					full.remove(key)

		# autocomplete argument
		return map(
			lambda x: x+'=',
			filter(
				lambda x: x.startswith(text),
				full))


	@docfix
	def do_remove(self, line):
		'''
		Usage: remove [all] [host1] [host2] [GROUP1] [GROUP2] [...]

		Remove hosts and/or groups from running configuration.
		After command shell is closed, nodes will be removed from saved
		configuration as well.
		'''

		# make data easier to process
		line = line.strip()
		while line.find('  ') != -1:
			line = line.replace('  ', ' ')
		Items = line.split(' ')

		for Item in Items:
			for Node in filter(lambda x: Item == x.Config.Name or Item in x.Config.Bundle, self.group.Nodes):
				Node.Disconnect()
				Node.Exit()
				self.group.Nodes.remove(Node)

	# autocomplete for remove command
	def complete_remove(self, text, line, begidx, endidx):
		NodeList = set()
		GroupList = set()
		for Node in self.nodes:
			NodeList.add(Node.config.Name)
			GroupList.update(Node.config.Group)

		FullList = ['all'] + list(NodeList) + list(GroupList)
		return filter(lambda x: x.startswith(text), FullList)


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
		while line.find('\t') != -1:
			line = line.find('\t', ' ')
		while line.find('  ') != -1:
			line = line.replace('  ', ' ')
		items = line.split(' ')

		for item in items:
			for node in self.nodes:
				if item == node.config.Name or item in node.config.Group:
					print 'connecting to node:', node.config.Name
					node.connect()

	# disconnect from node
	@docfix
	def do_disconnect(self, line):
		'''
		Usage: disconnect [node1] [node2] [GROUP1] [GROUP2] [...]

			Terminate ssh connection to nodes.
		'''
		while line.find('\t') != -1:
			line = line.find('\t', ' ')
		while line.find('  ') != -1:
			line = line.replace('  ', ' ')
		items = line.split(' ')

		for item in items:
			for node in self.nodes:
				if item == node.config.Name or item in node.config.Group:
					print 'disconnecting node:', node.config.Name
					node.disconnect()


	@docfix
	def do_list(self, line):
		'''
		Usage: list
		
			Display a list of all configured nodes and
			their connection status.
			Displayed filds include:
				Hostname	Name (or hostname) of the node
				Address		Node IP address
				CON		Connection status - ("Yes" for connected,
						"No" for disconnected)
				SEL		Selected status ("Yes" for selected, "No"
						for not selected. Shell commands will be
						executed on selected nodes only.
				Group		Node group the current node is in. A node
						can be in more than one group.
				ACo		AutoConnect status ("Yes" for autoconnect
						at startup, "No" for no autoconnect)
		'''

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
		gsize = max(
			max(
				map(
					lambda x: len(','.join(x.config.Group)),
					self.nodes)),
			5)

		template = '{:>%d}  {:<%d}  {:<3}  {:<3}  {:>%d}  {:<3}' % (hsize, asize, gsize)
		print template.format('Hostname', 'Address', 'CON', 'SEL', 'Group', 'ACo')
		print template.format('-'*hsize, '-'*asize, '-'*3, '-'*3, '-'*gsize, '-'*3)
		for node in self.nodes:
			print template.format(
				node.config.Name,
				node.config.Address,
				{True:'Yes', False:'No'}[node.connected()],
				{True:'Yes', False:'No'}[node in self.selected],
				','.join(getattr(node.config, 'Group', [])),
					{True:'Yes', False:'No'}[node.config.Auto])


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
