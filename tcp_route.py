#!/usr/bin/env python3

from base64 import b64encode
from os import environ
from random import uniform
from select import select
import socket
from threading import Thread
from time import sleep


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
	s.send(('\r\n'.join('%s: %s'%(k,v) for k,v in headers.items()) + '\r\n\r\n').encode())

	statusline = readline(s).strip()
	version, status, statusmsg = statusline.split(' ', 2)
	status = int(status)
	response_headers = {}
	l = '?'
	while l:
		l = readline(s).strip()
		if ':' in l:
			k, v = l.split(':', 1)
			response_headers[k.strip().lower()] = v.strip()
	return s, status, response_headers

def runrouter(targetaddr, boundaddr, latency = 0.32, jitter = 0.05, loss_bytes = 0.0, onevent = lambda e:e):
	latency, jitter = latency/2, jitter/2	# Half time there, half time home.
	targetaddr, boundaddr = [(addr[0], addr[1]) for addr in [targetaddr, boundaddr]]
	sock = socket.socket()	# TCP
	sock.bind(boundaddr)
	sock.listen(5)
	while True:
		inbound_sock,iaddr = sock.accept()
		Thread(target=handle_route, args=(inbound_sock, targetaddr, boundaddr, latency, jitter, loss_bytes, onevent)).start()


def handle_route(inbound_sock, targetaddr, boundaddr, latency, jitter, loss_bytes, onevent):
	try:
		onevent('i')
		outbound_sock,_,_ = http_proxy_connect(targetaddr)
		onevent('o')
		socks = [inbound_sock, outbound_sock]
		[s.setblocking(0) for s in socks]
		httpfrom, httpto = ('\r\nHost: %s:%i\r\n' % boundaddr).encode(), ('\r\nHost: %s:%i\r\n' % targetaddr).encode()
		quit = False
		while not quit:
			rs,_,xs = select(socks, [], socks)
			if xs:
				break
			for r in rs:
				sleep(latency + uniform(0.0, jitter))
				w = socks[socks.index(r)^1]
				data = r.recv(256*1024)
				if not data:
					quit = True
					break
				data = data.replace(httpfrom, httpto)
				if uniform(0.0, 100.0) < loss_bytes:
					onevent('d')
					continue
				else:
					onevent('.')
				w.send(data)
	except Exception as e:
		onevent(e)
	onevent('c')


def main():
	import sys
	if len(sys.argv) != 6:
		print('Usage:   %s <target_ip:port> <bound_ip:port> <latency> <jitter> <loss_byte_percent>' % sys.argv[0])
		print('Example: %s somedomain.com:80 localhost:8080 1.5 0.5 0.0' % sys.argv[0])
		sys.exit(1)
	targetaddr, boundaddr = [x.split(':') for x in sys.argv[1:3]]
	targetaddr, boundaddr = [(addr[0], int(addr[1])) for addr in [targetaddr, boundaddr]]
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
	print('i=incoming connect, o=outgoing connect, c=connection closed, .=packet routed, d=packet dropped.')
	runrouter(targetaddr, boundaddr, latency, jitter, loss_bytes, onevent)


if __name__ == '__main__':
	main()
