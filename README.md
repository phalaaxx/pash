pash
====

Parallel shell utility


Requirements
------------

 * Python 3.10+
 * python-readline
 * python-paramiko

Install
-------

Download code

	git clone https://github.com/phalaaxx/pash

Move/link binary

	mv pash/pash.py /usr/local/bin/pash
	chown root: /usr/local/bin/pash
	chmod 755 /usr/local/bin/pash

Usage
-----

In order to use pash a configuration file with list of nodes needs to be created first:

	$ mkdir ~/.pash
	$ cat << EOF > ~/.pash/servers.ini
	[server1]
	address = 1.2.3.4
	username = root

	[server2]
	address = 1.2.3.5
	username = root

	[server3]
	address = 1.2.3.6
	username = root

	[server4]
	address = 1.2.3.7
	username = root
	EOF


Once created, pash can be used to connect to nodes listed in the configuration file:

	$ pash

	pash> list
	Available Node Groups
	=====================
	  servers
	pash> use servers
	pash@servers> list
	  Hostname  Address  CON
	----------  -------  ---
	   server1  1.2.3.4  Yes
	   server2  1.2.3.5  Yes
	   server3  1.2.3.6  Yes
	   server4  1.2.3.7  Yes
	pash@servers> !ls -d /bin
	    server1: /bin
	    server2: /bin
	    server3: /bin
	    server4: /bin
	pash@servers>
