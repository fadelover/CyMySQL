#!/usr/bin/env python3
##############################################################################
#The MIT License (MIT)
#
#Copyright (c) 2016 Hajime Nakagami
#
#Permission is hereby granted, free of charge, to any person obtaining a copy
#of this software and associated documentation files (the "Software"), to deal
#in the Software without restriction, including without limitation the rights
#to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#copies of the Software, and to permit persons to whom the Software is
#furnished to do so, subject to the following conditions:
#
#The above copyright notice and this permission notice shall be included in all
#copies or substantial portions of the Software.
#
#THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
#SOFTWARE.
##############################################################################
import sys
import time
import socket
import binascii
import select

def recv_from_socket(sock, n):
    recieved = b''
    while n:
        bs = sock.recv(n)
        recieved += bs
        n -= len(bs)
    return recieved

def recv_mysql_packet(sock):
    head = recv_from_socket(sock, 4)
    n = int.from_bytes(head[:3], byteorder='little')
    return head + recv_from_socket(sock, n)

def to_ascii(s):
    r = ''
    for c in s:
        r += chr(c) if (c >= 32 and c < 128) else '.'
    return r


def proxy_wire(server_name, server_port, listen_host, listen_port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((listen_host, listen_port))
    sock.listen(1)
    client_sock, addr = sock.accept()
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.connect((server_name, server_port))

    # http://dev.mysql.com/doc/internals/en/connection-phase-packets.html

    # initial packet
    server_data = recv_mysql_packet(server_sock)
    client_sock.send(server_data)
    print('S->C initial packets', binascii.b2a_hex(server_data).decode('ascii'))
    print('   [' + to_ascii(server_data) + ']')

    # initial response (authentication)
    client_data = recv_mysql_packet(client_sock)
    server_sock.send(client_data)
    print('C->S initial response', binascii.b2a_hex(client_data).decode('ascii'))
    print('   [' + to_ascii(client_data) + ']')

    # auth result
    server_data = recv_mysql_packet(server_sock)
    client_sock.send(server_data)
    print('S->C auth result', binascii.b2a_hex(server_data).decode('ascii'))
    print('   [' + to_ascii(server_data) + ']')

    # http://dev.mysql.com/doc/internals/en/packet-OK_Packet.html
    # payload first byte eq 0.
    assert server_data[4] == 0

    while True:
        client_data = recv_mysql_packet(client_sock)
        server_sock.send(client_data)
        print('C->S', binascii.b2a_hex(client_data).decode('ascii'))
        print('   [' + to_ascii(client_data) + ']')
        if client_data[4] == 0x01:      # COM_QUIT
            break

        assert client_data[4] == 0x03   # COM_QUERY

        server_data = recv_mysql_packet(server_sock)
        client_sock.send(server_data)
        print('S->C', binascii.b2a_hex(server_data).decode('ascii'))
        print('   [' + to_ascii(server_data) + ']')

        if server_data[4] in (0x00, 0xFE, 0xFF):
            continue

        print('   Column definition')
        while True:
            server_data = recv_mysql_packet(server_sock)
            client_sock.send(server_data)
            print('S->C', binascii.b2a_hex(server_data).decode('ascii'))
            print('   [' + to_ascii(server_data) + ']')
            # [payload first byte] in (OK, EOF, ERROR)
            if server_data[4] in (0x00, 0xFE, 0xFF):
                break

        print('   Result Rows')
        while True:
            server_data = recv_mysql_packet(server_sock)
            client_sock.send(server_data)
            print('S->C', binascii.b2a_hex(server_data).decode('ascii'))
            print('   [' + to_ascii(server_data) + ']')
            # [payload first byte] in (OK, EOF, ERROR)
            if server_data[4] in (0x00, 0xFE, 0xFF):
                break


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('Usage : ' + sys.argv[0] + ' server[:port] [listen_host:]listen_port')
        sys.exit()

    server = sys.argv[1].split(':')
    server_name = server[0]
    if len(server) == 1:
        server_port = 3306
    else:
        server_port = int(server[1])

    listen = sys.argv[2].split(':')
    if len(listen) == 1:
        listen_host = 'localhost'
        listen_port = int(listen[0])
    else:
        listen_host = listen[0]
        listen_port = int(listen[1])

    proxy_wire(server_name, server_port, listen_host, listen_port)
