#!/usr/bin/env python3

from base64 import b64encode
from os import environ
from random import uniform
from sched import scheduler
from select import select
import socket
from threading import Semaphore, Thread


class EternalScheduler:
	def __init__(self):
		self.sched = scheduler()
		self.sem = Semaphore(0)
		Thread(target=self.run).start()

	def run(self):
		while True:
			self.sched.run()
			self.sem.acquire()

	def enter(self, delay, action, argument=()):
		self.sched.enter(delay, 1, action, argument)
		self.sem.release()

def readline(s):
	data = b = ''
	while b != '\n':
		b = s.recv(1).decode()
		data += b
	return data

def http_proxy_connect(addr):
	'''Returns (socket, status_code, headers).'''
	try:
		proxy = environ['http_proxy']
	except Exception as e:
		print(e)
		s = socket.socket()
		s.connect(addr)
		return s, 0, {}

	headers = {
		'host': addr[0]
	}
	
	proxy = proxy.replace('http://','').replace('https://','')
	headers['proxy-authorization'] = 'Basic'
	if '@' in proxy:
		headers['proxy-authorization'] += ' ' + b64encode(proxy.split('@')[0].encode()).decode()
	s = socket.socket()
	proxyaddr = proxy.split('@')[-1]
	if ':' in proxyaddr:
		phost,pport = proxyaddr.split(':')
		pport = int(pport)
	else:
		phost = proxyaddr
		pport = 80
	s.connect((phost,pport))

	s.send(('CONNECT %s:%d HTTP/1.0\r\n' % addr).encode())
	s.send(('\r\n'.join('%s: %s' % (k, v) for (k, v) in headers.items()) + '\r\n\r\n').encode())
	print('sent')

	statusline = readline(s).strip()
	version, status, statusmsg = statusline.split(' ', 2)
	status = int(status)
	response_headers = {}
	while True:
		l = readline(s).strip()
		if l == '':
			break
		if not ':' in l:
			continue
		k, v = l.split(':', 1)
		response_headers[k.strip().lower()] = v.strip()
	return s, status, response_headers

def runrouter(targetaddr, boundaddr, latency = 0.32, jitter = 0.05, loss_bytes = 0.0, onevent = None):
	latency, jitter = latency/2, jitter/2	# Half time there, half time home.
	targetaddr, boundaddr = [(socket.gethostbyname(addr[0]), addr[1]) for addr in [targetaddr, boundaddr]]
	sock = socket.socket()	# TCP
	sock.bind(boundaddr)
	sock.listen(5)
	while True:
		inbound_sock,iaddr = sock.accept()
		Thread(target=handle_route, args=(inbound_sock, targetaddr, latency, jitter, loss_bytes, onevent)).start()


def handle_route(inbound_sock, targetaddr, latency, jitter, loss_bytes, onevent):
	# try:
	onevent('i')
	scheduler = EternalScheduler()
	outbound_sock,_,_ = http_proxy_connect(targetaddr)
	onevent('o')
	socks = [inbound_sock, outbound_sock]
	print(socks)
	while True:
		rs,_,xs = select(socks, [], socks)
		if xs:
			break
		for r in rs:
			w = socks[socks.index(r)^1]
			data = r.recv(1)
			if uniform(0.0, 100.0) < loss_bytes:
				onevent('d')
				continue
			else:
				onevent(data)
			delay = latency + uniform(0.0, jitter)
			scheduler.enter(delay, w.send, (data,))
	# except Exception as e:
		# onevent(e)


def main():
	import sys
	if len(sys.argv) != 6:
		print('Usage:   %s <target_ip:port> <bound_ip:port> <latency> <jitter> <loss_byte_percent>' % sys.argv[0])
		print('Example: %s somedomain.com:80 localhost:8080 1.5 0.5 0.0' % sys.argv[0])
		sys.exit(1)
	targetaddr, boundaddr = [x.split(':') for x in sys.argv[1:3]]
	targetaddr, boundaddr = [(socket.gethostbyname(addr[0]), int(addr[1])) for addr in [targetaddr, boundaddr]]
	latency, jitter, loss_bytes = [float(x) for x in sys.argv[3:6]]
	def onevent(e):
		if type(e) == str:
			print(e, end='', flush=True)
		else:
			print('\nError:', e)
	print('TCP router by highfestiva@pixeldoctrine.com.')
	print('Sending towards server: %s.' % str(targetaddr))
	print('Connect your client to: %s.' % str(boundaddr))
	print('Latency setting:        %g' % latency)
	print('Jitter setting:         %g' % jitter)
	print('Byte loss setting:      %g%%' % loss_bytes)
	print('i means incoming connect, o outgoing connect, . packet routed, d means packet dropped.')
	runrouter(targetaddr, boundaddr, latency, jitter, loss_bytes, onevent)


if __name__ == '__main__':
	main()
