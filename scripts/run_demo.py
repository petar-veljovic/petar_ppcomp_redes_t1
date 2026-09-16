#!/usr/bin/env python3
"""
Gerador de cenarios de teste para o sistema de Smart Home (Trabalho de Sockets).

Uso:
    python run_demo.py --scenario full          --code-dir ../../src  --out-dir logs
    python run_demo.py --scenario unsupported   --code-dir ../../src  --out-dir logs
    python run_demo.py --scenario invalid_room  --code-dir ../../src  --out-dir logs
    python run_demo.py --scenario invalid_byte  --code-dir ../../src  --out-dir logs
    python run_demo.py --scenario partial_list  --code-dir ../../src  --out-dir logs

Cada cenario sobe um servidor real e um (ou mais) cliente(s) real(is), trocando
mensagens pela rede (TCP localhost), e salva todo o log dos terminais em arquivos
de texto para documentacao no README.

Rodar um cenario com --code-dir gabarito produz os logs do sistema original;
rodar com --code-dir src produz os logs do sistema expandido/corrigido.
"""
import argparse
import os
import signal
import subprocess
import sys
import tempfile
import time

SCENARIOS = ['full', 'unsupported', 'invalid_room', 'invalid_byte', 'partial_list']

ROOM_SALA = '1'        # primeiro ambiente do ambientes.txt


def err(msg):
    print('[run_demo] ' + msg, file=sys.stderr)


def spawn(code_dir, script, outdir, name, stdin_lines=None):
    """Executa `script` (python -u) no diretorio-code, capturando saida em arquivo."""
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    outfile = os.path.join(outdir, name + '.log')
    proc = subprocess.Popen(
        [sys.executable, '-u', script],
        cwd=code_dir,
        env=env,
        stdin=subprocess.PIPE,
        stdout=open(outfile, 'w', encoding='utf-8'),
        stderr=subprocess.STDOUT,
        bufsize=1,
    )
    return proc


def feed(proc, text):
    if proc and proc.poll() is None:
        proc.stdin.write(text.encode('utf-8'))
        proc.stdin.flush()


def stop(proc, name):
    if proc and proc.poll() is None:
        try:
            proc.terminate()
        except OSError:
            pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        err('encerrado: ' + name)


def scenario_full(code_dir, outdir):
    server = spawn(code_dir, 'Server.py', outdir, 'server')
    time.sleep(2.0)

    lamp = spawn(code_dir, 'Cliente_Lampada.py', outdir, 'cliente_lampada')
    feed(lamp, ROOM_SALA + '\n')
    time.sleep(1.2)

    ac = None
    if os.path.exists(os.path.join(code_dir, 'Cliente_ArCondicionado.py')):
        ac = spawn(code_dir, 'Cliente_ArCondicionado.py', outdir, 'cliente_arcondicionado')
        feed(ac, ROOM_SALA + '\n')
        time.sleep(1.2)

    # Termometro: seleciona a Sala e envia 3 leituras antes de ser encerrado
    termo = spawn(code_dir, 'Cliente_Temperatura.py', outdir, 'cliente_termometro')
    feed(termo, ROOM_SALA + '\n')
    time.sleep(0.8)
    for temp in ('26', '25', '24'):
        feed(termo, temp + '\n')
        time.sleep(0.6)
    stop(termo, 'cliente_termometro')

    # Sensor de presenca: detecta presenca (1), espera o tempo de auto-desligamento,
    # detecta presenca de novo (1) e por fim a ausencia (0)
    presenca = spawn(code_dir, 'Cliente_Presenca.py', outdir, 'cliente_presenca')
    feed(presenca, ROOM_SALA + '\n')
    time.sleep(0.8)
    err('>>> PRESENCA 1: detectada (lampada/AC ligam)')
    feed(presenca, '1\n')
    time.sleep(6.5)  # maior que TEMPO_LUZ_ACESA (5s) -> auto-desligamento

    err('>>> PRESENCA 1 novamente: detectada (liga de novo)')
    feed(presenca, '1\n')
    time.sleep(2.0)
    err('>>> PRESENCA 0: ausencia (apaga imediatamente)')
    feed(presenca, '0\n')
    time.sleep(1.5)

    stop(lamp, 'cliente_lampada')
    if ac:
        stop(ac, 'cliente_arcondicionado')
    stop(presenca, 'cliente_presenca')
    stop(server, 'server')


