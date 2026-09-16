#!/usr/bin/env python3
"""
Prova empirica do comportamento de "mensagem nao solicitada" enviada durante
a espera de um atuador (lampada).

O README (secao 7.4) afirmava que uma mensagem nao solicitada enviada durante
a espera ficaria no buffer do kernel ate o proximo evento e seria "inofensiva".
Este script reproduz a situacao com um servidor e clientes reais e registra o
que de fato acontece: quando o evento chega, a thread do atuador envia o
comando, volta a ler o socket, encontra a mensagem nao esperada e responde com
Status [10] (ERRO_MENSAGEM_NAO_ESPERADA), ENCERRANDO a conexao
(DeviceThread.py:248-252).

Cenario:
  1. Cliente LAMPADA registra e seleciona o ambiente (a thread do servidor fica
     bloqueada na fila da lampada, sem ler o socket) e envia uma leitura de
     sensor NAO SOLICITADA -- ela fica no buffer do kernel.
  2. Cliente PRESENCA detecta presenca: o controle geral alimenta a fila da
     lampada e o servidor, ao processar o evento, le a mensagem nao esperada.

Uso: python test_unsolicited.py [--code-dir ../src] [--out-dir docs/testes/unsolicited]
"""
import argparse
import os
import socket
import struct
import subprocess
import sys
import time

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
                buffer = buffer[1:]
                continue
            if code == 3:  # lista de ambientes tem tamanho variavel
                count = struct.unpack('!BdH', buffer[:11])[2]
                size = 11 + count * 22
            if len(buffer) >= size:
                msg = buffer[:size]
                return msg, buffer[size:]
            break  # mensagem incompleta: precisa de mais bytes
        sock.settimeout(10)
        try:
            data = sock.recv(1024)
        except socket.timeout:
            return None, buffer
        if not data:
            return None, buffer
        buffer += data


def parse_status(msg):
    code, _, deviceID, status = struct.unpack('!BdIH', msg[:15])
    return code, deviceID, status


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--code-dir', default='../src')
    ap.add_argument('--out-dir', default='docs/testes/unsolicited')
    args = ap.parse_args()
    code_dir = os.path.abspath(args.code_dir)
    outdir = os.path.abspath(args.out_dir)
    os.makedirs(outdir, exist_ok=True)

    sys.path.insert(0, code_dir)
    from Config import (NUM_LAMPADA, NUM_SENSOR_PRESENCA, PRESENCA_DETECTADA)
    from Message import (MessageRegister, MessageSelect, MessageSensor,
                         MSG_SENSOR, MSG_LAMPADA, MSG_STATUS,
                         ERRO_MENSAGEM_NAO_ESPERADA, LUZ_ACESA)

    proc = start_server(code_dir, outdir)
    results = []

    def linha(msg):
        print('  ' + msg)
        results.append(msg)

    try:
        print('=' * 74)
        print('CENARIO: mensagem nao solicitada enviada durante a espera do atuador')
        print('=' * 74)

        # ===== Cliente LAMPADA: registra, seleciona o ambiente e envia uma
        # mensagem NAO SOLICITADA enquanto o servidor esta bloqueado na fila.
        lamp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        lamp.connect(('localhost', 5000))
        lamp.sendall(MessageRegister().pack(NUM_LAMPADA))
        lista, buf = read_one_message(lamp, b'')
        linha('Lampada: registrada, lista de ambientes recebida (code=%d).' % lista[0])

        lamp.sendall(MessageSelect().pack(1))
        status, buf = read_one_message(lamp, buf)
        code, devLamp, st = parse_status(status)
        linha('Lampada: ambiente selecionado, deviceID=%d (Status [%d]).'
              % (devLamp, st))

        # A thread do servidor agora esta BLOQUEADA na fila da lampada
        # (WaitLampQueue) e nao le o socket.
        lamp.sendall(MessageSensor().pack(devLamp, 26.5))
        linha('Lampada: enviada mensagem NAO SOLICITADA '
              '(leitura de sensor, code=%d) durante a espera.' % MSG_SENSOR)

        # ===== Cliente PRESENCA: detecta presenca -> o controle geral move a
        # fila da lampada (evento que faz a thread voltar a ler o socket).
        time.sleep(0.5)
        pres = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        pres.connect(('localhost', 5000))
        pres.sendall(MessageRegister().pack(NUM_SENSOR_PRESENCA))
        plista, pbuf = read_one_message(pres, b'')
        pres.sendall(MessageSelect().pack(1))
        pstatus, pbuf = read_one_message(pres, pbuf)
        pcode, devPres, pst = parse_status(pstatus)
        linha('Presenca: registrada, deviceID=%d (Status [%d]).' % (devPres, pst))

        pres.sendall(MessageSensor().pack(devPres, PRESENCA_DETECTADA))
        linha('Presenca: enviada presenca detectada (1).')
        conf, pbuf = read_one_message(pres, pbuf)
        ccode, cdev, cst = parse_status(conf)
        linha('Presenca: confirmacao Status [%d] recebida.' % cst)
        pres.close()

        # ===== O evento chegou: o servidor envia o comando para a lampada e,
        # em seguida, LE a mensagem nao solicitada que estava no buffer.
        comando, buf = read_one_message(lamp, buf)
        if comando is None:
            linha('Lampada: conexao encerrada antes do comando.')
        else:
            ccode = comando[0]
            if ccode == MSG_LAMPADA:
                _, _, _, acao = struct.unpack('!BdIB', comando[:14])
                linha('Lampada: recebeu comando do servidor (code=%d, acao=%d%s).'
                      % (ccode, acao, ' [LUZ_ACESA]' if acao == LUZ_ACESA else ''))
            else:
                linha('Lampada: resposta inesperada, code=%d' % ccode)

        resp, buf = read_one_message(lamp, buf)
        if resp is None:
            linha('Lampada: FIM da conexao sem resposta a mensagem nao solicitada.')
        else:
            rcode, rid, rstatus = parse_status(resp)
            linha('Lampada: resposta a mensagem nao solicitada -> '
                  'code=%d, Status [%d]' % (rcode, rstatus))
            if rcode == MSG_STATUS and rstatus == ERRO_MENSAGEM_NAO_ESPERADA:
                linha('=> CONFIRMADO: Status [10] (mensagem nao esperada)')
            else:
                linha('=> Resposta inesperada.')

        fim, buf = read_one_message(lamp, buf)
        linha('Lampada: conexao %s.' % ('FECHADA pelo servidor'
              if fim is None else 'ainda aberta'))
        lamp.close()
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            proc.kill()

    print()
    print('FIM DO TESTE')


if __name__ == '__main__':
    main()