#!/usr/bin/env python3
"""
Demonstra o tratamento do buffer TCP pelo modulo Message.py.

O protocolo do sistema troca mensagens cujo primeiro byte indica o codigo
(e, portanto, o tamanho). Como TCP e um "riacho de bytes" (stream), nao ha
garantia de que um send() do remetente corresponda a exatamente um recv()
do destinatario. Este script conecta clientes reais ao servidor real e
envia a MESMA informacao de formas diferentes:

  TESTE 1 (FRAGMENTACAO): a mensagem de registro e quebrada em 3 pedacos
      -- 1 byte, 2 bytes e o restante -- enviados com pequenos intervalos.
      O servidor precisa acumular tudo no buffer e so decodificar quando a
      mensagem estiver completa.

  TESTE 2 (COALESCENCIA): o cliente envia DUAS mensagens de leitura dentro
      de um unico sendall(). O recv() do servidor pode entregar as duas
      juntas; o servidor precisa separa-las e processa-las na ordem.

Uso: python test_buffer_tcp.py [--code-dir ../src] [--out-dir docs/testes/tcp_buffer]
"""
import argparse
import os
import socket
import subprocess
import sys
import time
import struct

SIZES = {1: 15, 2: 10, 3: 11, 4: 11, 5: 17, 6: 14, 7: 18}  # ~ getMessage

def start_server(code_dir, outdir):
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    logpath = os.path.join(outdir, 'server.log')
    proc = subprocess.Popen(
        [sys.executable, '-u', 'Server.py'],
        cwd=code_dir, env=env,
        stdout=open(logpath, 'w', encoding='utf-8'),
        stderr=subprocess.STDOUT,
    )
    time.sleep(2.0)
    return proc


def read_one_message(sock, buffer):
    """Le do socket ate conseguir extrair UMA mensagem completa."""
    buffer = buffer or b''
    while True:
        while len(buffer) > 0:
            code = buffer[0]
            size = SIZES.get(code)
            if size is None:
                # byte invalido no inicio do buffer: descarta (como o getMessage)
                buffer = buffer[1:]
                continue
            if code == 3:  # lista de ambientes tem tamanho variavel
                count = struct.unpack('!BdH', buffer[:11])[2]
                size = 11 + count * 22
            if len(buffer) >= size:
                msg = buffer[:size]
                return msg, buffer[size:]
            break  # mensagem incompleta: precisa de mais bytes
        data = sock.recv(1024)
        if not data:
            return None, buffer
        buffer += data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--code-dir', default='../src')
    ap.add_argument('--out-dir', default='docs/testes/tcp_buffer')
    args = ap.parse_args()
    code_dir = os.path.abspath(args.code_dir)
    outdir = os.path.abspath(args.out_dir)
    os.makedirs(outdir, exist_ok=True)

    sys.path.insert(0, code_dir)
    from Config import NUM_TERMOMETRO
    from Message import (MessageRegister, MessageSelect, MessageSensor,
                         MSG_LISTA_AMBIENTES, MSG_STATUS, MSG_SENSOR, LEITURA_RECEBIDA)

    proc = start_server(code_dir, outdir)
    results = []

    def linha(msg):
        print('  ' + msg)
        results.append(msg)

    try:
        # ============================================== TESTE 1: FRAGMENTACAO
        print('=' * 74)
        print('TESTE 1 - FRAGMENTACAO: registro enviado em 3 pedacos, 1 byte + 2 bytes + resto')
        print('=' * 74)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(('localhost', 5000))
        payload = MessageRegister().pack(NUM_TERMOMETRO)   # 10 bytes
        s.sendall(payload[:1])    # 1o byte: codigo da mensagem
        time.sleep(0.4)
        s.sendall(payload[1:3])   # 2 bytes
        time.sleep(0.4)
        s.sendall(payload[3:])    # restante (7 bytes)
        first, buf = read_one_message(s, b'')
        if first and first[0] == MSG_LISTA_AMBIENTES:
            linha('Servidor respondeu com a Lista de Ambientes (code=3).')
            linha('=> O servidor REUNIU os pedacos do buffer e decodificou a mensagem. OK')
        else:
            linha('FALHA: resposta inesperada:', first)
        s.close()
        time.sleep(1.2)

        # ============================================== TESTE 2: COALESCENCIA
        print()
        print('=' * 74)
        print('TESTE 2 - COALESCENCIA: duas leituras dentro de um UNICO sendall()')
        print('=' * 74)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(('localhost', 5000))
        s.sendall(MessageRegister().pack(NUM_TERMOMETRO))
        time.sleep(0.5)
        lista, buf = read_one_message(s, b'')
        linha('Lista de ambientes recebida (code=%d).' % lista[0])
        s.sendall(MessageSelect().pack(1))
        status, buf = read_one_message(s, buf)
        code, _, deviceID, _ = struct.unpack('!BdIH', status[:15])
        linha('Registro confirmado, deviceID do termometro = %d (status code=%d).' % (deviceID, code))

        m1 = MessageSensor().pack(deviceID, 26.5)   # 17 bytes
        m2 = MessageSensor().pack(deviceID, 27.5)   # 17 bytes
        bloco = m1 + m2
        linha('Enviando um segmento TCP de %d bytes com as 2 mensagens juntas.' % len(bloco))
        s.sendall(bloco)
        time.sleep(0.8)

        r1, buf = read_one_message(s, buf)
        r2, buf = read_one_message(s, buf)
        ok1 = r1 is not None and struct.unpack('!BdIH', r1[:15])[3] == LEITURA_RECEBIDA and r1[0] == MSG_STATUS
        ok2 = r2 is not None and struct.unpack('!BdIH', r2[:15])[3] == LEITURA_RECEBIDA and r2[0] == MSG_STATUS
        linha('Resposta 1: code=%d, status=%d' % (r1[0], struct.unpack('!BdIH', r1[:15])[3]))
        linha('Resposta 2: code=%d, status=%d' % (r2[0], struct.unpack('!BdIH', r2[:15])[3]))
        if ok1 and ok2:
            linha('=> O servidor SEPAROU as duas mensagens agrupadas e confirmou as 2 leituras. OK')
        else:
            linha('FALHA no teste de coalescencia.')
        s.close()
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            proc.kill()

    print()
    print('FIM DOS TESTES')


if __name__ == '__main__':
    main()