def _custom_client(code_dir, outdir, name, pycode):
    """Executa um snippet Python que usa o modulo Message do code-dir."""
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    # cria um diretorio temporario com um cliente feito sob medida
    tmpdir = os.path.join(tempfile.mkdtemp(prefix='run_demo_'), name)
    os.makedirs(tmpdir, exist_ok=True)
    cli_path = os.path.join(tmpdir, name + '.py')
    if code_dir in ('', '.'):
        raise SystemExit('--code-dir precisa ser um caminho absoluto/relativo resolvivel')
    syspath = code_dir.replace('\\', '\\\\')
    pycode = 'import sys\nsys.path.insert(0, r"%s")\n' % syspath + pycode
    with open(cli_path, 'w', encoding='utf-8') as f:
        f.write(pycode)
    outfile = os.path.join(outdir, name + '.log')
    proc = subprocess.Popen(
        [sys.executable, '-u', cli_path],
        cwd=code_dir,          # garante import de Message/Config do sistema testado
        env=env,
        stdout=open(outfile, 'w', encoding='utf-8'),
        stderr=subprocess.STDOUT,
    )
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        stop(proc, name)
    return proc


def scenario_unsupported(code_dir, outdir):
    server = spawn(code_dir, 'Server.py', outdir, 'server')
    time.sleep(2.0)
    pycode = r'''
import socket, sys
from Config import *
from Message import *
from ClientUtil import *

def run():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((SERVIDOR, PORTA))
    device = Device(s, 99)                     # tipo inexistente
    msg = MessageRegister()
    s.send(msg.pack(99))
    print('Enviada solicitacao de registro com tipo invalido (99)')
    msg = ReceiveMessage(s, device)
    if msg:
        if msg.code == MSG_STATUS:
            print('Servidor respondeu: ' + msg.toStringMsg())
        else:
            print('Resposta inesperada, code=', msg.code)
    s.close()
    print('Fim do cliente de teste')
run()
'''
    _custom_client(code_dir, outdir, 'cliente_nao_suportado', pycode)
    time.sleep(1.0)
    stop(server, 'server')


def scenario_invalid_room(code_dir, outdir):
    server = spawn(code_dir, 'Server.py', outdir, 'server')
    time.sleep(2.0)
    pycode = r'''
import socket
from Config import *
from Message import *
from ClientUtil import *

def run():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((SERVIDOR, PORTA))
    device = Device(s, NUM_LAMPADA)
    msg = MessageRegister()
    s.send(msg.pack(NUM_LAMPADA))
    msg = ReceiveMessage(s, device)            # lista de ambientes
    if not msg or msg.code != MSG_LISTA_AMBIENTES:
        print('Falha ao obter lista de ambientes')
        s.close()
        return
    print('Lista de ambientes recebida (%d ambientes)' % msg.countRooms)
    msg = MessageSelect()
    s.send(msg.pack(999))                      # ambiente que nao existe
    print('Enviada selecao de ambiente invalida (999)')
    msg = ReceiveMessage(s, device)
    if msg:
        if msg.code == MSG_STATUS:
            print('Servidor respondeu status: ' + msg.toStringMsg())
        else:
            print('Resposta inesperada, code=', msg.code)
    else:
        print('Servidor encerrou a conexao.')
    s.close()
    print('Fim do cliente de teste')
run()
'''
    _custom_client(code_dir, outdir, 'cliente_ambiente_invalido', pycode)
    time.sleep(1.0)
    stop(server, 'server')


