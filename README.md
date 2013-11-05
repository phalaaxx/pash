pash
====

Parallel shell utility


Requirements
------------

 * Python 2.7+
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

	$ pash

	pash> add name=node1 address=1.2.3.4 auto=1 group=svrgr1
	pash> add name=node2 address=1.2.3.5 auto=1 group=svrgr1
	pash> add name=node3 address=1.2.3.6 auto=0 group=svrgr2
	pash> add name=node4 address=1.2.3.7 auto=0 group=svrgr2
	pash> list
	Hostname  Address  CON  SEL   Group  ACo
	--------  -------  ---  ---  ------  ---
	   node1  1.2.3.4  No   No   svrgr1  No
	   node2  1.2.3.5  No   No   svrgr1  No
	   node3  1.2.3.6  No   No   svrgr2  No
	   node4  1.2.3.7  No   No   svrgr2  No
	pash> connect svrgr1 node3
	pash> list
	Hostname  Address  CON  SEL   Group  ACo
	--------  -------  ---  ---  ------  ---
	   node1  1.2.3.4  Yes  Yes  svrgr1  No
	   node2  1.2.3.5  Yes  Yes  svrgr1  No
	   node3  1.2.3.6  Yes  Yes  svrgr2  No
	   node4  1.2.3.7  No   No   svrgr2  No
	pash> !ls -d /bin
	    node1: /bin
	    node2: /bin
	    node3: /bin
	pash>