def scenario_invalid_byte(code_dir, outdir):
    server = spawn(code_dir, 'Server.py', outdir, 'server')
    time.sleep(2.0)
    pycode = r'''
import socket
from Config import *
from Message import *
from ClientUtil import *

def run():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((SERVIDOR, PORTA))
    device = Device(s, NUM_LAMPADA)
    msg = MessageRegister()
    # envia um byte invalido (0x1F, codigo de mensagem inexistente) seguido
    # de uma mensagem de registro valida, tudo em um unico segmento TCP
    s.sendall(b'\x1f' + msg.pack(NUM_LAMPADA))
    print('Enviado segmento com byte invalido (0x1F) + registro valido')
    msg = ReceiveMessage(s, device)
    if msg:
        if msg.code == MSG_LISTA_AMBIENTES:
            print('Servidor ignorou o byte invalido e respondeu a lista de ambientes.')
        elif msg.code == MSG_STATUS:
            print('Servidor respondeu status: ' + msg.toStringMsg())
        else:
            print('Resposta inesperada, code=', msg.code)
    else:
        print('Conexao encerrada / sem resposta.')
    s.close()
    print('Fim do cliente de teste')
run()
'''
    _custom_client(code_dir, outdir, 'cliente_byte_invalido', pycode)
    time.sleep(1.5)
    stop(server, 'server')


def scenario_partial_list(code_dir, outdir):
    server = spawn(code_dir, 'Server.py', outdir, 'server')
    time.sleep(2.0)
    pycode = r'''
import socket, struct, time
from Config import *
from Message import *
from ClientUtil import *

def run():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((SERVIDOR, PORTA))
    device = Device(s, NUM_LAMPADA)

    msg = MessageRegister()
    s.send(msg.pack(NUM_LAMPADA))
    msg = ReceiveMessage(s, device)
    if not msg or msg.code != MSG_LISTA_AMBIENTES:
        print('Falha ao obter lista de ambientes')
        s.close()
        return
    print('Lista de ambientes recebida (%d ambientes)' % msg.countRooms)
    device.buffer = ''   # limpa o buffer do cliente

    # monta uma mensagem MSG_LISTA_AMBIENTES completa (11 bytes, 0 ambientes)
    full = struct.pack('!BdH', MSG_LISTA_AMBIENTES, time.time(), 0)

    # 1) envia apenas os primeiros 5 bytes (codigo 0x03 + inicio do double):
    #    menos que os 11 bytes do cabecalho fixo da lista
    s.sendall(full[:5])
    print('Enviado 0x03 + 4 bytes (parcial 5/11 do cabecalho)')
    time.sleep(1.2)

    # 2) envia mais 3 bytes: ainda faltam bytes do cabecalho fixo
    s.sendall(full[5:8])
    print('Enviado mais 3 bytes (parcial 8/11 do cabecalho)')
    time.sleep(1.2)

    # 3) completa o restante (total 11 bytes, lista com 0 ambientes)
    s.sendall(full[8:])
    print('Enviado restante (mensagem concluida, 0 ambientes)')

    # a mensagem de lista nao e esperada neste estado -> Status [10]
    # (mensagem nao esperada) e encerramento da conexao
    msg = ReceiveMessage(s, device)
    if msg and msg.code == MSG_STATUS:
        print('Servidor respondeu: ' + msg.toStringMsg())
    else:
        print('Resposta inesperada: ', getattr(msg, 'code', 'sem resposta'))
    print('Servidor sobreviveu a lista de ambientes recebida pela metade.')
    s.close()
run()
'''
    _custom_client(code_dir, outdir, 'cliente_lista_parcial', pycode)
    time.sleep(1.0)
    stop(server, 'server')


def main(argv=None):
    ap = argparse.ArgumentParser(description='Gera logs de teste do sistema')
    ap.add_argument('--scenario', choices=SCENARIOS, required=True)
    ap.add_argument('--code-dir', required=True, help='pasta com o codigo do sistema')
    ap.add_argument('--out-dir', required=True, help='pasta onde salvar os logs')
    args = ap.parse_args(argv)

    code_dir = os.path.abspath(args.code_dir)
    outdir = os.path.abspath(os.path.join(args.out_dir, args.scenario))
    os.makedirs(outdir, exist_ok=True)

    err('cenario=%s code-dir=%s out-dir=%s' % (args.scenario, code_dir, outdir))
    if args.scenario == 'full':
        scenario_full(code_dir, outdir)
    elif args.scenario == 'unsupported':
        scenario_unsupported(code_dir, outdir)
    elif args.scenario == 'invalid_room':
        scenario_invalid_room(code_dir, outdir)
    elif args.scenario == 'invalid_byte':
        scenario_invalid_byte(code_dir, outdir)
    elif args.scenario == 'partial_list':
        scenario_partial_list(code_dir, outdir)
    err('fim do cenario')


if __name__ == '__main__':
    main()